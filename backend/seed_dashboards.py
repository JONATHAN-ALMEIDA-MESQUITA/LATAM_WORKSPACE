"""Seed de métricas e dashboards exemplo (para popular o Business Portal).

Roda APÓS o seed.py inicial (que cria usuários e workspaces).
Os datasets sintéticos são gerados/recuperados pelo próprio script.

Para rodar standalone:
    python seed_dashboards.py
"""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.dashboard import Dashboard, DashboardStatus, DashboardWidget, WidgetType
from app.models.dataset import Dataset, DatasetSourceType
from app.models.metric import Metric, MetricStatus
from app.models.user import User
from app.services.dataset_service import generate_all_samples
from database import SessionLocal, init_db


def _ensure_user(db: Session, email: str) -> User:
    u = db.query(User).filter(User.email == email).first()
    if not u:
        raise RuntimeError(
            f"Usuário {email} não existe. Rode seed.py primeiro para criar usuários demo."
        )
    return u


def _get_sample_dataset(db: Session, name: str) -> Dataset | None:
    """Sample datasets têm o key do SAMPLE_DATASETS como Dataset.name."""
    return (
        db.query(Dataset)
        .filter(
            Dataset.name == name,
            Dataset.source_type == DatasetSourceType.SAMPLE.value,
        )
        .order_by(Dataset.created_at.desc())
        .first()
    )


def _ensure_metric(
    db: Session,
    *,
    name: str,
    dataset: Dataset,
    formula_type: str,
    formula_config: dict,
    output_format: str = "number",
    decimals: int = 2,
    business_area: str = "",
    workspace: str = "LATAM",
    created_by: str = "admin@latam.com",
    status: str = MetricStatus.CERTIFIED.value,
    description: str = "",
) -> Metric:
    m = (
        db.query(Metric)
        .filter(Metric.name == name, Metric.dataset_id == dataset.id)
        .first()
    )
    if m:
        return m
    m = Metric(
        name=name,
        description=description,
        dataset_id=dataset.id,
        workspace=workspace,
        business_area=business_area,
        formula_type=formula_type,
        formula_config=json.dumps(formula_config),
        output_format=output_format,
        decimals=decimals,
        status=status,
        created_by=created_by,
    )
    db.add(m)
    db.flush()
    return m


def _ensure_dashboard(
    db: Session,
    *,
    name: str,
    description: str,
    workspace: str,
    business_area: str,
    created_by: str,
    widgets: list[dict],
    status: str = DashboardStatus.PUBLISHED.value,
) -> Dashboard:
    existing = (
        db.query(Dashboard)
        .filter(Dashboard.name == name, Dashboard.workspace == workspace)
        .first()
    )
    if existing:
        return existing

    d = Dashboard(
        name=name,
        description=description,
        workspace=workspace,
        business_area=business_area,
        theme="Executive Light",
        status=status,
        created_by=created_by,
    )
    now = datetime.utcnow()
    if status == DashboardStatus.PUBLISHED.value:
        d.submitted_by = created_by
        d.submitted_at = now
        d.published_by = created_by
        d.published_at = now
    db.add(d)
    db.flush()

    for w in widgets:
        widget = DashboardWidget(
            dashboard_id=d.id,
            title=w["title"],
            widget_type=w["widget_type"],
            layout=json.dumps(w["layout"]),
            config=json.dumps(w["config"]),
        )
        db.add(widget)
    db.flush()
    return d


