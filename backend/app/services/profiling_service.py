"""Profiling de DataFrame para alimentar DatasetColumn.

Para cada coluna calculamos:
    - dtype lógico (string / integer / float / date / boolean)
    - null_count
    - distinct_count
    - min / max (string ou data) e mean/std (numéricos)
    - sample_values (até 5 valores distintos para preview)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_count: int
    distinct_count: int
    min_value: str | None
    max_value: str | None
    mean_value: float | None
    std_value: float | None
    sample_values: list[Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "null_count": self.null_count,
            "distinct_count": self.distinct_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "std_value": self.std_value,
            "sample_values": self.sample_values,
        }


def _logical_dtype(series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if pd.api.types.is_numeric_dtype(series):
        return "float"
    return "string"


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        try:
            return pd.Timestamp(value).isoformat()
        except Exception:
            return str(value)
    return str(value)


def _sample_values(series: pd.Series, k: int = 5) -> list[Any]:
    distinct = series.dropna().drop_duplicates().head(k).tolist()
    out: list[Any] = []
    for v in distinct:
        if isinstance(v, (pd.Timestamp, np.datetime64)):
            out.append(pd.Timestamp(v).isoformat())
        elif isinstance(v, (np.integer,)):
            out.append(int(v))
        elif isinstance(v, (np.floating,)):
            out.append(float(v))
        elif isinstance(v, (np.bool_,)):
            out.append(bool(v))
        else:
            out.append(str(v) if not isinstance(v, (int, float, bool, str)) else v)
    return out


def profile_dataframe(df: pd.DataFrame) -> list[ColumnProfile]:
    profiles: list[ColumnProfile] = []
    for col in df.columns:
        s = df[col]
        dtype = _logical_dtype(s)
        null_count = int(s.isna().sum())
        try:
            distinct_count = int(s.nunique(dropna=True))
        except Exception:
            distinct_count = 0

        min_value = max_value = None
        mean_value = std_value = None

        if dtype in {"integer", "float"} and not s.dropna().empty:
            mean_value = float(s.mean())
            std_value = float(s.std()) if len(s.dropna()) > 1 else 0.0
            min_value = _safe_str(s.min())
            max_value = _safe_str(s.max())
        elif dtype == "date" and not s.dropna().empty:
            min_value = _safe_str(s.min())
            max_value = _safe_str(s.max())
        elif dtype == "string" and not s.dropna().empty:
            try:
                min_value = _safe_str(s.dropna().astype(str).min())
                max_value = _safe_str(s.dropna().astype(str).max())
            except Exception:
                min_value = max_value = None

        profiles.append(
            ColumnProfile(
                name=str(col),
                dtype=dtype,
                null_count=null_count,
                distinct_count=distinct_count,
                min_value=min_value,
                max_value=max_value,
                mean_value=mean_value,
                std_value=std_value,
                sample_values=_sample_values(s),
            )
        )
    return profiles


def serialize_sample_values(values: list[Any]) -> str:
    """Converte sample_values para JSON string para persistência."""
    try:
        return json.dumps(values, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps([str(v) for v in values], ensure_ascii=False)
