"""Models de Dataset + DatasetColumn.

Dataset:
    - representação lógica de uma tabela disponível na plataforma
    - tem workspace, business_area, status (Draft/Validated/Certified)
    - origem: upload, sample sintético ou conexão com banco
    - persistido em parquet em storage/processed para leitura rápida

DatasetColumn:
    - cada coluna do dataset
    - tipo detectado + profiling básico (nulos, distinct, min, max, mean, std)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class DatasetStatus(str, Enum):
    DRAFT = "Draft"
    VALIDATED = "Validated"
    CERTIFIED = "Certified"
    DEPRECATED = "Deprecated"


class DatasetSourceType(str, Enum):
    UPLOAD = "Upload"
    SAMPLE = "Sample"
    CONNECTION = "Connection"
    ETL_OUTPUT = "ETL Output"
    FORECAST = "Forecast"
    REPORT_OUTPUT = "Report Output"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_data_source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    raw_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    processed_path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DatasetStatus.DRAFT.value, index=True
    )

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    certified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    certified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    columns: Mapped[list["DatasetColumn"]] = relationship(
        "DatasetColumn",
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetColumn.position",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "source_type": self.source_type,
            "source_data_source_id": self.source_data_source_id,
            "original_filename": self.original_filename,
            "file_size_bytes": self.file_size_bytes,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "certified_by": self.certified_by,
            "certified_at": self.certified_at.isoformat() if self.certified_at else None,
        }


class DatasetColumn(Base):
    __tablename__ = "dataset_columns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dtype: Mapped[str] = mapped_column(String(32), nullable=False, default="string")

    null_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    min_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    max_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mean_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    std_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_values: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    dataset: Mapped["Dataset"] = relationship("Dataset", back_populates="columns")

    def to_dict(self) -> dict:
        import json

        return {
            "id": self.id,
            "position": self.position,
            "name": self.name,
            "dtype": self.dtype,
            "null_count": self.null_count,
            "distinct_count": self.distinct_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "std_value": self.std_value,
            "sample_values": json.loads(self.sample_values or "[]"),
        }
