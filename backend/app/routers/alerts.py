"""Router de Alerts (Phase 5).

    GET    /alerts                       lista
    POST   /alerts                       cria
    GET    /alerts/{id}                  detalhe
    PUT    /alerts/{id}                  atualiza
    DELETE /alerts/{id}                  remove
    POST   /alerts/{id}/toggle           enabled <-> disabled

    POST   /alerts/{id}/evaluate         avalia agora (respeitando cooldown)
    POST   /alerts/{id}/test             avalia ignorando cooldown (sem cria Notification)
    POST   /alerts/evaluate-all          avalia todos os enabled do workspace
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertEvalStatus
from app.models.user import User
from app.schemas.alert import (
    AlertCreate,
    AlertEvaluationResult,
    AlertOut,
    AlertUpdate,
    EvaluateAllResponse,
)
from app.services.alert_engine import (
    AlertEvalError,
    evaluate as engine_evaluate,
    in_cooldown,
    validate_alert_type,
    validate_severity,
)
from app.services.audit_service import log_action
from app.services.auth_service import get_current_user, require_capability
from app.services.notification_service import fire_notification
from app.services.permission_service import (
    accessible_workspaces,
    can_create_alert,
    can_manage_alerts,
    has_capability,
)
from database import get_db


router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_out(a: Alert) -> AlertOut:
    return AlertOut(
        id=a.id,
        name=a.name,
        description=a.description,
        workspace=a.workspace,
        business_area=a.business_area,
        alert_type=a.alert_type,
        severity=a.severity,
        target_id=a.target_id,
        target_kind=a.target_kind,
        rule_config=a.rule_config_dict(),
        channels=a.channels_list(),
        recipients=a.recipients_list(),
        enabled=a.enabled,
        cooldown_minutes=a.cooldown_minutes,
        created_by=a.created_by,
        created_at=a.created_at,
        updated_at=a.updated_at,
        last_evaluated_at=a.last_evaluated_at,
        last_eval_status=a.last_eval_status,
        last_fired_at=a.last_fired_at,
        last_eval_error=a.last_eval_error,
        fire_count=a.fire_count,
    )


def _check_workspace(user: User, workspace: str) -> None:
    if workspace not in accessible_workspaces(user, [workspace]):
        raise HTTPException(status_code=403, detail=f"Sem acesso ao workspace {workspace}")


def _resolve_alert(db: Session, user: User, alert_id: int) -> Alert:
    a = db.get(Alert, alert_id)
    if not a:
        raise HTTPException(status_code=404, detail="Alerta nao encontrado.")
    _check_workspace(user, a.workspace)
    return a


def _validate_payload(data: dict) -> None:
    if "alert_type" in data and data["alert_type"]:
        try:
            validate_alert_type(data["alert_type"])
        except AlertEvalError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "severity" in data and data["severity"]:
        try:
            validate_severity(data["severity"])
        except AlertEvalError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AlertOut])
def list_alerts(
    workspace: str | None = None,
    business_area: str | None = None,
    alert_type: str | None = None,
    severity: str | None = None,
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> list[AlertOut]:
    q = db.query(Alert)
    if workspace:
        q = q.filter(Alert.workspace == workspace)
    if business_area:
        q = q.filter(Alert.business_area == business_area)
    if alert_type:
        q = q.filter(Alert.alert_type == alert_type)
    if severity:
        q = q.filter(Alert.severity == severity)
    if enabled is not None:
        q = q.filter(Alert.enabled == enabled)
    items = q.order_by(Alert.updated_at.desc()).all()
    if items:
        allowed = set(accessible_workspaces(user, list({a.workspace for a in items})))
        items = [a for a in items if a.workspace in allowed]
    return [_to_out(a) for a in items]


@router.post("", response_model=AlertOut)
def create_alert(
    payload: AlertCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_alert")),
) -> AlertOut:
    _check_workspace(user, payload.workspace)
    _validate_payload(payload.model_dump())

    a = Alert(
        name=payload.name,
        description=payload.description,
        workspace=payload.workspace,
        business_area=payload.business_area,
        alert_type=payload.alert_type,
        severity=payload.severity,
        target_id=payload.target_id,
        target_kind=payload.target_kind,
        rule_config=json.dumps(payload.rule_config or {}),
        channels=json.dumps(payload.channels or ["in_app"]),
        recipients=json.dumps(payload.recipients or []),
        enabled=payload.enabled,
        cooldown_minutes=payload.cooldown_minutes,
        created_by=user.email,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    log_action(
        db,
        user_email=user.email,
        action="create_alert",
        object_type="alert",
        object_name=a.name,
        workspace=a.workspace,
        business_area=a.business_area,
        details=f"type={a.alert_type} severity={a.severity} target_id={a.target_id}",
    )
    return _to_out(a)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> AlertOut:
    return _to_out(_resolve_alert(db, user, alert_id))


@router.put("/{alert_id}", response_model=AlertOut)
def update_alert(
    alert_id: int,
    payload: AlertUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_alert")),
) -> AlertOut:
    a = _resolve_alert(db, user, alert_id)
    if a.created_by != user.email and not can_manage_alerts(user):
        raise HTTPException(status_code=403, detail="Apenas o autor ou admin pode editar.")
    data = payload.model_dump(exclude_unset=True)
    _validate_payload(data)
    if "workspace" in data and data["workspace"]:
        _check_workspace(user, data["workspace"])

    for k, v in data.items():
        if k == "rule_config":
            a.rule_config = json.dumps(v or {})
        elif k == "channels":
            a.channels = json.dumps(v or ["in_app"])
        elif k == "recipients":
            a.recipients = json.dumps(v or [])
        else:
            setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{alert_id}")
def delete_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_alert")),
) -> dict:
    a = _resolve_alert(db, user, alert_id)
    if a.created_by != user.email and not can_manage_alerts(user):
        raise HTTPException(status_code=403, detail="Sem permissao para remover.")
    log_action(
        db,
        user_email=user.email,
        action="delete_alert",
        object_type="alert",
        object_name=a.name,
        workspace=a.workspace,
    )
    db.delete(a)
    db.commit()
    return {"deleted": True}


@router.post("/{alert_id}/toggle", response_model=AlertOut)
def toggle_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_alert")),
) -> AlertOut:
    a = _resolve_alert(db, user, alert_id)
    if a.created_by != user.email and not can_manage_alerts(user):
        raise HTTPException(status_code=403, detail="Sem permissao.")
    a.enabled = not a.enabled
    db.commit()
    db.refresh(a)
    return _to_out(a)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _run_evaluate_one(
    db: Session, alert: Alert, *, ignore_cooldown: bool, dry_run: bool = False
) -> AlertEvaluationResult:
    """Avalia 1 alert e (se fired e nao dry_run) cria notifications."""
    alert.last_evaluated_at = datetime.utcnow()

    if not alert.enabled and not dry_run:
        alert.last_eval_status = AlertEvalStatus.OK.value
        alert.last_eval_error = "disabled"
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=False,
            status="disabled",
            title=alert.name,
            message="Alert desabilitado.",
            severity=alert.severity,
        )

    if not ignore_cooldown and in_cooldown(alert):
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=False,
            status="cooldown",
            title=alert.name,
            message=(
                f"Em cooldown (ultimo disparo: {alert.last_fired_at.isoformat()}, "
                f"cooldown={alert.cooldown_minutes}min)."
            ),
            severity=alert.severity,
        )

    try:
        outcome = engine_evaluate(db, alert)
    except AlertEvalError as exc:
        alert.last_eval_status = AlertEvalStatus.ERROR.value
        alert.last_eval_error = str(exc)
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=False,
            status="error",
            title=alert.name,
            message="",
            severity=alert.severity,
            error=str(exc),
        )
    except Exception as exc:  # noqa: BLE001
        alert.last_eval_status = AlertEvalStatus.ERROR.value
        alert.last_eval_error = f"unexpected: {exc}"
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=False,
            status="error",
            title=alert.name,
            message="",
            severity=alert.severity,
            error=f"unexpected: {exc}",
        )

    if outcome.fired and not dry_run:
        alert.last_eval_status = AlertEvalStatus.FIRED.value
        alert.last_eval_error = None
        notifs = fire_notification(db, alert=alert, outcome=outcome)
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=True,
            status="fired",
            title=outcome.title or alert.name,
            message=outcome.message,
            severity=alert.severity,
            context=outcome.context,
            notification_id=notifs[0].id if notifs else None,
        )

    if outcome.fired and dry_run:
        # Teste: nao persiste, so reporta
        return AlertEvaluationResult(
            alert_id=alert.id,
            fired=True,
            status="would_fire",
            title=outcome.title or alert.name,
            message=outcome.message,
            severity=alert.severity,
            context=outcome.context,
        )

    alert.last_eval_status = AlertEvalStatus.OK.value
    alert.last_eval_error = None
    return AlertEvaluationResult(
        alert_id=alert.id,
        fired=False,
        status="ok",
        title=outcome.title or alert.name,
        message=outcome.message,
        severity=alert.severity,
        context=outcome.context,
    )


@router.post("/{alert_id}/evaluate", response_model=AlertEvaluationResult)
def evaluate_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> AlertEvaluationResult:
    a = _resolve_alert(db, user, alert_id)
    result = _run_evaluate_one(db, a, ignore_cooldown=False)
    db.commit()
    log_action(
        db,
        user_email=user.email,
        action="evaluate_alert",
        object_type="alert",
        object_name=a.name,
        workspace=a.workspace,
        details=f"status={result.status} fired={result.fired}",
    )
    return result


@router.post("/{alert_id}/test", response_model=AlertEvaluationResult)
def test_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("create_alert")),
) -> AlertEvaluationResult:
    """Testa o alert (ignora cooldown, NAO cria notification)."""
    a = _resolve_alert(db, user, alert_id)
    result = _run_evaluate_one(db, a, ignore_cooldown=True, dry_run=True)
    # Reverte mudanca de last_eval_status (test nao deve persistir nada)
    db.rollback()
    return result


@router.post("/evaluate-all", response_model=EvaluateAllResponse)
def evaluate_all(
    workspace: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_capability("view_alerts")),
) -> EvaluateAllResponse:
    """Avalia todos os alerts enabled (com permissao de workspace)."""
    q = db.query(Alert).filter(Alert.enabled == True)  # noqa: E712
    if workspace:
        q = q.filter(Alert.workspace == workspace)
    items = q.all()
    if items:
        allowed = set(accessible_workspaces(user, list({a.workspace for a in items})))
        items = [a for a in items if a.workspace in allowed]

    results: list[AlertEvaluationResult] = []
    fired = 0
    errors = 0
    cooldowned = 0
    for a in items:
        r = _run_evaluate_one(db, a, ignore_cooldown=False)
        results.append(r)
        if r.status == "fired":
            fired += 1
        elif r.status == "error":
            errors += 1
        elif r.status == "cooldown":
            cooldowned += 1
    db.commit()
    log_action(
        db,
        user_email=user.email,
        action="evaluate_alerts_batch",
        object_type="alert",
        details=f"evaluated={len(results)} fired={fired} errors={errors}",
    )
    return EvaluateAllResponse(
        evaluated=len(results),
        fired=fired,
        errors=errors,
        cooldowned=cooldowned,
        results=results,
    )
