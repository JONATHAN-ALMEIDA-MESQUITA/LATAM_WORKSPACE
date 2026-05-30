"""Router de Workspaces - lista RBAC + admin update (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.admin import WorkspaceUpdate
from app.schemas.workspace import WorkspaceOut
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.permission_service import accessible_workspaces
from database import get_db


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _to_out(w: Workspace) -> WorkspaceOut:
    return WorkspaceOut(
        id=w.id,
        name=w.name,
        description=w.description,
        scope=w.scope,
    )


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[WorkspaceOut]:
    all_ws = db.query(Workspace).order_by(Workspace.id).all()
    allowed_names = set(accessible_workspaces(user, [w.name for w in all_ws]))
    return [_to_out(w) for w in all_ws if w.name in allowed_names]


@router.get("/all", response_model=list[WorkspaceOut])
def list_all_workspaces(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability("manage_workspaces")),
) -> list[WorkspaceOut]:
    items = db.query(Workspace).order_by(Workspace.id).all()
    return [_to_out(w) for w in items]


@router.put("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: int,
    body: WorkspaceUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_capability("manage_workspaces")),
) -> WorkspaceOut:
    w = db.get(Workspace, workspace_id)
    if not w:
        raise HTTPException(status_code=404, detail="Workspace nao encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "scope" in data and data["scope"] not in {"regional", "country"}:
        raise HTTPException(status_code=400, detail="scope deve ser regional ou country.")
    for k, v in data.items():
        setattr(w, k, v)
    log_action(
        db,
        user_email=actor.email,
        action="update_workspace",
        object_type="workspace",
        object_name=w.name,
        workspace=w.name,
        details=str(data),
    )
    return _to_out(w)
