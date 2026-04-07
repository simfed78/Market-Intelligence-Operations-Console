"""Seasonality feature builders."""

from __future__ import annotations

import pandas as pd


def build_seasonal_return_table(series: pd.Series) -> dict[str, pd.Series]:
    """Create seasonality lookup tables from daily returns."""
    returns = series.pct_change().dropna()
    if returns.empty:
        return {
            "month": pd.Series(dtype=float),
            "week_of_month": pd.Series(dtype=float),
            "day_of_month": pd.Series(dtype=float),
            "day_of_week": pd.Series(dtype=float),
        }
    return {
        "month": returns.groupby(returns.index.month).mean(),
        "week_of_month": returns.groupby(((returns.index.day - 1) // 7) + 1).mean(),
        "day_of_month": returns.groupby(returns.index.day).mean(),
        "day_of_week": returns.groupby(returns.index.dayofweek).mean(),
    }


def turn_of_month_bias(series: pd.Series, window: int = 3) -> float:
    """Average turn-of-month return effect."""
    returns = series.pct_change().dropna()
    if returns.empty:
        return 0.0
    flags = (returns.index.day <= window) | (returns.index.day >= 28)
    return float(returns.loc[flags].mean() * 100)
