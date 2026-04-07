"""Breadth proxy builders."""

from __future__ import annotations

import pandas as pd


def percent_above_moving_average(prices: pd.DataFrame, window: int = 50) -> float:
    """Percentage of assets above moving average."""
    if prices.empty:
        return 0.0
    ma = prices.rolling(window).mean()
    flags = prices.iloc[-1] > ma.iloc[-1]
    return float(flags.mean() * 100)


def equal_vs_cap_relative(prices: pd.DataFrame, equal_weight: str = "RSP", cap_weight: str = "SPY", window: int = 20) -> float:
    """Equal-weight relative trend."""
    if equal_weight not in prices.columns or cap_weight not in prices.columns:
        return 0.0
    ratio = prices[equal_weight] / prices[cap_weight]
    return float(ratio.pct_change(window).iloc[-1] * 100)
