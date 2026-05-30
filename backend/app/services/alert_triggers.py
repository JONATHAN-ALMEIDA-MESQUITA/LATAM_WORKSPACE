"""Triggers automaticos de alerts (Phase 5).

Helpers chamados pelos routers de pipeline e forecast logo apos um run.
Avaliam todas as regras enabled cujo `target_kind` + `target_id` casa com
o objeto que acabou de rodar.

Falhas na avaliacao nao quebram o fluxo principal (logam e seguem).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertEvalStatus
from app.services.alert_engine import (
    AlertEvalError,
    evaluate as engine_evaluate,
    in_cooldown,
)
from app.services.notification_service import fire_notification


def trigger_for(
    db: Session, *, target_kind: str, target_id: int
) -> list[int]:
    """Avalia todos os alerts enabled cujo target casa.

    Retorna lista de notification IDs disparadas.
    """
    alerts = (
        db.query(Alert)
        .filter(
            Alert.enabled == True,  # noqa: E712
            Alert.target_kind == target_kind,
            Alert.target_id == target_id,
        )
        .all()
    )
    fired_ids: list[int] = []
    for alert in alerts:
        alert.last_evaluated_at = datetime.utcnow()
        if in_cooldown(alert):
            continue
        try:
            outcome = engine_evaluate(db, alert)
        except AlertEvalError as exc:
            alert.last_eval_status = AlertEvalStatus.ERROR.value
            alert.last_eval_error = str(exc)
            continue
        except Exception as exc:  # noqa: BLE001
            alert.last_eval_status = AlertEvalStatus.ERROR.value
            alert.last_eval_error = f"unexpected: {exc}"
            continue

        if outcome.fired:
            alert.last_eval_status = AlertEvalStatus.FIRED.value
            alert.last_eval_error = None
            notifs = fire_notification(db, alert=alert, outcome=outcome)
            fired_ids.extend(n.id for n in notifs)
        else:
            alert.last_eval_status = AlertEvalStatus.OK.value
            alert.last_eval_error = None
    return fired_ids
