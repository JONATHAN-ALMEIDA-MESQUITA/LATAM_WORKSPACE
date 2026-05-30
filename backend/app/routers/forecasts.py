"""Router de Forecasts (Phase 4 - Forecasting Studio).

    GET    /forecasts                        lista
    POST   /forecasts                        cria (Draft)
    GET    /forecasts/{id}                   detalhe
    PUT    /forecasts/{id}                   atualiza
    DELETE /forecasts/{id}                   remove

    POST   /forecasts/{id}/train             treina + backtest (NAO persiste dataset, registra run)
    POST   /forecasts/{id}/publish           treina + grava output como Dataset + status=Published
    POST   /forecasts/{id}/archive           Published -> Archived
    GET    /forecasts/{id}/runs              historico de runs

    POST   /forecasts/preview-adhoc          treina ad-hoc sem salvar (Editor sandbox)
"""

from __future__ import annotations

import json
import math
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetColumn, DatasetSourceType, DatasetStatus
from app.models.forecast import (
    Forecast,
    ForecastAlgorithm,
    ForecastFrequency,
    ForecastRun,
    ForecastRunStatus,
    ForecastStatus,
)
from app.models.user import User
from app.schemas.forecast import (
    ForecastCreate,
    ForecastOut,
    ForecastPointOut,
    ForecastRunOut,
    ForecastSummary,
    ForecastTrainResponse,
    ForecastUpdate,
    PublishActionRequest,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.forecast_engine import (
    ForecastError,
    points_to_dataframe,
    train as engine_train,
)
from app.services.permission_service import (
    accessible_workspaces,
    can_create_forecast,
    can_publish_forecast,
    has_capability,
)
from app.utils.file_utils import save_parquet
from config import settings
from database import get_db


router = APIRouter(prefix="/forecasts", tags=["forecasts"])


VALID_ALGORITHMS = {a.value for a in ForecastAlgorithm}
VALID_FREQUENCIES = {f.value for f in ForecastFrequency}


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------

def _to_out(f: Forecast) -> ForecastOut:
    return ForecastOut(
        id=f.id,
        name=f.name,
        description=f.description,
        workspace=f.workspace,
        business_area=f.business_area,
        source_dataset_id=f.source_dataset_id,
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
        status=f.status,
        created_by=f.created_by,
        created_at=f.created_at,
        updated_at=f.updated_at,
        published_by=f.published_by,
        published_at=f.published_at,
        archived_by=f.archived_by,
        archived_at=f.archived_at,
        last_run_at=f.last_run_at,
        last_run_status=f.last_run_status,
        last_metrics=f.last_metrics_dict(),
        output_dataset_id=f.output_dataset_id,
    )


def _to_summary(f: Forecast) -> ForecastSummary:
    return ForecastSummary(
        id=f.id,
        name=f.name,
        description=f.description,
        workspace=f.workspace,
        business_area=f.business_area,
        algorithm=f.algorithm,
        horizon=f.horizon,
        frequency=f.frequency,
        status=f.status,
        created_by=f.created_by,
        updated_at=f.updated_at,
        last_run_at=f.last_run_at,
        last_run_status=f.last_run_status,
        last_metrics=f.last_metrics_dict(),
        output_dataset_id=f.output_dataset_id,
    )


def _run_to_out(r: ForecastRun) -> ForecastRunOut:
    return ForecastRunOut(
        id=r.id,
        forecast_id=r.forecast_id,
        triggered_by=r.triggered_by,
        status=r.status,
        started_at=r.started_at,
        finished_at=r.finished_at,
        duration_ms=r.duration_ms,
        rows_in=r.rows_in,
        rows_forecast=r.rows_forecast,
        groups_count=r.groups_count,
        metrics=r.metrics_dict(),
        error_message=r.error_message,
        output_dataset_id=r.output_dataset_id,
    )


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(status_code=403, detail=f"Sem acesso ao workspace {workspace}")


def _resolve_forecast(db: Session, user: User, forecast_id: int) -> Forecast:
    f = db.get(Forecast, forecast_id)
    if not f:
        raise HTTPException(status_code=404, detail="Forecast nao encontrado.")
    _check_workspace(user, f.workspace)
    return f


def _validate_config(payload_dict: dict) -> None:
    if "algorithm" in payload_dict and payload_dict["algorithm"] not in VALID_ALGORITHMS:
        raise HTTPException(
            status_code=400,
            detail=f"algorithm invalido. Validos: {sorted(VALID_ALGORITHMS)}",
        )
    if "frequency" in payload_dict and payload_dict["frequency"] not in VALID_FREQUENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"frequency invalido. Validos: {sorted(VALID_FREQUENCIES)}",
        )


