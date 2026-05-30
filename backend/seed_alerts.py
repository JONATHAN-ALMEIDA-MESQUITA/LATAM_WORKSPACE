"""Seed de alertas de exemplo (Phase 5 - Alerts & Notifications).

Cria 6 alertas representativos cobrindo os 5 tipos:

1. METRIC_THRESHOLD  : Revenue YTD abaixo de 5M USD (warning)
2. METRIC_THRESHOLD  : Margin % abaixo de 25% (critical)
3. METRIC_CHANGE     : Revenue MTD caiu mais que 10% vs mes anterior (warning)
4. FORECAST_QUALITY  : MAPE de qualquer pais > 25% (warning)
5. PIPELINE_FAILURE  : Pipeline Sales Brazil falhou (critical)
6. DASHBOARD_STALE   : Sales LATAM Overview sem atualizacao ha >7 dias (info)

Idempotente: skip se ja existir alerta com o mesmo nome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.dashboard import Dashboard
from app.models.forecast import Forecast
from app.models.metric import Metric
from app.models.pipeline import Pipeline
from app.models.user import User
from database import SessionLocal, init_db

DEFAULT_OWNER = "admin@latam.com"


def _ensure_alert(session, **kwargs) -> Alert | None:
    name = kwargs["name"]
    existing = session.query(Alert).filter(Alert.name == name).first()
    if existing:
        return existing
    a = Alert(**kwargs)
    session.add(a)
    session.flush()
    return a


def _metric_id(session, name: str) -> int | None:
    m = session.query(Metric).filter(Metric.name == name).first()
    return m.id if m else None


def _forecast_id(session, name: str) -> int | None:
    f = session.query(Forecast).filter(Forecast.name == name).first()
    return f.id if f else None


def _pipeline_id(session, name: str) -> int | None:
    p = session.query(Pipeline).filter(Pipeline.name == name).first()
    return p.id if p else None


def _dashboard_id(session, name: str) -> int | None:
    d = session.query(Dashboard).filter(Dashboard.name == name).first()
    return d.id if d else None


def run() -> None:
    init_db()
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.email == DEFAULT_OWNER).first()
        if not admin:
            print(f"[!] Usuario {DEFAULT_OWNER} nao encontrado. Rode seed.py antes.")
            return

        configs = [
            {
                "name": "Revenue YTD abaixo de 5M USD",
                "description": "Alerta de receita LATAM acumulada no ano abaixo do esperado.",
                "workspace": "LATAM",
                "business_area": "Sales",
                "alert_type": AlertType.METRIC_THRESHOLD.value,
                "severity": AlertSeverity.WARNING.value,
                "target_kind": "metric",
                "target_id": _metric_id(session, "Revenue YTD"),
                "rule_config": {"operator": "<", "threshold": 5_000_000, "period": "all"},
            },
            {
                "name": "Margin % abaixo de 25%",
                "description": "Margem LATAM Finance caiu abaixo do piso saudavel.",
                "workspace": "LATAM",
                "business_area": "Finance",
                "alert_type": AlertType.METRIC_THRESHOLD.value,
                "severity": AlertSeverity.CRITICAL.value,
                "target_kind": "metric",
                "target_id": _metric_id(session, "Margin %"),
                "rule_config": {"operator": "<", "threshold": 0.25, "period": "all"},
            },
            {
                "name": "Revenue MTD caiu >10% vs mes anterior",
                "description": "Variacao significativa de queda de receita em relacao ao mes passado.",
                "workspace": "LATAM",
                "business_area": "Sales",
                "alert_type": AlertType.METRIC_CHANGE.value,
                "severity": AlertSeverity.WARNING.value,
                "target_kind": "metric",
                "target_id": _metric_id(session, "Revenue (USD)"),
                "rule_config": {
                    "change_pct_threshold": 10.0,
                    "direction": "drop",
                    "current_period": "mtd",
                    "previous_period": "prev_month",
                    "date_column": "date",
                },
            },
            {
                "name": "Forecast por pais com MAPE > 25%",
                "description": "Qualidade do forecast por pais piorando (algum pais > 25% de erro).",
                "workspace": "LATAM",
                "business_area": "Sales",
                "alert_type": AlertType.FORECAST_QUALITY.value,
                "severity": AlertSeverity.WARNING.value,
                "target_kind": "forecast",
                "target_id": _forecast_id(session, "Revenue Forecast by Country (Linear Trend)"),
                "rule_config": {"mape_threshold": 25.0, "scope": "any"},
            },
            {
                "name": "Pipeline Sales Brazil falhou",
                "description": "Disparado quando o run mais recente do pipeline esta em FAILED.",
                "workspace": "LATAM",
                "business_area": "Sales",
                "alert_type": AlertType.PIPELINE_FAILURE.value,
                "severity": AlertSeverity.CRITICAL.value,
                "target_kind": "pipeline",
                "target_id": _pipeline_id(session, "Sales Brazil - High-margin Top Clients"),
                "rule_config": {"lookback_minutes": 1440},  # 24h
            },
            {
                "name": "Dashboard Sales LATAM sem atualizacao >7d",
                "description": "Alerta para revisar dashboards estagnados.",
                "workspace": "LATAM",
                "business_area": "Sales",
                "alert_type": AlertType.DASHBOARD_STALE.value,
                "severity": AlertSeverity.INFO.value,
                "target_kind": "dashboard",
                "target_id": _dashboard_id(session, "Sales LATAM Overview"),
                "rule_config": {"max_age_days": 7},
            },
        ]

        created: list[str] = []
        skipped: list[str] = []
        for cfg in configs:
            if not cfg["target_id"]:
                print(f"  [skip] target nao encontrado para '{cfg['name']}'")
                continue
            existing = session.query(Alert).filter(Alert.name == cfg["name"]).first()
            if existing:
                skipped.append(cfg["name"])
                continue
            a = Alert(
                name=cfg["name"],
                description=cfg["description"],
                workspace=cfg["workspace"],
                business_area=cfg["business_area"],
                alert_type=cfg["alert_type"],
                severity=cfg["severity"],
                target_id=cfg["target_id"],
                target_kind=cfg["target_kind"],
                rule_config=json.dumps(cfg["rule_config"]),
                channels=json.dumps(["in_app", "email"]),
                recipients=json.dumps([DEFAULT_OWNER]),
                enabled=True,
                cooldown_minutes=60,
                created_by=DEFAULT_OWNER,
            )
            session.add(a)
            session.flush()
            created.append(cfg["name"])

        session.commit()
        print("Alertas:")
        for n in created:
            print(f"  [+] {n}")
        for n in skipped:
            print(f"  [=] {n} (ja existia)")
        print(f"Total: {len(created)} criados / {len(skipped)} ja existentes")
    finally:
        session.close()


if __name__ == "__main__":
    run()
