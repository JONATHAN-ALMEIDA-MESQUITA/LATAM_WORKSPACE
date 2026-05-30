"""Router Model Registry (Phase 9)."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.forecast import Forecast
from app.models.model_registry import RegisteredModel
from app.models.user import User
from app.schemas.phase9 import RegisteredModelCreate, RegisteredModelOut, RegisteredModelUpdate
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import accessible_workspaces
from database import get_db


router = APIRouter(prefix="/model-registry", tags=["model-registry"])


def _to_out(m: RegisteredModel) -> RegisteredModelOut:
    try:
        metrics = json.loads(m.metrics_json or "{}")
    except json.JSONDecodeError:
        metrics = {}
    return RegisteredModelOut(
        id=m.id,
        name=m.name,
        version=m.version,
        model_type=m.model_type,
        algorithm=m.algorithm,
        forecast_id=m.forecast_id,
        workspace=m.workspace,
        business_area=m.business_area,
        status=m.status,
        metrics=metrics,
        description=m.description,
        registered_by=m.registered_by,
        registered_at=m.registered_at,
    )


@router.get("", response_model=list[RegisteredModelOut])
def list_models(
    workspace: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_model_registry")),
) -> list[RegisteredModelOut]:
    q = db.query(RegisteredModel).order_by(RegisteredModel.registered_at.desc())
    items = q.all()
    if workspace:
        items = [m for m in items if m.workspace == workspace]
    if status:
        items = [m for m in items if m.status == status]
    allowed = set(accessible_workspaces(user, list({m.workspace for m in items})))
    if allowed:
        items = [m for m in items if m.workspace in allowed]
    return [_to_out(m) for m in items]


@router.post("", response_model=RegisteredModelOut)
def register_model(
    body: RegisteredModelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("register_model")),
) -> RegisteredModelOut:
    if body.workspace not in accessible_workspaces(user, [body.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso ao workspace.")
    metrics: dict = {}
    algorithm = body.algorithm
    if body.forecast_id:
        f = db.get(Forecast, body.forecast_id)
        if not f:
            raise HTTPException(status_code=404, detail="Forecast nao encontrado.")
        algorithm = algorithm or f.algorithm
        try:
            metrics = json.loads(f.last_metrics or "{}")
        except json.JSONDecodeError:
            metrics = {}
    m = RegisteredModel(
        name=body.name,
        version=body.version,
        model_type=body.model_type,
        algorithm=algorithm,
        forecast_id=body.forecast_id,
        workspace=body.workspace,
        business_area=body.business_area,
        status=body.status,
        metrics_json=json.dumps(metrics, default=str),
        description=body.description,
        registered_by=user.email,
    )
    db.add(m)
    db.flush()
    log_action(
        db,
        user_email=user.email,
        action="register_model",
        object_type="registered_model",
        object_name=m.name,
        workspace=m.workspace,
        details=f"version={m.version} algorithm={m.algorithm}",
    )
    return _to_out(m)


@router.put("/{model_id}", response_model=RegisteredModelOut)
def update_model(
    model_id: int,
    body: RegisteredModelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("register_model")),
) -> RegisteredModelOut:
    m = db.get(RegisteredModel, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado.")
    if m.workspace not in accessible_workspaces(user, [m.workspace]):
        raise HTTPException(status_code=403, detail="Sem acesso.")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.post("/{model_id}/promote", response_model=RegisteredModelOut)
def promote_model(
    model_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("register_model")),
) -> RegisteredModelOut:
    m = db.get(RegisteredModel, model_id)
    if not m:
        raise HTTPException(status_code=404, detail="Modelo nao encontrado.")
    m.status = "Production"
    m.registered_at = datetime.utcnow()
    log_action(
        db,
        user_email=user.email,
        action="promote_model",
        object_type="registered_model",
        object_name=m.name,
        workspace=m.workspace,
    )
    db.commit()
    db.refresh(m)
    return _to_out(m)