def _resolve_dataset(db: Session, user: User, ds_id: int) -> Dataset:
    ds = db.get(Dataset, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail=f"Dataset {ds_id} nao encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso ao dataset.")
    return ds


def _persist_output_dataset(
    db: Session,
    *,
    forecast: Forecast,
    df: pd.DataFrame,
    created_by: str,
) -> Dataset:
    """Grava output do forecast como Dataset (atualiza se ja existe)."""
    from app.services.profiling_service import profile_dataframe, serialize_sample_values

    overwrite_id = forecast.output_dataset_id
    if overwrite_id:
        ds = db.get(Dataset, overwrite_id)
        if ds:
            ds.row_count = int(len(df))
            ds.column_count = int(df.shape[1])
            ds.source_type = DatasetSourceType.FORECAST.value
        else:
            ds = None
    else:
        ds = None

    if not ds:
        ds = Dataset(
            name=f"forecast_{forecast.id}_{forecast.name[:60]}",
            description=f"Forecast '{forecast.name}' - {forecast.algorithm}",
            workspace=forecast.workspace,
            business_area=forecast.business_area,
            source_type=DatasetSourceType.FORECAST.value,
            row_count=int(len(df)),
            column_count=int(df.shape[1]),
            status=DatasetStatus.VALIDATED.value,
            created_by=created_by,
        )
        db.add(ds)
        db.flush()

    processed_path = (settings.processed_dir / f"dataset_{ds.id}.parquet").resolve()
    save_parquet(df, processed_path)
    ds.processed_path = str(processed_path)

    db.query(DatasetColumn).filter(DatasetColumn.dataset_id == ds.id).delete()
    profiles = profile_dataframe(df)
    for idx, prof in enumerate(profiles):
        db.add(
            DatasetColumn(
                dataset_id=ds.id,
                position=idx,
                name=prof.name,
                dtype=prof.dtype,
                null_count=prof.null_count,
                distinct_count=prof.distinct_count,
                min_value=prof.min_value,
                max_value=prof.max_value,
                mean_value=(
                    prof.mean_value
                    if prof.mean_value is not None
                    and not (isinstance(prof.mean_value, float) and math.isnan(prof.mean_value))
                    else None
                ),
                std_value=(
                    prof.std_value
                    if prof.std_value is not None
                    and not (isinstance(prof.std_value, float) and math.isnan(prof.std_value))
                    else None
                ),
                sample_values=serialize_sample_values(prof.sample_values),
            )
        )
    db.flush()
    return ds


# ---------------------------------------------------------------------------
# Lista + CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ForecastSummary])
def list_forecasts(
    workspace: str | None = None,
    business_area: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_forecasts")),
) -> list[ForecastSummary]:
    q = db.query(Forecast)
    if workspace:
        q = q.filter(Forecast.workspace == workspace)
    if business_area:
        q = q.filter(Forecast.business_area == business_area)
    if status:
        q = q.filter(Forecast.status == status)
    items = q.order_by(Forecast.updated_at.desc()).all()
    if items:
        allowed = set(accessible_workspaces(user, list({f.workspace for f in items})))
        items = [f for f in items if f.workspace in allowed]
    return [_to_summary(f) for f in items]


