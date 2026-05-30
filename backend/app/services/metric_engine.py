"""Motor de cálculo de métricas (camada semântica).

Pode operar sobre:
    - um DataFrame inteiro (calcula valor escalar)
    - um DataFrame agrupado (passa antes do groupby/aggregate quando usado por dashboard_engine)

NÃO usamos `eval()` aberto. CUSTOM_LIMITED é um mini-parser que aceita só
SUM/COUNT/AVG/MIN/MAX/DIVIDE/ADD/SUB e números literais.

Para métricas temporais (MTD/YTD/YOY) precisamos da coluna de data. O resultado
é o valor do período corrente menos/dividido pelo período de comparação.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd


class MetricError(ValueError):
    """Erro semântico ao calcular métrica (config inválida, coluna ausente, etc)."""


# ---------------------------------------------------------------------------
# Helpers                                                                    
# ---------------------------------------------------------------------------

def _require_column(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        raise MetricError(f"Coluna '{column}' não existe no dataset.")
    return df[column]


def _numeric_or_raise(series: pd.Series, op: str) -> pd.Series:
    if not pd.api.types.is_numeric_dtype(series):
        raise MetricError(f"Operação '{op}' requer coluna numérica, '{series.name}' é {series.dtype}.")
    return series


def _safe_divide(a: float, b: float) -> float | None:
    if b is None or b == 0 or (isinstance(b, float) and math.isnan(b)):
        return None
    return float(a) / float(b)


def _scalar_or_none(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Cálculos básicos                                                           
# ---------------------------------------------------------------------------

def _calc_sum(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    if not col:
        raise MetricError("SUM exige config.column")
    s = _numeric_or_raise(_require_column(df, col), "SUM")
    return _scalar_or_none(s.sum())


def _calc_average(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    if not col:
        raise MetricError("AVERAGE exige config.column")
    s = _numeric_or_raise(_require_column(df, col), "AVERAGE")
    return _scalar_or_none(s.mean())


def _calc_count(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    distinct = bool(cfg.get("distinct", False))
    if not col:
        return _scalar_or_none(len(df))
    s = _require_column(df, col)
    if distinct:
        return _scalar_or_none(s.nunique(dropna=True))
    return _scalar_or_none(s.notna().sum())


def _calc_min(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    if not col:
        raise MetricError("MIN exige config.column")
    s = _numeric_or_raise(_require_column(df, col), "MIN")
    return _scalar_or_none(s.min())


def _calc_max(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    if not col:
        raise MetricError("MAX exige config.column")
    s = _numeric_or_raise(_require_column(df, col), "MAX")
    return _scalar_or_none(s.max())


def _calc_ratio(df: pd.DataFrame, cfg: dict) -> float | None:
    num = cfg.get("numerator")
    den = cfg.get("denominator")
    if not num or not den:
        raise MetricError("RATIO exige numerator e denominator")
    n = _numeric_or_raise(_require_column(df, num), "RATIO").sum()
    d = _numeric_or_raise(_require_column(df, den), "RATIO").sum()
    return _safe_divide(n, d)


def _calc_variation_abs(df: pd.DataFrame, cfg: dict) -> float | None:
    actual = cfg.get("actual")
    baseline = cfg.get("baseline")
    if not actual or not baseline:
        raise MetricError("VARIATION_ABS exige actual e baseline (colunas)")
    a = _numeric_or_raise(_require_column(df, actual), "VARIATION_ABS").sum()
    b = _numeric_or_raise(_require_column(df, baseline), "VARIATION_ABS").sum()
    return _scalar_or_none(a - b)


def _calc_variation_pct(df: pd.DataFrame, cfg: dict) -> float | None:
    actual = cfg.get("actual")
    baseline = cfg.get("baseline")
    if not actual or not baseline:
        raise MetricError("VARIATION_PCT exige actual e baseline (colunas)")
    a = _numeric_or_raise(_require_column(df, actual), "VARIATION_PCT").sum()
    b = _numeric_or_raise(_require_column(df, baseline), "VARIATION_PCT").sum()
    return _safe_divide(a - b, b)


# ---------------------------------------------------------------------------
# Temporais (MTD / YTD / YOY)                                                
# ---------------------------------------------------------------------------

def _ensure_date_col(df: pd.DataFrame, col: str) -> pd.DataFrame:
    s = _require_column(df, col)
    if not pd.api.types.is_datetime64_any_dtype(s):
        try:
            df = df.copy()
            df[col] = pd.to_datetime(df[col], errors="coerce")
        except Exception as exc:
            raise MetricError(f"Falha ao converter coluna '{col}' para data: {exc}") from exc
    return df


def _max_date(df: pd.DataFrame, date_col: str) -> pd.Timestamp | None:
    s = df[date_col].dropna()
    if s.empty:
        return None
    return pd.Timestamp(s.max())


def _calc_mtd(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    date_col = cfg.get("date_column")
    if not col or not date_col:
        raise MetricError("MTD exige column e date_column")
    df = _ensure_date_col(df, date_col)
    ref = _max_date(df, date_col)
    if ref is None:
        return None
    mask = (df[date_col].dt.year == ref.year) & (df[date_col].dt.month == ref.month)
    s = _numeric_or_raise(_require_column(df[mask], col), "MTD")
    return _scalar_or_none(s.sum())


def _calc_ytd(df: pd.DataFrame, cfg: dict) -> float | None:
    col = cfg.get("column")
    date_col = cfg.get("date_column")
    if not col or not date_col:
        raise MetricError("YTD exige column e date_column")
    df = _ensure_date_col(df, date_col)
    ref = _max_date(df, date_col)
    if ref is None:
        return None
    mask = (df[date_col].dt.year == ref.year) & (df[date_col] <= ref)
    s = _numeric_or_raise(_require_column(df[mask], col), "YTD")
    return _scalar_or_none(s.sum())


def _calc_yoy(df: pd.DataFrame, cfg: dict) -> float | None:
    """Variação YoY: YTD(ano atual) - YTD(ano anterior) / YTD(ano anterior)."""
    col = cfg.get("column")
    date_col = cfg.get("date_column")
    mode = cfg.get("mode", "percent")  # "percent" ou "abs"
    if not col or not date_col:
        raise MetricError("YOY exige column e date_column")
    df = _ensure_date_col(df, date_col)
    ref = _max_date(df, date_col)
    if ref is None:
        return None
    cur_mask = (df[date_col].dt.year == ref.year) & (df[date_col] <= ref)
    prev_ref = ref - pd.DateOffset(years=1)
    prev_mask = (df[date_col].dt.year == prev_ref.year) & (df[date_col] <= prev_ref)
    cur = _numeric_or_raise(_require_column(df[cur_mask], col), "YOY").sum()
    prev = _numeric_or_raise(_require_column(df[prev_mask], col), "YOY").sum()
    if mode == "abs":
        return _scalar_or_none(cur - prev)
    return _safe_divide(cur - prev, prev)


# ---------------------------------------------------------------------------
# CUSTOM_LIMITED - mini DSL                                                  
# Suporta: SUM(col), AVG(col), MIN(col), MAX(col), COUNT(col),               
#          DIVIDE(a, b), ADD(a, b), SUB(a, b), MULT(a, b)                    
#          literais numéricos e referências a colunas como SUM(col).         
# ---------------------------------------------------------------------------

_FUNC_PATTERN = re.compile(r"^([A-Z]+)\s*\((.*)\)$", re.DOTALL)
_TOKEN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_AGGREGATORS = {"SUM", "AVG", "AVERAGE", "MIN", "MAX", "COUNT"}
_OPERATORS = {"DIVIDE", "ADD", "SUB", "MULT", "SUBTRACT", "MULTIPLY"}


@dataclass
class _ParsedNode:
    func: str
    args: list  # list of _ParsedNode | float | str


def _split_args(arg_str: str) -> list[str]:
    """Divide argumentos por vírgula respeitando parênteses balanceados."""
    parts: list[str] = []
    depth = 0
    current = ""
    for ch in arg_str:
        if ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())
    return parts


def _parse_dsl(expr: str) -> _ParsedNode | float | str:
    expr = expr.strip()
    if not expr:
        raise MetricError("Fórmula vazia")
    # Número?
    try:
        return float(expr)
    except ValueError:
        pass
    m = _FUNC_PATTERN.match(expr)
    if m:
        func = m.group(1).upper()
        args_raw = m.group(2)
        args = [_parse_dsl(a) for a in _split_args(args_raw)] if args_raw.strip() else []
        if func not in _AGGREGATORS and func not in _OPERATORS:
            raise MetricError(f"Função não permitida: {func}")
        return _ParsedNode(func=func, args=args)
    # Nome de coluna?
    if _TOKEN_PATTERN.match(expr):
        return expr
    raise MetricError(f"Expressão inválida: {expr!r}")


def _eval_node(node, df: pd.DataFrame) -> float | None:
    if isinstance(node, float):
        return node
    if isinstance(node, str):
        raise MetricError(
            f"Identificador '{node}' precisa estar dentro de um agregador (ex: SUM({node}))."
        )
    func = node.func
    args = node.args
    if func in _AGGREGATORS:
        if len(args) != 1 or not isinstance(args[0], str):
            raise MetricError(f"{func} aceita exatamente 1 coluna.")
        col_name = args[0]
        if func == "SUM":
            return _calc_sum(df, {"column": col_name})
        if func in {"AVG", "AVERAGE"}:
            return _calc_average(df, {"column": col_name})
        if func == "MIN":
            return _calc_min(df, {"column": col_name})
        if func == "MAX":
            return _calc_max(df, {"column": col_name})
        if func == "COUNT":
            return _calc_count(df, {"column": col_name})
    if func in _OPERATORS:
        if len(args) != 2:
            raise MetricError(f"{func} aceita exatamente 2 argumentos.")
        a = _eval_node(args[0], df)
        b = _eval_node(args[1], df)
        if a is None or b is None:
            return None
        if func == "DIVIDE":
            return _safe_divide(a, b)
        if func in {"SUB", "SUBTRACT"}:
            return a - b
        if func == "ADD":
            return a + b
        if func in {"MULT", "MULTIPLY"}:
            return a * b
    raise MetricError(f"Função desconhecida: {func}")


def _calc_custom_limited(df: pd.DataFrame, cfg: dict) -> float | None:
    expr = cfg.get("formula")
    if not expr or not isinstance(expr, str):
        raise MetricError("CUSTOM_LIMITED exige config.formula (string)")
    if len(expr) > 500:
        raise MetricError("Fórmula muito longa.")
    node = _parse_dsl(expr)
    return _eval_node(node, df)


# ---------------------------------------------------------------------------
# Dispatch                                                                   
# ---------------------------------------------------------------------------

_CALCULATORS = {
    "SUM": _calc_sum,
    "AVERAGE": _calc_average,
    "COUNT": _calc_count,
    "MIN": _calc_min,
    "MAX": _calc_max,
    "RATIO": _calc_ratio,
    "VARIATION_ABS": _calc_variation_abs,
    "VARIATION_PCT": _calc_variation_pct,
    "MTD": _calc_mtd,
    "YTD": _calc_ytd,
    "YOY": _calc_yoy,
    "CUSTOM_LIMITED": _calc_custom_limited,
}


def calc_metric(df: pd.DataFrame, *, formula_type: str, formula_config: dict) -> float | None:
    fn = _CALCULATORS.get(formula_type)
    if not fn:
        raise MetricError(f"Tipo de métrica desconhecido: {formula_type}")
    return fn(df, formula_config or {})


# ---------------------------------------------------------------------------
# Para uso por dashboard_engine quando há groupby                            
# ---------------------------------------------------------------------------

def calc_metric_grouped(
    df: pd.DataFrame,
    *,
    formula_type: str,
    formula_config: dict,
    group_by: str,
) -> pd.DataFrame:
    """Calcula a métrica por grupo. Retorna DataFrame com colunas [group_by, 'value']."""
    if group_by not in df.columns:
        raise MetricError(f"Coluna de agrupamento '{group_by}' não existe.")

    # Para tipos temporais/agregadores simples, somos diretos. Para CUSTOM_LIMITED,
    # rodamos por grupo (mais lento mas correto).
    results = []
    for key, sub in df.groupby(group_by, dropna=False):
        value = calc_metric(sub, formula_type=formula_type, formula_config=formula_config)
        # Converte chaves Timestamp para ISO para serialização limpa.
        if isinstance(key, (pd.Timestamp, np.datetime64)):
            key = pd.Timestamp(key).strftime("%Y-%m-%d")
        results.append({group_by: key if key is not None else "(null)", "value": value})

    out = pd.DataFrame(results)
    return out


# ---------------------------------------------------------------------------
# Formatação para o frontend                                                 
# ---------------------------------------------------------------------------

def format_metric_value(value: float | None, *, output_format: str = "number", decimals: int = 2) -> str:
    if value is None:
        return "—"
    try:
        if output_format == "percent":
            return f"{value * 100:.{decimals}f}%"
        if output_format == "currency":
            return f"$ {value:,.{decimals}f}"
        if output_format == "integer":
            return f"{int(value):,}"
        return f"{value:,.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)
