"""Schemas Ad-Hoc Report Builder."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExtraDatasetRef(BaseModel):
    dataset_id: int
    alias: str | None = Field(default=None, max_length=32)


class ReportPreviewRequest(BaseModel):
    dataset_id: int
    extra_datasets: list[ExtraDatasetRef] = Field(default_factory=list)
    sql: str = Field(min_length=3)
    limit: int = Field(default=200, ge=1, le=5000)


class ReportPreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    notes: str = ""
    generated_sql: str | None = None


class ReportExportRequest(BaseModel):
    dataset_id: int
    extra_datasets: list[ExtraDatasetRef] = Field(default_factory=list)
    sql: str = Field(min_length=3)
    limit: int = Field(default=10000, ge=1, le=50000)


class ReportSaveDatasetRequest(BaseModel):
    dataset_id: int
    extra_datasets: list[ExtraDatasetRef] = Field(default_factory=list)
    sql: str = Field(min_length=3)
    output_name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""


class JoinSuggestion(BaseModel):
    left: str
    right: str
    label: str = ""


class VisualColumnRef(BaseModel):
    table: str
    column: str
    alias: str | None = None


class VisualFilter(BaseModel):
    table: str
    column: str
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "starts_with"] = "eq"
    value: str = ""


class VisualMetric(BaseModel):
    table: str
    column: str
    aggregation: Literal["none", "sum", "avg", "count", "min", "max"] = "sum"
    alias: str | None = None


class VisualJoin(BaseModel):
    dataset_id: int
    alias: str | None = None
    left_column: str
    right_column: str
    join_type: Literal["inner", "left"] = "inner"


class VisualReportRequest(BaseModel):
    primary_dataset_id: int
    join: VisualJoin | None = None
    columns: list[VisualColumnRef] = Field(default_factory=list)
    filters: list[VisualFilter] = Field(default_factory=list)
    group_by: list[VisualColumnRef] = Field(default_factory=list)
    metrics: list[VisualMetric] = Field(default_factory=list)
    order_by: VisualColumnRef | None = None
    order_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=200, ge=1, le=5000)


class SavedReportBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    source_dataset_id: int
    sql_query: str = Field(min_length=3)


class SavedReportCreate(SavedReportBase):
    pass


class SavedReportUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    source_dataset_id: int | None = None
    sql_query: str | None = None


class SavedReportOut(SavedReportBase):
    id: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    source_dataset_name: str | None = None
