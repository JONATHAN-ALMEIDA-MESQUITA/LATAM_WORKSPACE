"""Seed de pipelines de exemplo (Phase 3b - ETL Builder).

Cria 3 pipelines representativos demonstrando todos os operadores:

1. "Sales Brazil - High-margin clients" (LATAM/Sales)
   sales_latam -> FILTER country=Brazil
                -> COMPUTED margin_pct = margin/revenue
                -> FILTER margin_pct > 0.3
                -> GROUP_BY client agg revenue/margin
                -> SORT desc revenue, LIMIT 50
                -> TARGET "Brazil Top Clients (high margin)"

2. "Finance - Variance Actual vs Budget" (LATAM/Finance)
   finance_actual_budget -> COMPUTED var_abs = actual - budget
                         -> COMPUTED var_pct = var_abs / budget
                         -> GROUP_BY country,account_group aggs actual/budget/var_abs
                         -> SORT desc var_abs
                         -> TARGET "Finance Variance Summary"

3. "Supplier - Risk Watchlist" (LATAM/Supplier)
   supplier_performance -> FILTER risk_level in [High, Medium]
                        -> SELECT (subset)
                        -> SORT asc sla_score
                        -> LIMIT 100
                        -> TARGET "Supplier Watchlist"

Idempotente: skip se ja existir um pipeline com o mesmo nome.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

from app.models.dataset import Dataset
from app.models.pipeline import Pipeline, PipelineStatus, PipelineStep, StepType
from app.models.user import User
from database import SessionLocal, init_db


SEED_USER_EMAIL = "admin@latam.com"


def _step(order: int, name: str, step_type: StepType, config: dict) -> PipelineStep:
    return PipelineStep(
        order_index=order,
        name=name,
        step_type=step_type.value,
        config=json.dumps(config),
    )


def _ensure_pipeline(db, name: str, builder) -> Pipeline | None:
    existing = db.query(Pipeline).filter(Pipeline.name == name).first()
    if existing:
        print(f"  - skip (ja existe): {name}")
        return existing
    p = builder()
    db.add(p)
    db.commit()
    db.refresh(p)
    print(f"  + criado: {name} ({len(p.steps)} steps)")
    return p


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == SEED_USER_EMAIL).first()
        if not admin:
            print(f"ERRO: usuario {SEED_USER_EMAIL} nao encontrado. Rode seed.py antes.")
            return

        sales = db.query(Dataset).filter(Dataset.name == "sales_latam").first()
        finance = db.query(Dataset).filter(Dataset.name == "finance_actual_budget").first()
        supplier = db.query(Dataset).filter(Dataset.name == "supplier_performance").first()
        if not (sales and finance and supplier):
            print("ERRO: datasets sample nao encontrados. Rode seed.py para gerar os samples.")
            return

        print("\nSeedando pipelines...")

        # ----------- Pipeline 1: Sales Brazil top clients high-margin -------
        def build_sales_top():
            p = Pipeline(
                name="Sales Brazil - High-margin Top Clients",
                description=(
                    "Filtra vendas do Brasil, calcula margin %, mantem clientes acima de 30% de margem "
                    "e ranqueia top 50 por revenue. Output usado em dashboards de Sales."
                ),
                workspace="LATAM",
                business_area="Sales",
                schedule_cron="0 6 * * *",  # daily 06:00 (informativo)
                status=PipelineStatus.PUBLISHED.value,
                created_by=admin.email,
                published_by=admin.email,
            )
            p.steps = [
                _step(0, "Source: sales_latam", StepType.SOURCE,
                      {"dataset_id": sales.id}),
                _step(1, "Filter Brazil", StepType.FILTER,
                      {"conditions": [{"col": "country", "op": "==", "value": "Brazil"}]}),
                _step(2, "Compute margin_pct", StepType.COMPUTED_COLUMN,
                      {"new_col": "margin_pct", "expression": "margin / revenue"}),
                _step(3, "Filter margin_pct > 0.3", StepType.FILTER,
                      {"conditions": [{"col": "margin_pct", "op": ">", "value": 0.3}]}),
                _step(4, "Aggregate by client", StepType.GROUP_BY, {
                    "by": ["client"],
                    "aggs": [
                        {"col": "revenue", "func": "sum", "as": "revenue_total"},
                        {"col": "margin", "func": "sum", "as": "margin_total"},
                        {"col": "transactions", "func": "sum", "as": "transactions_total"},
                    ],
                }),
                _step(5, "Sort by revenue desc", StepType.SORT,
                      {"by": ["revenue_total"], "ascending": [False]}),
                _step(6, "Top 50", StepType.LIMIT, {"n": 50}),
                _step(7, "Target dataset", StepType.TARGET, {
                    "dataset_name": "Brazil Top Clients (high margin)",
                    "workspace": "LATAM",
                    "business_area": "Sales",
                    "description": "Pipeline output: top 50 clientes BR com margem > 30%.",
                }),
            ]
            return p
        _ensure_pipeline(db, "Sales Brazil - High-margin Top Clients", build_sales_top)

        # ----------- Pipeline 2: Finance variance --------------------------
        def build_finance_variance():
            p = Pipeline(
                name="Finance - Variance Actual vs Budget",
                description=(
                    "Calcula variancia absoluta e percentual entre actual e budget por pais e "
                    "grupo de conta. Output alimenta dashboards de FP&A."
                ),
                workspace="LATAM",
                business_area="Finance",
                schedule_cron="0 7 1 * *",  # mensal dia 1, 07:00
                status=PipelineStatus.PUBLISHED.value,
                created_by=admin.email,
                published_by=admin.email,
            )
            p.steps = [
                _step(0, "Source: finance_actual_budget", StepType.SOURCE,
                      {"dataset_id": finance.id}),
                _step(1, "Compute variance abs", StepType.COMPUTED_COLUMN,
                      {"new_col": "var_abs", "expression": "actual - budget"}),
                _step(2, "Compute variance pct", StepType.COMPUTED_COLUMN,
                      {"new_col": "var_pct", "expression": "(actual - budget) / budget"}),
                _step(3, "Aggregate by country/account_group", StepType.GROUP_BY, {
                    "by": ["country", "account_group"],
                    "aggs": [
                        {"col": "actual", "func": "sum", "as": "actual_total"},
                        {"col": "budget", "func": "sum", "as": "budget_total"},
                        {"col": "var_abs", "func": "sum", "as": "variance_abs"},
                    ],
                }),
                _step(4, "Sort by variance_abs desc", StepType.SORT,
                      {"by": ["variance_abs"], "ascending": [False]}),
                _step(5, "Target dataset", StepType.TARGET, {
                    "dataset_name": "Finance Variance Summary",
                    "workspace": "LATAM",
                    "business_area": "Finance",
                    "description": "Pipeline output: variancia actual vs budget consolidada.",
                }),
            ]
            return p
        _ensure_pipeline(db, "Finance - Variance Actual vs Budget", build_finance_variance)

        # ----------- Pipeline 3: Supplier watchlist ------------------------
        def build_supplier_watchlist():
            p = Pipeline(
                name="Supplier - Risk Watchlist",
                description=(
                    "Identifica fornecedores em risco (SLA baixo ou qualidade ruim) "
                    "e gera lista priorizada para acao. Roda semanalmente."
                ),
                workspace="LATAM",
                business_area="Supplier",
                schedule_cron="0 8 * * 1",  # segunda 08:00
                status=PipelineStatus.DRAFT.value,
                created_by=admin.email,
            )
            p.steps = [
                _step(0, "Source: supplier_performance", StepType.SOURCE,
                      {"dataset_id": supplier.id}),
                _step(1, "Filter risk High or Medium", StepType.FILTER, {
                    "conditions": [
                        {"col": "risk_level", "op": "in", "value": ["High", "Medium"]},
                    ],
                }),
                _step(2, "Compute savings_rate", StepType.COMPUTED_COLUMN,
                      {"new_col": "savings_rate", "expression": "savings / spend"}),
                _step(3, "Select subset", StepType.SELECT, {
                    "columns": [
                        "date", "country", "supplier", "category",
                        "spend", "savings", "savings_rate",
                        "sla_score", "quality_score", "risk_level",
                    ],
                }),
                _step(4, "Sort by sla_score asc", StepType.SORT,
                      {"by": ["sla_score"], "ascending": [True]}),
                _step(5, "Top 100 at-risk", StepType.LIMIT, {"n": 100}),
                _step(6, "Target dataset", StepType.TARGET, {
                    "dataset_name": "Supplier Watchlist",
                    "workspace": "LATAM",
                    "business_area": "Supplier",
                    "description": "Pipeline output: fornecedores em risco para acao.",
                }),
            ]
            return p
        _ensure_pipeline(db, "Supplier - Risk Watchlist", build_supplier_watchlist)

        print("\nSeed concluido.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