def seed(db: Session) -> dict:
    admin = _ensure_user(db, "admin@latam.com")

    # Garante datasets sintéticos (idempotente; usa generate_all_samples)
    generate_all_samples(db, workspace="LATAM", created_by=admin.email)
    db.commit()

    dataset_sales = _get_sample_dataset(db, "sales_latam")
    dataset_fin = _get_sample_dataset(db, "finance_actual_budget")
    dataset_sup = _get_sample_dataset(db, "supplier_performance")
    dataset_cash = _get_sample_dataset(db, "cash_flow")
    dataset_comm = _get_sample_dataset(db, "commission_forecast")

    if not all([dataset_sales, dataset_fin, dataset_sup, dataset_cash, dataset_comm]):
        raise RuntimeError("Falha ao localizar os 5 datasets sintéticos.")

    # -----------------------------------------------------------
    # Métricas reutilizáveis (Camada Semântica)
    # -----------------------------------------------------------

    # Sales LATAM (cols: date, year, month, country, client, sales_rep, business_unit,
    # product, revenue, cost, margin, transactions, currency, channel)
    m_revenue = _ensure_metric(
        db,
        name="Revenue (USD)",
        description="Soma da coluna revenue.",
        dataset=dataset_sales,
        formula_type="SUM",
        formula_config={"column": "revenue"},
        output_format="currency", decimals=0,
        business_area="Sales", created_by=admin.email,
    )
    m_transactions = _ensure_metric(
        db,
        name="Transactions",
        description="Soma de transações.",
        dataset=dataset_sales,
        formula_type="SUM",
        formula_config={"column": "transactions"},
        output_format="integer", decimals=0,
        business_area="Sales", created_by=admin.email,
    )
    m_margin_pct = _ensure_metric(
        db,
        name="Margin %",
        description="Margem percentual: (revenue - cost) / revenue.",
        dataset=dataset_sales,
        formula_type="CUSTOM_LIMITED",
        formula_config={"formula": "DIVIDE(SUB(SUM(revenue), SUM(cost)), SUM(revenue))"},
        output_format="percent", decimals=1,
        business_area="Finance", created_by=admin.email,
    )
    m_revenue_ytd = _ensure_metric(
        db,
        name="Revenue YTD",
        description="Soma de revenue do início do ano corrente até a última data.",
        dataset=dataset_sales,
        formula_type="YTD",
        formula_config={"column": "revenue", "date_column": "date"},
        output_format="currency", decimals=0,
        business_area="Sales", created_by=admin.email,
    )
    m_revenue_yoy = _ensure_metric(
        db,
        name="Revenue YoY %",
        description="Crescimento YoY de revenue (YTD corrente vs YTD ano anterior).",
        dataset=dataset_sales,
        formula_type="YOY",
        formula_config={"column": "revenue", "date_column": "date", "mode": "percent"},
        output_format="percent", decimals=1,
        business_area="Sales", created_by=admin.email,
    )

    # Finance (cols: date, year, month, country, account, account_group, scenario,
    # actual, budget, forecast, currency, business_unit)
    m_actual = _ensure_metric(
        db,
        name="Actual",
        dataset=dataset_fin,
        formula_type="SUM",
        formula_config={"column": "actual"},
        output_format="currency", decimals=0,
        business_area="Finance", created_by=admin.email,
    )
    m_budget = _ensure_metric(
        db,
        name="Budget",
        dataset=dataset_fin,
        formula_type="SUM",
        formula_config={"column": "budget"},
        output_format="currency", decimals=0,
        business_area="Finance", created_by=admin.email,
    )
    m_var_pct = _ensure_metric(
        db,
        name="Variance vs Budget %",
        description="(Actual - Budget) / Budget. Negativo = abaixo do orçado.",
        dataset=dataset_fin,
        formula_type="VARIATION_PCT",
        formula_config={"actual": "actual", "baseline": "budget"},
        output_format="percent", decimals=1,
        business_area="Finance", created_by=admin.email,
    )
    m_forecast = _ensure_metric(
        db,
        name="Forecast",
        dataset=dataset_fin,
        formula_type="SUM",
        formula_config={"column": "forecast"},
        output_format="currency", decimals=0,
        business_area="Finance", created_by=admin.email,
    )

    # Supplier (cols: date, country, supplier, category, spend, savings,
    # transactions, sla_score, quality_score, risk_level)
    m_sla = _ensure_metric(
        db,
        name="SLA Score",
        description="Pontuação média de SLA por fornecedor.",
        dataset=dataset_sup,
        formula_type="AVERAGE",
        formula_config={"column": "sla_score"},
        output_format="number", decimals=1,
        business_area="Supplier", created_by=admin.email,
    )
    m_quality = _ensure_metric(
        db,
        name="Quality Score",
        dataset=dataset_sup,
        formula_type="AVERAGE",
        formula_config={"column": "quality_score"},
        output_format="number", decimals=1,
        business_area="Supplier", created_by=admin.email,
    )
    m_spend = _ensure_metric(
        db,
        name="Total Spend",
        dataset=dataset_sup,
        formula_type="SUM",
        formula_config={"column": "spend"},
        output_format="currency", decimals=0,
        business_area="Supplier", created_by=admin.email,
    )
    m_savings = _ensure_metric(
        db,
        name="Savings",
        dataset=dataset_sup,
        formula_type="SUM",
        formula_config={"column": "savings"},
        output_format="currency", decimals=0,
        business_area="Supplier", created_by=admin.email,
    )

    # Cash flow (cols: due_date, country, client_vendor, type, amount, currency,
    # status, aging_bucket, payment_probability)
    m_amount = _ensure_metric(
        db,
        name="Total Amount",
        dataset=dataset_cash,
        formula_type="SUM",
        formula_config={"column": "amount"},
        output_format="currency", decimals=0,
        business_area="Finance", created_by=admin.email,
    )
    m_avg_probability = _ensure_metric(
        db,
        name="Avg Payment Probability",
        dataset=dataset_cash,
        formula_type="AVERAGE",
        formula_config={"column": "payment_probability"},
        output_format="percent", decimals=1,
        business_area="Finance", created_by=admin.email,
    )

    db.commit()

    # -----------------------------------------------------------
    # Dashboards
    # -----------------------------------------------------------

    # 1) Sales LATAM Overview (Sales area, LATAM workspace)
    _ensure_dashboard(
        db,
        name="Sales LATAM Overview",
        description="Visão geral de receita, margem e canais em toda a região LATAM.",
        workspace="LATAM",
        business_area="Sales",
        created_by=admin.email,
        widgets=[
            {
                "title": "Revenue YTD",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 3, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue_ytd.id,
                    "label": "Revenue YTD",
                },
            },
            {
                "title": "Revenue YoY %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 3, "y": 0, "w": 3, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue_yoy.id,
                    "label": "Revenue YoY %",
                },
            },
            {
                "title": "Transactions",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 6, "y": 0, "w": 3, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_transactions.id,
                    "label": "Transactions",
                },
            },
            {
                "title": "Margin %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 9, "y": 0, "w": 3, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_margin_pct.id,
                    "label": "Margin %",
                },
            },
            {
                "title": "Revenue por País",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "country",
                    "sort": "desc", "limit": 10,
                },
            },
            {
                "title": "Revenue por Mês",
                "widget_type": WidgetType.LINE_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "date", "time_grain": "month",
                    "sort_by": "date", "sort": "asc", "limit": 36,
                },
            },
            {
                "title": "Revenue por Produto",
                "widget_type": WidgetType.PIE_CHART.value,
                "layout": {"x": 0, "y": 8, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "product", "sort": "desc", "limit": 8,
                },
            },
            {
                "title": "Top Channels",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 6, "y": 8, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "channel", "sort": "desc",
                },
            },
        ],
    )

    # 2) Finance - Budget vs Actual
    _ensure_dashboard(
        db,
        name="Finance - Budget vs Actual",
        description="Comparativo de gastos reais vs orçamento por país e conta.",
        workspace="LATAM",
        business_area="Finance",
        created_by=admin.email,
        widgets=[
            {
                "title": "Actual",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_fin.id, "metric_id": m_actual.id},
            },
            {
                "title": "Budget",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 3, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_fin.id, "metric_id": m_budget.id},
            },
            {
                "title": "Forecast",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 6, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_fin.id, "metric_id": m_forecast.id},
            },
            {
                "title": "Variance %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 9, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_fin.id, "metric_id": m_var_pct.id},
            },
            {
                "title": "Actual por Conta",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_fin.id,
                    "metric_id": m_actual.id,
                    "dimension": "account", "sort": "desc",
                },
            },
            {
                "title": "Actual por Mês",
                "widget_type": WidgetType.AREA_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_fin.id,
                    "metric_id": m_actual.id,
                    "dimension": "date", "time_grain": "month",
                    "sort_by": "date", "sort": "asc",
                },
            },
            {
                "title": "Detalhe por país e conta",
                "widget_type": WidgetType.TABLE.value,
                "layout": {"x": 0, "y": 8, "w": 12, "h": 5},
                "config": {
                    "dataset_id": dataset_fin.id,
                    "columns": ["date", "country", "account", "business_unit", "actual", "budget", "forecast"],
                    "sort_by": "actual", "sort": "desc", "limit": 25,
                },
            },
        ],
    )

    # 3) Supplier Performance
    _ensure_dashboard(
        db,
        name="Supplier Performance LATAM",
        description="KPIs de fornecedores: SLA, qualidade, gasto e savings.",
        workspace="LATAM",
        business_area="Supplier",
        created_by=admin.email,
        widgets=[
            {
                "title": "SLA Score",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sup.id, "metric_id": m_sla.id},
            },
            {
                "title": "Quality Score",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 3, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sup.id, "metric_id": m_quality.id},
            },
            {
                "title": "Total Spend",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 6, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sup.id, "metric_id": m_spend.id},
            },
            {
                "title": "Savings",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 9, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sup.id, "metric_id": m_savings.id},
            },
            {
                "title": "SLA por Fornecedor",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sup.id,
                    "metric_id": m_sla.id,
                    "dimension": "supplier", "sort": "desc", "limit": 12,
                },
            },
            {
                "title": "Spend por Categoria",
                "widget_type": WidgetType.DONUT_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sup.id,
                    "metric_id": m_spend.id,
                    "dimension": "category", "sort": "desc",
                },
            },
            {
                "title": "Fornecedores detalhados",
                "widget_type": WidgetType.TABLE.value,
                "layout": {"x": 0, "y": 8, "w": 12, "h": 5},
                "config": {
                    "dataset_id": dataset_sup.id,
                    "columns": [
                        "supplier", "country", "category",
                        "spend", "savings", "sla_score", "quality_score", "risk_level",
                    ],
                    "sort_by": "spend", "sort": "desc", "limit": 30,
                },
            },
        ],
    )

    # 4) Cash Flow Operations
    _ensure_dashboard(
        db,
        name="Cash Flow Operations",
        description="AR/AP por aging, status e país.",
        workspace="LATAM",
        business_area="Operations",
        created_by=admin.email,
        widgets=[
            {
                "title": "Total Amount",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 6, "h": 3},
                "config": {"dataset_id": dataset_cash.id, "metric_id": m_amount.id},
            },
            {
                "title": "Avg Payment Probability",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 6, "y": 0, "w": 6, "h": 3},
                "config": {"dataset_id": dataset_cash.id, "metric_id": m_avg_probability.id},
            },
            {
                "title": "Amount por País",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_cash.id,
                    "metric_id": m_amount.id,
                    "dimension": "country", "sort": "desc",
                },
            },
            {
                "title": "Aging Bucket Distribution",
                "widget_type": WidgetType.PIE_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_cash.id,
                    "metric_id": m_amount.id,
                    "dimension": "aging_bucket", "sort": "desc",
                },
            },
            {
                "title": "Status do Pagamento",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 8, "w": 12, "h": 5},
                "config": {
                    "dataset_id": dataset_cash.id,
                    "metric_id": m_amount.id,
                    "dimension": "status", "sort": "desc",
                },
            },
        ],
    )

    # 5) LATAM Executive Summary - cross-area
    _ensure_dashboard(
        db,
        name="LATAM Executive Summary",
        description="Visão executiva LATAM: receita, margem, gastos e operações.",
        workspace="LATAM",
        business_area="Executive",
        created_by=admin.email,
        widgets=[
            {
                "title": "Revenue YTD",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sales.id, "metric_id": m_revenue_ytd.id},
            },
            {
                "title": "Revenue YoY %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 3, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sales.id, "metric_id": m_revenue_yoy.id},
            },
            {
                "title": "Margin %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 6, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_sales.id, "metric_id": m_margin_pct.id},
            },
            {
                "title": "Variance vs Budget %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 9, "y": 0, "w": 3, "h": 3},
                "config": {"dataset_id": dataset_fin.id, "metric_id": m_var_pct.id},
            },
            {
                "title": "Revenue por País",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "country", "sort": "desc", "limit": 8,
                },
            },
            {
                "title": "Spend por Categoria",
                "widget_type": WidgetType.BAR_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sup.id,
                    "metric_id": m_spend.id,
                    "dimension": "category", "sort": "desc",
                },
            },
            {
                "title": "Executive Briefing",
                "widget_type": WidgetType.TEXT_BOX.value,
                "layout": {"x": 0, "y": 8, "w": 12, "h": 3},
                "config": {
                    "text_content": (
                        "**LATAM Executive Briefing** — Dashboard executivo gerado a partir de "
                        "dados sintéticos para demonstração. Receita YTD em crescimento, margem "
                        "estável, variância orçamentária dentro do esperado, operações com fluxo "
                        "de caixa positivo. Monitoramento contínuo via dashboards Operations e "
                        "Supplier Performance."
                    ),
                },
            },
        ],
    )

    # 6) Brazil Sales (workspace específico)
    _ensure_dashboard(
        db,
        name="Brazil Sales",
        description="Sales LATAM filtrado para o Brasil.",
        workspace="Brazil",
        business_area="Sales",
        created_by=admin.email,
        widgets=[
            {
                "title": "Brazil - Revenue",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 0, "y": 0, "w": 4, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "filters": {"country": "Brazil"},
                },
            },
            {
                "title": "Brazil - Transactions",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 4, "y": 0, "w": 4, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_transactions.id,
                    "filters": {"country": "Brazil"},
                },
            },
            {
                "title": "Brazil - Margin %",
                "widget_type": WidgetType.KPI_CARD.value,
                "layout": {"x": 8, "y": 0, "w": 4, "h": 3},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_margin_pct.id,
                    "filters": {"country": "Brazil"},
                },
            },
            {
                "title": "Receita por Produto (Brasil)",
                "widget_type": WidgetType.DONUT_CHART.value,
                "layout": {"x": 0, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "product",
                    "filters": {"country": "Brazil"},
                    "sort": "desc",
                },
            },
            {
                "title": "Receita Mensal (Brasil)",
                "widget_type": WidgetType.LINE_CHART.value,
                "layout": {"x": 6, "y": 3, "w": 6, "h": 5},
                "config": {
                    "dataset_id": dataset_sales.id,
                    "metric_id": m_revenue.id,
                    "dimension": "date", "time_grain": "month",
                    "sort_by": "date", "sort": "asc",
                    "filters": {"country": "Brazil"},
                    "limit": 36,
                },
            },
        ],
    )

    db.commit()

    n_metrics = db.query(Metric).count()
    n_dashboards = db.query(Dashboard).count()
    n_widgets = db.query(DashboardWidget).count()

    return {
        "metrics": n_metrics,
        "dashboards": n_dashboards,
        "widgets": n_widgets,
    }


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        result = seed(db)
        print(f"[OK] Seed concluido: {result}")
    finally:
        db.close()
