"""Schemas Pydantic para Alert + Notification (Phase 5)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# =====================
# Alert
# =====================

class AlertBase(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    description: str = ""
    workspace: str = "LATAM"
    business_area: str = ""
    alert_type: str  # metric_threshold | metric_change | forecast_quality | pipeline_failure | dashboard_stale
    severity: str = "warning"  # info | warning | critical
    target_id: int | None = None
    target_kind: str | None = None  # metric | forecast | pipeline | dashboard
    rule_config: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=lambda: ["in_app"])
    recipients: list[str] = Field(default_factory=list)
    enabled: bool = True
    cooldown_minutes: int = Field(default=60, ge=0, le=10080)


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    workspace: str | None = None
    business_area: str | None = None
    alert_type: str | None = None
    severity: str | None = None
    target_id: int | None = None
    target_kind: str | None = None
    rule_config: dict[str, Any] | None = None
    channels: list[str] | None = None
    recipients: list[str] | None = None
    enabled: bool | None = None
    cooldown_minutes: int | None = None


class AlertOut(AlertBase):
    id: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    last_evaluated_at: datetime | None = None
    last_eval_status: str | None = None
    last_fired_at: datetime | None = None
    last_eval_error: str | None = None
    fire_count: int = 0


class AlertEvaluationResult(BaseModel):
    alert_id: int
    fired: bool
    status: str  # ok | fired | error | cooldown
    title: str = ""
    message: str = ""
    severity: str
    context: dict[str, Any] = Field(default_factory=dict)
    notification_id: int | None = None
    error: str | None = None


class EvaluateAllResponse(BaseModel):
    evaluated: int
    fired: int
    errors: int
    cooldowned: int
    results: list[AlertEvaluationResult]


# =====================
# Notification
# =====================

class NotificationOut(BaseModel):
    id: int
    alert_id: int
    alert_name: str
    alert_type: str
    severity: str
    workspace: str
    business_area: str
    title: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)
    recipient_email: str
    channels_delivered: list[str]
    fired_at: datetime
    status: str
    read_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    ack_note: str | None = None


class NotificationSummary(BaseModel):
    total_unread: int
    total_unack: int
    by_severity: dict[str, int]  # {info: 1, warning: 5, critical: 0}
    recent: list[NotificationOut]


class NotificationAckPayload(BaseModel):
    note: str = ""
