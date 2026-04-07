"""Lead-lag helpers."""

from __future__ import annotations

import pandas as pd

from src.features.cross_asset_features import lagged_correlation
from src.utils.enums import RelationshipStability


def build_leadlag_table(prices: pd.DataFrame, benchmark: str = "SPY", max_lag: int = 10) -> pd.DataFrame:
    """Build a simple lead-lag ranking table."""
    if benchmark not in prices.columns:
        return pd.DataFrame()
    records = []
    for ticker in prices.columns:
        if ticker == benchmark:
            continue
        lag, corr = lagged_correlation(prices[benchmark], prices[ticker], max_lag=max_lag)
        stability = RelationshipStability.STABLE.value if abs(corr) >= 0.45 else (
            RelationshipStability.WATCH.value if abs(corr) >= 0.25 else RelationshipStability.UNSTABLE.value
        )
        records.append(
            {
                "ticker": ticker,
                "best_lag_days": lag,
                "lagged_corr": corr,
                "stability_flag": stability,
            }
        )
    if not records:
        return pd.DataFrame()
    table = pd.DataFrame(records).sort_values(["lagged_corr"], ascending=False).reset_index(drop=True)
    return table
