"""Engine de Forecasting (Phase 4).

3 algoritmos:
    - NAIVE_SEASONAL : baseline. yhat[t+h] = media dos ultimos N valores do mesmo "slot" sazonal.
    - LINEAR_TREND   : sklearn LinearRegression sobre trend (t) + dummies de sazonalidade.
    - HOLT_WINTERS   : statsmodels ExponentialSmoothing (trend + seasonal).

Suporta forecast agrupado: se group_by != [], gera 1 serie por grupo.
Aplica holdout (ultimos N periodos) para backtest e computa MAE/RMSE/MAPE.

Output:
    {
        points: [{ds, y?, yhat?, yhat_lower?, yhat_upper?, is_forecast, group_key?}],
        metrics: {grupo: {mae, rmse, mape, n_train, n_test}},
        rows_in, rows_forecast, groups_count
    }
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from app.models.dataset import Dataset
from app.models.forecast import ForecastAlgorithm, ForecastFrequency


class ForecastError(Exception):
    """Erro de execucao do forecast."""


# Mapeamento frequency -> sazonalidade default + offset
_FREQ_SEASONAL = {
    "D": 7,
    "W": 52,
    "M": 12,
    "Q": 4,
    "Y": 1,
}

_FREQ_OFFSET = {
    "D": pd.DateOffset(days=1),
    "W": pd.DateOffset(weeks=1),
    "M": pd.DateOffset(months=1),
    "Q": pd.DateOffset(months=3),
    "Y": pd.DateOffset(years=1),
}

# Pandas >= 2.2 troca M/Q/Y por ME/QE/YE no resample
_FREQ_RESAMPLE = {
    "D": "D",
    "W": "W",
    "M": "ME",
    "Q": "QE",
    "Y": "YE",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_dataset_df(ds: Dataset) -> pd.DataFrame:
    if not ds.processed_path:
        raise ForecastError(f"Dataset '{ds.name}' sem parquet processado.")
    path = Path(ds.processed_path)
    if not path.exists():
        raise ForecastError(f"Parquet nao encontrado: {path}")
    return pd.read_parquet(path)


def _apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Filtros simples col=value (string|number) ou col=[v1,v2]."""
    out = df
    for col, val in (filters or {}).items():
        if col not in out.columns:
            continue
        if isinstance(val, list):
            out = out[out[col].isin(val)]
        else:
            out = out[out[col] == val]
    return out


def _coerce_series(
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    frequency: str,
    aggregation: str,
) -> pd.DataFrame:
    """Normaliza para series temporal: ds, y agregado por frequency."""
    if date_col not in df.columns:
        raise ForecastError(f"date_column '{date_col}' nao existe no dataset.")
    if target_col not in df.columns:
        raise ForecastError(f"target_column '{target_col}' nao existe no dataset.")
    if not pd.api.types.is_numeric_dtype(df[target_col]):
        raise ForecastError(
            f"target_column '{target_col}' precisa ser numerica (atual: {df[target_col].dtype})."
        )

    work = df[[date_col, target_col]].copy()
    work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
    work = work.dropna(subset=[date_col])
    work = work.set_index(date_col).sort_index()

    agg = "sum" if (aggregation or "sum").lower() == "sum" else "mean"
    resample_freq = _FREQ_RESAMPLE.get(frequency, frequency)
    resampled = getattr(work[target_col].resample(resample_freq), agg)()
    out = resampled.reset_index()
    out.columns = ["ds", "y"]
    out["y"] = out["y"].astype(float)
    return out


