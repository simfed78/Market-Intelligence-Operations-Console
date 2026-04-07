"""Cross-asset feature builders."""

from __future__ import annotations

import numpy as np
import pandas as pd


def relative_strength(prices: pd.DataFrame, benchmark: str = "SPY") -> pd.DataFrame:
    """Relative performance ratio vs benchmark."""
    if benchmark not in prices.columns:
        return pd.DataFrame(index=prices.index)
    base = prices[benchmark]
    ratios = prices.divide(base, axis=0)
    return ratios


def rolling_correlations(prices: pd.DataFrame, benchmark: str = "SPY", windows: list[int] | None = None) -> pd.DataFrame:
    """Latest rolling correlations vs benchmark."""
    windows = windows or [20, 60, 120]
    if benchmark not in prices.columns:
        return pd.DataFrame()
    returns = prices.pct_change().dropna()
    records = []
    for ticker in returns.columns:
        if ticker == benchmark:
            continue
        row = {"ticker": ticker}
        for window in windows:
            corr = returns[benchmark].rolling(window).corr(returns[ticker])
            row[f"corr_{window}"] = float(corr.dropna().iloc[-1]) if not corr.dropna().empty else 0.0
        records.append(row)
    return pd.DataFrame(records).set_index("ticker") if records else pd.DataFrame()


def rolling_beta(prices: pd.DataFrame, benchmark: str = "SPY", window: int = 60) -> pd.Series:
    """Rolling beta vs benchmark."""
    returns = prices.pct_change().dropna()
    if benchmark not in returns.columns:
        return pd.Series(dtype=float)
    benchmark_var = returns[benchmark].rolling(window).var()
    betas = {}
    for ticker in returns.columns:
        if ticker == benchmark:
            continue
        cov = returns[ticker].rolling(window).cov(returns[benchmark])
        beta = cov / benchmark_var
        betas[ticker] = float(beta.dropna().iloc[-1]) if not beta.dropna().empty else 0.0
    return pd.Series(betas).sort_values(ascending=False)


def lagged_correlation(target: pd.Series, driver: pd.Series, max_lag: int = 10) -> tuple[int, float]:
    """Find the best lagged correlation."""
    best_lag = 0
    best_corr = -np.inf
    target_returns = target.pct_change().dropna()
    driver_returns = driver.pct_change().dropna()
    aligned = pd.concat([target_returns, driver_returns], axis=1, join="inner").dropna()
    if aligned.empty:
        return 0, 0.0
    target_series = aligned.iloc[:, 0]
    driver_series = aligned.iloc[:, 1]
    for lag in range(-max_lag, max_lag + 1):
        corr = target_series.corr(driver_series.shift(lag))
        if pd.notna(corr) and corr > best_corr:
            best_corr = corr
            best_lag = lag
    return best_lag, float(best_corr if np.isfinite(best_corr) else 0.0)
