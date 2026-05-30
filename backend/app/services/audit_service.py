"""Serviço de Audit Log - grava eventos importantes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    user_email: str,
    action: str,
    object_type: str = "",
    object_name: str = "",
    workspace: str = "",
    business_area: str = "",
    details: str = "",
) -> AuditLog:
    entry = AuditLog(
        user_email=user_email,
        action=action,
        object_type=object_type,
        object_name=object_name,
        workspace=workspace,
        business_area=business_area,
        details=details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
