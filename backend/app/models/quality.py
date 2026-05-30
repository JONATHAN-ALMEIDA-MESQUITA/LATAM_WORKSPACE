"""Model de Data Quality (Phase 9)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DatasetQualityReport(Base):
    __tablename__ = "dataset_quality_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id"), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    checks_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
