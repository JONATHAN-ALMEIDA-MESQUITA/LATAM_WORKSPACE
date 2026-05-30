"""Engine Ad-Hoc Report — SQL controlado via DuckDB (Phase 7).

Regras de seguranca:
    - Apenas SELECT / WITH ... SELECT
    - Bloqueia DDL/DML e funcoes perigosas
    - Dataset exposto como view `data` (parquet read-only)
    - LIMIT forcado no preview
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from app.models.dataset import Dataset


class AdHocQueryError(Exception):
    pass


_FORBIDDEN = re.compile(
    r"\b("
    r"insert|update|delete|drop|create|alter|attach|detach|copy|export|import|"
    r"load|install|pragma|call|execute|grant|revoke|truncate|replace|merge"
    r")\b",
    re.IGNORECASE,
)

# Remove comentarios SQL (-- e /* */)
def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


def validate_sql(sql: str) -> None:
    """Valida que SQL e read-only."""
    if not sql or not sql.strip():
        raise AdHocQueryError("SQL vazio.")
    cleaned = _strip_comments(sql)
    if _FORBIDDEN.search(cleaned):
        raise AdHocQueryError(
            "SQL contem operacao nao permitida. Apenas SELECT/WITH sao aceitos."
        )
    first = cleaned.lstrip().split(None, 1)[0].upper() if cleaned.strip() else ""
    if first not in {"SELECT", "WITH"}:
        raise AdHocQueryError(
            f"Query deve comecar com SELECT ou WITH (recebido: {first or 'vazio'})."
        )
    if ";" in cleaned.rstrip(";"):
        # multi-statement
        parts = [p.strip() for p in cleaned.split(";") if p.strip()]
        if len(parts) > 1:
            raise AdHocQueryError("Multiplos statements nao sao permitidos.")


def _ensure_limit(sql: str, limit: int) -> str:
    """Adiciona LIMIT se query nao tiver um (heuristica simples)."""
    cleaned = _strip_comments(sql).rstrip(";").strip()
    if re.search(r"\blimit\s+\d+\b", cleaned, re.IGNORECASE):
        return cleaned
    return f"{cleaned}\nLIMIT {limit}"


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool
    notes: str


def _load_parquet_path(ds: Dataset) -> Path:
    if not ds.processed_path:
        raise AdHocQueryError(f"Dataset '{ds.name}' sem parquet processado.")
    path = Path(ds.processed_path)
    if not path.exists():
        raise AdHocQueryError(f"Parquet nao encontrado: {path}")
    return path


def run_query(
    ds: Dataset,
    sql: str,
    *,
    limit: int = 200,
    force_limit: bool = True,
) -> QueryResult:
    validate_sql(sql)
    path = _load_parquet_path(ds)
    exec_sql = _ensure_limit(sql, limit) if force_limit else _strip_comments(sql).rstrip(";")

    con = duckdb.connect(":memory:")
    try:
        # View read-only sobre o parquet
        con.execute(
            f"CREATE VIEW data AS SELECT * FROM read_parquet('{path.as_posix()}')"
        )
        df = con.execute(exec_sql).fetchdf()
    except Exception as exc:
        raise AdHocQueryError(f"Erro DuckDB: {exc}") from exc
    finally:
        con.close()

    truncated = force_limit and len(df) >= limit
    rows = _df_to_rows(df)
    return QueryResult(
        columns=list(df.columns),
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        notes=f"Limitado a {limit} linhas." if truncated else "",
    )


def run_query_dataframe(
    ds: Dataset,
    sql: str,
    *,
    limit: int | None = 10000,
) -> pd.DataFrame:
    validate_sql(sql)
    path = _load_parquet_path(ds)
    exec_sql = _ensure_limit(sql, limit) if limit else _strip_comments(sql).rstrip(";")

    con = duckdb.connect(":memory:")
    try:
        con.execute(
            f"CREATE VIEW data AS SELECT * FROM read_parquet('{path.as_posix()}')"
        )
        return con.execute(exec_sql).fetchdf()
    except Exception as exc:
        raise AdHocQueryError(f"Erro DuckDB: {exc}") from exc
    finally:
        con.close()


def _df_to_rows(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    # Serializa timestamps e NaN
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    out = out.where(pd.notna(out), None)
    return out.to_dict(orient="records")


def example_queries(dataset_name: str) -> list[dict[str, str]]:
    """Templates de exemplo para a UI."""
    return [
        {
            "label": "Top 10 linhas",
            "sql": "SELECT * FROM data LIMIT 10",
        },
        {
            "label": "Agregacao por pais",
            "sql": (
                "SELECT country, SUM(revenue) AS total_revenue, COUNT(*) AS n "
                "FROM data GROUP BY country ORDER BY total_revenue DESC"
            ),
        },
        {
            "label": "Filtro + ordenacao",
            "sql": (
                "SELECT * FROM data WHERE country = 'Brazil' "
                "ORDER BY revenue DESC LIMIT 20"
            ),
        },
        {
            "label": "Media mensal (se coluna date)",
            "sql": (
                "SELECT DATE_TRUNC('month', CAST(date AS DATE)) AS month, "
                "AVG(revenue) AS avg_revenue FROM data "
                "GROUP BY 1 ORDER BY 1"
            ),
        },
    ]
