"""Gerador de bases sintéticas para a demo.

Datasets disponíveis (conforme especificação):
    - sales_latam               (>= 5.000 linhas)
    - finance_actual_budget
    - supplier_performance
    - cash_flow
    - commission_forecast

Cada gerador retorna um pandas.DataFrame. A persistência (parquet em
storage/sample_data/) é feita pelo dataset_service.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

import numpy as np
import pandas as pd


COUNTRIES = ["Brazil", "Colombia", "Mexico", "Argentina", "Chile", "Peru"]
CURRENCIES = {
    "Brazil": "BRL",
    "Colombia": "COP",
    "Mexico": "MXN",
    "Argentina": "ARS",
    "Chile": "CLP",
    "Peru": "PEN",
}
BUSINESS_UNITS = ["Retail", "Wholesale", "Corporate", "E-commerce"]
PRODUCTS = [
    "Product Alpha", "Product Beta", "Product Gamma", "Product Delta",
    "Product Epsilon", "Product Zeta", "Product Eta", "Product Theta",
]
CHANNELS = ["Online", "Retail Store", "Partner", "Direct Sales"]
CLIENTS_POOL = [f"Client {chr(ord('A') + i)}{i:02d}" for i in range(40)]
SALES_REPS_POOL = [
    "Lucas Pereira", "Camila Souza", "Diego Lopez", "Mariana Castro",
    "Felipe Andrade", "Sofia Mendes", "Rodrigo Vargas", "Beatriz Costa",
    "Andres Garcia", "Valentina Ortiz", "Mateus Lima", "Isabela Pinto",
]
SUPPLIERS_POOL = [f"Supplier {chr(ord('A') + i)}" for i in range(15)]
CATEGORIES = ["Logistics", "Technology", "Office", "Marketing", "Facilities", "Travel"]
RISK_LEVELS = ["Low", "Medium", "High"]
ACCOUNTS = [
    ("Revenue", "Income"),
    ("Cost of Sales", "Cost"),
    ("Operating Expenses", "Cost"),
    ("Marketing", "Cost"),
    ("Salaries", "Cost"),
    ("Taxes", "Cost"),
    ("Other Income", "Income"),
]
SCENARIOS = ["Actual", "Budget", "Forecast", "Prior Year"]
AGING_BUCKETS = ["0-30", "31-60", "61-90", "91-180", "180+"]


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _month_range(start: date, months: int) -> list[date]:
    out: list[date] = []
    y, m = start.year, start.month
    for _ in range(months):
        out.append(date(y, m, 1))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


# ---------------------------------------------------------------------------
# sales_latam
# ---------------------------------------------------------------------------

def gen_sales_latam(n_rows: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = _rng(seed)
    start = date(2024, 1, 1)
    days = (date(2026, 4, 30) - start).days

    dates = [start + timedelta(days=int(d)) for d in rng.integers(0, days, n_rows)]
    countries = rng.choice(COUNTRIES, n_rows, p=[0.35, 0.15, 0.20, 0.10, 0.12, 0.08])

    # Revenue dependente do país (Brazil/Mexico maiores)
    base_rev = np.where(
        np.isin(countries, ["Brazil", "Mexico"]),
        rng.lognormal(mean=8.5, sigma=0.7, size=n_rows),
        rng.lognormal(mean=7.8, sigma=0.6, size=n_rows),
    )
    revenue = np.round(base_rev, 2)
    cost = np.round(revenue * rng.uniform(0.55, 0.85, n_rows), 2)
    margin = np.round(revenue - cost, 2)
    transactions = rng.integers(1, 80, n_rows)

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "country": countries,
            "client": rng.choice(CLIENTS_POOL, n_rows),
            "sales_rep": rng.choice(SALES_REPS_POOL, n_rows),
            "business_unit": rng.choice(BUSINESS_UNITS, n_rows),
            "product": rng.choice(PRODUCTS, n_rows),
            "revenue": revenue,
            "cost": cost,
            "margin": margin,
            "transactions": transactions,
            "currency": [CURRENCIES[c] for c in countries],
            "channel": rng.choice(CHANNELS, n_rows),
        }
    )
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    df = df[
        [
            "date", "year", "month", "country", "client", "sales_rep",
            "business_unit", "product", "revenue", "cost", "margin",
            "transactions", "currency", "channel",
        ]
    ]
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# client_master / product_catalog — dimensões para joins no Ad-Hoc Report
# ---------------------------------------------------------------------------

def gen_client_master(seed: int = 43) -> pd.DataFrame:
    """Dimensão de clientes — join com sales_latam via coluna `client`."""
    rng = _rng(seed)
    tiers = ["Bronze", "Silver", "Gold", "Platinum"]
    industries = ["Retail", "Manufacturing", "Services", "Technology", "Finance", "Healthcare"]
    regions = ["South", "North", "Central", "Andes", "Caribbean"]
    rows = []
    for i, client in enumerate(CLIENTS_POOL):
        rows.append(
            {
                "client": client,
                "client_code": f"CL-{i + 1:04d}",
                "industry": rng.choice(industries),
                "tier": rng.choice(tiers, p=[0.30, 0.35, 0.25, 0.10]),
                "region": rng.choice(regions),
                "account_manager": rng.choice(SALES_REPS_POOL),
                "credit_limit_usd": round(float(rng.uniform(50_000, 2_000_000)), 2),
                "is_strategic": bool(rng.random() < 0.15),
                "onboard_year": int(rng.integers(2015, 2024)),
            }
        )
    return pd.DataFrame(rows)


def gen_product_catalog(seed: int = 44) -> pd.DataFrame:
    """Dimensão de produtos — join com sales_latam via coluna `product`."""
    rng = _rng(seed)
    categories = ["Hardware", "Software", "Services", "Consumables", "Subscription"]
    rows = []
    for i, product in enumerate(PRODUCTS):
        list_price = round(float(rng.uniform(120, 4500)), 2)
        unit_cost = round(list_price * float(rng.uniform(0.35, 0.72)), 2)
        rows.append(
            {
                "product": product,
                "product_code": f"PRD-{i + 1:03d}",
                "category": rng.choice(categories),
                "list_price_usd": list_price,
                "unit_cost_usd": unit_cost,
                "margin_target_pct": round(float(rng.uniform(0.18, 0.42)), 3),
                "is_active": bool(rng.random() < 0.92),
                "launch_year": int(rng.integers(2018, 2025)),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# finance_actual_budget
# ---------------------------------------------------------------------------

def gen_finance_actual_budget(seed: int = 43) -> pd.DataFrame:
    rng = _rng(seed)
    months = _month_range(date(2024, 1, 1), 28)
    rows = []
    for d in months:
        for country in COUNTRIES:
            for acc_name, acc_group in ACCOUNTS:
                for bu in BUSINESS_UNITS:
                    base = rng.uniform(40_000, 350_000)
                    actual = round(base * rng.uniform(0.85, 1.15), 2)
                    budget = round(base * rng.uniform(0.90, 1.05), 2)
                    forecast = round(base * rng.uniform(0.95, 1.10), 2)
                    rows.append(
                        {
                            "date": d,
                            "year": d.year,
                            "month": d.month,
                            "country": country,
                            "account": acc_name,
                            "account_group": acc_group,
                            "scenario": "Actual",
                            "actual": actual,
                            "budget": budget,
                            "forecast": forecast,
                            "currency": CURRENCIES[country],
                            "business_unit": bu,
                        }
                    )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# supplier_performance
# ---------------------------------------------------------------------------

def gen_supplier_performance(seed: int = 44) -> pd.DataFrame:
    rng = _rng(seed)
    months = _month_range(date(2024, 6, 1), 22)
    rows = []
    for d in months:
        for country in COUNTRIES:
            for supplier in SUPPLIERS_POOL:
                if rng.random() < 0.3:
                    continue  # nem todo supplier opera em todo país/mês
                spend = round(rng.uniform(10_000, 250_000), 2)
                savings = round(spend * rng.uniform(0.0, 0.18), 2)
                sla = round(rng.uniform(70, 99), 1)
                quality = round(rng.uniform(65, 99), 1)
                risk = (
                    "High"
                    if sla < 80 or quality < 75
                    else "Medium"
                    if sla < 90
                    else "Low"
                )
                rows.append(
                    {
                        "date": d,
                        "country": country,
                        "supplier": supplier,
                        "category": rng.choice(CATEGORIES),
                        "spend": spend,
                        "savings": savings,
                        "transactions": int(rng.integers(5, 400)),
                        "sla_score": sla,
                        "quality_score": quality,
                        "risk_level": risk,
                    }
                )
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


# ---------------------------------------------------------------------------
# cash_flow
# ---------------------------------------------------------------------------

def gen_cash_flow(n_rows: int = 4500, seed: int = 45) -> pd.DataFrame:
    rng = _rng(seed)
    start = date(2025, 1, 1)
    horizon = 540
    due_dates = [start + timedelta(days=int(d)) for d in rng.integers(0, horizon, n_rows)]
    countries = rng.choice(COUNTRIES, n_rows)
    types = rng.choice(["AR", "AP"], n_rows, p=[0.55, 0.45])
    amounts = np.round(rng.lognormal(mean=9.0, sigma=0.9, size=n_rows), 2)
    today = pd.Timestamp("2026-05-28")

    df = pd.DataFrame(
        {
            "due_date": pd.to_datetime(due_dates),
            "country": countries,
            "client_vendor": rng.choice(CLIENTS_POOL + SUPPLIERS_POOL, n_rows),
            "type": types,
            "amount": amounts,
            "currency": [CURRENCIES[c] for c in countries],
            "status": rng.choice(
                ["Open", "Paid", "Partial", "Overdue", "Disputed"],
                n_rows,
                p=[0.45, 0.30, 0.10, 0.10, 0.05],
            ),
        }
    )

    days_to_due = (df["due_date"] - today).dt.days
    aging = pd.cut(
        -days_to_due,
        bins=[-99999, 0, 30, 60, 90, 180, 99999],
        labels=["future", "0-30", "31-60", "61-90", "91-180", "180+"],
    )
    df["aging_bucket"] = aging.astype(str)
    df["payment_probability"] = np.round(
        rng.uniform(0.45, 0.99, n_rows)
        - np.where(df["status"] == "Overdue", 0.25, 0)
        - np.where(df["status"] == "Disputed", 0.20, 0),
        2,
    ).clip(0.05, 0.99)

    return df.sort_values("due_date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# commission_forecast
# ---------------------------------------------------------------------------

def gen_commission_forecast(seed: int = 46) -> pd.DataFrame:
    rng = _rng(seed)
    months = _month_range(date(2025, 1, 1), 18)
    rows = []
    for m in months:
        for country in COUNTRIES:
            for rep in rng.choice(SALES_REPS_POOL, size=6, replace=False):
                for product in rng.choice(PRODUCTS, size=3, replace=False):
                    for client in rng.choice(CLIENTS_POOL, size=2, replace=False):
                        revenue = round(rng.uniform(8_000, 95_000), 2)
                        transactions = int(rng.integers(1, 25))
                        rate = round(float(rng.uniform(0.015, 0.08)), 4)
                        historical = round(revenue * rate * rng.uniform(0.7, 1.3), 2)
                        target = round(revenue * rate * rng.uniform(1.05, 1.30), 2)
                        rows.append(
                            {
                                "month": m,
                                "country": country,
                                "sales_rep": rep,
                                "client": client,
                                "product": product,
                                "revenue": revenue,
                                "transactions": transactions,
                                "commission_rate": rate,
                                "historical_commission": historical,
                                "target": target,
                            }
                        )
    df = pd.DataFrame(rows)
    df["month"] = pd.to_datetime(df["month"])
    return df


# ---------------------------------------------------------------------------
# Catálogo público
# ---------------------------------------------------------------------------

SAMPLE_DATASETS: dict[str, dict] = {
    "sales_latam": {
        "name": "sales_latam",
        "description": "Vendas LATAM por país, cliente, produto e canal (sintético).",
        "business_area": "Sales",
        "workspace": "LATAM",
        "generator": gen_sales_latam,
    },
    "client_master": {
        "name": "client_master",
        "description": "Dimensão de clientes (indústria, tier, região) — join via `client`.",
        "business_area": "Sales",
        "workspace": "LATAM",
        "generator": gen_client_master,
    },
    "product_catalog": {
        "name": "product_catalog",
        "description": "Catálogo de produtos (categoria, preço, margem) — join via `product`.",
        "business_area": "Sales",
        "workspace": "LATAM",
        "generator": gen_product_catalog,
    },
    "finance_actual_budget": {
        "name": "finance_actual_budget",
        "description": "Actual vs Budget vs Forecast por país, conta e BU.",
        "business_area": "Finance",
        "workspace": "LATAM",
        "generator": gen_finance_actual_budget,
    },
    "supplier_performance": {
        "name": "supplier_performance",
        "description": "Performance de fornecedores: gasto, savings, SLA, qualidade, risco.",
        "business_area": "Supplier",
        "workspace": "LATAM",
        "generator": gen_supplier_performance,
    },
    "cash_flow": {
        "name": "cash_flow",
        "description": "AR/AP com vencimento, aging bucket e probabilidade de pagamento.",
        "business_area": "Finance",
        "workspace": "LATAM",
        "generator": gen_cash_flow,
    },
    "commission_forecast": {
        "name": "commission_forecast",
        "description": "Comissões previstas por rep, cliente, produto e mês.",
        "business_area": "Sales",
        "workspace": "LATAM",
        "generator": gen_commission_forecast,
    },
}


def get_generator(name: str) -> Callable[..., pd.DataFrame]:
    if name not in SAMPLE_DATASETS:
        raise KeyError(f"Sample dataset desconhecido: {name}")
    return SAMPLE_DATASETS[name]["generator"]
