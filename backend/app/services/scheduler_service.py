"""APScheduler integration (Phase 6).

Gerencia BackgroundScheduler, sync com DB, calcula next_run_at.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.models.scheduled_job import ScheduledJob
from app.services.job_runner import execute_job
from database import SessionLocal

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _parse_cron(expr: str) -> dict:
    parts = expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Cron invalido (5 campos): {expr!r}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def compute_next_run(cron_expression: str, tz: str = "UTC", after: datetime | None = None) -> datetime | None:
    """Calcula proxima execucao a partir do cron."""
    try:
        trigger = CronTrigger(**_parse_cron(cron_expression), timezone=tz)
        base = after or datetime.now(timezone.utc)
        nxt = trigger.get_next_fire_time(None, base)
        if nxt and nxt.tzinfo:
            return nxt.replace(tzinfo=None)
        return nxt
    except Exception as exc:  # noqa: BLE001
        logger.warning("compute_next_run failed: %s", exc)
        return None


def _job_callback(job_id: int) -> None:
    """Callback APScheduler - executa job em thread separada."""
    db = SessionLocal()
    try:
        job = db.get(ScheduledJob, job_id)
        if not job or not job.enabled or job.paused:
            return
        execute_job(db, job, triggered_by="scheduler")
        job = db.get(ScheduledJob, job_id)
        if job:
            job.next_run_at = compute_next_run(job.cron_expression, job.timezone)
            db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduled job %s failed: %s", job_id, exc)
        db.rollback()
    finally:
        db.close()


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC")
    return _scheduler


def is_running() -> bool:
    s = _scheduler
    return s is not None and s.running


def register_job(job: ScheduledJob) -> None:
    """Adiciona/atualiza job no APScheduler."""
    sched = get_scheduler()
    job_id_str = f"scheduled-job-{job.id}"
    if sched.get_job(job_id_str):
        sched.remove_job(job_id_str)
    if not job.enabled or job.paused:
        return
    try:
        trigger = CronTrigger(**_parse_cron(job.cron_expression), timezone=job.timezone or "UTC")
        sched.add_job(
            _job_callback,
            trigger=trigger,
            id=job_id_str,
            args=[job.id],
            replace_existing=True,
            misfire_grace_time=300,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("register_job %s failed: %s", job.id, exc)


def unregister_job(job_id: int) -> None:
    sched = get_scheduler()
    job_id_str = f"scheduled-job-{job_id}"
    if sched.get_job(job_id_str):
        sched.remove_job(job_id_str)


def sync_all_jobs() -> int:
    """Carrega todos os jobs enabled+!paused do DB e registra no scheduler."""
    db = SessionLocal()
    try:
        jobs = db.query(ScheduledJob).filter(
            ScheduledJob.enabled == True,  # noqa: E712
            ScheduledJob.paused == False,  # noqa: E712
        ).all()
        for job in jobs:
            register_job(job)
            nxt = compute_next_run(job.cron_expression, job.timezone)
            if nxt != job.next_run_at:
                job.next_run_at = nxt
        db.commit()
        return len(jobs)
    finally:
        db.close()


def start_scheduler() -> None:
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("APScheduler started")
    sync_all_jobs()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None


def scheduler_status() -> dict:
    sched = get_scheduler()
    active = 0
    next_runs: list[dict] = []
    if sched.running:
        for ap_job in sched.get_jobs():
            active += 1
            nxt = ap_job.next_run_time
            next_runs.append({
                "apscheduler_id": ap_job.id,
                "next_run_at": nxt.isoformat() if nxt else None,
            })
    return {"running": sched.running, "active_jobs": active, "next_runs": next_runs}


def run_job_now(job_id: int, triggered_by: str = "manual") -> None:
    """Dispara execucao imediata (fora do cron)."""
    db = SessionLocal()
    try:
        job = db.get(ScheduledJob, job_id)
        if not job:
            raise ValueError(f"Job {job_id} nao encontrado")
        execute_job(db, job, triggered_by=triggered_by)
        job = db.get(ScheduledJob, job_id)
        if job:
            job.next_run_at = compute_next_run(job.cron_expression, job.timezone)
            db.commit()
        register_job(job)  # refresh schedule
    finally:
        db.close()
