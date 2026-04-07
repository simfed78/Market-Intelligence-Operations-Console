"""Transparent signal fusion agent."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.scoring import AgentResult, FusionResult
from src.utils.enums import RiskEnvironment


@dataclass
class SignalFusionAgent:
    """Fuse agent outputs into final scores."""

    weights: dict[str, float]

    def run(self, agent_results: dict[str, AgentResult]) -> FusionResult:
        """Combine transparent scores into a final assessment."""
        macro_score = (
            agent_results["macro_regime"].scores.get("growth_score", 50) * 0.4
            + (100 - agent_results["macro_regime"].scores.get("inflation_score", 50)) * 0.2
            + agent_results["macro_regime"].scores.get("policy_score", 50) * 0.4
        )
        liquidity_score = (
            agent_results["liquidity_rates_credit"].scores.get("liquidity_score", 50) * 0.45
            + (100 - agent_results["liquidity_rates_credit"].scores.get("credit_stress_score", 50)) * 0.35
            + agent_results["liquidity_rates_credit"].scores.get("rates_pressure_score", 50) * 0.20
        )
        cross_asset_score = agent_results["cross_asset_leadlag"].scores.get("proxy_stability_score", 50)
        sentiment_score = (
            agent_results["sentiment_internals"].scores.get("breadth_score", 50) * 0.4
            + agent_results["sentiment_internals"].scores.get("sentiment_score", 50) * 0.3
            + (100 - agent_results["sentiment_internals"].scores.get("fragility_score", 50)) * 0.3
        )
        seasonality_score = agent_results["seasonality"].scores.get("seasonality_bias_score", 50)
        technical_score = (
            agent_results["technical_structure"].scores.get("technical_state_score", 50) * 0.6
            + agent_results["technical_structure"].scores.get("trend_quality_score", 50) * 0.4
        )
        sector_score = agent_results["sector_rotation"].scores.get("sector_opportunity_score", 50)
        cyclical_score = agent_results["sector_rotation"].scores.get("cyclical_opportunity_score", 50)

        contributions = {
            "macro": macro_score * self.weights.get("macro", 0.0),
            "liquidity": liquidity_score * self.weights.get("liquidity", 0.0),
            "cross_asset": cross_asset_score * self.weights.get("cross_asset", 0.0),
            "sentiment": sentiment_score * self.weights.get("sentiment", 0.0),
            "seasonality": seasonality_score * self.weights.get("seasonality", 0.0),
            "technical": technical_score * self.weights.get("technical", 0.0),
            "sector": sector_score * self.weights.get("sector", 0.0),
        }
        spx_regime_score = sum(contributions.values())
        sector_opportunity_score = sector_score
        cyclical_opportunity_score = cyclical_score

        risk_environment_flag = RiskEnvironment.NEUTRAL.value
        if spx_regime_score >= 65 and sentiment_score >= 55 and liquidity_score >= 50:
            risk_environment_flag = RiskEnvironment.RISK_ON.value
        elif spx_regime_score < 45 or sentiment_score < 40 or liquidity_score < 40:
            risk_environment_flag = RiskEnvironment.RISK_OFF.value

        biggest = sorted(contributions.items(), key=lambda item: item[1], reverse=True)[:3]
        explanation = (
            f"SPX regime score is {spx_regime_score:.1f}. "
            f"Biggest contributors were {', '.join([f'{name} ({value:.1f})' for name, value in biggest])}. "
            f"Sector opportunity score is {sector_opportunity_score:.1f} and cyclical opportunity score is {cyclical_opportunity_score:.1f}."
        )
        return FusionResult(
            spx_regime_score=float(spx_regime_score),
            sector_opportunity_score=float(sector_opportunity_score),
            cyclical_opportunity_score=float(cyclical_opportunity_score),
            risk_environment_flag=risk_environment_flag,
            explanation=explanation,
            contributions=contributions,
            component_scores={
                "macro": macro_score,
                "liquidity": liquidity_score,
                "cross_asset": cross_asset_score,
                "sentiment": sentiment_score,
                "seasonality": seasonality_score,
                "technical": technical_score,
                "sector": sector_score,
            },
        )
