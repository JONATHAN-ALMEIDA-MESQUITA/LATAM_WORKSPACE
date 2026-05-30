"""Schemas Pydantic para Pipeline + Step + Run (Phase 3b)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# -------- Step --------

class StepBase(BaseModel):
    name: str = ""
    step_type: str  # source|filter|select|computed|group_by|join|union|sort|limit|target
    order_index: int = 0
    config: dict[str, Any] = Field(default_factory=dict)


class StepCreate(StepBase):
    pass


class StepUpdate(BaseModel):
    name: str | None = None
    step_type: str | None = None
    order_index: int | None = None
    config: dict[str, Any] | None = None


class StepOut(StepBase):
    id: int
    pipeline_id: int
    created_at: datetime
    updated_at: datetime


# -------- Pipeline --------

class PipelineBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    schedule_cron: str = ""


class PipelineCreate(PipelineBase):
    pass


class PipelineUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    schedule_cron: str | None = None


class PipelineOut(PipelineBase):
    id: int
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    published_by: str | None = None
    published_at: datetime | None = None
    archived_by: str | None = None
    archived_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    steps: list[StepOut] = Field(default_factory=list)


class PipelineSummary(PipelineBase):
    id: int
    status: str
    created_by: str
    updated_at: datetime
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    step_count: int = 0


# -------- Run --------

class RunOut(BaseModel):
    id: int
    pipeline_id: int
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    rows_in: int | None = None
    rows_out: int | None = None
    target_dataset_id: int | None = None
    error_message: str | None = None
    failed_step_index: int | None = None
    failed_step_name: str | None = None
    failed_step_type: str | None = None
    logs: str = ""


# -------- Preview --------

class PreviewRequest(BaseModel):
    """Preview do output ate um determinado step (1-indexed).

    Permite preview de pipeline 'em construcao' (steps em memoria, ainda nao salvos).
    """
    pipeline_id: int | None = None
    steps: list[StepCreate] | None = None
    up_to_index: int = Field(default=-1, description="Indice 0-based do ultimo step a executar; -1 = todos")
    sample_rows: int = Field(default=50, ge=1, le=500)


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int
    dataframe_schema: list[dict[str, Any]] = Field(default_factory=list)
    notes: str = ""


# -------- Publish actions --------

class PublishActionRequest(BaseModel):
    note: str = ""


# -------- Run trigger --------

class RunRequest(BaseModel):
    note: str = ""
