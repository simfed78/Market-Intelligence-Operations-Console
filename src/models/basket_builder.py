"""Basket building helpers."""

from __future__ import annotations

import pandas as pd


def build_weighted_basket(table: pd.DataFrame, max_names: int, weighting: str = "equal", min_score: float = 0.0, max_single_weight: float = 0.35) -> pd.DataFrame:
    """Create a simple basket from ranked names."""
    if table.empty:
        return pd.DataFrame(columns=["ticker", "weight", "weighting", "rationale"])
    subset = table[table.get("early_opportunity_score", table.get("score", 0)) >= min_score].head(max_names).copy()
    if subset.empty:
        subset = table.head(max_names).copy()
    score_col = "early_opportunity_score" if "early_opportunity_score" in subset.columns else "score"
    if weighting == "score" and subset[score_col].sum() > 0:
        subset["weight"] = subset[score_col] / subset[score_col].sum()
    else:
        subset["weight"] = 1 / len(subset)
    subset["weight"] = subset["weight"].clip(upper=max_single_weight)
    subset["weight"] = subset["weight"] / subset["weight"].sum()
    subset["weighting"] = weighting
    subset["rationale"] = subset.apply(lambda row: f"{row.get('ticker', '')} selected with {score_col} {row.get(score_col, 0):.1f}.", axis=1)
    return subset[["ticker", "weight", "weighting", "rationale"]]