def _split_holdout(
    series: pd.DataFrame, holdout: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa serie em train + test (holdout)."""
    if holdout <= 0 or holdout >= len(series):
        return series.copy(), series.iloc[0:0].copy()
    train = series.iloc[:-holdout].copy()
    test = series.iloc[-holdout:].copy()
    return train, test


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """MAE, RMSE, MAPE com guards p/ vetores vazios ou zeros."""
    if len(y_true) == 0:
        return {"mae": None, "rmse": None, "mape": None, "n_test": 0}
    err = y_true - y_pred
    mae = float(np.mean(np.abs(err)))
    rmse = float(math.sqrt(np.mean(err ** 2)))
    # MAPE: ignora y=0
    mask = y_true != 0
    if mask.any():
        mape = float(np.mean(np.abs(err[mask] / y_true[mask])) * 100.0)
    else:
        mape = None
    return {"mae": mae, "rmse": rmse, "mape": mape, "n_test": int(len(y_true))}


# ---------------------------------------------------------------------------
# Algoritmos
# ---------------------------------------------------------------------------

def _algo_naive_seasonal(
    train: pd.DataFrame, horizon_steps: list[pd.Timestamp], params: dict, frequency: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Media dos ultimos N periodos do mesmo "slot" sazonal."""
    season = int(params.get("season", _FREQ_SEASONAL.get(frequency, 12)))
    lookback = int(params.get("lookback_cycles", 3))
    y = train["y"].values
    if len(y) == 0:
        raise ForecastError("Naive Seasonal: train vazio.")

    yhat = []
    for i in range(len(horizon_steps)):
        # Posicao no ciclo sazonal
        slot = (len(y) + i) % season
        # Pega os valores no mesmo slot dos ultimos `lookback` ciclos
        samples = []
        cyc = 1
        while len(samples) < lookback and (len(y) - cyc * season + slot) >= 0:
            idx = len(y) - cyc * season + slot
            if 0 <= idx < len(y):
                samples.append(y[idx])
            cyc += 1
        if not samples:
            # Fallback: media global
            yhat.append(float(np.mean(y)))
        else:
            yhat.append(float(np.mean(samples)))
    yhat_arr = np.array(yhat, dtype=float)

    # Intervalo de confianca = +- 1.96 * std do erro recente
    if len(y) > season:
        residual_std = float(np.std(y[-season * 2 :])) if len(y) >= season * 2 else float(np.std(y))
    else:
        residual_std = float(np.std(y)) if len(y) > 1 else 0.0
    band = 1.96 * residual_std
    return yhat_arr, yhat_arr - band, yhat_arr + band


def _algo_linear_trend(
    train: pd.DataFrame, horizon_steps: list[pd.Timestamp], params: dict, frequency: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """LinearRegression com trend + dummies de mes (ou periodo)."""
    from sklearn.linear_model import LinearRegression

    season = int(params.get("season", _FREQ_SEASONAL.get(frequency, 12)))
    n = len(train)
    if n < 3:
        raise ForecastError("Linear Trend: precisa de >=3 pontos de treino.")

    def make_features(t_idx: np.ndarray, dates: pd.DatetimeIndex) -> np.ndarray:
        # trend (escalado) + one-hot do mes (ou periodo do ciclo)
        trend = (t_idx - t_idx.mean()) / (t_idx.std() if t_idx.std() > 0 else 1.0)
        # Sazonalidade baseada na frequency
        if frequency == "M":
            slot = dates.month - 1
        elif frequency == "Q":
            slot = dates.quarter - 1
        elif frequency == "W":
            slot = dates.isocalendar().week.values % 52
        elif frequency == "D":
            slot = dates.dayofweek
        else:
            slot = np.zeros(len(dates), dtype=int)
        dummies = np.eye(max(season, 1))[np.clip(slot, 0, season - 1)]
        return np.column_stack([trend.reshape(-1, 1), dummies])

    t_idx_train = np.arange(n, dtype=float)
    X_train = make_features(t_idx_train, pd.DatetimeIndex(train["ds"]))
    y_train = train["y"].values

    model = LinearRegression()
    model.fit(X_train, y_train)

    # Residuo no treino p/ intervalo
    resid = y_train - model.predict(X_train)
    residual_std = float(np.std(resid)) if len(resid) > 1 else 0.0

    t_idx_future = np.arange(n, n + len(horizon_steps), dtype=float)
    X_future = make_features(t_idx_future, pd.DatetimeIndex(horizon_steps))
    yhat = model.predict(X_future)
    band = 1.96 * residual_std
    return yhat, yhat - band, yhat + band


def _algo_holt_winters(
    train: pd.DataFrame, horizon_steps: list[pd.Timestamp], params: dict, frequency: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """statsmodels ExponentialSmoothing (Holt-Winters)."""
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
    except ImportError as exc:
        raise ForecastError(
            "Holt-Winters requer statsmodels. Instale: pip install statsmodels"
        ) from exc

    season = int(params.get("season", _FREQ_SEASONAL.get(frequency, 12)))
    seasonal = params.get("seasonal", "add")  # add | mul | None
    trend = params.get("trend", "add")  # add | mul | None
    damped = bool(params.get("damped", False))

    y = train["y"].astype(float).values
    n = len(y)
    use_seasonal = season > 1 and n >= 2 * season
    fit_kwargs = {
        "trend": trend if trend in {"add", "mul"} else None,
        "damped_trend": damped if trend else False,
        "seasonal": seasonal if use_seasonal and seasonal in {"add", "mul"} else None,
        "seasonal_periods": season if use_seasonal else None,
        "initialization_method": "estimated",
    }
    if n < 3:
        raise ForecastError("Holt-Winters: precisa de >=3 pontos de treino.")

    try:
        model = ExponentialSmoothing(y, **fit_kwargs).fit(optimized=True)
    except Exception as exc:
        # Fallback: sem sazonalidade
        try:
            model = ExponentialSmoothing(y, trend=fit_kwargs["trend"]).fit(optimized=True)
        except Exception as exc2:
            raise ForecastError(f"Holt-Winters: falha ao ajustar ({exc2})") from exc2

    yhat = np.array(model.forecast(len(horizon_steps)), dtype=float)
    resid = model.resid if hasattr(model, "resid") else (y - model.fittedvalues)
    residual_std = float(np.std(resid)) if len(resid) > 1 else 0.0
    band = 1.96 * residual_std
    return yhat, yhat - band, yhat + band


_ALGO_DISPATCH: dict[str, Callable] = {
    ForecastAlgorithm.NAIVE_SEASONAL.value: _algo_naive_seasonal,
    ForecastAlgorithm.LINEAR_TREND.value: _algo_linear_trend,
    ForecastAlgorithm.HOLT_WINTERS.value: _algo_holt_winters,
}


# ---------------------------------------------------------------------------
# Treino por grupo
# ---------------------------------------------------------------------------

def _build_future_dates(last_ds: pd.Timestamp, horizon: int, frequency: str) -> list[pd.Timestamp]:
    offset = _FREQ_OFFSET.get(frequency, pd.DateOffset(months=1))
    return [last_ds + offset * (i + 1) for i in range(horizon)]


@dataclass
class GroupResult:
    group_key: str | None
    points: list[dict]
    metrics: dict


def _train_one_series(
    series: pd.DataFrame,
    *,
    algorithm: str,
    params: dict,
    horizon: int,
    holdout: int,
    frequency: str,
    group_key: str | None,
) -> GroupResult:
    if len(series) < 3:
        raise ForecastError(
            f"Serie '{group_key or 'global'}' tem apenas {len(series)} pontos (minimo 3)."
        )

    train, test = _split_holdout(series, holdout)
    if len(train) < 3:
        # Sem espaco pra holdout - usa serie inteira como train
        train, test = series.copy(), series.iloc[0:0].copy()

    algo_fn = _ALGO_DISPATCH.get(algorithm)
    if not algo_fn:
        raise ForecastError(f"Algoritmo desconhecido: {algorithm}")

    # 1. Backtest no holdout (se houver)
    backtest_pred = None
    metrics = {"mae": None, "rmse": None, "mape": None, "n_test": 0, "n_train": int(len(train))}
    if len(test) > 0:
        test_steps = list(pd.DatetimeIndex(test["ds"]))
        bt_yhat, _, _ = algo_fn(train, test_steps, params, frequency)
        backtest_pred = bt_yhat
        metrics.update(_compute_metrics(test["y"].values, bt_yhat))

    # 2. Refit no dataset completo e projeta horizon
    last_ds = pd.Timestamp(series["ds"].iloc[-1])
    future_dates = _build_future_dates(last_ds, horizon, frequency)
    yhat, yhat_lower, yhat_upper = algo_fn(series, future_dates, params, frequency)

    # 3. Monta points (historico + holdout-pred + futuro)
    points: list[dict] = []
    # Historico (treino + teste, com y real)
    for i, row in series.reset_index(drop=True).iterrows():
        ds = row["ds"]
        y_val = float(row["y"]) if pd.notna(row["y"]) else None
        # Se essa data e parte do holdout, pega yhat do backtest
        bt_yhat = None
        if backtest_pred is not None and i >= len(train):
            bt_yhat = float(backtest_pred[i - len(train)])
        points.append({
            "ds": ds.strftime("%Y-%m-%d"),
            "y": y_val,
            "yhat": bt_yhat,
            "yhat_lower": None,
            "yhat_upper": None,
            "is_forecast": False,
            "group_key": group_key,
        })
    # Futuro
    for i, ds in enumerate(future_dates):
        points.append({
            "ds": ds.strftime("%Y-%m-%d"),
            "y": None,
            "yhat": float(yhat[i]),
            "yhat_lower": float(yhat_lower[i]),
            "yhat_upper": float(yhat_upper[i]),
            "is_forecast": True,
            "group_key": group_key,
        })

    return GroupResult(group_key=group_key, points=points, metrics=metrics)


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

@dataclass
class TrainResult:
    points: list[dict]
    metrics: dict  # {group_key: {mae, rmse, mape, n_test, n_train}}
    rows_in: int
    rows_forecast: int
    groups_count: int


def train(
    *,
    ds: Dataset,
    target_column: str,
    date_column: str,
    frequency: str = "M",
    group_by: list[str] | None = None,
    aggregation: str = "sum",
    algorithm: str = "holt_winters",
    algorithm_params: dict | None = None,
    horizon: int = 12,
    holdout_periods: int = 6,
    filters: dict | None = None,
) -> TrainResult:
    """Treina o forecast e retorna pontos + metricas. NAO persiste nada."""
    if frequency not in _FREQ_SEASONAL:
        raise ForecastError(
            f"frequency invalido: {frequency}. Validos: {list(_FREQ_SEASONAL.keys())}"
        )

    df = _load_dataset_df(ds)
    df = _apply_filters(df, filters or {})
    if df.empty:
        raise ForecastError("Dataset vazio apos filtros.")

    group_by = group_by or []
    params = algorithm_params or {}

    all_points: list[dict] = []
    metrics_by_group: dict[str, dict] = {}
    rows_in = 0
    rows_forecast = 0
    groups_count = 0

    if group_by:
        missing = [c for c in group_by if c not in df.columns]
        if missing:
            raise ForecastError(f"Colunas de group_by inexistentes: {', '.join(missing)}")
        for keys, sub in df.groupby(group_by, dropna=False):
            group_key = " | ".join(str(k) for k in (keys if isinstance(keys, tuple) else [keys]))
            try:
                series = _coerce_series(sub, date_column, target_column, frequency, aggregation)
                if len(series) < 3:
                    continue
                rows_in += int(len(series))
                result = _train_one_series(
                    series,
                    algorithm=algorithm,
                    params=params,
                    horizon=horizon,
                    holdout=holdout_periods,
                    frequency=frequency,
                    group_key=group_key,
                )
                all_points.extend(result.points)
                metrics_by_group[group_key] = result.metrics
                rows_forecast += horizon
                groups_count += 1
            except ForecastError as exc:
                metrics_by_group[group_key] = {"error": str(exc)}
    else:
        series = _coerce_series(df, date_column, target_column, frequency, aggregation)
        rows_in = int(len(series))
        result = _train_one_series(
            series,
            algorithm=algorithm,
            params=params,
            horizon=horizon,
            holdout=holdout_periods,
            frequency=frequency,
            group_key=None,
        )
        all_points = result.points
        metrics_by_group["__global__"] = result.metrics
        rows_forecast = horizon
        groups_count = 1

    if groups_count == 0:
        raise ForecastError("Nenhum grupo com dados suficientes para forecast.")

    return TrainResult(
        points=all_points,
        metrics=metrics_by_group,
        rows_in=rows_in,
        rows_forecast=rows_forecast,
        groups_count=groups_count,
    )


def points_to_dataframe(points: list[dict]) -> pd.DataFrame:
    """Converte points em DataFrame com colunas tipadas (para gravar como dataset)."""
    df = pd.DataFrame(points)
    if "ds" in df.columns:
        df["ds"] = pd.to_datetime(df["ds"])
    return df
