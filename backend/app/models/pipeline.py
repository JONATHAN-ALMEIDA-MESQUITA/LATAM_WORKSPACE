"""Models do Pipeline Studio (Phase 3b - ETL Builder).

Pipeline: sequência LINEAR de steps que transforma um ou mais datasets-fonte
em um dataset-target gravado em storage/processed/.

PipelineStep: bloco da pipeline, ordenado por order_index. Cada step recebe
o DataFrame do step anterior (ou um dataset externo no caso de SOURCE/JOIN/UNION)
e devolve um DataFrame transformado.

PipelineRun: registro de execução (status, métricas, logs).

Workflow:
    Draft -> (Run now repetido) -> Published -> Archived
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PipelineStatus(str, Enum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"


class StepType(str, Enum):
    SOURCE = "source"               # le um dataset existente
    FILTER = "filter"               # filtra rows
    SELECT = "select"               # seleciona/renomeia colunas
    COMPUTED_COLUMN = "computed"    # cria coluna via expressao
    GROUP_BY = "group_by"           # groupby + aggs
    JOIN = "join"                   # join com outro dataset
    UNION = "union"                 # concatena com outro dataset
    SORT = "sort"                   # ordena por coluna(s)
    LIMIT = "limit"                 # top N
    TARGET = "target"               # grava como Dataset


class RunStatus(str, Enum):
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"


class Pipeline(Base):
    __tablename__ = "pipelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PipelineStatus.DRAFT.value, index=True
    )
    # Cron textual (informativo na demo, sem scheduler real)
    schedule_cron: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    steps: Mapped[list["PipelineStep"]] = relationship(
        "PipelineStep",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="PipelineStep.order_index",
    )
    runs: Mapped[list["PipelineRun"]] = relationship(
        "PipelineRun",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        order_by="desc(PipelineRun.started_at)",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "status": self.status,
            "schedule_cron": self.schedule_cron,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_by": self.published_by,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "archived_by": self.archived_by,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
        }


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Config JSON especifico por tipo. Exemplos:
    #  SOURCE  : {"dataset_id": 1}
    #  FILTER  : {"conditions": [{"col": "country", "op": "==", "value": "Brazil"}]}
    #  SELECT  : {"columns": ["country", "revenue"], "rename": {"revenue": "rev"}}
    #  COMPUTED: {"new_col": "margin", "expression": "DIVIDE(SUB(revenue,cost), revenue)"}
    #  GROUP_BY: {"by": ["country"], "aggs": [{"col": "revenue", "func": "sum", "as": "rev"}]}
    #  JOIN    : {"right_dataset_id": 2, "how": "left", "left_on": "id", "right_on": "id"}
    #  UNION   : {"datasets": [2, 3]}
    #  SORT    : {"by": ["revenue"], "ascending": [False]}
    #  LIMIT   : {"n": 1000}
    #  TARGET  : {"dataset_name": "Sales Enriched", "workspace": "LATAM", "business_area": "Sales"}
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="steps")

    def config_dict(self) -> dict:
        try:
            return json.loads(self.config or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "order_index": self.order_index,
            "name": self.name,
            "step_type": self.step_type,
            "config": self.config_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_id: Mapped[int] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=RunStatus.RUNNING.value)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_step_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_step_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failed_step_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    logs: Mapped[str] = mapped_column(Text, nullable=False, default="")

    pipeline: Mapped["Pipeline"] = relationship("Pipeline", back_populates="runs")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_id": self.pipeline_id,
            "triggered_by": self.triggered_by,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "target_dataset_id": self.target_dataset_id,
            "error_message": self.error_message,
            "failed_step_index": self.failed_step_index,
            "failed_step_name": self.failed_step_name,
            "failed_step_type": self.failed_step_type,
            "logs": self.logs,
        }
