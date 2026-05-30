"""Router de Notifications (Phase 5).

    GET    /notifications                  inbox do usuario logado (com filtros)
    GET    /notifications/summary          contadores + ultimas 5 (header bell)
    POST   /notifications/{id}/read        marca como read
    POST   /notifications/{id}/ack         acknowledge (com nota opcional)
    POST   /notifications/read-all         marca tudo unread -> read
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.alert import Notification, NotificationStatus
from app.models.user import User
from app.schemas.alert import (
    NotificationAckPayload,
    NotificationOut,
    NotificationSummary,
)
from app.services.audit_service import log_action
from app.services.auth_service import require_capability
from app.services.permission_service import has_capability
from database import get_db


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _to_out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        alert_id=n.alert_id,
        alert_name=n.alert_name,
        alert_type=n.alert_type,
        severity=n.severity,
        workspace=n.workspace,
        business_area=n.business_area,
        title=n.title,
        message=n.message,
        context=n.context_dict(),
        recipient_email=n.recipient_email,
        channels_delivered=n.channels_list(),
        fired_at=n.fired_at,
        status=n.status,
        read_at=n.read_at,
        acknowledged_at=n.acknowledged_at,
        acknowledged_by=n.acknowledged_by,
        ack_note=n.ack_note,
    )


def _user_filter(q, user: User):
    """Notification e destinada a recipient_email do user, OU manage_alerts ve tudo."""
    if has_capability(user, "manage_alerts"):
        return q
    return q.filter(Notification.recipient_email == user.email)


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    status: str | None = None,
    severity: str | None = None,
    alert_type: str | None = None,
    workspace: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> list[NotificationOut]:
    q = db.query(Notification)
    q = _user_filter(q, user)
    if status:
        q = q.filter(Notification.status == status)
    if severity:
        q = q.filter(Notification.severity == severity)
    if alert_type:
        q = q.filter(Notification.alert_type == alert_type)
    if workspace:
        q = q.filter(Notification.workspace == workspace)
    items = q.order_by(Notification.fired_at.desc()).limit(limit).all()
    return [_to_out(n) for n in items]


@router.get("/summary", response_model=NotificationSummary)
def notifications_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> NotificationSummary:
    q = _user_filter(db.query(Notification), user)
    total_unread = q.filter(Notification.status == NotificationStatus.UNREAD.value).count()
    total_unack = q.filter(
        Notification.status != NotificationStatus.ACKNOWLEDGED.value
    ).count()

    by_sev = {"info": 0, "warning": 0, "critical": 0}
    for sev in by_sev:
        by_sev[sev] = q.filter(
            Notification.severity == sev,
            Notification.status != NotificationStatus.ACKNOWLEDGED.value,
        ).count()

    recent = (
        _user_filter(db.query(Notification), user)
        .order_by(Notification.fired_at.desc())
        .limit(5)
        .all()
    )
    return NotificationSummary(
        total_unread=total_unread,
        total_unack=total_unack,
        by_severity=by_sev,
        recent=[_to_out(n) for n in recent],
    )


def _own_or_admin(n: Notification, user: User) -> bool:
    if has_capability(user, "manage_alerts"):
        return True
    return n.recipient_email == user.email


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> NotificationOut:
    n = db.get(Notification, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification nao encontrada.")
    if not _own_or_admin(n, user):
        raise HTTPException(status_code=403, detail="Nao e sua.")
    if n.status == NotificationStatus.UNREAD.value:
        n.status = NotificationStatus.READ.value
        n.read_at = datetime.utcnow()
        db.commit()
        db.refresh(n)
    return _to_out(n)


@router.post("/{notification_id}/ack", response_model=NotificationOut)
def acknowledge(
    notification_id: int,
    payload: NotificationAckPayload,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> NotificationOut:
    n = db.get(Notification, notification_id)
    if not n:
        raise HTTPException(status_code=404, detail="Notification nao encontrada.")
    if not _own_or_admin(n, user):
        raise HTTPException(status_code=403, detail="Nao e sua.")
    n.status = NotificationStatus.ACKNOWLEDGED.value
    n.acknowledged_at = datetime.utcnow()
    n.acknowledged_by = user.email
    n.ack_note = payload.note or None
    if not n.read_at:
        n.read_at = n.acknowledged_at
    db.commit()
    db.refresh(n)
    log_action(
        db,
        user_email=user.email,
        action="ack_notification",
        object_type="notification",
        object_name=str(n.id),
        workspace=n.workspace,
        details=f"alert={n.alert_name} note={payload.note}",
    )
    return _to_out(n)


@router.post("/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> dict:
    q = _user_filter(db.query(Notification), user).filter(
        Notification.status == NotificationStatus.UNREAD.value
    )
    now = datetime.utcnow()
    count = 0
    for n in q.all():
        n.status = NotificationStatus.READ.value
        n.read_at = now
        count += 1
    db.commit()
    return {"updated": count}
