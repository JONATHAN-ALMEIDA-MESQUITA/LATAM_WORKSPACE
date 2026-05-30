"""Schemas Pydantic para Dataset + DatasetColumn."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetColumnOut(BaseModel):
    id: int
    position: int
    name: str
    dtype: str
    null_count: int
    distinct_count: int
    min_value: str | None = None
    max_value: str | None = None
    mean_value: float | None = None
    std_value: float | None = None
    sample_values: list[Any] = Field(default_factory=list)


class DatasetSummaryOut(BaseModel):
    """Versão compacta para listagens."""

    id: int
    name: str
    description: str
    workspace: str
    business_area: str
    source_type: str
    row_count: int
    column_count: int
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class DatasetOut(BaseModel):
    id: int
    name: str
    description: str
    workspace: str
    business_area: str
    source_type: str
    source_data_source_id: int | None = None
    original_filename: str
    file_size_bytes: int
    row_count: int
    column_count: int
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    certified_by: str | None = None
    certified_at: datetime | None = None
    columns: list[DatasetColumnOut] = Field(default_factory=list)


class DatasetPreviewOut(BaseModel):
    dataset_id: int
    name: str
    row_count: int
    column_count: int
    columns: list[str]
    rows: list[dict[str, Any]]
    truncated: bool


class DatasetCertifyRequest(BaseModel):
    status: str  # Draft | Validated | Certified | Deprecated


class GenerateSampleRequest(BaseModel):
    name: str  # sales_latam | finance_actual_budget | supplier_performance | cash_flow | commission_forecast
    workspace: str = "LATAM"
