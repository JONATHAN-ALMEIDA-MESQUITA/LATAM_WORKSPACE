"""Schemas Pydantic para Forecast + ForecastRun (Phase 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ForecastBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    source_dataset_id: int
    target_column: str
    date_column: str
    frequency: str = "M"  # D|W|M|Q|Y
    group_by: list[str] = Field(default_factory=list)
    aggregation: str = "sum"  # sum|mean
    algorithm: str = "holt_winters"  # naive_seasonal|linear_trend|holt_winters
    algorithm_params: dict[str, Any] = Field(default_factory=dict)
    horizon: int = Field(default=12, ge=1, le=120)
    holdout_periods: int = Field(default=6, ge=0, le=60)
    filters: dict[str, Any] = Field(default_factory=dict)


class ForecastCreate(ForecastBase):
    pass


class ForecastUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    source_dataset_id: int | None = None
    target_column: str | None = None
    date_column: str | None = None
    frequency: str | None = None
    group_by: list[str] | None = None
    aggregation: str | None = None
    algorithm: str | None = None
    algorithm_params: dict[str, Any] | None = None
    horizon: int | None = None
    holdout_periods: int | None = None
    filters: dict[str, Any] | None = None


class ForecastOut(ForecastBase):
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
    last_metrics: dict[str, Any] | None = None
    output_dataset_id: int | None = None


class ForecastSummary(BaseModel):
    id: int
    name: str
    description: str
    workspace: str
    business_area: str
    algorithm: str
    horizon: int
    frequency: str
    status: str
    created_by: str
    updated_at: datetime
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    last_metrics: dict[str, Any] | None = None
    output_dataset_id: int | None = None


class ForecastRunOut(BaseModel):
    id: int
    forecast_id: int
    triggered_by: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: int | None = None
    rows_in: int | None = None
    rows_forecast: int | None = None
    groups_count: int | None = None
    metrics: dict[str, Any] | None = None
    error_message: str | None = None
    output_dataset_id: int | None = None


# Resultado in-memory de um train (nao persiste)
class ForecastPointOut(BaseModel):
    ds: str
    y: float | None = None
    yhat: float | None = None
    yhat_lower: float | None = None
    yhat_upper: float | None = None
    is_forecast: bool = False
    group_key: str | None = None


class ForecastTrainResponse(BaseModel):
    forecast_id: int
    rows_in: int
    rows_forecast: int
    groups_count: int
    points: list[ForecastPointOut]
    metrics: dict[str, Any]  # {grupo: {mae, rmse, mape}}
    notes: str = ""


class PublishActionRequest(BaseModel):
    note: str = ""
