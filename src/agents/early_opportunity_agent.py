"""Early opportunity detection agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.opportunity_scoring import classify_opportunity, explain_components, weighted_score
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class EarlyOpportunityAgent:
    """Detect early opportunities across SPX, sectors, and cyclicals."""

    weights: dict

    def run(
        self,
        sector_table: pd.DataFrame,
        cyclical_table: pd.DataFrame,
        technical_result: AgentResult,
        sector_internals_result: AgentResult,
        macro_result: AgentResult,
        liquidity_result: AgentResult,
        event_result: AgentResult,
        options_result: AgentResult,
        earnings_result: AgentResult,
        sentiment_result: AgentResult,
        validation_table: pd.DataFrame,
    ) -> AgentResult:
        """Build early opportunity scores and ranking tables."""
        spx_components = {
            "technical_improvement": technical_result.scores.get("technical_state_score", 50),
            "breadth_improvement": sentiment_result.scores.get("breadth_score", 50),
            "macro_alignment": macro_result.scores.get("growth_score", 50),
            "liquidity_alignment": liquidity_result.scores.get("liquidity_score", 50),
            "proxy_confirmation": float(validation_table["proxy_quality_score"].head(5).mean()) if not validation_table.empty else 50.0,
            "event_context": 100 - event_result.scores.get("event_risk_score", 50),
            "options_context": options_result.scores.get("options_structure_score", 50),
            "anti_crowding": 100 - sentiment_result.scores.get("fragility_score", 50),
        }
        spx_score = weighted_score(spx_components, self.weights.get("spx", {}))
        breakout_quality = clamp(technical_result.scores.get("trend_quality_score", 50) * 0.5 + sector_internals_result.scores.get("participation_score", 50) * 0.5)
        spx_label = classify_opportunity(spx_score, sentiment_result.scores.get("squeeze_risk_score", 50), sentiment_result.scores.get("fragility_score", 50), sentiment_result.scores.get("breadth_score", 50))

        earnings_table = earnings_result.details.get("sector_earnings_table", pd.DataFrame())
        internals_table = sector_internals_result.details.get("sector_internals_table", pd.DataFrame())
        opp_sector = self._rank_table(sector_table, internals_table, earnings_table, macro_result, event_result, options_result, validation_table, self.weights.get("sector", {}))
        opp_cyclical = self._rank_table(cyclical_table, internals_table, earnings_table, liquidity_result, event_result, options_result, validation_table, self.weights.get("cyclical", {}), join_key="ticker")
        sector_score = float(opp_sector["early_opportunity_score"].head(5).mean()) if not opp_sector.empty else 50.0
        cyclical_score = float(opp_cyclical["early_opportunity_score"].head(5).mean()) if not opp_cyclical.empty else 50.0
        top_components = sorted(spx_components.items(), key=lambda item: item[1], reverse=True)[:3]
        explanation = explain_components(spx_label, top_components)
        return AgentResult(
            name="early_opportunity",
            scores={
                "spx_tactical_opportunity_score": spx_score,
                "sector_early_opportunity_score": sector_score,
                "cyclical_early_opportunity_score": cyclical_score,
                "breakout_quality_score": breakout_quality,
            },
            summary=f"SPX tactical opportunity score {spx_score:.1f}, breakout quality {breakout_quality:.1f}, classification {spx_label}.",
            details={
                "classification": spx_label,
                "explanation": explanation,
                "sector_opportunity_table": opp_sector,
                "cyclical_opportunity_table": opp_cyclical,
            },
        )

    def _rank_table(
        self,
        ranking: pd.DataFrame,
        internals_table: pd.DataFrame,
        earnings_table: pd.DataFrame,
        alignment_result: AgentResult,
        event_result: AgentResult,
        options_result: AgentResult,
        validation_table: pd.DataFrame,
        weights: dict[str, float],
        join_key: str = "ticker",
    ) -> pd.DataFrame:
        if ranking.empty:
            return pd.DataFrame()
        table = ranking.copy()
        if not internals_table.empty:
            table = table.merge(internals_table, how="left", left_on="ticker", right_on="sector")
        if not earnings_table.empty:
            table = table.merge(earnings_table, how="left", left_on="ticker", right_on="sector", suffixes=("", "_earn"))
        quality = validation_table.groupby("proxy")["proxy_quality_score"].mean().to_dict() if not validation_table.empty else {}
        event_context = 100 - event_result.scores.get("event_risk_score", 50)
        options_context = options_result.scores.get("options_structure_score", 50)
        alignment = list(alignment_result.scores.values())[0] if alignment_result.scores else 50.0
        table["relative_strength_improvement"] = clamp_series(table.get("relative_strength_20d", pd.Series(0, index=table.index)) * 2 + table.get("relative_strength_60d", pd.Series(0, index=table.index)) * 1.2 + 50)
        table["internal_breadth"] = table.get("sector_internal_breadth_score", pd.Series(50, index=table.index)).fillna(50)
        table["technical_state"] = table.get("trend_quality", pd.Series(50, index=table.index)).fillna(50)
        table["earnings_tone"] = table.get("earnings_tone_score", pd.Series(50, index=table.index)).fillna(50)
        table["macro_alignment"] = alignment
        table["liquidity_alignment"] = alignment
        table["options_context"] = options_context
        table["event_context"] = event_context
        table["proxy_confirmation"] = table["ticker"].map(lambda x: quality.get(x, 50.0))
        table["anti_crowding"] = 100 - table.get("rsi", pd.Series(50, index=table.index)).fillna(50)
        table["early_opportunity_score"] = table.apply(
            lambda row: weighted_score({name: float(row.get(name, 50.0)) for name in weights}, weights),
            axis=1,
        )
        table["opportunity_label"] = table.apply(
            lambda row: classify_opportunity(
                float(row["early_opportunity_score"]),
                100 - float(row.get("anti_crowding", 50.0)),
                100 - float(row.get("internal_breadth", 50.0)),
                float(row.get("internal_breadth", 50.0)),
            ),
            axis=1,
        )
        return table.sort_values("early_opportunity_score", ascending=False).reset_index(drop=True)


def clamp_series(series: pd.Series) -> pd.Series:
    """Clamp a pandas series to 0-100."""
    return series.fillna(50).clip(lower=0, upper=100)
