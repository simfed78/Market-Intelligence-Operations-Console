"""Cross-asset lead-lag agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.cross_asset_features import relative_strength, rolling_beta, rolling_correlations
from src.models.leadlag import build_leadlag_table
from src.models.scoring import AgentResult
from src.models.validation import relationship_instability


@dataclass
class CrossAssetLeadLagAgent:
    """Detect cross-asset proxy relationships and lead-lag behavior."""

    windows: list[int]
    max_lag: int = 10

    def run(self, market_prices: pd.DataFrame, benchmark: str = "SPY") -> AgentResult:
        """Generate active drivers and stability flags."""
        corr_table = rolling_correlations(market_prices, benchmark=benchmark, windows=self.windows)
        beta_series = rolling_beta(market_prices, benchmark=benchmark)
        leadlag_table = build_leadlag_table(market_prices, benchmark=benchmark, max_lag=self.max_lag)
        rs = relative_strength(market_prices, benchmark=benchmark)

        if not leadlag_table.empty:
            leadlag_table["relative_strength_60d"] = leadlag_table["ticker"].map(
                lambda ticker: float(rs[ticker].pct_change(60).iloc[-1] * 100) if ticker in rs.columns else 0.0
            )
            leadlag_table["beta_60d"] = leadlag_table["ticker"].map(lambda ticker: float(beta_series.get(ticker, 0.0)))
            active_drivers = leadlag_table.sort_values(["lagged_corr", "relative_strength_60d"], ascending=False).head(10)
        else:
            active_drivers = pd.DataFrame()

        instability = relationship_instability(corr_table)
        stability_flags = {
            "correlation_instability": float(instability),
            "proxy_stability": "unstable" if instability > 0.25 else ("watch" if instability > 0.15 else "stable"),
        }
        summary = "Cross-asset relationships are unavailable."
        if not active_drivers.empty:
            top = active_drivers.iloc[0]
            summary = (
                f"Top active driver is {top['ticker']} with lagged correlation {top['lagged_corr']:.2f} "
                f"and best lag {int(top['best_lag_days'])} days. Proxy stability is {stability_flags['proxy_stability']}."
            )
        return AgentResult(
            name="cross_asset_leadlag",
            scores={"proxy_stability_score": max(0.0, 100 - instability * 100)},
            summary=summary,
            details={
                "active_drivers_table": active_drivers,
                "lead_lag_table": leadlag_table,
                "proxy_stability_flags": stability_flags,
                "correlation_table": corr_table,
            },
        )
