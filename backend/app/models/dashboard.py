"""Models de Dashboard + DashboardWidget.

Dashboard: collection de widgets + metadata (workspace, area, status, owner).
Widget: KPI / Bar / Line / Area / Pie / Donut / Table / TextBox / Slicer.

Layout do widget é JSON {x, y, w, h} compatível com react-grid-layout (12 colunas).
Config do widget é JSON: dataset_id, metric_id ou metric_inline, dimension, filters, sort, limit, style.

Workflow de publicação:
    Draft -> Pending Approval -> Published -> Archived
    Draft -> Archived (descartar)
    Published -> Archived
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class DashboardStatus(str, Enum):
    DRAFT = "Draft"
    PENDING_APPROVAL = "Pending Approval"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"
    DEPRECATED = "Deprecated"


class WidgetType(str, Enum):
    KPI_CARD = "kpi_card"
    BAR_CHART = "bar_chart"
    LINE_CHART = "line_chart"
    AREA_CHART = "area_chart"
    PIE_CHART = "pie_chart"
    DONUT_CHART = "donut_chart"
    TABLE = "table"
    TEXT_BOX = "text_box"


class Dashboard(Base):
    __tablename__ = "dashboards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DashboardStatus.DRAFT.value, index=True
    )
    theme: Mapped[str] = mapped_column(String(64), nullable=False, default="Executive Light")

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    submitted_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    widgets: Mapped[list["DashboardWidget"]] = relationship(
        "DashboardWidget",
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardWidget.created_at",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "status": self.status,
            "theme": self.theme,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "submitted_by": self.submitted_by,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "published_by": self.published_by,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "archived_by": self.archived_by,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }


class DashboardWidget(Base):
    __tablename__ = "dashboard_widgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dashboard_id: Mapped[int] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    widget_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Layout React Grid (12 cols): {"x": 0, "y": 0, "w": 6, "h": 4}
    layout: Mapped[str] = mapped_column(Text, nullable=False, default='{"x":0,"y":0,"w":6,"h":4}')
    # Config completo: {dataset_id, metric_id, metric_inline, dimension, time_grain,
    #                   filters, sort, limit, style, text_content}
    config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    dashboard: Mapped["Dashboard"] = relationship("Dashboard", back_populates="widgets")

    def layout_dict(self) -> dict:
        try:
            return json.loads(self.layout or "{}")
        except json.JSONDecodeError:
            return {"x": 0, "y": 0, "w": 6, "h": 4}

    def config_dict(self) -> dict:
        try:
            return json.loads(self.config or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "dashboard_id": self.dashboard_id,
            "title": self.title,
            "widget_type": self.widget_type,
            "layout": self.layout_dict(),
            "config": self.config_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
