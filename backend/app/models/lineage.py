"""Model de Data Lineage (Phase 9)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class LineageEdge(Base):
    __tablename__ = "lineage_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    from_dataset_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets.id"), nullable=True, index=True
    )
    to_dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
