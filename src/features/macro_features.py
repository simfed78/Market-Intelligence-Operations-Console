"""Macro feature builders."""

from __future__ import annotations

import pandas as pd


def yoy_change(series: pd.Series, periods: int = 12) -> pd.Series:
    """Year-over-year percentage change."""
    return series.pct_change(periods) * 100


def momentum_change(series: pd.Series, periods: int = 3) -> pd.Series:
    """Short-term directional change."""
    return series.diff(periods)


def composite_direction(frame: pd.DataFrame) -> pd.Series:
    """Average sign-based directional composite."""
    if frame.empty:
        return pd.Series(dtype=float)
    transformed = frame.apply(lambda col: col.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)))
    return transformed.mean(axis=1)
