"""Engine de avaliacao de alertas (Phase 5).

5 evaluators (todos retornam EvalOutcome):
    - metric_threshold  : compara metric value com threshold (op: <, >, ==, !=, <=, >=)
    - metric_change     : variacao % entre periodo atual vs anterior (mesma metrica)
    - forecast_quality  : MAPE do ultimo run >= threshold
    - pipeline_failure  : ultimo run de um pipeline com status FAILED
    - dashboard_stale   : dashboard publicado sem update ha N dias

A engine retorna se disparou + contexto rico (valores, thresholds) que vai pro
campo `context` da Notification e pode ser exibido no frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.dashboard import Dashboard, DashboardStatus
from app.models.dataset import Dataset
from app.models.forecast import Forecast
from app.models.metric import Metric
from app.models.pipeline import Pipeline, PipelineRun, RunStatus
from app.services.metric_engine import MetricError, calc_metric, format_metric_value


@dataclass
class EvalOutcome:
    fired: bool
    title: str = ""
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)


class AlertEvalError(Exception):
    """Erro ao avaliar um alerta (config invalida, target nao encontrado, etc.)."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_OPERATORS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}

_OPERATOR_LABEL = {
    "<": "menor que",
    "<=": "menor ou igual a",
    ">": "maior que",
    ">=": "maior ou igual a",
    "==": "igual a",
    "!=": "diferente de",
}


def _load_dataset_df(ds: Dataset) -> pd.DataFrame:
    if not ds.processed_path:
        raise AlertEvalError(f"Dataset '{ds.name}' sem parquet processado.")
    path = Path(ds.processed_path)
    if not path.exists():
        raise AlertEvalError(f"Parquet nao encontrado: {path}")
    return pd.read_parquet(path)


def _filter_df(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Aplica filtros simples col=value ou col=[v1,v2]."""
    out = df
    for col, val in (filters or {}).items():
        if col not in out.columns:
            continue
        if isinstance(val, list):
            out = out[out[col].isin(val)]
        else:
            out = out[out[col] == val]
    return out


def _filter_by_period(
    df: pd.DataFrame, date_col: str, period: str, ref_date: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Filtra DataFrame por periodo relativo a uma data de referencia.

    period: 'mtd' (mes atual ate hoje), 'ytd' (ano atual ate hoje),
            'last_30d', 'last_7d', 'prev_month', 'prev_year'
    """
    if date_col not in df.columns:
        raise AlertEvalError(f"date_column '{date_col}' nao existe no dataset.")
    work = df.copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col])
    if work.empty:
        return work

    if ref_date is None:
        ref_date = pd.Timestamp(work[date_col].max())

    if period == "mtd":
        start = pd.Timestamp(ref_date.year, ref_date.month, 1)
        end = ref_date
    elif period == "ytd":
        start = pd.Timestamp(ref_date.year, 1, 1)
        end = ref_date
    elif period == "last_30d":
        start = ref_date - pd.Timedelta(days=30)
        end = ref_date
    elif period == "last_7d":
        start = ref_date - pd.Timedelta(days=7)
        end = ref_date
    elif period == "prev_month":
        first_curr = pd.Timestamp(ref_date.year, ref_date.month, 1)
        last_prev = first_curr - pd.Timedelta(days=1)
        start = pd.Timestamp(last_prev.year, last_prev.month, 1)
        end = last_prev
    elif period == "prev_year":
        start = pd.Timestamp(ref_date.year - 1, ref_date.month, 1)
        end = pd.Timestamp(
            ref_date.year - 1, ref_date.month, min(ref_date.day, 28)
        )
    elif period == "all":
        return work
    else:
        raise AlertEvalError(f"period invalido: {period}")

    mask = (work[date_col] >= start) & (work[date_col] <= end)
    return work[mask]


# ---------------------------------------------------------------------------
# Evaluators
# ---------------------------------------------------------------------------

