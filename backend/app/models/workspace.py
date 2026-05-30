"""Model de Workspace e enum de áreas de negócio.

Workspaces representam países + visão regional LATAM.
Business Areas representam áreas de negócio transversais.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class WorkspaceName(str, Enum):
    LATAM = "LATAM"
    BRAZIL = "Brazil"
    COLOMBIA = "Colombia"
    MEXICO = "Mexico"
    ARGENTINA = "Argentina"
    CHILE = "Chile"
    PERU = "Peru"


class BusinessArea(str, Enum):
    OPERATIONS = "Operations"
    FINANCE = "Finance"
    SUPPLIER = "Supplier"
    SALES = "Sales"
    LATAM_EXECUTIVE = "LATAM Executive"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # "regional" para LATAM (acesso restrito) ou "country".
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="country")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
