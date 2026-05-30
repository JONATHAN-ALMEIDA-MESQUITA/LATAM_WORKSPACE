"""Data Quality engine (Phase 9)."""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.quality import DatasetQualityReport
from app.schemas.phase9 import DatasetQualityOut, QualityCheckResult
from app.services.dataset_service import _load_processed_df


def _check_not_null(df: pd.DataFrame, col: str, threshold: float = 0.95) -> QualityCheckResult:
    if col not in df.columns:
        return QualityCheckResult(
            name="not_null", column=col, passed=True, severity="info", message=f"Coluna {col} ausente (skip)."
        )
    rate = float(df[col].notna().mean())
    passed = rate >= threshold
    return QualityCheckResult(
        name="not_null",
        column=col,
        passed=passed,
        severity="critical" if not passed else "info",
        message=f"Completude {rate:.1%} (min {threshold:.0%})",
        value=round(rate, 4),
    )


def _check_positive(df: pd.DataFrame, col: str) -> QualityCheckResult:
    if col not in df.columns:
        return QualityCheckResult(name="positive", column=col, passed=True, severity="info", message="Skip.")
    numeric = pd.to_numeric(df[col], errors="coerce")
    bad = int((numeric < 0).sum())
    passed = bad == 0
    return QualityCheckResult(
        name="positive",
        column=col,
        passed=passed,
        severity="warning",
        message=f"{bad} valores negativos em {col}",
        value=bad,
    )


def _check_row_count(ds: Dataset, df: pd.DataFrame) -> QualityCheckResult:
    passed = len(df) == ds.row_count
    return QualityCheckResult(
        name="row_count_match",
        column=None,
        passed=passed,
        severity="warning",
        message=f"Parquet {len(df)} vs metadata {ds.row_count}",
        value=len(df),
    )


def _check_distinct(df: pd.DataFrame, col: str, min_distinct: int = 2) -> QualityCheckResult:
    if col not in df.columns:
        return QualityCheckResult(name="distinct", column=col, passed=True, severity="info", message="Skip.")
    n = int(df[col].nunique(dropna=True))
    passed = n >= min_distinct
    return QualityCheckResult(
        name="distinct",
        column=col,
        passed=passed,
        severity="warning",
        message=f"{n} valores distintos (min {min_distinct})",
        value=n,
    )


def run_quality_checks(ds: Dataset) -> tuple[list[QualityCheckResult], float]:
    df = _load_processed_df(ds)
    checks: list[QualityCheckResult] = [
        _check_row_count(ds, df),
        _check_not_null(df, "date"),
        _check_not_null(df, "country", 0.90),
        _check_positive(df, "revenue"),
        _check_distinct(df, "country", 2),
    ]
    # Remove skips that always pass on missing cols from score denominator
    scored = [c for c in checks if c.message != "Skip."]
    if not scored:
        scored = checks
    passed = sum(1 for c in scored if c.passed)
    score = round(100.0 * passed / len(scored), 1) if scored else 100.0
    return checks, score


def persist_quality_report(db: Session, ds: Dataset) -> DatasetQualityOut:
    checks, score = run_quality_checks(ds)
    payload = [c.model_dump() for c in checks]
    report = DatasetQualityReport(
        dataset_id=ds.id,
        score=score,
        checks_json=json.dumps(payload, default=str),
    )
    db.add(report)
    db.flush()
    return DatasetQualityOut(
        dataset_id=ds.id,
        score=score,
        checks=checks,
        run_at=report.run_at,
    )


def latest_quality(db: Session, ds: Dataset) -> DatasetQualityOut | None:
    report = (
        db.query(DatasetQualityReport)
        .filter(DatasetQualityReport.dataset_id == ds.id)
        .order_by(DatasetQualityReport.run_at.desc())
        .first()
    )
    if not report:
        return None
    checks_raw = json.loads(report.checks_json or "[]")
    return DatasetQualityOut(
        dataset_id=ds.id,
        score=report.score,
        checks=[QualityCheckResult(**c) for c in checks_raw],
        run_at=report.run_at,
    )
