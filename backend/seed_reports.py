"""Seed de relatorios ad-hoc salvos (Phase 7).

Cria 2 queries de exemplo sobre o dataset sales_latam.
Idempotente: skip se ja existir relatorio com o mesmo nome.
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.dataset import Dataset
from app.models.report import SavedReport
from database import SessionLocal, init_db

DEFAULT_OWNER = "admin@latam.com"


def _dataset_id(session, name: str) -> int | None:
    ds = session.query(Dataset).filter(Dataset.name == name).first()
    return ds.id if ds else None


def _ensure_report(session, **kwargs) -> SavedReport | None:
    name = kwargs["name"]
    existing = session.query(SavedReport).filter(SavedReport.name == name).first()
    if existing:
        existing.sql_query = kwargs["sql_query"]
        existing.description = kwargs.get("description", existing.description)
        return existing
    r = SavedReport(**kwargs)
    session.add(r)
    session.flush()
    return r


def main() -> None:
    init_db()
    session = SessionLocal()
    try:
        sales_id = _dataset_id(session, "sales_latam")
        if not sales_id:
            print("Dataset sales_latam nao encontrado. Rode seed.py primeiro.")
            return

        _ensure_report(
            session,
            name="Revenue por país (Top 10)",
            description="Agregacao de revenue e contagem por pais, ordenado desc.",
            workspace="LATAM",
            business_area="Sales",
            source_dataset_id=sales_id,
            sql_query=(
                "SELECT country, SUM(revenue) AS total_revenue, COUNT(*) AS n "
                "FROM sales GROUP BY country ORDER BY total_revenue DESC LIMIT 10"
            ),
            created_by=DEFAULT_OWNER,
        )

        _ensure_report(
            session,
            name="JOIN vendas × clientes por tier",
            description="Cross-table: revenue agregado por pais e tier do cliente.",
            workspace="LATAM",
            business_area="Sales",
            source_dataset_id=sales_id,
            sql_query=(
                "SELECT s.country, c.tier, c.industry, SUM(s.revenue) AS total_revenue "
                "FROM sales s INNER JOIN clients c ON s.client = c.client "
                "GROUP BY s.country, c.tier, c.industry "
                "ORDER BY total_revenue DESC LIMIT 20"
            ),
            created_by=DEFAULT_OWNER,
        )

        session.commit()
        count = session.query(SavedReport).count()
        print(f"Seed reports OK — {count} saved report(s) no banco.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
