"""Engine multi-tabela + Visual Report Builder (Phase 7)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from app.models.dataset import Dataset
from app.services.ad_hoc_engine import (
    AdHocQueryError,
    QueryResult,
    _df_to_rows,
    _ensure_limit,
    _load_parquet_path,
    _strip_comments,
    validate_sql,
)

# Aliases amigáveis para joins na demo
DATASET_ALIASES: dict[str, str] = {
    "sales_latam": "sales",
    "client_master": "clients",
    "product_catalog": "products",
}

JOIN_KEYS: dict[frozenset[str], list[dict[str, str]]] = {
    frozenset({"sales_latam", "client_master"}): [
        {"left": "sales.client", "right": "clients.client", "label": "Cliente"},
    ],
    frozenset({"sales_latam", "product_catalog"}): [
        {"left": "sales.product", "right": "products.product", "label": "Produto"},
    ],
    frozenset({"client_master", "product_catalog"}): [],
}

_SAFE_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_FILTER_OPS = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}


@dataclass
class TableRef:
    alias: str
    dataset: Dataset


def friendly_alias(ds: Dataset, fallback: str | None = None) -> str:
    return DATASET_ALIASES.get(ds.name, fallback or ds.name.replace("-", "_")[:24])


def suggest_joins(names: list[str]) -> list[dict[str, str]]:
    """Sugere joins entre datasets pelo par de nomes."""
    out: list[dict[str, str]] = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            pair = JOIN_KEYS.get(frozenset({a, b}), [])
            out.extend(pair)
    return out


def _quote_ident(name: str) -> str:
    if not _SAFE_IDENT.match(name):
        raise AdHocQueryError(f"Identificador invalido: {name}")
    return f'"{name}"'


def _quote_table_col(ref: str) -> str:
    if "." not in ref:
        raise AdHocQueryError(f"Referencia de coluna invalida: {ref}")
    table, col = ref.split(".", 1)
    return f"{_quote_ident(table)}.{_quote_ident(col)}"


def _escape_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def register_tables(con: duckdb.DuckDBPyConnection, tables: list[TableRef]) -> None:
    seen: set[str] = set()
    for t in tables:
        if t.alias in seen:
            raise AdHocQueryError(f"Alias duplicado: {t.alias}")
        seen.add(t.alias)
        path = _load_parquet_path(t.dataset)
        con.execute(
            f"CREATE VIEW {_quote_ident(t.alias)} AS "
            f"SELECT * FROM read_parquet('{path.as_posix()}')"
        )


def run_query_tables(
    tables: list[TableRef],
    sql: str,
    *,
    limit: int = 200,
    force_limit: bool = True,
) -> QueryResult:
    validate_sql(sql)
    exec_sql = _ensure_limit(sql, limit) if force_limit else _strip_comments(sql).rstrip(";")
    con = duckdb.connect(":memory:")
    try:
        register_tables(con, tables)
        df = con.execute(exec_sql).fetchdf()
    except AdHocQueryError:
        raise
    except Exception as exc:
        raise AdHocQueryError(f"Erro DuckDB: {exc}") from exc
    finally:
        con.close()

    truncated = force_limit and len(df) >= limit
    return QueryResult(
        columns=list(df.columns),
        rows=_df_to_rows(df),
        row_count=len(df),
        truncated=truncated,
        notes=f"Limitado a {limit} linhas." if truncated else "",
    )


def run_query_tables_dataframe(
    tables: list[TableRef],
    sql: str,
    *,
    limit: int | None = 10000,
) -> pd.DataFrame:
    validate_sql(sql)
    exec_sql = _ensure_limit(sql, limit) if limit else _strip_comments(sql).rstrip(";")
    con = duckdb.connect(":memory:")
    try:
        register_tables(con, tables)
        return con.execute(exec_sql).fetchdf()
    except AdHocQueryError:
        raise
    except Exception as exc:
        raise AdHocQueryError(f"Erro DuckDB: {exc}") from exc
    finally:
        con.close()


def build_table_refs(
    primary: Dataset,
    extras: list[tuple[Dataset, str | None]] | None = None,
) -> list[TableRef]:
    """Monta refs: primary como `data` + alias amigavel; extras com alias informado ou amigavel."""
    refs: list[TableRef] = []
    primary_friendly = friendly_alias(primary, "data")
    refs.append(TableRef(alias="data", dataset=primary))
    if primary_friendly != "data":
        refs.append(TableRef(alias=primary_friendly, dataset=primary))
    for ds, alias in extras or []:
        a = alias or friendly_alias(ds)
        if any(r.alias == a for r in refs):
            continue
        refs.append(TableRef(alias=a, dataset=ds))
    return refs


def example_queries_multi(primary_name: str, extra_names: list[str] | None = None) -> list[dict[str, str]]:
    """Templates SQL incluindo joins quando dimensões disponíveis."""
    extras = set(extra_names or [])
    examples = [
        {"label": "Top 10 vendas", "sql": "SELECT * FROM sales LIMIT 10"},
        {
            "label": "Revenue por país",
            "sql": (
                "SELECT country, SUM(revenue) AS total_revenue, COUNT(*) AS n "
                "FROM sales GROUP BY country ORDER BY total_revenue DESC"
            ),
        },
    ]
    if "client_master" in extras or primary_name == "client_master":
        examples.append(
            {
                "label": "JOIN vendas + clientes (tier)",
                "sql": (
                    "SELECT s.country, c.tier, c.industry, "
                    "SUM(s.revenue) AS total_revenue, COUNT(*) AS n "
                    "FROM sales s "
                    "INNER JOIN clients c ON s.client = c.client "
                    "GROUP BY s.country, c.tier, c.industry "
                    "ORDER BY total_revenue DESC"
                ),
            }
        )
        examples.append(
            {
                "label": "Clientes estratégicos — top revenue",
                "sql": (
                    "SELECT s.client, c.tier, c.industry, SUM(s.revenue) AS total "
                    "FROM sales s "
                    "INNER JOIN clients c ON s.client = c.client "
                    "WHERE c.is_strategic = true "
                    "GROUP BY s.client, c.tier, c.industry "
                    "ORDER BY total DESC LIMIT 15"
                ),
            }
        )
    if "product_catalog" in extras or primary_name == "product_catalog":
        examples.append(
            {
                "label": "JOIN vendas + produtos (categoria)",
                "sql": (
                    "SELECT p.category, p.product, SUM(s.revenue) AS total_revenue "
                    "FROM sales s "
                    "INNER JOIN products p ON s.product = p.product "
                    "GROUP BY p.category, p.product "
                    "ORDER BY total_revenue DESC"
                ),
            }
        )
    if "client_master" in extras and "product_catalog" in extras:
        examples.append(
            {
                "label": "Cross-table: cliente × produto × tier",
                "sql": (
                    "SELECT c.tier, p.category, SUM(s.revenue) AS total_revenue "
                    "FROM sales s "
                    "INNER JOIN clients c ON s.client = c.client "
                    "INNER JOIN products p ON s.product = p.product "
                    "GROUP BY c.tier, p.category "
                    "ORDER BY total_revenue DESC"
                ),
            }
        )
    return examples


# ---------------------------------------------------------------------------
# Visual Report Builder → SQL seguro
# ---------------------------------------------------------------------------

def build_visual_sql(
    *,
    primary_alias: str,
    join: dict | None,
    columns: list[dict],
    filters: list[dict],
    group_by: list[dict],
    metrics: list[dict],
    order_by: dict | None,
    order_dir: str,
    limit: int,
    allowed_columns: set[str],
) -> str:
    """Gera SQL a partir de config visual. Colunas no formato `alias.column`."""

    def col_ref(table: str, column: str) -> str:
        ref = f"{table}.{column}"
        if ref not in allowed_columns:
            raise AdHocQueryError(f"Coluna nao permitida: {ref}")
        return _quote_table_col(ref)

    primary_alias = primary_alias or "sales"
    from_parts = f"{_quote_ident(primary_alias)} AS {_quote_ident(primary_alias)}"
    if join:
        jtype = join.get("join_type", "inner").upper()
        if jtype not in {"INNER", "LEFT"}:
            raise AdHocQueryError("Tipo de join invalido.")
        right_alias = join["alias"]
        left_col = join["left_column"]
        right_col = join["right_column"]
        if left_col not in allowed_columns or right_col not in allowed_columns:
            raise AdHocQueryError("Colunas de join invalidas.")
        from_parts += (
            f" {jtype} JOIN {_quote_ident(right_alias)} AS {_quote_ident(right_alias)} "
            f"ON {_quote_table_col(left_col)} = {_quote_table_col(right_col)}"
        )

    select_parts: list[str] = []
    group_refs: list[str] = []

    for g in group_by:
        ref = col_ref(g["table"], g["column"])
        select_parts.append(ref)
        group_refs.append(ref)

    for m in metrics:
        agg = m.get("aggregation", "none")
        ref = col_ref(m["table"], m["column"])
        alias = m.get("alias") or f"{agg}_{m['column']}"
        if not _SAFE_IDENT.match(alias.replace(" ", "_")):
            raise AdHocQueryError(f"Alias invalido: {alias}")
        if agg == "none":
            select_parts.append(f"{ref} AS {_quote_ident(alias)}")
        elif agg == "count":
            select_parts.append(f"COUNT({ref}) AS {_quote_ident(alias)}")
        elif agg in {"sum", "avg", "min", "max"}:
            select_parts.append(f"{agg.upper()}({ref}) AS {_quote_ident(alias)}")
        else:
            raise AdHocQueryError(f"Agregacao invalida: {agg}")

    if not group_by and not metrics:
        for c in columns:
            alias = c.get("alias") or c["column"]
            select_parts.append(
                f"{col_ref(c['table'], c['column'])} AS {_quote_ident(alias)}"
            )

    if not select_parts:
        raise AdHocQueryError("Selecione ao menos uma coluna ou metrica.")

    where_parts: list[str] = []
    for f in filters:
        op = f.get("operator", "eq")
        ref = col_ref(f["table"], f["column"])
        val = f.get("value", "")
        if op == "contains":
            where_parts.append(f"CAST({ref} AS VARCHAR) ILIKE '%' || {_escape_literal(val)} || '%'")
        elif op == "starts_with":
            where_parts.append(f"CAST({ref} AS VARCHAR) ILIKE {_escape_literal(val + '%')}")
        elif op in _FILTER_OPS:
            where_parts.append(f"{ref} {_FILTER_OPS[op]} {_escape_literal(val)}")
        else:
            raise AdHocQueryError(f"Operador invalido: {op}")

    sql = f"SELECT {', '.join(select_parts)} FROM {from_parts}"
    if where_parts:
        sql += " WHERE " + " AND ".join(where_parts)
    if group_refs:
        sql += " GROUP BY " + ", ".join(group_refs)
    if order_by:
        direction = "DESC" if order_dir.lower() == "desc" else "ASC"
        ob_table = order_by["table"]
        ob_col = order_by["column"]
        matching_metric = next(
            (m for m in metrics if m["table"] == ob_table and m["column"] == ob_col),
            None,
        )
        if group_refs and matching_metric:
            alias = matching_metric.get("alias") or f"{matching_metric['aggregation']}_{ob_col}"
            sql += f" ORDER BY {_quote_ident(alias)} {direction}"
        elif group_refs:
            ref = col_ref(ob_table, ob_col)
            if ref in group_refs:
                sql += " ORDER BY " + ref + f" {direction}"
        else:
            sql += f" ORDER BY {col_ref(ob_table, ob_col)} {direction}"
    sql += f" LIMIT {min(max(limit, 1), 5000)}"
    return sql


def allowed_column_set(tables: list[TableRef], profiles: dict[str, list[str]]) -> set[str]:
    out: set[str] = set()
    for t in tables:
        cols = profiles.get(t.alias, [])
        for c in cols:
            out.add(f"{t.alias}.{c}")
    return out
