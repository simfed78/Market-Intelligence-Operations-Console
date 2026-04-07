"""Research-grade basket performance helpers."""

from __future__ import annotations

import pandas as pd


def basket_performance(prices: pd.DataFrame, basket: pd.DataFrame, benchmark: str = "SPY", friction_bps: float = 10.0) -> dict:
    """Compute simple basket vs benchmark performance."""
    if prices.empty or basket.empty:
        return {"basket_return": 0.0, "benchmark_return": 0.0, "relative_return": 0.0, "basket_drawdown": 0.0, "benchmark_drawdown": 0.0, "turnover_estimate": 0.0}
    members = [ticker for ticker in basket["ticker"] if ticker in prices.columns]
    if not members:
        return {"basket_return": 0.0, "benchmark_return": 0.0, "relative_return": 0.0, "basket_drawdown": 0.0, "benchmark_drawdown": 0.0, "turnover_estimate": 0.0}
    weights = basket.set_index("ticker")["weight"].reindex(members).fillna(0)
    returns = prices[members].pct_change().fillna(0)
    basket_curve = (1 + returns.mul(weights, axis=1).sum(axis=1)).cumprod()
    benchmark_curve = (1 + prices[benchmark].pct_change().fillna(0)).cumprod() if benchmark in prices.columns else pd.Series(1.0, index=prices.index)
    basket_dd = (basket_curve / basket_curve.cummax() - 1).min() * 100
    benchmark_dd = (benchmark_curve / benchmark_curve.cummax() - 1).min() * 100
    turnover = abs(weights.diff().fillna(0)).sum() if hasattr(weights, "diff") else 0.0
    return {
        "basket_return": float((basket_curve.iloc[-1] - 1) * 100),
        "benchmark_return": float((benchmark_curve.iloc[-1] - 1) * 100),
        "relative_return": float(((basket_curve.iloc[-1] - benchmark_curve.iloc[-1])) * 100),
        "basket_drawdown": float(basket_dd),
        "benchmark_drawdown": float(benchmark_dd),
        "turnover_estimate": float(turnover + friction_bps / 10000),
    }
