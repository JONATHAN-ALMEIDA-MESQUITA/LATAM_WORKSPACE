"""Schemas Pydantic para ScheduledJob (Phase 6)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduledJobBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    job_type: str  # pipeline_run | forecast_train | alerts_evaluate
    target_id: int | None = None
    cron_expression: str = Field(min_length=9, max_length=128)
    timezone: str = "UTC"
    enabled: bool = True
    paused: bool = False


class ScheduledJobCreate(ScheduledJobBase):
    pass


class ScheduledJobUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    job_type: str | None = None
    target_id: int | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    paused: bool | None = None


class ScheduledJobOut(ScheduledJobBase):
    id: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    next_run_at: datetime | None = None
    run_count: int = 0
    source_pipeline_id: int | None = None
    target_name: str | None = None


class ScheduledJobRunOut(BaseModel):
    id: int
    job_id: int
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    result_summary: dict[str, Any] | None = None
    error_message: str | None = None


class SchedulerStatusOut(BaseModel):
    running: bool
    active_jobs: int
    next_runs: list[dict[str, Any]]
