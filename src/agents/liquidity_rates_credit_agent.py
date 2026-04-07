"""Liquidity, rates, and credit agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import AgentResult
from src.utils.helpers import clamp, scale_centered


@dataclass
class LiquidityRatesCreditAgent:
    """Assess rates pressure, liquidity, and credit stress."""

    def run(self, macro_frame: pd.DataFrame, market_prices: pd.DataFrame) -> AgentResult:
        """Generate rates and credit context."""
        gs2 = float(macro_frame["gs2"].dropna().iloc[-1]) if "gs2" in macro_frame and not macro_frame["gs2"].dropna().empty else 4.0
        gs10 = float(macro_frame["gs10"].dropna().iloc[-1]) if "gs10" in macro_frame and not macro_frame["gs10"].dropna().empty else 4.2
        real_yield = float(macro_frame["real_yield_10y"].dropna().iloc[-1]) if "real_yield_10y" in macro_frame and not macro_frame["real_yield_10y"].dropna().empty else 1.8
        nfci = float(macro_frame["nfci"].dropna().iloc[-1]) if "nfci" in macro_frame and not macro_frame["nfci"].dropna().empty else 0.0
        hy_oas = float(macro_frame["hy_oas"].dropna().iloc[-1]) if "hy_oas" in macro_frame and not macro_frame["hy_oas"].dropna().empty else 4.0

        curve_slope = gs10 - gs2
        rates_pressure_score = clamp(100 - scale_centered(gs2 + real_yield, scale=1.2, center=4.8))
        liquidity_score = clamp(60 - nfci * 20 + curve_slope * 8)
        credit_stress_score = clamp(scale_centered(hy_oas, scale=1.5, center=4.0))

        hyg_lqd_ratio = 1.0
        if {"HYG", "LQD"}.issubset(market_prices.columns):
            ratio = market_prices["HYG"] / market_prices["LQD"]
            hyg_lqd_ratio = float(ratio.pct_change(20).iloc[-1] * 100)
            credit_stress_score = clamp(credit_stress_score - hyg_lqd_ratio * 2)

        summary = (
            f"Rates pressure score {rates_pressure_score:.1f}, liquidity score {liquidity_score:.1f}, "
            f"credit stress score {credit_stress_score:.1f}. Curve slope is {curve_slope:.2f} and "
            f"HYG/LQD 20-day change is {hyg_lqd_ratio:.2f}%."
        )
        return AgentResult(
            name="liquidity_rates_credit",
            scores={
                "rates_pressure_score": rates_pressure_score,
                "liquidity_score": liquidity_score,
                "credit_stress_score": credit_stress_score,
            },
            summary=summary,
            details={"curve_slope": curve_slope, "hyg_lqd_ratio_20d": hyg_lqd_ratio},
        )
