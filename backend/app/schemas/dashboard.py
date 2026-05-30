"""Schemas Pydantic para Dashboard + Widget."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# -------- Widget --------

class WidgetLayout(BaseModel):
    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 4


class WidgetBase(BaseModel):
    title: str = ""
    widget_type: str  # kpi_card | bar_chart | line_chart | area_chart | pie_chart | donut_chart | table | text_box
    layout: WidgetLayout = Field(default_factory=WidgetLayout)
    config: dict[str, Any] = Field(default_factory=dict)


class WidgetCreate(WidgetBase):
    pass


class WidgetUpdate(BaseModel):
    title: str | None = None
    widget_type: str | None = None
    layout: WidgetLayout | None = None
    config: dict[str, Any] | None = None


class WidgetOut(WidgetBase):
    id: int
    dashboard_id: int
    created_at: datetime
    updated_at: datetime


# -------- Dashboard --------

class DashboardBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    theme: str = "Executive Light"


class DashboardCreate(DashboardBase):
    pass


class DashboardUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    theme: str | None = None


class DashboardSummary(BaseModel):
    id: int
    name: str
    description: str
    workspace: str
    business_area: str
    status: str
    theme: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    widget_count: int = 0


class DashboardOut(DashboardSummary):
    submitted_by: str | None = None
    submitted_at: datetime | None = None
    published_by: str | None = None
    published_at: datetime | None = None
    archived_by: str | None = None
    archived_at: datetime | None = None
    widgets: list[WidgetOut] = Field(default_factory=list)


# -------- Widget preview (renderiza dados) --------

class WidgetPreviewRequest(BaseModel):
    """Permite testar um widget antes de salvá-lo no dashboard."""
    widget_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class WidgetPreviewSeries(BaseModel):
    """Um ponto/série retornado para o frontend renderizar com Plotly."""
    label: str
    values: list[float | int | None]
    categories: list[str | float | int]


class WidgetPreviewResponse(BaseModel):
    widget_type: str
    title: str
    # Para KPI: value + delta + format. Para charts: series + categories. Para table: rows + columns.
    kpi: dict[str, Any] | None = None
    chart: dict[str, Any] | None = None
    table: dict[str, Any] | None = None
    text: str | None = None
    rows_used: int = 0
    notes: str = ""
    # Preenchidos só quando renderizando um dashboard inteiro (lista de widgets).
    widget_id: int | None = None
    layout: dict[str, Any] | None = None


# -------- Publish flow --------

class PublishActionRequest(BaseModel):
    """Comentário opcional ao mudar status."""
    comment: str = ""
