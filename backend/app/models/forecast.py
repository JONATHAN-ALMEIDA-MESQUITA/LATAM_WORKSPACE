"""Models do Forecasting Studio (Phase 4).

Forecast: configuracao de um modelo preditivo sobre um dataset.
ForecastRun: registro de execucao (treino + backtest + projecao).

Workflow:
    Draft -> Published -> Archived
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ForecastStatus(str, Enum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    ARCHIVED = "Archived"


class ForecastAlgorithm(str, Enum):
    NAIVE_SEASONAL = "naive_seasonal"
    LINEAR_TREND = "linear_trend"
    HOLT_WINTERS = "holt_winters"


class ForecastFrequency(str, Enum):
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    YEARLY = "Y"


class ForecastRunStatus(str, Enum):
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"


class Forecast(Base):
    __tablename__ = "forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    # Configuracao
    source_dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id"), nullable=False, index=True
    )
    target_column: Mapped[str] = mapped_column(String(128), nullable=False)
    date_column: Mapped[str] = mapped_column(String(128), nullable=False)
    frequency: Mapped[str] = mapped_column(
        String(8), nullable=False, default=ForecastFrequency.MONTHLY.value
    )
    # Coluna(s) para agrupar (forecasts separados por grupo). JSON list[str].
    group_by: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # Funcao de agregacao quando ha multiplas linhas por data (sum/mean)
    aggregation: Mapped[str] = mapped_column(String(16), nullable=False, default="sum")

    algorithm: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ForecastAlgorithm.HOLT_WINTERS.value
    )
    # Parametros especificos do algoritmo (JSON)
    algorithm_params: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    horizon: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    # Quantos periodos usar como holdout para backtest
    holdout_periods: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    # Filtros opcionais (mesmo formato que pipeline_engine filters)
    filters: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ForecastStatus.DRAFT.value, index=True
    )

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Ultimas metricas (MAE/RMSE/MAPE) calculadas (JSON {grupo: {metric: val}})
    last_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Dataset gerado pela ultima publicacao (id)
    output_dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    runs: Mapped[list["ForecastRun"]] = relationship(
        "ForecastRun",
        back_populates="forecast",
        cascade="all, delete-orphan",
        order_by="desc(ForecastRun.started_at)",
    )

    def group_by_list(self) -> list[str]:
        try:
            v = json.loads(self.group_by or "[]")
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return []

    def algorithm_params_dict(self) -> dict:
        try:
            return json.loads(self.algorithm_params or "{}")
        except json.JSONDecodeError:
            return {}

    def filters_dict(self) -> dict:
        try:
            return json.loads(self.filters or "{}")
        except json.JSONDecodeError:
            return {}

    def last_metrics_dict(self) -> dict | None:
        if not self.last_metrics:
            return None
        try:
            return json.loads(self.last_metrics)
        except json.JSONDecodeError:
            return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "source_dataset_id": self.source_dataset_id,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "frequency": self.frequency,
            "group_by": self.group_by_list(),
            "aggregation": self.aggregation,
            "algorithm": self.algorithm,
            "algorithm_params": self.algorithm_params_dict(),
            "horizon": self.horizon,
            "holdout_periods": self.holdout_periods,
            "filters": self.filters_dict(),
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "published_by": self.published_by,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "archived_by": self.archived_by,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "last_run_status": self.last_run_status,
            "last_metrics": self.last_metrics_dict(),
            "output_dataset_id": self.output_dataset_id,
        }


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    forecast_id: Mapped[int] = mapped_column(
        ForeignKey("forecasts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    triggered_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ForecastRunStatus.RUNNING.value
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rows_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_forecast: Mapped[int | None] = mapped_column(Integer, nullable=True)
    groups_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # JSON {grupo: {mae, rmse, mape}}
    metrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    forecast: Mapped["Forecast"] = relationship("Forecast", back_populates="runs")

    def metrics_dict(self) -> dict | None:
        if not self.metrics:
            return None
        try:
            return json.loads(self.metrics)
        except json.JSONDecodeError:
            return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "forecast_id": self.forecast_id,
            "triggered_by": self.triggered_by,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "rows_in": self.rows_in,
            "rows_forecast": self.rows_forecast,
            "groups_count": self.groups_count,
            "metrics": self.metrics_dict(),
            "error_message": self.error_message,
            "output_dataset_id": self.output_dataset_id,
        }
