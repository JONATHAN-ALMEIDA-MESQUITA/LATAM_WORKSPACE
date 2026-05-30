"""Seed de forecasts de exemplo (Phase 4 - Forecasting Studio).

Cria 3 forecasts representativos demonstrando os 3 algoritmos:

1. "LATAM Revenue Forecast 6M" (LATAM/Sales, Holt-Winters, global)
   sales_latam -> sum(revenue) por mes -> Holt-Winters -> horizon=6

2. "Revenue Forecast by Country" (LATAM/Sales, Linear Trend, group_by=country)
   sales_latam -> sum(revenue) por mes por pais -> LinearRegression -> horizon=6

3. "Finance Actual Forecast Baseline" (LATAM/Finance, Naive Seasonal, group_by=country)
   finance_actual_budget -> sum(actual) -> Naive Seasonal -> horizon=12

Idempotente: skip se ja existir um forecast com o mesmo nome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.dataset import Dataset
from app.models.forecast import (
    Forecast,
    ForecastAlgorithm,
    ForecastFrequency,
    ForecastStatus,
)
from app.models.user import User
from database import SessionLocal, init_db

DEFAULT_OWNER = "admin@latam.com"


def _get_dataset(session, name: str) -> Dataset | None:
    return session.query(Dataset).filter(Dataset.name == name).first()


def _ensure_forecast(
    session,
    *,
    name: str,
    description: str,
    workspace: str,
    business_area: str,
    dataset_name: str,
    target_column: str,
    date_column: str,
    algorithm: str,
    horizon: int,
    holdout_periods: int,
    frequency: str = ForecastFrequency.MONTHLY.value,
    group_by: list[str] | None = None,
    aggregation: str = "sum",
    algorithm_params: dict | None = None,
    filters: dict | None = None,
) -> Forecast | None:
    existing = session.query(Forecast).filter(Forecast.name == name).first()
    if existing:
        return existing
    ds = _get_dataset(session, dataset_name)
    if not ds:
        print(f"  [skip] dataset '{dataset_name}' nao encontrado")
        return None
    f = Forecast(
        name=name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        source_dataset_id=ds.id,
        target_column=target_column,
        date_column=date_column,
        frequency=frequency,
        group_by=json.dumps(group_by or []),
        aggregation=aggregation,
        algorithm=algorithm,
        algorithm_params=json.dumps(algorithm_params or {}),
        horizon=horizon,
        holdout_periods=holdout_periods,
        filters=json.dumps(filters or {}),
        status=ForecastStatus.DRAFT.value,
        created_by=DEFAULT_OWNER,
    )
    session.add(f)
    session.flush()
    return f


def run() -> None:
    init_db()
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.email == DEFAULT_OWNER).first()
        if not admin:
            print(f"[!] Usuario {DEFAULT_OWNER} nao encontrado. Rode seed.py antes.")
            return

        created: list[str] = []
        skipped: list[str] = []

        f1 = _ensure_forecast(
            session,
            name="LATAM Revenue Forecast (Holt-Winters)",
            description="Previsao de receita LATAM agregada mensalmente, 6 meses a frente.",
            workspace="LATAM",
            business_area="Sales",
            dataset_name="sales_latam",
            target_column="revenue",
            date_column="date",
            algorithm=ForecastAlgorithm.HOLT_WINTERS.value,
            horizon=6,
            holdout_periods=6,
            algorithm_params={"trend": "add", "seasonal": "add", "damped": False},
        )
        if f1 and f1.created_at == f1.updated_at:
            created.append(f1.name)
        else:
            skipped.append("LATAM Revenue Forecast (Holt-Winters)")

        f2 = _ensure_forecast(
            session,
            name="Revenue Forecast by Country (Linear Trend)",
            description="Previsao por pais usando regressao linear com sazonalidade mensal.",
            workspace="LATAM",
            business_area="Sales",
            dataset_name="sales_latam",
            target_column="revenue",
            date_column="date",
            algorithm=ForecastAlgorithm.LINEAR_TREND.value,
            horizon=6,
            holdout_periods=6,
            group_by=["country"],
        )
        if f2 and f2.created_at == f2.updated_at:
            created.append(f2.name)
        else:
            skipped.append("Revenue Forecast by Country (Linear Trend)")

        f3 = _ensure_forecast(
            session,
            name="Finance Actual Forecast Baseline (Naive Seasonal)",
            description="Baseline naive sazonal sobre realizados financeiros por pais.",
            workspace="LATAM",
            business_area="Finance",
            dataset_name="finance_actual_budget",
            target_column="actual",
            date_column="date",
            algorithm=ForecastAlgorithm.NAIVE_SEASONAL.value,
            horizon=12,
            holdout_periods=6,
            group_by=["country"],
            algorithm_params={"season": 12, "lookback_cycles": 3},
        )
        if f3 and f3.created_at == f3.updated_at:
            created.append(f3.name)
        else:
            skipped.append("Finance Actual Forecast Baseline (Naive Seasonal)")

        session.commit()
        print("Forecasts criados:")
        for n in created:
            print(f"  [+] {n}")
        for n in skipped:
            print(f"  [=] {n} (ja existia)")
        print(f"Total: {len(created)} criados / {len(skipped)} ja existentes")
    finally:
        session.close()


if __name__ == "__main__":
    run()
