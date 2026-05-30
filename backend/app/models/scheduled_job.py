"""Models do Scheduler (Phase 6).

ScheduledJob: agendamento cron para executar pipeline, forecast ou alertas.
ScheduledJobRun: historico de execucoes do scheduler.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class JobType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    FORECAST_TRAIN = "forecast_train"
    ALERTS_EVALUATE = "alerts_evaluate"


class JobRunStatus(str, Enum):
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"
    SKIPPED = "Skipped"


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    job_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # pipeline_id ou forecast_id (null para alerts_evaluate)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    # Cron 5 campos: "min hour dom month dow" ex: "0 6 * * *"
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Se veio de pipeline.schedule_cron sync
    source_pipeline_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    runs: Mapped[list["ScheduledJobRun"]] = relationship(
        "ScheduledJobRun",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="desc(ScheduledJobRun.started_at)",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "job_type": self.job_type,
            "target_id": self.target_id,
            "cron_expression": self.cron_expression,
            "timezone": self.timezone,
            "enabled": self.enabled,
            "paused": self.paused,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "run_count": self.run_count,
            "source_pipeline_id": self.source_pipeline_id,
        }


class ScheduledJobRun(Base):
    __tablename__ = "scheduled_job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("scheduled_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="scheduler")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=JobRunStatus.RUNNING.value
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped["ScheduledJob"] = relationship("ScheduledJob", back_populates="runs")

    def result_dict(self) -> dict | None:
        if not self.result_summary:
            return None
        try:
            return json.loads(self.result_summary)
        except json.JSONDecodeError:
            return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "triggered_by": self.triggered_by,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "result_summary": self.result_dict(),
            "error_message": self.error_message,
        }