def _eval_metric_threshold(db: Session, alert: Alert) -> EvalOutcome:
    """rule_config:
        {
            "operator": "<", "<=", ">", ">=", "==", "!=",
            "threshold": 1000000,
            "period": "mtd" | "ytd" | "last_30d" | "last_7d" | "all" (default "all"),
            "filters": {"country": "Brazil"} (opcional)
        }
    """
    cfg = alert.rule_config_dict()
    operator = cfg.get("operator", "<")
    threshold = cfg.get("threshold")
    period = cfg.get("period", "all")
    filters = cfg.get("filters", {})

    if threshold is None:
        raise AlertEvalError("rule_config.threshold obrigatorio.")
    if operator not in _OPERATORS:
        raise AlertEvalError(f"operator invalido: {operator}")
    if not alert.target_id:
        raise AlertEvalError("target_id (metric_id) obrigatorio.")

    metric = db.get(Metric, alert.target_id)
    if not metric:
        raise AlertEvalError(f"Metric {alert.target_id} nao encontrada.")
    ds = db.get(Dataset, metric.dataset_id)
    if not ds:
        raise AlertEvalError(f"Dataset {metric.dataset_id} nao encontrado.")

    df = _load_dataset_df(ds)
    df = _filter_df(df, filters)
    if period != "all":
        date_col = metric.config_dict().get("date_column") or cfg.get("date_column")
        if not date_col:
            raise AlertEvalError(
                f"period={period} requer date_column (no metric.config ou rule_config)."
            )
        df = _filter_by_period(df, date_col, period)

    try:
        value = calc_metric(
            df, formula_type=metric.formula_type, formula_config=metric.config_dict()
        )
    except MetricError as exc:
        raise AlertEvalError(f"Erro ao calcular metric: {exc}") from exc

    if value is None:
        return EvalOutcome(
            fired=False,
            message=f"Metric '{metric.name}' retornou None.",
            context={"value": None, "threshold": threshold, "operator": operator},
        )

    fired = _OPERATORS[operator](value, threshold)
    fmt_value = format_metric_value(
        value, output_format=metric.output_format, decimals=metric.decimals
    )
    fmt_thresh = format_metric_value(
        threshold, output_format=metric.output_format, decimals=metric.decimals
    )

    period_label = f" ({period.upper()})" if period != "all" else ""
    title = f"Metric '{metric.name}'{period_label} {_OPERATOR_LABEL[operator]} {fmt_thresh}"

    if fired:
        message = (
            f"Valor atual {fmt_value} viola a regra ({_OPERATOR_LABEL[operator]} {fmt_thresh})."
        )
    else:
        message = f"Valor atual {fmt_value} - dentro do esperado."

    return EvalOutcome(
        fired=fired,
        title=title,
        message=message,
        context={
            "metric_id": metric.id,
            "metric_name": metric.name,
            "value": value,
            "value_formatted": fmt_value,
            "threshold": threshold,
            "threshold_formatted": fmt_thresh,
            "operator": operator,
            "period": period,
            "filters": filters,
        },
    )


def _eval_metric_change(db: Session, alert: Alert) -> EvalOutcome:
    """rule_config:
        {
            "change_pct_threshold": -10.0,  # variacao significativa (% absoluta ou sinalizada)
            "direction": "drop" | "raise" | "any" (default "any"),
            "current_period": "mtd",
            "previous_period": "prev_month",
            "filters": {} (opcional)
        }
    """
    cfg = alert.rule_config_dict()
    change_threshold = float(cfg.get("change_pct_threshold", 10.0))
    direction = cfg.get("direction", "any")
    current_period = cfg.get("current_period", "mtd")
    prev_period = cfg.get("previous_period", "prev_month")
    filters = cfg.get("filters", {})

    if not alert.target_id:
        raise AlertEvalError("target_id (metric_id) obrigatorio.")

    metric = db.get(Metric, alert.target_id)
    if not metric:
        raise AlertEvalError(f"Metric {alert.target_id} nao encontrada.")
    ds = db.get(Dataset, metric.dataset_id)
    if not ds:
        raise AlertEvalError(f"Dataset {metric.dataset_id} nao encontrado.")

    date_col = metric.config_dict().get("date_column") or cfg.get("date_column")
    if not date_col:
        raise AlertEvalError("metric_change requer date_column.")

    df = _load_dataset_df(ds)
    df = _filter_df(df, filters)
    df_curr = _filter_by_period(df, date_col, current_period)
    df_prev = _filter_by_period(df, date_col, prev_period)

    try:
        val_curr = calc_metric(
            df_curr, formula_type=metric.formula_type, formula_config=metric.config_dict()
        )
        val_prev = calc_metric(
            df_prev, formula_type=metric.formula_type, formula_config=metric.config_dict()
        )
    except MetricError as exc:
        raise AlertEvalError(f"Erro ao calcular metric: {exc}") from exc

    if val_curr is None or val_prev is None or val_prev == 0:
        return EvalOutcome(
            fired=False,
            message=f"Sem dados suficientes para comparar (curr={val_curr}, prev={val_prev}).",
            context={"current": val_curr, "previous": val_prev},
        )

    change_pct = ((val_curr - val_prev) / abs(val_prev)) * 100.0

    if direction == "drop":
        fired = change_pct <= -abs(change_threshold)
    elif direction == "raise":
        fired = change_pct >= abs(change_threshold)
    else:  # any
        fired = abs(change_pct) >= abs(change_threshold)

    fmt_curr = format_metric_value(
        val_curr, output_format=metric.output_format, decimals=metric.decimals
    )
    fmt_prev = format_metric_value(
        val_prev, output_format=metric.output_format, decimals=metric.decimals
    )
    sign = "+" if change_pct >= 0 else ""
    title = (
        f"Metric '{metric.name}' variou {sign}{change_pct:.2f}% "
        f"({current_period.upper()} vs {prev_period.upper()})"
    )

    if fired:
        message = (
            f"{fmt_curr} vs {fmt_prev}. Variacao de {sign}{change_pct:.2f}% supera o threshold ({change_threshold}%, direction={direction})."
        )
    else:
        message = f"{fmt_curr} vs {fmt_prev}. Variacao {sign}{change_pct:.2f}% dentro do esperado."

    return EvalOutcome(
        fired=fired,
        title=title,
        message=message,
        context={
            "metric_id": metric.id,
            "metric_name": metric.name,
            "current_value": val_curr,
            "current_formatted": fmt_curr,
            "previous_value": val_prev,
            "previous_formatted": fmt_prev,
            "change_pct": change_pct,
            "threshold_pct": change_threshold,
            "direction": direction,
            "current_period": current_period,
            "previous_period": prev_period,
        },
    )


