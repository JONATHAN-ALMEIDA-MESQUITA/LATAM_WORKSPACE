"""Models Ad-Hoc Report Builder (Phase 7).

SavedReport: definicao SQL salva pelo usuario (dataset + query).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SavedReport(Base):
    __tablename__ = "saved_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    source_dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    sql_query: Mapped[str] = mapped_column(Text, nullable=False)

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "source_dataset_id": self.source_dataset_id,
            "sql_query": self.sql_query,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
        }
