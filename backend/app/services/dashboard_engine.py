"""Motor de Dashboard - resolve a query de um widget para um payload renderizável.

Cada widget tem:
    widget_type     kpi_card | bar_chart | line_chart | area_chart | pie_chart |
                    donut_chart | table | text_box
    config:
        dataset_id  int - dataset de origem (parquet em storage/processed)
        metric_id   int? - usa Metric persistida (preferencial)
        metric_inline {formula_type, formula_config, output_format, decimals, name}
        dimension   str? - coluna para groupby (charts)
        time_grain  str? - "month" | "quarter" | "year" - quando dimension é data
        filters     dict[str, list|scalar] - filtra rows antes do calc
        sort        "asc" | "desc"
        limit       int - top N
        style       dict - opções visuais (cores, etc - frontend)
        text_content str - para text_box

A saída é sempre o WidgetPreviewResponse do schema (kpi | chart | table | text).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.models.dashboard import WidgetType
from app.models.dataset import Dataset
from app.models.metric import Metric
from app.services.metric_engine import (
    MetricError,
    calc_metric,
    calc_metric_grouped,
    format_metric_value,
)


class DashboardEngineError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Helpers                                                                    
# ---------------------------------------------------------------------------

def _load_dataset_df(ds: Dataset) -> pd.DataFrame:
    p = Path(ds.processed_path)
    if not p.exists():
        raise DashboardEngineError(
            f"Parquet do dataset '{ds.name}' não encontrado em disco."
        )
    return pd.read_parquet(p)


def _apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """filters = {"country": "Brazil"} ou {"country": ["Brazil", "Mexico"]}
    ou {"revenue__gte": 1000} (sufixos: __gte/__lte/__gt/__lt/__ne).
    """
    if not filters:
        return df
    out = df
    for raw_key, value in filters.items():
        col = raw_key
        op = "eq"
        for suffix in ("__gte", "__lte", "__gt", "__lt", "__ne"):
            if raw_key.endswith(suffix):
                col = raw_key[: -len(suffix)]
                op = suffix.strip("_")
                break
        if col not in out.columns:
            continue  # silenciosamente ignora filtros de colunas inexistentes
        s = out[col]
        if op == "eq":
            if isinstance(value, list):
                out = out[s.isin(value)]
            elif value is not None and value != "":
                out = out[s == value]
        elif op == "ne":
            out = out[s != value]
        elif op == "gte":
            out = out[s >= value]
        elif op == "lte":
            out = out[s <= value]
        elif op == "gt":
            out = out[s > value]
        elif op == "lt":
            out = out[s < value]
    return out


def _apply_time_grain(series: pd.Series, grain: str) -> pd.Series:
    s = pd.to_datetime(series, errors="coerce")
    if grain == "year":
        return s.dt.to_period("Y").dt.strftime("%Y")
    if grain == "quarter":
        return s.dt.to_period("Q").dt.strftime("%Y-Q%q")
    if grain == "month":
        return s.dt.to_period("M").dt.strftime("%Y-%m")
    if grain == "week":
        return s.dt.to_period("W").dt.strftime("%Y-W%U")
    if grain == "day":
        return s.dt.strftime("%Y-%m-%d")
    return series


def _is_date_column(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns and pd.api.types.is_datetime64_any_dtype(df[col])


def _resolve_metric_config(metric: Metric | None, inline: dict | None) -> dict:
    """Retorna {formula_type, formula_config, output_format, decimals, name}."""
    if metric:
        return {
            "formula_type": metric.formula_type,
            "formula_config": metric.config_dict(),
            "output_format": metric.output_format,
            "decimals": metric.decimals,
            "name": metric.name,
        }
    if inline:
        return {
            "formula_type": inline.get("formula_type", "SUM"),
            "formula_config": inline.get("formula_config", {}),
            "output_format": inline.get("output_format", "number"),
            "decimals": int(inline.get("decimals", 2)),
            "name": inline.get("name", "metric"),
        }
    raise DashboardEngineError("Widget exige metric_id ou metric_inline.")


# ---------------------------------------------------------------------------
# Resolução por tipo                                                         
# ---------------------------------------------------------------------------

def _resolve_kpi(df: pd.DataFrame, metric_cfg: dict, config: dict) -> dict:
    """KPI = valor escalar + (opcional) delta vs baseline (filtros comparativos)."""
    try:
        value = calc_metric(
            df,
            formula_type=metric_cfg["formula_type"],
            formula_config=metric_cfg["formula_config"],
        )
    except MetricError as exc:
        raise DashboardEngineError(str(exc)) from exc
    formatted = format_metric_value(
        value,
        output_format=metric_cfg["output_format"],
        decimals=metric_cfg["decimals"],
    )
    return {
        "value": value,
        "formatted": formatted,
        "label": config.get("label") or metric_cfg["name"],
        "output_format": metric_cfg["output_format"],
        "decimals": metric_cfg["decimals"],
        "delta": None,  # extensão futura: comparativo
    }


def _resolve_chart(df: pd.DataFrame, metric_cfg: dict, config: dict) -> dict:
    """Charts (bar/line/area/pie/donut): groupby por dimensão + aggregate."""
    dimension = config.get("dimension")
    if not dimension:
        raise DashboardEngineError("Widget de chart exige 'dimension'.")
    if dimension not in df.columns:
        raise DashboardEngineError(f"Coluna de dimensão '{dimension}' não existe no dataset.")

    work = df.copy()
    time_grain = config.get("time_grain")
    if time_grain and _is_date_column(work, dimension):
        work[dimension] = _apply_time_grain(work[dimension], time_grain)

    try:
        grouped = calc_metric_grouped(
            work,
            formula_type=metric_cfg["formula_type"],
            formula_config=metric_cfg["formula_config"],
            group_by=dimension,
        )
    except MetricError as exc:
        raise DashboardEngineError(str(exc)) from exc

    grouped = grouped.dropna(subset=["value"])
    sort_dir = config.get("sort", "desc")
    if config.get("sort_by", "value") == dimension:
        grouped = grouped.sort_values(dimension, ascending=(sort_dir == "asc"))
    else:
        grouped = grouped.sort_values("value", ascending=(sort_dir == "asc"))

    limit = int(config.get("limit", 50))
    if limit > 0:
        grouped = grouped.head(limit)

    categories = [str(c) for c in grouped[dimension].tolist()]
    values = [float(v) if v is not None and not pd.isna(v) else None for v in grouped["value"].tolist()]

    return {
        "metric_name": metric_cfg["name"],
        "output_format": metric_cfg["output_format"],
        "decimals": metric_cfg["decimals"],
        "categories": categories,
        "series": [
            {
                "name": metric_cfg["name"],
                "values": values,
            }
        ],
    }


def _resolve_table(df: pd.DataFrame, config: dict) -> dict:
    """Table: lista colunas + filtros + sort + limit. Sem agregação."""
    columns = config.get("columns") or [str(c) for c in df.columns]
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DashboardEngineError(f"Colunas inexistentes: {', '.join(missing)}")

    out = df[columns].copy()
    sort_by = config.get("sort_by")
    if sort_by and sort_by in out.columns:
        out = out.sort_values(sort_by, ascending=(config.get("sort", "asc") == "asc"))

    limit = int(config.get("limit", 100))
    if limit > 0:
        out = out.head(limit)

    # Datetime -> ISO
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime("%Y-%m-%d")
    out = out.where(pd.notna(out), None)

    return {
        "columns": columns,
        "rows": out.to_dict(orient="records"),
        "total_rows": int(len(df)),
    }


# ---------------------------------------------------------------------------
# Função pública                                                             
# ---------------------------------------------------------------------------

def render_widget(
    *,
    widget_type: str,
    config: dict,
    title: str,
    dataset_resolver,
    metric_resolver,
) -> dict:
    """Resolve um widget e devolve dict pronto para serializar como WidgetPreviewResponse.

    dataset_resolver(dataset_id) -> Dataset
    metric_resolver(metric_id)   -> Metric | None
    """
    # text_box é trivial
    if widget_type == WidgetType.TEXT_BOX.value:
        return {
            "widget_type": widget_type,
            "title": title,
            "kpi": None,
            "chart": None,
            "table": None,
            "text": str(config.get("text_content", "")),
            "rows_used": 0,
            "notes": "",
        }

    dataset_id = config.get("dataset_id")
    if not dataset_id:
        raise DashboardEngineError("Widget exige config.dataset_id")
    ds = dataset_resolver(int(dataset_id))
    if not ds:
        raise DashboardEngineError("Dataset não encontrado / sem permissão.")

    df = _load_dataset_df(ds)
    df = _apply_filters(df, config.get("filters") or {})
    rows_used = int(len(df))

    # Tabela nao usa metrica - resolve direto sem exigir metric_id/metric_inline
    if widget_type == WidgetType.TABLE.value:
        return {
            "widget_type": widget_type,
            "title": title or ds.name,
            "kpi": None,
            "chart": None,
            "table": _resolve_table(df, config),
            "text": None,
            "rows_used": rows_used,
            "notes": "",
        }

    metric = None
    metric_id = config.get("metric_id")
    if metric_id:
        metric = metric_resolver(int(metric_id))
        if not metric:
            raise DashboardEngineError("Métrica não encontrada / sem permissão.")
    metric_cfg = _resolve_metric_config(metric, config.get("metric_inline"))

    payload: dict = {
        "widget_type": widget_type,
        "title": title or metric_cfg["name"],
        "kpi": None,
        "chart": None,
        "table": None,
        "text": None,
        "rows_used": rows_used,
        "notes": "",
    }

    if widget_type == WidgetType.KPI_CARD.value:
        payload["kpi"] = _resolve_kpi(df, metric_cfg, config)
        return payload

    # Charts: bar / line / area / pie / donut
    if widget_type in {
        WidgetType.BAR_CHART.value,
        WidgetType.LINE_CHART.value,
        WidgetType.AREA_CHART.value,
        WidgetType.PIE_CHART.value,
        WidgetType.DONUT_CHART.value,
    }:
        payload["chart"] = _resolve_chart(df, metric_cfg, config)
        return payload

    raise DashboardEngineError(f"Tipo de widget desconhecido: {widget_type}")
