"""Models do Alerts & Notifications (Phase 5).

Alert: regra configurada que avalia algo periodicamente / on-demand / on-trigger.
Notification: instancia disparada (1 alert pode gerar N notifications ao longo do tempo).
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class AlertType(str, Enum):
    METRIC_THRESHOLD = "metric_threshold"
    METRIC_CHANGE = "metric_change"
    FORECAST_QUALITY = "forecast_quality"
    PIPELINE_FAILURE = "pipeline_failure"
    DASHBOARD_STALE = "dashboard_stale"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertEvalStatus(str, Enum):
    OK = "ok"           # avaliado e nao disparou
    FIRED = "fired"     # avaliado e disparou
    ERROR = "error"     # erro na avaliacao


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ACKNOWLEDGED = "acknowledged"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    workspace: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    business_area: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")

    alert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AlertSeverity.WARNING.value
    )

    # Target generico - pode ser metric_id, forecast_id, pipeline_id ou dashboard_id
    # dependendo do alert_type. Resolvido no engine.
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    target_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Regra (JSON especifico por tipo)
    rule_config: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Canais (JSON list[str]: "in_app", "email")
    channels: Mapped[str] = mapped_column(Text, nullable=False, default='["in_app"]')

    # Lista de e-mails que recebem (JSON). Se vazio, usa o criador.
    recipients: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Cooldown em minutos: nao re-disparar se ja disparou recentemente
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)

    created_by: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_eval_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_eval_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fire_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="alert",
        cascade="all, delete-orphan",
        order_by="desc(Notification.fired_at)",
    )

    def rule_config_dict(self) -> dict:
        try:
            return json.loads(self.rule_config or "{}")
        except json.JSONDecodeError:
            return {}

    def channels_list(self) -> list[str]:
        try:
            v = json.loads(self.channels or "[]")
            return v if isinstance(v, list) else ["in_app"]
        except json.JSONDecodeError:
            return ["in_app"]

    def recipients_list(self) -> list[str]:
        try:
            v = json.loads(self.recipients or "[]")
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "rule_config": self.rule_config_dict(),
            "channels": self.channels_list(),
            "recipients": self.recipients_list(),
            "enabled": self.enabled,
            "cooldown_minutes": self.cooldown_minutes,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_evaluated_at": self.last_evaluated_at.isoformat()
            if self.last_evaluated_at
            else None,
            "last_eval_status": self.last_eval_status,
            "last_fired_at": self.last_fired_at.isoformat() if self.last_fired_at else None,
            "last_eval_error": self.last_eval_error,
            "fire_count": self.fire_count,
        }


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_id: Mapped[int] = mapped_column(
        ForeignKey("alerts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Snapshot do alert no momento do disparo (denormalizado pra preservar contexto)
    alert_name: Mapped[str] = mapped_column(String(255), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    workspace: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_area: Mapped[str] = mapped_column(String(64), nullable=False, default="")

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Contexto da avaliacao (JSON: valores, thresholds, etc.)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channels_delivered: Mapped[str] = mapped_column(Text, nullable=False, default='["in_app"]')

    fired_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=NotificationStatus.UNREAD.value, index=True
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ack_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    alert: Mapped["Alert"] = relationship("Alert", back_populates="notifications")

    def context_dict(self) -> dict:
        try:
            return json.loads(self.context or "{}")
        except json.JSONDecodeError:
            return {}

    def channels_list(self) -> list[str]:
        try:
            v = json.loads(self.channels_delivered or "[]")
            return v if isinstance(v, list) else []
        except json.JSONDecodeError:
            return []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "alert_id": self.alert_id,
            "alert_name": self.alert_name,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "workspace": self.workspace,
            "business_area": self.business_area,
            "title": self.title,
            "message": self.message,
            "context": self.context_dict(),
            "recipient_email": self.recipient_email,
            "channels_delivered": self.channels_list(),
            "fired_at": self.fired_at.isoformat() if self.fired_at else None,
            "status": self.status,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat()
            if self.acknowledged_at
            else None,
            "acknowledged_by": self.acknowledged_by,
            "ack_note": self.ack_note,
        }
