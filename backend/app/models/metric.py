"""Model de Metric - camada semântica reutilizável.

Uma métrica é uma definição formal de cálculo sobre um dataset.
Ela vive em um workspace + business_area, e tem status (Draft/Certified/etc).

Tipos suportados (formula_type):
    SUM, AVERAGE, COUNT, MIN, MAX
    RATIO          - column_a / column_b (somados)
    VARIATION_ABS  - actual - baseline (duas colunas ou duas métricas)
    VARIATION_PCT  - (actual - baseline) / baseline
    MTD, YTD, YOY  - métricas temporais (delta vs período anterior)
    CUSTOM_LIMITED - DSL controlada (SUM/DIVIDE/SUB/ADD apenas)
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MetricStatus(str, Enum):
    DRAFT = "Draft"
    CERTIFIED = "Certified"
    PUBLISHED = "Published"
    DEPRECATED = "Deprecated"


class MetricFormulaType(str, Enum):
    SUM = "SUM"
    AVERAGE = "AVERAGE"
    COUNT = "COUNT"
    MIN = "MIN"
    MAX = "MAX"
    RATIO = "RATIO"
    VARIATION_ABS = "VARIATION_ABS"
    VARIATION_PCT = "VARIATION_PCT"
    MTD = "MTD"
    YTD = "YTD"
    YOY = "YOY"
    CUSTOM_LIMITED = "CUSTOM_LIMITED"


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    formula_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # Config JSON livre conforme o type:
    #   SUM/AVG/MIN/MAX/COUNT: {"column": "revenue"}
    #   RATIO:                  {"numerator": "margin", "denominator": "revenue"}
    #   VARIATION_*:            {"actual": "actual", "baseline": "budget"}
    #   MTD/YTD/YOY:            {"column": "revenue", "date_column": "date"}
    #   CUSTOM_LIMITED:         {"formula": "SUM(revenue) - SUM(cost)"}
    formula_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # "currency", "percent", "number" ou "integer" - para formatação no front.
    output_format: Mapped[str] = mapped_column(String(32), nullable=False, default="number")
    # Casas decimais para display.
    decimals: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=MetricStatus.DRAFT.value, index=True
    )

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    def config_dict(self) -> dict:
        try:
            return json.loads(self.formula_config or "{}")
        except json.JSONDecodeError:
            return {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "dataset_id": self.dataset_id,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "formula_type": self.formula_type,
            "formula_config": self.config_dict(),
            "output_format": self.output_format,
            "decimals": self.decimals,
            "status": self.status,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
