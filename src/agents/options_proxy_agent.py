"""Options and gamma proxy agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class OptionsProxyAgent:
    """Summarize options structure using public and manual proxies."""

    config: dict

    def run(self, prices: pd.DataFrame, manual_options: pd.DataFrame | None = None) -> AgentResult:
        """Generate options context."""
        manual_options = manual_options if manual_options is not None else pd.DataFrame()
        vix_level = float(prices["^VIX"].iloc[-1]) if "^VIX" in prices.columns else 18.0
        vvix_level = float(prices["VVIX"].iloc[-1]) if "VVIX" in prices.columns else vix_level * 6.5
        realized = float(prices["SPY"].pct_change().tail(20).std() * (252**0.5) * 100) if "SPY" in prices.columns else 16.0
        implied_gap = vix_level - realized
        put_call = float(manual_options["put_call"].dropna().iloc[-1]) if not manual_options.empty and "put_call" in manual_options.columns else 0.95
        skew = float(manual_options["skew"].dropna().iloc[-1]) if not manual_options.empty and "skew" in manual_options.columns else 138.0
        expected_move = float(manual_options["expected_move"].dropna().iloc[-1]) if not manual_options.empty and "expected_move" in manual_options.columns else 1.8
        gamma_flip = float(manual_options["gamma_flip"].dropna().iloc[-1]) if not manual_options.empty and "gamma_flip" in manual_options.columns else 5550.0
        dealer_positioning = float(manual_options["dealer_positioning"].dropna().iloc[-1]) if not manual_options.empty and "dealer_positioning" in manual_options.columns else 0.0

        options_structure_score = clamp(65 - max(vix_level - 16, 0) * 2 - max(vvix_level - 95, 0) * 0.2 + dealer_positioning * 30)
        squeeze_unwind_risk_score = clamp(40 + max(put_call - 0.9, 0) * 60 + max(skew - 135, 0) * 0.8 + max(implied_gap, 0) * 1.5)
        gamma_context_label = "supportive"
        if options_structure_score < 40 or squeeze_unwind_risk_score > 65:
            gamma_context_label = "unstable"
        elif squeeze_unwind_risk_score > 55:
            gamma_context_label = "squeeze-prone"
        elif expected_move < 1.5:
            gamma_context_label = "suppressive"

        summary = (
            f"Options structure score {options_structure_score:.1f}, gamma context {gamma_context_label}, "
            f"expected move {expected_move:.1f}%, squeeze/unwind risk {squeeze_unwind_risk_score:.1f}."
        )
        table = pd.DataFrame(
            [
                {
                    "vix": vix_level,
                    "vvix": vvix_level,
                    "put_call": put_call,
                    "skew": skew,
                    "expected_move": expected_move,
                    "gamma_flip": gamma_flip,
                    "dealer_positioning": dealer_positioning,
                    "options_structure_score": options_structure_score,
                    "squeeze_unwind_risk_score": squeeze_unwind_risk_score,
                    "gamma_context_label": gamma_context_label,
                }
            ]
        )
        return AgentResult(
            name="options_proxy",
            scores={
                "options_structure_score": options_structure_score,
                "squeeze_unwind_risk_score": squeeze_unwind_risk_score,
            },
            summary=summary,
            details={
                "gamma_context_label": gamma_context_label,
                "expected_move_context": expected_move,
                "options_context_table": table,
            },
        )
