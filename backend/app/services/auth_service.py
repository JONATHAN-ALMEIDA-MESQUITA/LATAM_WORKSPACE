"""Autenticação SIMULADA - apenas para a demo.

Não há senha real. O usuário escolhe um perfil na tela de login e o backend
emite um token "fake" no formato `demo-token::<email>` que é usado nas
próximas requisições como Authorization: Bearer.

Em produção: substituir por OAuth/OIDC + JWT.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from config import settings
from database import get_db


def create_demo_token(email: str) -> str:
    return f"{settings.demo_token_prefix}{email.lower()}"


def parse_demo_token(token: str) -> str | None:
    if not token.startswith(settings.demo_token_prefix):
        return None
    return token[len(settings.demo_token_prefix):]


def authenticate(db: Session, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower()).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou inativo.",
        )
    return user


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """Dependency do FastAPI - extrai User a partir do header Authorization."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente.",
        )
    token = authorization.split(" ", 1)[1].strip()
    email = parse_demo_token(token)
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inválido.",
        )
    return user


def require_capability(capability: str):
    """Factory de dependency que exige uma capability específica."""
    from app.services.permission_service import has_capability

    def _checker(user: User = Depends(get_current_user)) -> User:
        if not has_capability(user, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão necessária: {capability}",
            )
        return user

    return _checker
