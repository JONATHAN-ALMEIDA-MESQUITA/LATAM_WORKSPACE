"""Notification service (Phase 5).

Cria objetos Notification persistidos no DB + faz delivery nos canais
configurados (in_app sempre; email mock escreve em arquivo JSONL).

Para a demo, email = log estruturado em storage/notifications/emails.jsonl.
Em producao, basta swappar `_deliver_email` por SES/SendGrid/etc.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.alert import Alert, Notification, NotificationStatus
from app.services.alert_engine import EvalOutcome
from app.services.audit_service import log_action
from config import settings


_EMAIL_LOG_FILE = settings.notifications_log_dir / "emails.jsonl"


def _resolve_recipients(alert: Alert) -> list[str]:
    """Recipients explicitos OU criador do alerta."""
    rec = alert.recipients_list()
    if rec:
        return rec
    if alert.created_by:
        return [alert.created_by]
    return ["unknown@latam.com"]


_SLACK_LOG_FILE = settings.notifications_log_dir / "slack.jsonl"
_TEAMS_LOG_FILE = settings.notifications_log_dir / "teams.jsonl"


def _append_channel_log(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")


def _deliver_slack(recipient: str, notification: Notification) -> None:
    _append_channel_log(
        _SLACK_LOG_FILE,
        {
            "ts": datetime.utcnow().isoformat(),
            "channel": f"#{recipient.split('@')[0]}",
            "to": recipient,
            "text": f"[{notification.severity.upper()}] {notification.title}\n{notification.message}",
            "notification_id": notification.id,
        },
    )


def _deliver_teams(recipient: str, notification: Notification) -> None:
    _append_channel_log(
        _TEAMS_LOG_FILE,
        {
            "ts": datetime.utcnow().isoformat(),
            "webhook": "mock-teams-webhook",
            "to": recipient,
            "title": notification.title,
            "text": notification.message,
            "severity": notification.severity,
            "notification_id": notification.id,
        },
    )


def _deliver_email(recipient: str, notification: Notification) -> None:
    """Mock de envio de email - escreve em jsonl pra inspecionar na demo."""
    _EMAIL_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "to": recipient,
        "subject": f"[{notification.severity.upper()}] {notification.title}",
        "body": notification.message,
        "notification_id": notification.id,
        "alert_id": notification.alert_id,
        "alert_type": notification.alert_type,
        "workspace": notification.workspace,
        "context": notification.context_dict(),
    }
    with _EMAIL_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")


def fire_notification(
    db: Session,
    *,
    alert: Alert,
    outcome: EvalOutcome,
) -> list[Notification]:
    """Cria 1 Notification por recipient + entrega nos canais configurados.

    Retorna a lista de Notification persistidas.
    """
    channels = alert.channels_list() or ["in_app"]
    recipients = _resolve_recipients(alert)

    created: list[Notification] = []
    now = datetime.utcnow()

    for recipient in recipients:
        n = Notification(
            alert_id=alert.id,
            alert_name=alert.name,
            alert_type=alert.alert_type,
            severity=alert.severity,
            workspace=alert.workspace,
            business_area=alert.business_area,
            title=outcome.title or alert.name,
            message=outcome.message,
            context=json.dumps(outcome.context, default=str),
            recipient_email=recipient,
            channels_delivered=json.dumps(channels),
            fired_at=now,
            status=NotificationStatus.UNREAD.value,
        )
        db.add(n)
        db.flush()  # pra ter o id antes do log
        created.append(n)

        if "email" in channels:
            try:
                _deliver_email(recipient, n)
            except Exception as exc:  # noqa: BLE001
                log_action(
                    db,
                    user_email="system",
                    action="email_delivery_error",
                    object_type="notification",
                    object_name=str(n.id),
                    details=f"recipient={recipient} err={exc}",
                )
        if "slack" in channels:
            try:
                _deliver_slack(recipient, n)
            except Exception as exc:  # noqa: BLE001
                log_action(
                    db,
                    user_email="system",
                    action="slack_delivery_error",
                    object_type="notification",
                    object_name=str(n.id),
                    details=f"recipient={recipient} err={exc}",
                )
        if "teams" in channels:
            try:
                _deliver_teams(recipient, n)
            except Exception as exc:  # noqa: BLE001
                log_action(
                    db,
                    user_email="system",
                    action="teams_delivery_error",
                    object_type="notification",
                    object_name=str(n.id),
                    details=f"recipient={recipient} err={exc}",
                )

    alert.last_fired_at = now
    alert.fire_count = (alert.fire_count or 0) + 1
    log_action(
        db,
        user_email="system",
        action="alert_fired",
        object_type="alert",
        object_name=alert.name,
        workspace=alert.workspace,
        details=(
            f"severity={alert.severity} recipients={len(recipients)} "
            f"channels={','.join(channels)} type={alert.alert_type}"
        ),
    )

    return created
