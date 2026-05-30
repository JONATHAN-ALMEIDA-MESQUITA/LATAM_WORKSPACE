"""Model de usuário e enum de roles.

Roles centralizadas - usadas pelo permission_service para RBAC.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Role(str, Enum):
    PLATFORM_ADMIN = "Platform Admin"
    DATA_DEVELOPER = "Data Developer"
    DATA_ANALYST = "Data Analyst"
    FINANCE_OWNER = "Finance Owner"
    OPERATIONS_OWNER = "Operations Owner"
    LATAM_EXECUTIVE_VIEWER = "LATAM Executive Viewer"
    VIEWER = "Viewer"
    ML_OWNER = "ML Owner"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    # Workspace "home" do usuário (ex.: "Brazil" para analyst.br). LATAM = acesso regional.
    home_workspace: Mapped[str] = mapped_column(String(64), nullable=False, default="LATAM")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "home_workspace": self.home_workspace,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
