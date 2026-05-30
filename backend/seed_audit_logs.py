"""Seed de audit logs de exemplo (Phase 8).

Popula trilha de auditoria se houver poucos registros (demo Admin panel).
Idempotente: skip se ja existirem >= 10 logs.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.audit_log import AuditLog
from database import SessionLocal, init_db

SAMPLES = [
    ("admin@latam.com", "login", "user", "admin@latam.com", "LATAM", "", "Demo login"),
    ("data.dev@latam.com", "run_pipeline", "pipeline", "Sales Brazil ETL", "LATAM", "Sales", "status=Success duration=842ms"),
    ("admin@latam.com", "publish_dashboard", "dashboard", "Sales LATAM Overview", "LATAM", "Sales", "Draft -> Published"),
    ("finance.owner@latam.com", "create_metric", "metric", "Revenue YTD", "LATAM", "Finance", "formula_type=SUM"),
    ("ml.owner@latam.com", "train_forecast", "forecast", "Revenue LATAM Holt-Winters", "LATAM", "Sales", "mape=0.12"),
    ("admin@latam.com", "create_alert", "alert", "Revenue YTD abaixo de 5M", "LATAM", "Finance", "type=metric_threshold"),
    ("data.dev@latam.com", "create_scheduled_job", "scheduled_job", "Pipeline Daily BR", "LATAM", "Sales", "cron=0 6 * * *"),
    ("admin@latam.com", "report_save_dataset", "dataset", "report_revenue_by_tier", "LATAM", "Sales", "rows=24"),
    ("analyst.br@latam.com", "upload_dataset", "dataset", "upload_br_q1.csv", "Brazil", "Sales", "rows=1200"),
    ("admin@latam.com", "update_user", "user", "viewer.br@latam.com", "Brazil", "", "role=Viewer is_active=True"),
    ("admin@latam.com", "evaluate_alerts", "alert", "batch LATAM", "LATAM", "", "fired=2 evaluated=6"),
    ("operations.owner@latam.com", "publish_dashboard", "dashboard", "Ops KPI Board", "LATAM", "Operations", "Pending -> Published"),
]


def main() -> None:
    init_db()
    session = SessionLocal()
    try:
        count = session.query(AuditLog).count()
        if count >= 10:
            print(f"Seed audit logs OK — {count} registros (skip).")
            return
        base = datetime.utcnow() - timedelta(days=7)
        for i, (email, action, obj_type, obj_name, ws, area, details) in enumerate(SAMPLES):
            session.add(
                AuditLog(
                    user_email=email,
                    action=action,
                    object_type=obj_type,
                    object_name=obj_name,
                    workspace=ws,
                    business_area=area,
                    details=details,
                    timestamp=base + timedelta(hours=i * 5),
                )
            )
        session.commit()
        total = session.query(AuditLog).count()
        print(f"Seed audit logs OK — {total} registros no banco.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
