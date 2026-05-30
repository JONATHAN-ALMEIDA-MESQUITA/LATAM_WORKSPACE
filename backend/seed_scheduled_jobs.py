"""Seed de scheduled jobs (Phase 6).

Cria jobs a partir de pipelines com schedule_cron + jobs extras:
  - 3 pipeline_run (sync dos pipelines seed)
  - 1 forecast_train (Holt-Winters LATAM)
  - 1 alerts_evaluate (LATAM, diario)

Idempotente: skip se job com mesmo name ja existir.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.forecast import Forecast
from app.models.pipeline import Pipeline
from app.models.scheduled_job import JobType, ScheduledJob
from app.models.user import User
from app.services.scheduler_service import compute_next_run
from database import SessionLocal, init_db

DEFAULT_OWNER = "admin@latam.com"


def _ensure_job(
    session,
    *,
    name: str,
    description: str,
    workspace: str,
    business_area: str,
    job_type: str,
    target_id: int | None,
    cron_expression: str,
    source_pipeline_id: int | None = None,
) -> ScheduledJob | None:
    existing = session.query(ScheduledJob).filter(ScheduledJob.name == name).first()
    if existing:
        return existing
    job = ScheduledJob(
        name=name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        job_type=job_type,
        target_id=target_id,
        cron_expression=cron_expression,
        timezone="UTC",
        enabled=True,
        paused=False,
        created_by=DEFAULT_OWNER,
        source_pipeline_id=source_pipeline_id,
        next_run_at=compute_next_run(cron_expression, "UTC"),
    )
    session.add(job)
    session.flush()
    return job


def run() -> None:
    init_db()
    session = SessionLocal()
    try:
        admin = session.query(User).filter(User.email == DEFAULT_OWNER).first()
        if not admin:
            print(f"[!] Usuario {DEFAULT_OWNER} nao encontrado.")
            return

        created: list[str] = []
        skipped: list[str] = []

        pipelines = session.query(Pipeline).filter(Pipeline.schedule_cron != "").all()
        for p in pipelines:
            name = f"Pipeline: {p.name}"
            before = session.query(ScheduledJob).filter(ScheduledJob.name == name).count()
            j = _ensure_job(
                session,
                name=name,
                description=f"Run automatico do pipeline '{p.name}'",
                workspace=p.workspace,
                business_area=p.business_area or "",
                job_type=JobType.PIPELINE_RUN.value,
                target_id=p.id,
                cron_expression=p.schedule_cron,
                source_pipeline_id=p.id,
            )
            if j and before == 0:
                created.append(name)
            else:
                skipped.append(name)

        f = session.query(Forecast).filter(
            Forecast.name == "LATAM Revenue Forecast (Holt-Winters)"
        ).first()
        if f:
            name = "Forecast: LATAM Revenue (train diario)"
            before = session.query(ScheduledJob).filter(ScheduledJob.name == name).count()
            j = _ensure_job(
                session,
                name=name,
                description="Treina forecast Holt-Winters LATAM as 05:00 UTC",
                workspace=f.workspace,
                business_area=f.business_area or "Sales",
                job_type=JobType.FORECAST_TRAIN.value,
                target_id=f.id,
                cron_expression="0 5 * * *",
            )
            if j and before == 0:
                created.append(name)
            else:
                skipped.append(name)

        name = "Alerts: Evaluate All LATAM"
        before = session.query(ScheduledJob).filter(ScheduledJob.name == name).count()
        j = _ensure_job(
            session,
            name=name,
            description="Avalia todos os alertas enabled do workspace LATAM as 06:30 UTC",
            workspace="LATAM",
            business_area="",
            job_type=JobType.ALERTS_EVALUATE.value,
            target_id=None,
            cron_expression="30 6 * * *",
        )
        if j and before == 0:
            created.append(name)
        else:
            skipped.append(name)

        session.commit()
        print("Scheduled jobs:")
        for n in created:
            print(f"  [+] {n}")
        for n in skipped:
            print(f"  [=] {n} (ja existia)")
        print(f"Total: {len(created)} criados / {len(skipped)} ja existentes")
    finally:
        session.close()


if __name__ == "__main__":
    run()
