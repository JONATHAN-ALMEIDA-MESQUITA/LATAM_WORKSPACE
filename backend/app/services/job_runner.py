"""Execucao de jobs agendados (Phase 6).

Funcoes chamadas pelo scheduler_service. Cada uma abre sua propria logica
sem passar pelo HTTP layer, mas reutiliza os engines existentes.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertEvalStatus
from app.models.dataset import Dataset
from app.models.forecast import Forecast, ForecastRun, ForecastRunStatus
from app.models.pipeline import Pipeline, PipelineRun, RunStatus
from app.models.scheduled_job import JobRunStatus, JobType, ScheduledJob, ScheduledJobRun
from app.models.user import User
from app.services.alert_engine import AlertEvalError, evaluate as alert_evaluate, in_cooldown
from app.services.alert_triggers import trigger_for
from app.services.audit_service import log_action
from app.services.forecast_engine import ForecastError, train as engine_train
from app.services.notification_service import fire_notification
from app.services.pipeline_engine import PipelineError, StepFailure, execute


@dataclass
class JobResult:
    status: str
    summary: dict
    error: str | None = None


def _get_system_user(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def _resolve_dataset(db: Session, ds_id: int) -> Dataset | None:
    return db.get(Dataset, ds_id)


def _steps_payload_from_pipeline(p: Pipeline) -> list[dict]:
    return [
        {
            "step_type": s.step_type,
            "name": s.name,
            "config": s.config_dict(),
        }
        for s in p.steps
    ]


def run_pipeline_job(db: Session, *, pipeline_id: int, triggered_by: str) -> JobResult:
    p = db.get(Pipeline, pipeline_id)
    if not p:
        return JobResult(JobRunStatus.FAILED.value, {}, f"Pipeline {pipeline_id} nao encontrado.")
    if not p.steps:
        return JobResult(JobRunStatus.FAILED.value, {}, "Pipeline sem steps.")

    run = PipelineRun(
        pipeline_id=p.id,
        triggered_by=triggered_by,
        status=RunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    def resolver(ds_id: int) -> Dataset | None:
        return _resolve_dataset(db, ds_id)

    t0 = time.perf_counter()
    try:
        result = execute(
            _steps_payload_from_pipeline(p),
            dataset_resolver=resolver,
            db=db,
            created_by=triggered_by,
            pipeline_id=p.id,
            persist_target=True,
        )
        run.status = RunStatus.SUCCESS.value
        run.rows_in = result.total_rows_in()
        run.rows_out = result.total_rows_out()
        run.target_dataset_id = result.target_dataset_id
        run.logs = json.dumps([log.__dict__ for log in result.logs], default=str)
        summary = {
            "pipeline_run_id": run.id,
            "status": run.status,
            "rows_in": run.rows_in,
            "rows_out": run.rows_out,
            "target_dataset_id": run.target_dataset_id,
        }
    except StepFailure as exc:
        db.rollback()
        run = db.get(PipelineRun, run.id)
        run.status = RunStatus.FAILED.value
        run.error_message = exc.original_message
        run.failed_step_index = exc.step_index
        run.failed_step_name = exc.step_name
        run.failed_step_type = exc.step_type
        summary = {"pipeline_run_id": run.id, "status": run.status}
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        p_db = db.get(Pipeline, p.id)
        p_db.last_run_at = run.finished_at
        p_db.last_run_status = run.status
        db.commit()
        try:
            trigger_for(db, target_kind="pipeline", target_id=p.id)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        return JobResult(JobRunStatus.FAILED.value, summary, exc.original_message)
    except (PipelineError, Exception) as exc:
        db.rollback()
        run = db.get(PipelineRun, run.id)
        run.status = RunStatus.FAILED.value
        run.error_message = str(exc)
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        p_db = db.get(Pipeline, p.id)
        p_db.last_run_at = run.finished_at
        p_db.last_run_status = run.status
        db.commit()
        return JobResult(JobRunStatus.FAILED.value, {"pipeline_run_id": run.id}, str(exc))

    run.finished_at = datetime.utcnow()
    run.duration_ms = int((time.perf_counter() - t0) * 1000)
    p_db = db.get(Pipeline, p.id)
    p_db.last_run_at = run.finished_at
    p_db.last_run_status = run.status
    db.commit()

    try:
        trigger_for(db, target_kind="pipeline", target_id=p.id)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return JobResult(
        JobRunStatus.SUCCESS.value if run.status == RunStatus.SUCCESS.value else JobRunStatus.FAILED.value,
        summary,
        run.error_message,
    )


def run_forecast_train_job(db: Session, *, forecast_id: int, triggered_by: str) -> JobResult:
    f = db.get(Forecast, forecast_id)
    if not f:
        return JobResult(JobRunStatus.FAILED.value, {}, f"Forecast {forecast_id} nao encontrado.")
    ds = _resolve_dataset(db, f.source_dataset_id)
    if not ds:
        return JobResult(JobRunStatus.FAILED.value, {}, f"Dataset {f.source_dataset_id} nao encontrado.")

    run = ForecastRun(
        forecast_id=f.id,
        triggered_by=triggered_by,
        status=ForecastRunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    t0 = time.perf_counter()
    try:
        result = engine_train(
            ds=ds,
            target_column=f.target_column,
            date_column=f.date_column,
            frequency=f.frequency,
            group_by=f.group_by_list(),
            aggregation=f.aggregation,
            algorithm=f.algorithm,
            algorithm_params=f.algorithm_params_dict(),
            horizon=f.horizon,
            holdout_periods=f.holdout_periods,
            filters=f.filters_dict(),
        )
        run.status = ForecastRunStatus.SUCCESS.value
        run.rows_in = result.rows_in
        run.rows_forecast = result.rows_forecast
        run.groups_count = result.groups_count
        run.metrics = json.dumps(result.metrics, default=str)
        f_db = db.get(Forecast, f.id)
        f_db.last_metrics = json.dumps(result.metrics, default=str)
        summary = {
            "forecast_run_id": run.id,
            "groups_count": result.groups_count,
            "rows_in": result.rows_in,
            "metrics": result.metrics,
        }
        err = None
    except (ForecastError, Exception) as exc:
        db.rollback()
        run = db.get(ForecastRun, run.id)
        run.status = ForecastRunStatus.FAILED.value
        run.error_message = str(exc)
        summary = {"forecast_run_id": run.id}
        err = str(exc)

    run.finished_at = datetime.utcnow()
    run.duration_ms = int((time.perf_counter() - t0) * 1000)
    f_db = db.get(Forecast, f.id)
    f_db.last_run_at = run.finished_at
    f_db.last_run_status = run.status
    db.commit()

    try:
        trigger_for(db, target_kind="forecast", target_id=f.id)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    status = JobRunStatus.SUCCESS.value if run.status == ForecastRunStatus.SUCCESS.value else JobRunStatus.FAILED.value
    return JobResult(status, summary, err)


def run_alerts_evaluate_job(db: Session, *, workspace: str | None, triggered_by: str) -> JobResult:
    q = db.query(Alert).filter(Alert.enabled == True)  # noqa: E712
    if workspace:
        q = q.filter(Alert.workspace == workspace)
    alerts = q.all()

    fired = 0
    errors = 0
    evaluated = 0
    for alert in alerts:
        evaluated += 1
        alert.last_evaluated_at = datetime.utcnow()
        if in_cooldown(alert):
            continue
        try:
            outcome = alert_evaluate(db, alert)
        except AlertEvalError as exc:
            alert.last_eval_status = AlertEvalStatus.ERROR.value
            alert.last_eval_error = str(exc)
            errors += 1
            continue
        except Exception as exc:  # noqa: BLE001
            alert.last_eval_status = AlertEvalStatus.ERROR.value
            alert.last_eval_error = str(exc)
            errors += 1
            continue

        if outcome.fired:
            alert.last_eval_status = AlertEvalStatus.FIRED.value
            alert.last_eval_error = None
            fire_notification(db, alert=alert, outcome=outcome)
            fired += 1
        else:
            alert.last_eval_status = AlertEvalStatus.OK.value
            alert.last_eval_error = None

    db.commit()
    summary = {"evaluated": evaluated, "fired": fired, "errors": errors}
    status = JobRunStatus.SUCCESS.value if errors == 0 else JobRunStatus.FAILED.value
    return JobResult(status, summary, None if errors == 0 else f"{errors} alert(s) com erro")


def execute_job(db: Session, job: ScheduledJob, *, triggered_by: str = "scheduler") -> ScheduledJobRun:
    """Executa um ScheduledJob e persiste ScheduledJobRun."""
    run = ScheduledJobRun(
        job_id=job.id,
        triggered_by=triggered_by,
        status=JobRunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    t0 = time.perf_counter()
    actor = job.created_by or triggered_by

    if job.job_type == JobType.PIPELINE_RUN.value:
        if not job.target_id:
            result = JobResult(JobRunStatus.FAILED.value, {}, "target_id obrigatorio para pipeline_run")
        else:
            result = run_pipeline_job(db, pipeline_id=job.target_id, triggered_by=actor)
    elif job.job_type == JobType.FORECAST_TRAIN.value:
        if not job.target_id:
            result = JobResult(JobRunStatus.FAILED.value, {}, "target_id obrigatorio para forecast_train")
        else:
            result = run_forecast_train_job(db, forecast_id=job.target_id, triggered_by=actor)
    elif job.job_type == JobType.ALERTS_EVALUATE.value:
        result = run_alerts_evaluate_job(db, workspace=job.workspace, triggered_by=actor)
    else:
        result = JobResult(JobRunStatus.FAILED.value, {}, f"job_type desconhecido: {job.job_type}")

    run.status = result.status
    run.result_summary = json.dumps(result.summary, default=str)
    run.error_message = result.error
    run.finished_at = datetime.utcnow()
    run.duration_ms = int((time.perf_counter() - t0) * 1000)

    job.last_run_at = run.finished_at
    job.last_run_status = run.status
    job.run_count = (job.run_count or 0) + 1
    db.commit()
    db.refresh(run)

    log_action(
        db,
        user_email=actor,
        action="scheduled_job_run",
        object_type="scheduled_job",
        object_name=job.name,
        workspace=job.workspace,
        details=f"status={run.status} type={job.job_type}",
    )
    return run
