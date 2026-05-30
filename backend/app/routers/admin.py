"""Router Admin panel (Phase 8).

    GET /admin/audit-logs           trilha de auditoria
    GET /admin/permissions/matrix   matriz RBAC
    GET /admin/system-status        saude da plataforma
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.audit_log import AuditLog
from app.models.dashboard import Dashboard
from app.models.dataset import Dataset
from app.models.forecast import Forecast
from app.models.pipeline import Pipeline
from app.models.scheduled_job import ScheduledJob, ScheduledJobRun
from app.models.user import User
from app.schemas.admin import AuditLogOut, PermissionsMatrixOut, SystemStatusOut
from app.services.auth_service import require_capability
from app.services.permission_service import export_permissions_matrix
from app.services.scheduler_service import scheduler_status
from config import settings
from database import get_db


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit_logs(
    user_email: str | None = None,
    action: str | None = None,
    workspace: str | None = None,
    object_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_capability("view_audit_logs")),
) -> list[AuditLogOut]:
    q = db.query(AuditLog).order_by(AuditLog.timestamp.desc())
    if user_email:
        q = q.filter(AuditLog.user_email.ilike(f"%{user_email}%"))
    if action:
        q = q.filter(AuditLog.action.ilike(f"%{action}%"))
    if workspace:
        q = q.filter(AuditLog.workspace == workspace)
    if object_type:
        q = q.filter(AuditLog.object_type == object_type)
    rows = q.limit(limit).all()
    return [
        AuditLogOut(
            id=r.id,
            user_email=r.user_email,
            action=r.action,
            object_type=r.object_type,
            object_name=r.object_name,
            workspace=r.workspace,
            business_area=r.business_area,
            timestamp=r.timestamp,
            details=r.details,
        )
        for r in rows
    ]


@router.get("/permissions/matrix", response_model=PermissionsMatrixOut)
def permissions_matrix(
    _: User = Depends(require_capability("manage_permissions")),
) -> PermissionsMatrixOut:
    data = export_permissions_matrix()
    return PermissionsMatrixOut(**data)


@router.get("/system-status", response_model=SystemStatusOut)
def system_status(
    db: Session = Depends(get_db),
    _: User = Depends(require_capability("view_admin")),
) -> SystemStatusOut:
    sched = scheduler_status()
    failed_recent = (
        db.query(ScheduledJobRun)
        .filter(ScheduledJobRun.status == "Failed")
        .count()
    )
    return SystemStatusOut(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database_url=settings.database_url.split("///")[-1][:80],
        scheduler_running=bool(sched.get("running")),
        scheduler_active_jobs=int(sched.get("active_jobs", 0)),
        entity_counts={
            "users": db.query(User).count(),
            "datasets": db.query(Dataset).count(),
            "pipelines": db.query(Pipeline).count(),
            "dashboards": db.query(Dashboard).count(),
            "forecasts": db.query(Forecast).count(),
            "alerts": db.query(Alert).count(),
            "scheduled_jobs": db.query(ScheduledJob).count(),
            "audit_logs": db.query(AuditLog).count(),
        },
        recent_failed_jobs=failed_recent,
    )
