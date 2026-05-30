"""Router de usuários - listagem (admin) e CRUD básico (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import Role, User
from app.schemas.admin import UserCreate, UserUpdate
from app.schemas.auth import UserOut
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from database import get_db


router = APIRouter(prefix="/users", tags=["users"])

VALID_ROLES = {r.value for r in Role}


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        role=u.role,
        home_workspace=u.home_workspace,
        is_active=u.is_active,
    )


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability("manage_users")),
) -> list[UserOut]:
    users = db.query(User).order_by(User.id).all()
    return [_to_out(u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_capability("manage_users")),
) -> UserOut:
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role invalida: {body.role}")
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email ja cadastrado.")
    u = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        home_workspace=body.home_workspace,
        is_active=True,
    )
    db.add(u)
    db.flush()
    log_action(
        db,
        user_email=actor.email,
        action="create_user",
        object_type="user",
        object_name=u.email,
        workspace=u.home_workspace,
        details=f"role={u.role}",
    )
    return _to_out(u)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_capability("manage_users")),
) -> UserOut:
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Role invalida: {data['role']}")
    if u.id == actor.id and data.get("is_active") is False:
        raise HTTPException(status_code=400, detail="Nao e possivel desativar o proprio usuario.")
    for k, v in data.items():
        setattr(u, k, v)
    log_action(
        db,
        user_email=actor.email,
        action="update_user",
        object_type="user",
        object_name=u.email,
        workspace=u.home_workspace,
        details=str(data),
    )
    return _to_out(u)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _to_out(user)
