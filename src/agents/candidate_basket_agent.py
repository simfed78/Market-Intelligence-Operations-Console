"""Candidate basket agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.basket_builder import build_weighted_basket
from src.models.scoring import AgentResult


@dataclass
class CandidateBasketAgent:
    """Create research baskets from current rankings."""

    config: dict

    def run(self, sector_table: pd.DataFrame, cyclical_table: pd.DataFrame, opportunity_table: pd.DataFrame) -> AgentResult:
        """Build configured baskets."""
        baskets: dict[str, pd.DataFrame] = {}
        defs = self.config.get("baskets", {})
        controls = self.config.get("controls", {})
        for name, rules in defs.items():
            source = rules.get("source", "")
            if source == "sector":
                base = sector_table
            elif source == "cyclical":
                base = cyclical_table
            elif source == "opportunity":
                base = opportunity_table
            else:
                tickers = rules.get("tickers", [])
                base = opportunity_table[opportunity_table["ticker"].isin(tickers)] if not opportunity_table.empty else pd.DataFrame({"ticker": tickers, "score": [50.0] * len(tickers)})
            baskets[name] = build_weighted_basket(
                base,
                max_names=rules.get("max_names", 5),
                weighting=rules.get("weighting", "equal"),
                min_score=rules.get("min_score", 0.0),
                max_single_weight=controls.get("max_single_weight", 0.35),
            )
        summary = f"Generated {len([k for k, v in baskets.items() if not v.empty])} candidate baskets."
        return AgentResult(
            name="candidate_baskets",
            scores={"basket_count": float(len(baskets))},
            summary=summary,
            details={"baskets": baskets},
        )
