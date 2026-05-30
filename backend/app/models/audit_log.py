"""Model de Audit Log - registra ações importantes da plataforma."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    object_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    object_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    business_area: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def to_dict(self) -> dict:
        return {
            "log_id": self.id,
            "user_email": self.user_email,
            "action": self.action,
            "object_type": self.object_type,
            "object_name": self.object_name,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "details": self.details,
        }
