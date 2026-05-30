"""Router de autenticação simulada.

POST /auth/login   -> recebe email, devolve token + user + permissions + menu.
GET  /auth/me     -> retorna o usuário atual (com permissions e menu).
GET  /auth/users-demo -> retorna lista de usuários disponíveis para a tela de login.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.services.audit_service import log_action
from app.services.auth_service import (
    authenticate,
    create_demo_token,
    get_current_user,
)
from app.services.permission_service import build_user_menu, build_user_permissions
from database import get_db


router = APIRouter(prefix="/auth", tags=["auth"])


def _to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        home_workspace=user.home_workspace,
        is_active=user.is_active,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = authenticate(db, payload.email)
    token = create_demo_token(user.email)
    log_action(
        db,
        user_email=user.email,
        action="login",
        object_type="user",
        object_name=user.email,
        details=f"role={user.role}",
    )
    return LoginResponse(
        token=token,
        user=_to_user_out(user),
        permissions=build_user_permissions(user),
        menu=build_user_menu(user),
    )


@router.get("/me", response_model=LoginResponse)
def me(user: User = Depends(get_current_user)) -> LoginResponse:
    return LoginResponse(
        token=create_demo_token(user.email),
        user=_to_user_out(user),
        permissions=build_user_permissions(user),
        menu=build_user_menu(user),
    )


@router.get("/users-demo")
def list_demo_users(db: Session = Depends(get_db)) -> list[dict]:
    """Lista os usuários disponíveis para login simulado (somente para a demo!).

    Em produção esse endpoint NÃO existiria.
    """
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "home_workspace": u.home_workspace,
        }
        for u in users
    ]
