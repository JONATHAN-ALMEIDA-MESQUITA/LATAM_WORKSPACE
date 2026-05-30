"""Seed Phase 9 — lineage, quality, model registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.dataset import Dataset
from app.models.forecast import Forecast
from app.models.model_registry import RegisteredModel
from app.services.lineage_service import rebuild_lineage_from_entities
from app.services.quality_engine import persist_quality_report
from database import SessionLocal, init_db

DEFAULT_OWNER = "admin@latam.com"


def main() -> None:
    init_db()
    session = SessionLocal()
    try:
        edges = rebuild_lineage_from_entities(session)
        print(f"  lineage edges ensured: {edges}")

        sales = session.query(Dataset).filter(Dataset.name == "sales_latam").first()
        if sales:
            try:
                q = persist_quality_report(session, sales)
                session.commit()
                print(f"  quality score sales_latam: {q.score}")
            except Exception as exc:
                print(f"  quality skip: {exc}")

        forecasts = session.query(Forecast).limit(3).all()
        for f in forecasts:
            existing = (
                session.query(RegisteredModel)
                .filter(RegisteredModel.forecast_id == f.id)
                .first()
            )
            if existing:
                continue
            metrics = {}
            try:
                metrics = json.loads(f.last_metrics or "{}")
            except json.JSONDecodeError:
                pass
            session.add(
                RegisteredModel(
                    name=f.name[:80],
                    version="1.0.0",
                    model_type="forecast",
                    algorithm=f.algorithm,
                    forecast_id=f.id,
                    workspace=f.workspace,
                    business_area=f.business_area,
                    status="Production" if f.status == "Published" else "Staging",
                    metrics_json=json.dumps(metrics, default=str),
                    description=f"Auto-registered from forecast #{f.id}",
                    registered_by=DEFAULT_OWNER,
                )
            )
        session.commit()
        count = session.query(RegisteredModel).count()
        print(f"Seed Phase 9 OK — {count} model(s) in registry.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
