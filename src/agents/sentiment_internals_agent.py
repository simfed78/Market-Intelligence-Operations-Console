"""Sentiment and internals agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.breadth_features import equal_vs_cap_relative, percent_above_moving_average
from src.features.technical_features import realized_volatility
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class SentimentInternalsAgent:
    """Measure internal market health and fragility."""

    def run(self, market_prices: pd.DataFrame, manual_sentiment: pd.DataFrame | None = None) -> AgentResult:
        """Generate breadth and sentiment proxy scores."""
        breadth_score = percent_above_moving_average(market_prices, window=50)
        equal_weight_delta = equal_vs_cap_relative(market_prices, equal_weight="RSP", cap_weight="SPY", window=20)
        vol_proxy = 0.0
        if "^VIX" in market_prices.columns:
            vol_proxy = float(market_prices["^VIX"].pct_change(10).iloc[-1] * 100)
        elif "VIXY" in market_prices.columns:
            vol_proxy = float(market_prices["VIXY"].pct_change(10).iloc[-1] * 100)

        hyg_confirmation = 0.0
        if {"HYG", "SPY"}.issubset(market_prices.columns):
            ratio = market_prices["HYG"] / market_prices["SPY"]
            hyg_confirmation = float(ratio.pct_change(20).iloc[-1] * 100)

        manual_put_call = 0.0
        manual_skew = 0.0
        if manual_sentiment is not None and not manual_sentiment.empty:
            if "PUT_CALL" in manual_sentiment.columns:
                manual_put_call = float(manual_sentiment["PUT_CALL"].dropna().iloc[-1])
            if "SKEW" in manual_sentiment.columns:
                manual_skew = float(manual_sentiment["SKEW"].dropna().iloc[-1])

        sentiment_score = clamp(50 + equal_weight_delta * 3 + hyg_confirmation * 2 - vol_proxy * 0.8)
        fragility_score = clamp(100 - breadth_score + max(vol_proxy, 0) * 0.8 + manual_skew * 0.1)
        squeeze_risk_score = clamp(50 - breadth_score * 0.3 - manual_put_call * 10 + realized_volatility(market_prices["SPY"]) * 20 if "SPY" in market_prices.columns else 50)

        summary = (
            f"Breadth score {breadth_score:.1f}, sentiment score {sentiment_score:.1f}, "
            f"fragility score {fragility_score:.1f}, squeeze risk score {squeeze_risk_score:.1f}."
        )
        return AgentResult(
            name="sentiment_internals",
            scores={
                "breadth_score": breadth_score,
                "sentiment_score": sentiment_score,
                "fragility_score": fragility_score,
                "squeeze_risk_score": squeeze_risk_score,
            },
            summary=summary,
            details={
                "equal_weight_relative_20d": equal_weight_delta,
                "hyg_confirmation_20d": hyg_confirmation,
                "vol_proxy_10d": vol_proxy,
            },
        )
