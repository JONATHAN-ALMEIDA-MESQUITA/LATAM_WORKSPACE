"""Schemas Pydantic para Metric."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MetricBase(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    description: str = ""
    dataset_id: int
    workspace: str = "LATAM"
    business_area: str = ""
    formula_type: str
    formula_config: dict[str, Any] = Field(default_factory=dict)
    output_format: str = "number"  # number | currency | percent | integer
    decimals: int = 2


class MetricCreate(MetricBase):
    pass


class MetricUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    formula_type: str | None = None
    formula_config: dict[str, Any] | None = None
    output_format: str | None = None
    decimals: int | None = None
    status: str | None = None


class MetricOut(MetricBase):
    id: int
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class MetricPreviewRequest(BaseModel):
    """Para preview sob demanda (testar uma fórmula antes de salvar)."""
    dataset_id: int
    formula_type: str
    formula_config: dict[str, Any] = Field(default_factory=dict)
    filters: dict[str, Any] = Field(default_factory=dict)


class MetricPreviewResponse(BaseModel):
    value: float | None
    formatted: str
    output_format: str
    decimals: int
    rows_used: int
