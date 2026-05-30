"""Router Scheduled Jobs (Phase 6).

    GET    /scheduled-jobs              lista
    POST   /scheduled-jobs              cria
    GET    /scheduled-jobs/status       status do APScheduler
    GET    /scheduled-jobs/{id}         detalhe
    PUT    /scheduled-jobs/{id}         atualiza
    DELETE /scheduled-jobs/{id}         remove
    POST   /scheduled-jobs/{id}/pause    pausa
    POST   /scheduled-jobs/{id}/resume   retoma
    POST   /scheduled-jobs/{id}/run-now    executa agora
    GET    /scheduled-jobs/{id}/runs       historico
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.forecast import Forecast
from app.models.pipeline import Pipeline
from app.models.scheduled_job import JobType, ScheduledJob, ScheduledJobRun
from app.models.user import User
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobOut,
    ScheduledJobRunOut,
    ScheduledJobUpdate,
    SchedulerStatusOut,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import accessible_workspaces, has_capability
from app.services.scheduler_service import (
    compute_next_run,
    register_job,
    run_job_now,
    scheduler_status,
    unregister_job,
)
from database import get_db

router = APIRouter(prefix="/scheduled-jobs", tags=["scheduled-jobs"])

VALID_JOB_TYPES = {t.value for t in JobType}


def _target_name(db: Session, job: ScheduledJob) -> str | None:
    if job.job_type == JobType.PIPELINE_RUN.value and job.target_id:
        p = db.get(Pipeline, job.target_id)
        return p.name if p else None
    if job.job_type == JobType.FORECAST_TRAIN.value and job.target_id:
        f = db.get(Forecast, job.target_id)
        return f.name if f else None
    if job.job_type == JobType.ALERTS_EVALUATE.value:
        return f"Alerts ({job.workspace})"
    return None


def _to_out(db: Session, job: ScheduledJob) -> ScheduledJobOut:
    return ScheduledJobOut(
        id=job.id,
        name=job.name,
        description=job.description,
        workspace=job.workspace,
        business_area=job.business_area,
        job_type=job.job_type,
        target_id=job.target_id,
        cron_expression=job.cron_expression,
        timezone=job.timezone,
        enabled=job.enabled,
        paused=job.paused,
        created_by=job.created_by,
        created_at=job.created_at,
        updated_at=job.updated_at,
        last_run_at=job.last_run_at,
        last_run_status=job.last_run_status,
        next_run_at=job.next_run_at,
        run_count=job.run_count,
        source_pipeline_id=job.source_pipeline_id,
        target_name=_target_name(db, job),
    )


def _run_to_out(r: ScheduledJobRun) -> ScheduledJobRunOut:
    return ScheduledJobRunOut(
        id=r.id,
        job_id=r.job_id,
        triggered_by=r.triggered_by,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        duration_ms=r.duration_ms,
        result_summary=r.result_dict(),
        error_message=r.error_message,
    )


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(status_code=403, detail=f"Sem acesso ao workspace {workspace}")


def _validate_cron(expr: str) -> None:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise HTTPException(status_code=400, detail="cron_expression deve ter 5 campos (min hour dom month dow)")


@router.get("/status", response_model=SchedulerStatusOut)
def get_status(
    user: User = Depends(require_capability("schedule_job")),
) -> SchedulerStatusOut:
    st = scheduler_status()
    return SchedulerStatusOut(**st)


@router.get("", response_model=list[ScheduledJobOut])
def list_jobs(
    workspace: str | None = None,
    job_type: str | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ScheduledJobOut]:
    if not has_capability(user, "schedule_job") and not has_capability(user, "view_pipelines"):
        raise HTTPException(status_code=403, detail="Sem permissao.")
    q = db.query(ScheduledJob)
    if workspace:
        q = q.filter(ScheduledJob.workspace == workspace)
    if job_type:
        q = q.filter(ScheduledJob.job_type == job_type)
    if enabled is not None:
        q = q.filter(ScheduledJob.enabled == enabled)
    items = q.order_by(ScheduledJob.next_run_at.asc().nulls_last(), ScheduledJob.name).all()
    if items:
        allowed = set(accessible_workspaces(user, list({j.workspace for j in items})))
        items = [j for j in items if j.workspace in allowed]
    return [_to_out(db, j) for j in items]


@router.post("", response_model=ScheduledJobOut)
def create_job(
    payload: ScheduledJobCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobOut:
    _check_workspace(user, payload.workspace)
    _validate_cron(payload.cron_expression)
    if payload.job_type not in VALID_JOB_TYPES:
        raise HTTPException(status_code=400, detail=f"job_type invalido. Validos: {sorted(VALID_JOB_TYPES)}")
    if payload.job_type in {JobType.PIPELINE_RUN.value, JobType.FORECAST_TRAIN.value} and not payload.target_id:
        raise HTTPException(status_code=400, detail="target_id obrigatorio para este job_type.")

    job = ScheduledJob(
        name=payload.name,
        description=payload.description,
        workspace=payload.workspace,
        business_area=payload.business_area,
        job_type=payload.job_type,
        target_id=payload.target_id,
        cron_expression=payload.cron_expression,
        timezone=payload.timezone,
        enabled=payload.enabled,
        paused=payload.paused,
        created_by=user.email,
        next_run_at=compute_next_run(payload.cron_expression, payload.timezone),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    register_job(job)
    log_action(db, user_email=user.email, action="create_scheduled_job", object_type="scheduled_job", object_name=job.name, workspace=job.workspace)
    return _to_out(db, job)


@router.get("/{job_id}", response_model=ScheduledJobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobOut:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    _check_workspace(user, job.workspace)
    return _to_out(db, job)


@router.put("/{job_id}", response_model=ScheduledJobOut)
def update_job(
    job_id: int,
    payload: ScheduledJobUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobOut:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    _check_workspace(user, job.workspace)
    data = payload.model_dump(exclude_unset=True)
    if "cron_expression" in data and data["cron_expression"]:
        _validate_cron(data["cron_expression"])
    if "workspace" in data and data["workspace"]:
        _check_workspace(user, data["workspace"])
    for k, v in data.items():
        setattr(job, k, v)
    job.next_run_at = compute_next_run(job.cron_expression, job.timezone)
    db.commit()
    db.refresh(job)
    register_job(job)
    return _to_out(db, job)


@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> dict:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    _check_workspace(user, job.workspace)
    unregister_job(job_id)
    db.delete(job)
    db.commit()
    return {"deleted": True}


@router.post("/{job_id}/pause", response_model=ScheduledJobOut)
def pause_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobOut:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    job.paused = True
    db.commit()
    unregister_job(job_id)
    db.refresh(job)
    return _to_out(db, job)


@router.post("/{job_id}/resume", response_model=ScheduledJobOut)
def resume_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobOut:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    job.paused = False
    job.next_run_at = compute_next_run(job.cron_expression, job.timezone)
    db.commit()
    db.refresh(job)
    register_job(job)
    return _to_out(db, job)


@router.post("/{job_id}/run-now", response_model=ScheduledJobRunOut)
def trigger_now(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> ScheduledJobRunOut:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    _check_workspace(user, job.workspace)
    run_job_now(job_id, triggered_by=user.email)
    db.refresh(job)
    last = (
        db.query(ScheduledJobRun)
        .filter(ScheduledJobRun.job_id == job_id)
        .order_by(ScheduledJobRun.started_at.desc())
        .first()
    )
    if not last:
        raise HTTPException(status_code=500, detail="Run nao registrado.")
    return _run_to_out(last)


@router.get("/{job_id}/runs", response_model=list[ScheduledJobRunOut])
def list_runs(
    job_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("schedule_job")),
) -> list[ScheduledJobRunOut]:
    job = db.get(ScheduledJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado.")
    _check_workspace(user, job.workspace)
    runs = (
        db.query(ScheduledJobRun)
        .filter(ScheduledJobRun.job_id == job_id)
        .order_by(ScheduledJobRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_out(r) for r in runs]