@router.post("", response_model=ForecastOut)
def create_forecast(
    payload: ForecastCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_forecast")),
) -> ForecastOut:
    _check_workspace(user, payload.workspace)
    _validate_config(payload.model_dump())
    _resolve_dataset(db, user, payload.source_dataset_id)

    f = Forecast(
        name=payload.name,
        description=payload.description,
        workspace=payload.workspace,
        business_area=payload.business_area,
        source_dataset_id=payload.source_dataset_id,
        target_column=payload.target_column,
        date_column=payload.date_column,
        frequency=payload.frequency,
        group_by=json.dumps(payload.group_by or []),
        aggregation=payload.aggregation,
        algorithm=payload.algorithm,
        algorithm_params=json.dumps(payload.algorithm_params or {}),
        horizon=payload.horizon,
        holdout_periods=payload.holdout_periods,
        filters=json.dumps(payload.filters or {}),
        status=ForecastStatus.DRAFT.value,
        created_by=user.email,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    log_action(
        db,
        user_email=user.email,
        action="create_forecast",
        object_type="forecast",
        object_name=f.name,
        workspace=f.workspace,
        business_area=f.business_area,
    )
    return _to_out(f)


@router.get("/{forecast_id}", response_model=ForecastOut)
def get_forecast(
    forecast_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_forecasts")),
) -> ForecastOut:
    f = _resolve_forecast(db, user, forecast_id)
    return _to_out(f)


@router.put("/{forecast_id}", response_model=ForecastOut)
def update_forecast(
    forecast_id: int,
    payload: ForecastUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_forecast")),
) -> ForecastOut:
    f = _resolve_forecast(db, user, forecast_id)
    if f.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(status_code=403, detail="Apenas o autor ou admin pode editar.")
    data = payload.model_dump(exclude_unset=True)
    _validate_config(data)
    if "workspace" in data and data["workspace"]:
        _check_workspace(user, data["workspace"])
    if "source_dataset_id" in data and data["source_dataset_id"]:
        _resolve_dataset(db, user, data["source_dataset_id"])

    for k, v in data.items():
        if k == "group_by":
            f.group_by = json.dumps(v or [])
        elif k == "algorithm_params":
            f.algorithm_params = json.dumps(v or {})
        elif k == "filters":
            f.filters = json.dumps(v or {})
        else:
            setattr(f, k, v)
    db.commit()
    db.refresh(f)
    return _to_out(f)


@router.delete("/{forecast_id}")
def delete_forecast(
    forecast_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_forecast")),
) -> dict:
    f = _resolve_forecast(db, user, forecast_id)
    if f.created_by != user.email and not has_capability(user, "publish_any"):
        raise HTTPException(status_code=403, detail="Sem permissao para remover.")
    log_action(
        db,
        user_email=user.email,
        action="delete_forecast",
        object_type="forecast",
        object_name=f.name,
        workspace=f.workspace,
    )
    db.delete(f)
    db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Train + Publish
# ---------------------------------------------------------------------------

def _run_train_internal(
    db: Session, user: User, f: Forecast, persist_output: bool
) -> tuple[ForecastRun, list[ForecastPointOut], dict, int | None]:
    """Helper: cria PipelineRun, treina, opcionalmente grava output dataset."""
    ds = _resolve_dataset(db, user, f.source_dataset_id)

    run = ForecastRun(
        forecast_id=f.id,
        triggered_by=user.email,
        status=ForecastRunStatus.RUNNING.value,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    t0 = time.perf_counter()
    output_ds_id: int | None = None
    points_out: list[ForecastPointOut] = []
    metrics: dict = {}
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
        metrics = result.metrics
        points_out = [ForecastPointOut(**p) for p in result.points]

        if persist_output:
            df_out = points_to_dataframe(result.points)
            new_ds = _persist_output_dataset(db, forecast=f, df=df_out, created_by=user.email)
            output_ds_id = new_ds.id
            f.output_dataset_id = new_ds.id

        run.status = ForecastRunStatus.SUCCESS.value
        run.rows_in = result.rows_in
        run.rows_forecast = result.rows_forecast
        run.groups_count = result.groups_count
        run.metrics = json.dumps(metrics, default=str)
        run.output_dataset_id = output_ds_id

        f.last_metrics = json.dumps(metrics, default=str)
    except ForecastError as exc:
        db.rollback()
        run = db.get(ForecastRun, run.id)
        run.status = ForecastRunStatus.FAILED.value
        run.error_message = str(exc)
    except Exception as exc:
        db.rollback()
        run = db.get(ForecastRun, run.id)
        run.status = ForecastRunStatus.FAILED.value
        run.error_message = f"Erro inesperado: {exc}"
    finally:
        run.finished_at = datetime.utcnow()
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        f_db = db.get(Forecast, f.id)
        f_db.last_run_at = run.finished_at
        f_db.last_run_status = run.status
        db.commit()
        db.refresh(run)
        db.refresh(f_db)

    return run, points_out, metrics, output_ds_id


@router.post("/{forecast_id}/train", response_model=ForecastTrainResponse)
def train_forecast(
    forecast_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ForecastTrainResponse:
    """Treina + backtest. NAO grava output como dataset. Util pro Editor."""
    f = _resolve_forecast(db, user, forecast_id)
    if not can_create_forecast(user, f.workspace):
        raise HTTPException(status_code=403, detail="Sem permissao para treinar.")
    run, points, metrics, _ = _run_train_internal(db, user, f, persist_output=False)

    if run.status == ForecastRunStatus.FAILED.value:
        raise HTTPException(status_code=400, detail=run.error_message or "Falha no treino.")

    log_action(
        db,
        user_email=user.email,
        action="train_forecast",
        object_type="forecast",
        object_name=f.name,
        workspace=f.workspace,
        details=f"status={run.status} groups={run.groups_count}",
    )

    # Trigger alerts (best-effort)
    try:
        from app.services.alert_triggers import trigger_for
        trigger_for(db, target_kind="forecast", target_id=f.id)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return ForecastTrainResponse(
        forecast_id=f.id,
        rows_in=run.rows_in or 0,
        rows_forecast=run.rows_forecast or 0,
        groups_count=run.groups_count or 0,
        points=points,
        metrics=metrics,
    )


@router.post("/{forecast_id}/publish", response_model=ForecastOut)
def publish_forecast(
    forecast_id: int,
    payload: PublishActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ForecastOut:
    """Treina E grava output como Dataset + status=Published."""
    f = _resolve_forecast(db, user, forecast_id)
    if not can_publish_forecast(user, f.workspace):
        raise HTTPException(status_code=403, detail="Sem permissao para publicar forecast.")

    run, _, _, output_ds_id = _run_train_internal(db, user, f, persist_output=True)
    if run.status == ForecastRunStatus.FAILED.value:
        raise HTTPException(status_code=400, detail=run.error_message or "Falha no treino.")

    f.status = ForecastStatus.PUBLISHED.value
    f.published_by = user.email
    f.published_at = datetime.utcnow()
    db.commit()
    db.refresh(f)

    log_action(
        db,
        user_email=user.email,
        action="publish_forecast",
        object_type="forecast",
        object_name=f.name,
        workspace=f.workspace,
        details=f"output_dataset_id={output_ds_id} note={payload.note}",
    )

    # Trigger alerts (best-effort)
    try:
        from app.services.alert_triggers import trigger_for
        trigger_for(db, target_kind="forecast", target_id=f.id)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()

    return _to_out(f)


@router.post("/{forecast_id}/archive", response_model=ForecastOut)
def archive_forecast(
    forecast_id: int,
    payload: PublishActionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ForecastOut:
    f = _resolve_forecast(db, user, forecast_id)
    if not can_publish_forecast(user, f.workspace) and f.created_by != user.email:
        raise HTTPException(status_code=403, detail="Sem permissao para arquivar.")
    f.status = ForecastStatus.ARCHIVED.value
    f.archived_by = user.email
    f.archived_at = datetime.utcnow()
    db.commit()
    db.refresh(f)
    log_action(
        db,
        user_email=user.email,
        action="archive_forecast",
        object_type="forecast",
        object_name=f.name,
        workspace=f.workspace,
    )
    return _to_out(f)


@router.get("/{forecast_id}/runs", response_model=list[ForecastRunOut])
def list_runs(
    forecast_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_forecasts")),
) -> list[ForecastRunOut]:
    f = _resolve_forecast(db, user, forecast_id)
    runs = (
        db.query(ForecastRun)
        .filter(ForecastRun.forecast_id == f.id)
        .order_by(ForecastRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_out(r) for r in runs]