def _eval_forecast_quality(db: Session, alert: Alert) -> EvalOutcome:
    """rule_config:
        {
            "mape_threshold": 30.0,
            "scope": "any" | "all" | "average" (default "any")
                any   : dispara se algum grupo MAPE >= threshold
                all   : dispara se todos os grupos MAPE >= threshold
                average: dispara se a media dos MAPEs >= threshold
        }
    """
    cfg = alert.rule_config_dict()
    mape_threshold = float(cfg.get("mape_threshold", 30.0))
    scope = cfg.get("scope", "any")

    if not alert.target_id:
        raise AlertEvalError("target_id (forecast_id) obrigatorio.")

    forecast = db.get(Forecast, alert.target_id)
    if not forecast:
        raise AlertEvalError(f"Forecast {alert.target_id} nao encontrado.")

    metrics_dict = forecast.last_metrics_dict()
    if not metrics_dict:
        return EvalOutcome(
            fired=False,
            message=f"Forecast '{forecast.name}' nao tem metricas. Rode Train primeiro.",
            context={"forecast_id": forecast.id},
        )

    # Coleta MAPEs validos
    mapes = []
    per_group = {}
    for group, m in metrics_dict.items():
        mape = m.get("mape") if isinstance(m, dict) else None
        if mape is not None:
            mapes.append(float(mape))
            per_group[group] = float(mape)

    if not mapes:
        return EvalOutcome(
            fired=False,
            message="Nenhum MAPE valido para avaliar.",
            context={"forecast_id": forecast.id, "metrics": metrics_dict},
        )

    if scope == "any":
        fired = any(m >= mape_threshold for m in mapes)
        observed = max(mapes)
        scope_label = "max"
    elif scope == "all":
        fired = all(m >= mape_threshold for m in mapes)
        observed = min(mapes)
        scope_label = "min"
    else:  # average
        observed = sum(mapes) / len(mapes)
        fired = observed >= mape_threshold
        scope_label = "avg"

    title = f"Forecast '{forecast.name}' MAPE {scope_label}={observed:.2f}%"
    if fired:
        violated = {g: v for g, v in per_group.items() if v >= mape_threshold}
        message = (
            f"MAPE observado ({scope}) = {observed:.2f}% supera o limite de {mape_threshold}%. "
            f"Grupos violando: {len(violated)}/{len(per_group)}"
        )
    else:
        message = f"MAPE observado ({scope}) = {observed:.2f}% dentro do limite ({mape_threshold}%)."

    return EvalOutcome(
        fired=fired,
        title=title,
        message=message,
        context={
            "forecast_id": forecast.id,
            "forecast_name": forecast.name,
            "algorithm": forecast.algorithm,
            "observed_mape": observed,
            "threshold": mape_threshold,
            "scope": scope,
            "per_group": per_group,
        },
    )


