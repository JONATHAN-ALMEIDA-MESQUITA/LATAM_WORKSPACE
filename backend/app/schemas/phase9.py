"""Schemas Phase 9 — Lineage, Quality, Model Registry."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LineageNode(BaseModel):
    id: int
    name: str
    source_type: str
    workspace: str


class LineageEdgeOut(BaseModel):
    from_dataset_id: int | None
    to_dataset_id: int
    relation_type: str
    entity_type: str
    entity_id: int | None
    entity_name: str


class DatasetLineageOut(BaseModel):
    dataset_id: int
    dataset_name: str
    upstream: list[LineageNode]
    downstream: list[LineageNode]
    edges: list[LineageEdgeOut]


class QualityCheckResult(BaseModel):
    name: str
    column: str | None = None
    passed: bool
    severity: str = "warning"
    message: str
    value: Any = None


class DatasetQualityOut(BaseModel):
    dataset_id: int
    score: float
    checks: list[QualityCheckResult]
    run_at: datetime | None = None


class RegisteredModelOut(BaseModel):
    id: int
    name: str
    version: str
    model_type: str
    algorithm: str
    forecast_id: int | None
    workspace: str
    business_area: str
    status: str
    metrics: dict[str, Any]
    description: str
    registered_by: str
    registered_at: datetime


class RegisteredModelCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    version: str = "1.0.0"
    model_type: str = "forecast"
    algorithm: str = ""
    forecast_id: int | None = None
    workspace: str = "LATAM"
    business_area: str = ""
    status: str = "Staging"
    description: str = ""


class RegisteredModelUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    status: str | None = None
    description: str | None = None
