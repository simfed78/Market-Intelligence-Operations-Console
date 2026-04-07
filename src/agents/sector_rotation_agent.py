"""Sector rotation agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.cross_asset_features import relative_strength
from src.features.technical_features import add_indicator_pack, moving_average_state, multi_horizon_returns, persistence_ratio, rolling_trend_quality
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class SectorRotationAgent:
    """Rank sectors and cyclical ETFs."""

    sector_map: dict[str, dict]
    ranking_weights: dict[str, float]

    def run(
        self,
        market_prices: pd.DataFrame,
        macro_result: AgentResult,
        liquidity_result: AgentResult,
        sentiment_result: AgentResult,
        seasonality_result: AgentResult,
        cross_asset_result: AgentResult,
        technical_result: AgentResult,
        validation_table: pd.DataFrame | None = None,
        benchmark: str = "SPY",
    ) -> AgentResult:
        """Rank sector and cyclical opportunity quality."""
        returns = multi_horizon_returns(market_prices)
        rs = relative_strength(market_prices, benchmark=benchmark)
        technical_table = technical_result.details.get("technical_table", pd.DataFrame())
        validation_table = validation_table if validation_table is not None else pd.DataFrame()

        rows = []
        for ticker in market_prices.columns:
            if ticker == benchmark or ticker.startswith("^"):
                continue
            meta = self.sector_map.get(ticker, {"name": ticker, "style": "other"})
            trend_state = moving_average_state(market_prices[ticker], short=20, long=50)
            indicator_pack = add_indicator_pack(market_prices[ticker])
            rs_20 = float(rs[ticker].pct_change(20).iloc[-1] * 100) if ticker in rs.columns else 0.0
            rs_60 = float(rs[ticker].pct_change(60).iloc[-1] * 100) if ticker in rs.columns else 0.0
            ret20 = float(returns.loc[ticker, "ret_20"] * 100) if ticker in returns.index else 0.0
            ret60 = float(returns.loc[ticker, "ret_60"] * 100) if ticker in returns.index else 0.0
            trend_quality = rolling_trend_quality(market_prices[ticker])
            momentum_persistence = persistence_ratio(market_prices[ticker], lookback=60) * 100
            rs_persistence = float((rs[ticker].pct_change().tail(60) > 0).mean() * 100) if ticker in rs.columns else 50.0
            breadth_proxy = sentiment_result.scores.get("breadth_score", 50.0)
            macro_alignment = macro_result.scores.get("growth_score", 50.0)
            liquidity_alignment = liquidity_result.scores.get("liquidity_score", 50.0)
            sentiment_confirmation = sentiment_result.scores.get("sentiment_score", 50.0)
            seasonality_context = seasonality_result.scores.get("seasonality_bias_score", 50.0)
            proxy_stability = 50.0
            if not validation_table.empty and ticker in validation_table["proxy"].values:
                proxy_stability = float(validation_table.loc[validation_table["proxy"] == ticker, "stability_score"].mean())
            elif not technical_table.empty and ticker in technical_table["ticker"].values:
                proxy_stability = float(technical_table.loc[technical_table["ticker"] == ticker, "trend_quality_score"].iloc[0])

            components = {
                "trend_quality": clamp(trend_quality),
                "momentum_persistence": clamp(momentum_persistence),
                "relative_strength_persistence": clamp((rs_20 * 2) + (rs_60 * 1.2) + rs_persistence * 0.4),
                "internal_breadth": breadth_proxy,
                "macro_alignment": macro_alignment,
                "liquidity_alignment": liquidity_alignment,
                "sentiment_confirmation": sentiment_confirmation,
                "seasonality_context": seasonality_context,
                "proxy_stability": proxy_stability if pd.notna(proxy_stability) else cross_asset_result.scores.get("proxy_stability_score", 50),
            }
            composite = clamp(sum(components[name] * self.ranking_weights.get(name, 0.0) for name in components))

            classification = "weak / avoid"
            if composite >= 80:
                classification = "confirmed_leadership"
            elif composite >= 70:
                classification = "early_leadership"
            elif composite >= 60 and proxy_stability < 45:
                classification = "high beta but unstable"
            elif composite >= 60 and indicator_pack["rsi"] > 70:
                classification = "crowded"

            rows.append(
                {
                    "ticker": ticker,
                    "name": meta.get("name", ticker),
                    "style": meta.get("style", "other"),
                    "score": composite,
                    "relative_strength_20d": rs_20,
                    "return_20d": ret20,
                    "return_60d": ret60,
                    "relative_strength_60d": rs_60,
                    "rsi": indicator_pack["rsi"],
                    "adx": indicator_pack["adx"],
                    "trend_quality": trend_quality,
                    "momentum_persistence": momentum_persistence,
                    "proxy_stability": proxy_stability,
                    "classification": classification,
                }
            )

        ranking = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
        sectors = ranking[ranking["style"] != "cyclical_detail"].reset_index(drop=True)
        cyclical = ranking[ranking["style"].isin({"cyclical", "cyclical_detail"})].reset_index(drop=True)
        risk_rotation = ranking[ranking["ticker"].isin(["XLP", "XLU", "XLV", "XLE", "XLF", "XLK", "IWM", "RSP"])].reset_index(drop=True)
        summary = "Sector ranking unavailable."
        if not ranking.empty:
            leaders = ", ".join(ranking.head(3)["ticker"].tolist())
            summary = f"Sector rotation favors {leaders}. Top cyclical opportunities are {', '.join(cyclical.head(3)['ticker'].tolist())}."
        return AgentResult(
            name="sector_rotation",
            scores={
                "sector_opportunity_score": float(sectors["score"].head(5).mean()) if not sectors.empty else 50.0,
                "cyclical_opportunity_score": float(cyclical["score"].head(5).mean()) if not cyclical.empty else 50.0,
            },
            summary=summary,
            details={"sector_rank_table": sectors, "cyclical_opportunity_table": cyclical, "risk_rotation_table": risk_rotation},
        )