def _eval_pipeline_failure(db: Session, alert: Alert) -> EvalOutcome:
    """rule_config:
        {
            "lookback_minutes": 60   # so dispara se o failure aconteceu nos ultimos N min
        }
    """
    cfg = alert.rule_config_dict()
    lookback_min = int(cfg.get("lookback_minutes", 60))

    if not alert.target_id:
        raise AlertEvalError("target_id (pipeline_id) obrigatorio.")

    pipeline = db.get(Pipeline, alert.target_id)
    if not pipeline:
        raise AlertEvalError(f"Pipeline {alert.target_id} nao encontrado.")

    last_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.pipeline_id == pipeline.id)
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if not last_run:
        return EvalOutcome(
            fired=False,
            message=f"Pipeline '{pipeline.name}' ainda nao executou.",
            context={"pipeline_id": pipeline.id},
        )

    is_failed = last_run.status == RunStatus.FAILED.value
    fresh = (datetime.utcnow() - last_run.started_at) <= timedelta(minutes=lookback_min)
    fired = is_failed and fresh

    title = f"Pipeline '{pipeline.name}' - last run: {last_run.status}"
    if fired:
        step_info = ""
        if last_run.failed_step_index is not None:
            step_info = (
                f" no step #{last_run.failed_step_index + 1} "
                f"({last_run.failed_step_name}/{last_run.failed_step_type})"
            )
        message = (
            f"Pipeline FALHOU{step_info}: {last_run.error_message or 'erro desconhecido'}"
        )
    elif is_failed:
        message = f"Pipeline ja falhou em {last_run.started_at.isoformat()} mas fora do lookback ({lookback_min}min)."
    else:
        message = f"Last run OK: {last_run.status}."

    return EvalOutcome(
        fired=fired,
        title=title,
        message=message,
        context={
            "pipeline_id": pipeline.id,
            "pipeline_name": pipeline.name,
            "last_run_id": last_run.id,
            "last_run_status": last_run.status,
            "last_run_started_at": last_run.started_at.isoformat()
            if last_run.started_at
            else None,
            "failed_step_index": last_run.failed_step_index,
            "failed_step_name": last_run.failed_step_name,
            "failed_step_type": last_run.failed_step_type,
            "error_message": last_run.error_message,
            "lookback_minutes": lookback_min,
        },
    )


def _eval_dashboard_stale(db: Session, alert: Alert) -> EvalOutcome:
    """rule_config:
        {
            "max_age_days": 7
        }
    """
    cfg = alert.rule_config_dict()
    max_age_days = int(cfg.get("max_age_days", 7))

    if not alert.target_id:
        raise AlertEvalError("target_id (dashboard_id) obrigatorio.")

    dash = db.get(Dashboard, alert.target_id)
    if not dash:
        raise AlertEvalError(f"Dashboard {alert.target_id} nao encontrado.")

    if dash.status != DashboardStatus.PUBLISHED.value:
        return EvalOutcome(
            fired=False,
            message=f"Dashboard '{dash.name}' nao esta Published (status={dash.status}).",
            context={"dashboard_id": dash.id, "status": dash.status},
        )

    ref = dash.updated_at or dash.published_at or dash.created_at
    age = datetime.utcnow() - ref
    age_days = age.total_seconds() / 86400.0
    fired = age_days >= max_age_days

    title = f"Dashboard '{dash.name}' tem {age_days:.1f} dias sem atualizacao"
    if fired:
        message = (
            f"Excedeu max_age_days={max_age_days}. Ultima atualizacao: {ref.isoformat()}."
        )
    else:
        message = f"Atualizado ha {age_days:.1f} dias (limite: {max_age_days})."

    return EvalOutcome(
        fired=fired,
        title=title,
        message=message,
        context={
            "dashboard_id": dash.id,
            "dashboard_name": dash.name,
            "last_update": ref.isoformat() if ref else None,
            "age_days": age_days,
            "max_age_days": max_age_days,
        },
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_EVALUATORS = {
    AlertType.METRIC_THRESHOLD.value: _eval_metric_threshold,
    AlertType.METRIC_CHANGE.value: _eval_metric_change,
    AlertType.FORECAST_QUALITY.value: _eval_forecast_quality,
    AlertType.PIPELINE_FAILURE.value: _eval_pipeline_failure,
    AlertType.DASHBOARD_STALE.value: _eval_dashboard_stale,
}


def evaluate(db: Session, alert: Alert) -> EvalOutcome:
    fn = _EVALUATORS.get(alert.alert_type)
    if not fn:
        raise AlertEvalError(f"alert_type desconhecido: {alert.alert_type}")
    return fn(db, alert)


def in_cooldown(alert: Alert) -> bool:
    """Verifica se o alert esta em cooldown (disparou recentemente)."""
    if not alert.last_fired_at or alert.cooldown_minutes <= 0:
        return False
    elapsed = datetime.utcnow() - alert.last_fired_at
    return elapsed < timedelta(minutes=alert.cooldown_minutes)


# ---------------------------------------------------------------------------
# Validacao de severity / type
# ---------------------------------------------------------------------------

def validate_alert_type(t: str) -> None:
    valid = {a.value for a in AlertType}
    if t not in valid:
        raise AlertEvalError(f"alert_type invalido: {t}. Validos: {sorted(valid)}")


def validate_severity(s: str) -> None:
    valid = {a.value for a in AlertSeverity}
    if s not in valid:
        raise AlertEvalError(f"severity invalido: {s}. Validos: {sorted(valid)}")
