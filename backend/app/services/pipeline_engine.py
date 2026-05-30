"""Executor de Pipelines (Phase 3b - ETL Builder).

Executa sequencia LINEAR de steps em Pandas. Cada step recebe o DataFrame
do anterior (ou cria/junta com outro dataset) e devolve um DataFrame.

Suporta dois modos:
    - execute(): roda tudo, grava TARGET, retorna dataset_id criado
    - preview(): roda steps[0..up_to_index], retorna amostra do DataFrame

Operadores (10):
    SOURCE  : carrega um dataset existente (parquet)
    FILTER  : aplica condicoes AND (col op value)
    SELECT  : seleciona/renomeia colunas
    COMPUTED: cria coluna via expressao pandas.eval (segura)
    GROUP_BY: groupby + agregacoes (sum/avg/min/max/count)
    JOIN    : join com outro dataset
    UNION   : concat com outros datasets
    SORT    : ordena por colunas
    LIMIT   : top N rows
    TARGET  : grava DataFrame como Dataset (parquet + registro DB)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import pandas as pd
from sqlalchemy.orm import Session

from app.models.dataset import Dataset, DatasetSourceType, DatasetStatus
from app.models.pipeline import StepType
from app.utils.file_utils import save_parquet
from config import settings


class PipelineError(Exception):
    """Erro de execucao de pipeline."""


@dataclass
class StepResult:
    step_index: int
    step_type: str
    step_name: str
    rows_in: int
    rows_out: int
    duration_ms: int
    note: str = ""


@dataclass
class ExecutionResult:
    df: pd.DataFrame | None = None
    logs: list[StepResult] = field(default_factory=list)
    target_dataset_id: int | None = None

    def total_rows_in(self) -> int:
        # rows lidas do source (step 0): rows_in do SOURCE e 0, entao usamos rows_out
        return self.logs[0].rows_out if self.logs else 0

    def total_rows_out(self) -> int:
        return self.logs[-1].rows_out if self.logs else 0


class StepFailure(PipelineError):
    """Erro com contexto de qual step falhou (index 0-based)."""

    def __init__(self, step_index: int, step_name: str, step_type: str, message: str):
        self.step_index = step_index
        self.step_name = step_name
        self.step_type = step_type
        self.original_message = message
        super().__init__(
            f"[step {step_index + 1}: {step_name} ({step_type})] {message}"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dataset_df(ds: Dataset, sample: int | None = None) -> pd.DataFrame:
    if not ds.processed_path:
        raise PipelineError(f"Dataset '{ds.name}' sem parquet processado.")
    path = Path(ds.processed_path)
    if not path.exists():
        raise PipelineError(f"Parquet nao encontrado: {path}")
    df = pd.read_parquet(path)
    if sample and sample > 0:
        df = df.head(sample)
    return df


def _ensure_columns(df: pd.DataFrame, cols: list[str], step: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise PipelineError(f"[{step}] Colunas inexistentes: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Operadores
# ---------------------------------------------------------------------------

def _op_source(
    cfg: dict,
    dataset_resolver: Callable[[int], Dataset | None],
    sample: int | None,
) -> pd.DataFrame:
    dataset_id = cfg.get("dataset_id")
    if not dataset_id:
        raise PipelineError("SOURCE exige config.dataset_id")
    ds = dataset_resolver(int(dataset_id))
    if not ds:
        raise PipelineError(f"Dataset {dataset_id} nao encontrado / sem permissao.")
    return _load_dataset_df(ds, sample=sample)


_FILTER_OPS = {
    "==": lambda s, v: s == v,
    "!=": lambda s, v: s != v,
    ">":  lambda s, v: s > v,
    "<":  lambda s, v: s < v,
    ">=": lambda s, v: s >= v,
    "<=": lambda s, v: s <= v,
    "in": lambda s, v: s.isin(v if isinstance(v, list) else [v]),
    "not_in": lambda s, v: ~s.isin(v if isinstance(v, list) else [v]),
    "contains": lambda s, v: s.astype(str).str.contains(str(v), case=False, na=False),
    "is_null": lambda s, _v: s.isna(),
    "is_not_null": lambda s, _v: s.notna(),
}


def _coerce_value(series: pd.Series, value):
    """Coerce filter value to the series dtype (best-effort)."""
    if value is None:
        return None
    if pd.api.types.is_numeric_dtype(series):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if pd.api.types.is_datetime64_any_dtype(series):
        try:
            return pd.to_datetime(value)
        except Exception:
            return value
    return value


def _op_filter(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    conditions = cfg.get("conditions") or []
    if not conditions:
        return df
    mask = pd.Series(True, index=df.index)
    for cond in conditions:
        col = cond.get("col")
        op = cond.get("op", "==")
        val = cond.get("value")
        if not col:
            continue
        _ensure_columns(df, [col], "FILTER")
        if op not in _FILTER_OPS:
            raise PipelineError(f"[FILTER] Operador invalido: {op}")
        coerced = _coerce_value(df[col], val) if isinstance(val, (str, int, float)) else val
        mask &= _FILTER_OPS[op](df[col], coerced)
    return df[mask]


def _op_select(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    columns = cfg.get("columns") or list(df.columns)
    rename = cfg.get("rename") or {}
    _ensure_columns(df, columns, "SELECT")
    out = df[columns].copy()
    if rename:
        out = out.rename(columns=rename)
    return out


def _op_computed(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    new_col = cfg.get("new_col")
    expr = cfg.get("expression")
    if not new_col or not isinstance(new_col, str):
        raise PipelineError("COMPUTED exige config.new_col (string)")
    if not expr or not isinstance(expr, str):
        raise PipelineError("COMPUTED exige config.expression (string)")
    if len(expr) > 500:
        raise PipelineError("COMPUTED expression muito longa (>500 chars)")
    # pandas.eval e seguro: nao executa codigo Python arbitrario. Suporta:
    # operadores aritmeticos (+ - * / ** %), comparacoes, & |, e fn matematicas via numexpr.
    try:
        result = df.eval(expr, engine="python")
    except Exception as exc:
        raise PipelineError(f"COMPUTED falhou: {exc}") from exc
    out = df.copy()
    out[new_col] = result
    return out


_AGG_FUNCS = {
    "sum": "sum",
    "avg": "mean",
    "mean": "mean",
    "min": "min",
    "max": "max",
    "count": "count",
    "nunique": "nunique",
}


def _op_group_by(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    by = cfg.get("by") or []
    aggs = cfg.get("aggs") or []
    if not by or not aggs:
        raise PipelineError("GROUP_BY exige config.by (list) e config.aggs (list)")
    _ensure_columns(df, by, "GROUP_BY")
    agg_map: dict[str, list] = {}
    rename_map: dict[str, str] = {}
    for a in aggs:
        col = a.get("col")
        func = (a.get("func") or "sum").lower()
        alias = a.get("as") or f"{func}_{col}"
        if func not in _AGG_FUNCS:
            raise PipelineError(f"[GROUP_BY] funcao agg invalida: {func}")
        if not col:
            raise PipelineError("[GROUP_BY] agg sem 'col'")
        _ensure_columns(df, [col], "GROUP_BY")
        agg_map.setdefault(col, []).append(_AGG_FUNCS[func])
        rename_map[f"{col}_{_AGG_FUNCS[func]}"] = alias
    grouped = df.groupby(by, dropna=False, as_index=False).agg(agg_map)
    # Flatten columns: (col, func) -> col_func
    grouped.columns = [
        "_".join([str(c) for c in col]).strip("_") if isinstance(col, tuple) else col
        for col in grouped.columns
    ]
    grouped = grouped.rename(columns=rename_map)
    return grouped


def _op_join(
    df: pd.DataFrame,
    cfg: dict,
    dataset_resolver: Callable[[int], Dataset | None],
    sample: int | None,
) -> pd.DataFrame:
    right_id = cfg.get("right_dataset_id")
    how = cfg.get("how", "left")
    left_on = cfg.get("left_on")
    right_on = cfg.get("right_on")
    if not right_id or not left_on or not right_on:
        raise PipelineError(
            "JOIN exige config.right_dataset_id, config.left_on, config.right_on"
        )
    if how not in {"left", "right", "inner", "outer"}:
        raise PipelineError(f"[JOIN] how invalido: {how}")
    right_ds = dataset_resolver(int(right_id))
    if not right_ds:
        raise PipelineError(f"JOIN: dataset {right_id} nao encontrado.")
    right_df = _load_dataset_df(right_ds, sample=sample)
    _ensure_columns(df, [left_on], "JOIN")
    _ensure_columns(right_df, [right_on], "JOIN")
    suffix = cfg.get("suffix", "_right")
    return df.merge(
        right_df, how=how, left_on=left_on, right_on=right_on, suffixes=("", suffix)
    )


def _op_union(
    df: pd.DataFrame,
    cfg: dict,
    dataset_resolver: Callable[[int], Dataset | None],
    sample: int | None,
) -> pd.DataFrame:
    ds_ids = cfg.get("datasets") or []
    if not ds_ids:
        raise PipelineError("UNION exige config.datasets (list[int])")
    frames = [df]
    for did in ds_ids:
        right = dataset_resolver(int(did))
        if not right:
            raise PipelineError(f"UNION: dataset {did} nao encontrado.")
        frames.append(_load_dataset_df(right, sample=sample))
    return pd.concat(frames, ignore_index=True, sort=False)


def _op_sort(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    by = cfg.get("by") or []
    asc_raw = cfg.get("ascending")
    if not by:
        return df
    _ensure_columns(df, by, "SORT")
    if isinstance(asc_raw, list):
        ascending = asc_raw
    elif isinstance(asc_raw, bool):
        ascending = asc_raw
    else:
        ascending = True
    return df.sort_values(by=by, ascending=ascending, na_position="last")


def _op_limit(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    n = int(cfg.get("n", 1000))
    if n <= 0:
        return df
    return df.head(n)


def _op_target(
    df: pd.DataFrame,
    cfg: dict,
    db: Session,
    created_by: str,
    pipeline_id: int,
) -> tuple[pd.DataFrame, int]:
    """Grava DataFrame como Dataset novo (ou atualiza se ja existe um do mesmo pipeline)."""
    dataset_name = cfg.get("dataset_name") or f"Pipeline {pipeline_id} output"
    workspace = cfg.get("workspace") or "LATAM"
    business_area = cfg.get("business_area") or ""
    description = cfg.get("description") or f"Generated by pipeline #{pipeline_id}"
    overwrite_id = cfg.get("dataset_id")  # se passado, atualiza dataset existente

    # Cria ou atualiza Dataset
    if overwrite_id:
        ds = db.get(Dataset, int(overwrite_id))
        if not ds:
            raise PipelineError(f"TARGET: dataset {overwrite_id} nao encontrado para overwrite.")
        ds.row_count = int(len(df))
        ds.column_count = int(df.shape[1])
        ds.source_type = DatasetSourceType.ETL_OUTPUT.value
    else:
        ds = Dataset(
            name=dataset_name,
            description=description,
            workspace=workspace,
            business_area=business_area,
            source_type=DatasetSourceType.ETL_OUTPUT.value,
            row_count=int(len(df)),
            column_count=int(df.shape[1]),
            status=DatasetStatus.VALIDATED.value,
            created_by=created_by,
        )
        db.add(ds)
        db.flush()

    processed_path = (settings.processed_dir / f"dataset_{ds.id}.parquet").resolve()
    save_parquet(df, processed_path)
    ds.processed_path = str(processed_path)

    # Recria DatasetColumns (profiling rapido)
    from app.models.dataset import DatasetColumn
    from app.services.profiling_service import profile_dataframe, serialize_sample_values

    db.query(DatasetColumn).filter(DatasetColumn.dataset_id == ds.id).delete()
    profiles = profile_dataframe(df)
    for idx, prof in enumerate(profiles):
        db.add(
            DatasetColumn(
                dataset_id=ds.id,
                position=idx,
                name=prof.name,
                dtype=prof.dtype,
                null_count=prof.null_count,
                distinct_count=prof.distinct_count,
                min_value=prof.min_value,
                max_value=prof.max_value,
                mean_value=(
                    prof.mean_value
                    if prof.mean_value is not None
                    and not (isinstance(prof.mean_value, float) and math.isnan(prof.mean_value))
                    else None
                ),
                std_value=(
                    prof.std_value
                    if prof.std_value is not None
                    and not (isinstance(prof.std_value, float) and math.isnan(prof.std_value))
                    else None
                ),
                sample_values=serialize_sample_values(prof.sample_values),
            )
        )
    db.flush()
    return df, ds.id


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def _run_step(
    df_in: pd.DataFrame | None,
    step_type: str,
    cfg: dict,
    *,
    dataset_resolver: Callable[[int], Dataset | None],
    db: Session | None,
    created_by: str,
    pipeline_id: int,
    sample: int | None,
    persist_target: bool,
) -> tuple[pd.DataFrame, int | None]:
    """Roda 1 step e retorna (df_out, target_dataset_id|None)."""
    if step_type == StepType.SOURCE.value:
        return _op_source(cfg, dataset_resolver, sample), None

    if df_in is None:
        raise PipelineError(f"Step '{step_type}' precisa de SOURCE antes.")

    if step_type == StepType.FILTER.value:
        return _op_filter(df_in, cfg), None
    if step_type == StepType.SELECT.value:
        return _op_select(df_in, cfg), None
    if step_type == StepType.COMPUTED_COLUMN.value:
        return _op_computed(df_in, cfg), None
    if step_type == StepType.GROUP_BY.value:
        return _op_group_by(df_in, cfg), None
    if step_type == StepType.JOIN.value:
        return _op_join(df_in, cfg, dataset_resolver, sample), None
    if step_type == StepType.UNION.value:
        return _op_union(df_in, cfg, dataset_resolver, sample), None
    if step_type == StepType.SORT.value:
        return _op_sort(df_in, cfg), None
    if step_type == StepType.LIMIT.value:
        return _op_limit(df_in, cfg), None
    if step_type == StepType.TARGET.value:
        if not persist_target or db is None:
            # Modo preview: nao grava, apenas passa adiante
            return df_in, None
        df_out, ds_id = _op_target(df_in, cfg, db, created_by, pipeline_id)
        return df_out, ds_id
    raise PipelineError(f"step_type desconhecido: {step_type}")


def execute(
    steps: list[dict],
    *,
    dataset_resolver: Callable[[int], Dataset | None],
    db: Session,
    created_by: str,
    pipeline_id: int,
    persist_target: bool = True,
    sample: int | None = None,
    up_to_index: int = -1,
) -> ExecutionResult:
    """Executa lista de steps. Cada step e um dict {step_type, name, config}.

    up_to_index: -1 = roda todos; >=0 = roda apenas steps[0..up_to_index] (inclusive).
    persist_target: se False, TARGET vira no-op (modo preview).
    """
    if not steps:
        raise PipelineError("Pipeline sem steps.")

    last_idx = len(steps) - 1 if up_to_index < 0 else min(up_to_index, len(steps) - 1)

    result = ExecutionResult()
    df: pd.DataFrame | None = None

    for i, step in enumerate(steps):
        if i > last_idx:
            break
        step_type = step.get("step_type")
        cfg = step.get("config") or {}
        name = step.get("name") or step_type
        rows_in = int(len(df)) if df is not None else 0
        t0 = time.perf_counter()
        try:
            df, ds_id = _run_step(
                df,
                step_type,
                cfg,
                dataset_resolver=dataset_resolver,
                db=db,
                created_by=created_by,
                pipeline_id=pipeline_id,
                sample=sample,
                persist_target=persist_target,
            )
        except StepFailure:
            raise  # ja contextualizado
        except PipelineError as exc:
            raise StepFailure(i, name, step_type, str(exc)) from exc
        except Exception as exc:
            raise StepFailure(i, name, step_type, f"erro inesperado: {exc}") from exc
        dt = int((time.perf_counter() - t0) * 1000)
        rows_out = int(len(df)) if df is not None else 0
        result.logs.append(
            StepResult(
                step_index=i,
                step_type=step_type,
                step_name=name,
                rows_in=rows_in,
                rows_out=rows_out,
                duration_ms=dt,
            )
        )
        if ds_id is not None:
            result.target_dataset_id = ds_id

    result.df = df
    return result


def preview(
    steps: list[dict],
    *,
    dataset_resolver: Callable[[int], Dataset | None],
    up_to_index: int = -1,
    sample_rows: int = 50,
) -> dict:
    """Preview rapido: roda steps[0..up_to_index] sem persistir nada.

    Retorna {columns, rows, total_rows, schema, notes}.
    """
    # Para preview, usamos um Session fake-ish: passamos db=None com persist_target=False
    res = execute(
        steps,
        dataset_resolver=dataset_resolver,
        db=None,  # type: ignore[arg-type]
        created_by="preview",
        pipeline_id=0,
        persist_target=False,
        sample=None,  # nao limita o source aqui - so limitamos no output final
        up_to_index=up_to_index,
    )
    df = res.df
    if df is None or df.empty:
        return {
            "columns": [],
            "rows": [],
            "total_rows": 0,
            "dataframe_schema": [],
            "notes": "DataFrame vazio.",
        }
    dataframe_schema = [{"name": str(c), "dtype": str(df[c].dtype)} for c in df.columns]
    head = df.head(sample_rows).copy()
    # Datetime -> ISO; NaN -> None
    for c in head.columns:
        if pd.api.types.is_datetime64_any_dtype(head[c]):
            head[c] = head[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    head = head.where(pd.notna(head), None)
    return {
        "columns": [str(c) for c in df.columns],
        "rows": head.to_dict(orient="records"),
        "total_rows": int(len(df)),
        "dataframe_schema": dataframe_schema,
        "notes": "",
    }
