"""Model Registry — modelos ML registrados (Phase 9)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class RegisteredModel(Base):
    __tablename__ = "registered_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    model_type: Mapped[str] = mapped_column(String(32), nullable=False, default="forecast")
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    forecast_id: Mapped[int | None] = mapped_column(ForeignKey("forecasts.id"), nullable=True)
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="LATAM")
    business_area: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Staging", index=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    registered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
