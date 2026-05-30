"""Router de Metric (camada semântica).

Endpoints:
    GET    /metrics               lista (filtra por workspace acessível, opcionalmente por dataset)
    POST   /metrics               cria
    GET    /metrics/{id}          detalhe
    PUT    /metrics/{id}          atualiza
    POST   /metrics/{id}/status   muda status (Draft/Certified/Published/Deprecated)
    DELETE /metrics/{id}          remove
    POST   /metrics/preview       calcula valor sem persistir (útil no Metric Builder)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.metric import Metric, MetricStatus
from app.models.user import User
from app.schemas.metric import (
    MetricCreate,
    MetricOut,
    MetricPreviewRequest,
    MetricPreviewResponse,
    MetricUpdate,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.metric_engine import (
    MetricError,
    calc_metric,
    format_metric_value,
)
from app.services.permission_service import accessible_workspaces
from database import get_db


router = APIRouter(prefix="/metrics", tags=["metrics"])


VALID_STATUS = {s.value for s in MetricStatus}


def _to_out(m: Metric) -> MetricOut:
    return MetricOut(
        id=m.id,
        name=m.name,
        description=m.description,
        dataset_id=m.dataset_id,
        workspace=m.workspace,
        business_area=m.business_area,
        formula_type=m.formula_type,
        formula_config=m.config_dict(),
        output_format=m.output_format,
        decimals=m.decimals,
        status=m.status,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _check_dataset_access(db: Session, user: User, dataset_id: int) -> Dataset:
    ds = db.get(Dataset, dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset não encontrado.")
    if ds.workspace not in accessible_workspaces(user, [ds.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso ao workspace do dataset.")
    return ds


@router.get("", response_model=list[MetricOut])
def list_metrics(
    dataset_id: int | None = None,
    workspace: str | None = None,
    business_area: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_metrics")),
) -> list[MetricOut]:
    q = db.query(Metric)
    if dataset_id:
        q = q.filter(Metric.dataset_id == dataset_id)
    if workspace:
        q = q.filter(Metric.workspace == workspace)
    if business_area:
        q = q.filter(Metric.business_area == business_area)
    if status:
        q = q.filter(Metric.status == status)
    items = q.order_by(Metric.updated_at.desc()).all()
    if items:
        allowed = set(accessible_workspaces(user, list({m.workspace for m in items})))
        items = [m for m in items if m.workspace in allowed]
    return [_to_out(m) for m in items]


@router.post("", response_model=MetricOut)
def create_metric(
    payload: MetricCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_metric")),
) -> MetricOut:
    ds = _check_dataset_access(db, user, payload.dataset_id)

    # Workspace deve ser acessível ao user
    if payload.workspace not in accessible_workspaces(user, [payload.workspace]):
        raise HTTPException(
            status_code=403,
            detail=f"Sem acesso ao workspace {payload.workspace}",
        )

    m = Metric(
        name=payload.name,
        description=payload.description,
        dataset_id=ds.id,
        workspace=payload.workspace,
        business_area=payload.business_area or ds.business_area,
        formula_type=payload.formula_type,
        formula_config=json.dumps(payload.formula_config or {}),
        output_format=payload.output_format,
        decimals=payload.decimals,
        status=MetricStatus.DRAFT.value,
        created_by=user.email,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    log_action(
        db,
        user_email=user.email,
        action="create_metric",
        object_type="metric",
        object_name=m.name,
        workspace=m.workspace,
        business_area=m.business_area,
        details=f"type={m.formula_type} dataset={ds.name}",
    )
    return _to_out(m)


@router.get("/{metric_id}", response_model=MetricOut)
def get_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_metrics")),
) -> MetricOut:
    m = db.get(Metric, metric_id)
    if not m:
        raise HTTPException(status_code=404, detail="Métrica não encontrada.")
    if m.workspace not in accessible_workspaces(user, [m.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    return _to_out(m)


@router.put("/{metric_id}", response_model=MetricOut)
def update_metric(
    metric_id: int,
    payload: MetricUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_metric")),
) -> MetricOut:
    m = db.get(Metric, metric_id)
    if not m:
        raise HTTPException(status_code=404, detail="Métrica não encontrada.")
    if m.workspace not in accessible_workspaces(user, [m.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")

    if payload.name is not None:
        m.name = payload.name
    if payload.description is not None:
        m.description = payload.description
    if payload.formula_type is not None:
        m.formula_type = payload.formula_type
    if payload.formula_config is not None:
        m.formula_config = json.dumps(payload.formula_config)
    if payload.output_format is not None:
        m.output_format = payload.output_format
    if payload.decimals is not None:
        m.decimals = int(payload.decimals)
    if payload.status is not None:
        if payload.status not in VALID_STATUS:
            raise HTTPException(status_code=400, detail=f"Status inválido: {payload.status}")
        m.status = payload.status
    db.commit()
    db.refresh(m)
    log_action(
        db,
        user_email=user.email,
        action="update_metric",
        object_type="metric",
        object_name=m.name,
        workspace=m.workspace,
        business_area=m.business_area,
    )
    return _to_out(m)


@router.delete("/{metric_id}")
def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_metric")),
) -> dict:
    m = db.get(Metric, metric_id)
    if not m:
        raise HTTPException(status_code=404, detail="Métrica não encontrada.")
    if m.workspace not in accessible_workspaces(user, [m.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso a este workspace.")
    name = m.name
    workspace = m.workspace
    db.delete(m)
    db.commit()
    log_action(
        db,
        user_email=user.email,
        action="delete_metric",
        object_type="metric",
        object_name=name,
        workspace=workspace,
    )
    return {"ok": True}


@router.post("/preview", response_model=MetricPreviewResponse)
def preview_metric(
    payload: MetricPreviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_metrics")),
) -> MetricPreviewResponse:
    """Calcula uma métrica sob demanda (sem persistir). Usado pelo Metric Builder."""
    import pandas as pd

    ds = _check_dataset_access(db, user, payload.dataset_id)
    path = Path(ds.processed_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Parquet do dataset ausente.")
    df = pd.read_parquet(path)

    # Aplica filtros simples
    for col, val in (payload.filters or {}).items():
        if col not in df.columns:
            continue
        if isinstance(val, list):
            df = df[df[col].isin(val)]
        elif val is not None and val != "":
            df = df[df[col] == val]

    try:
        value = calc_metric(
            df,
            formula_type=payload.formula_type,
            formula_config=payload.formula_config or {},
        )
    except MetricError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    output_format = "number"
    decimals = 2
    formatted = format_metric_value(value, output_format=output_format, decimals=decimals)
    return MetricPreviewResponse(
        value=value,
        formatted=formatted,
        output_format=output_format,
        decimals=decimals,
        rows_used=int(len(df)),
    )
