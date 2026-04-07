"""Technical structure agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.technical_features import add_indicator_pack, moving_average_state, realized_volatility
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class TechnicalStructureAgent:
    """Summarize technical structure for benchmark, sectors, and cyclicals."""

    weights: dict[str, float]

    def analyze_universe(self, prices: pd.DataFrame, volumes: pd.DataFrame | None = None) -> pd.DataFrame:
        """Build a technical table for all symbols."""
        rows = []
        volumes = volumes if volumes is not None else pd.DataFrame(index=prices.index, columns=prices.columns)
        for ticker in prices.columns:
            series = prices[ticker].dropna()
            if series.empty:
                continue
            indicators = add_indicator_pack(series)
            ma20 = series.rolling(20).mean().iloc[-1]
            ma50 = series.rolling(50).mean().iloc[-1]
            ma200 = series.rolling(200).mean().iloc[-1] if len(series) >= 200 else series.rolling(min(100, len(series))).mean().iloc[-1]
            current = float(series.iloc[-1])
            dist_20 = ((current / ma20) - 1) * 100 if pd.notna(ma20) and ma20 else 0.0
            dist_50 = ((current / ma50) - 1) * 100 if pd.notna(ma50) and ma50 else 0.0
            trend_state = moving_average_state(series, 20, 50)
            vol = realized_volatility(series, window=20)
            rel_volume = 1.0
            if ticker in volumes.columns and not volumes[ticker].dropna().empty:
                vol_series = volumes[ticker].dropna()
                rel_volume = float(vol_series.iloc[-1] / max(vol_series.tail(20).mean(), 1))

            breakout = dist_20 > 2 and indicators["adx"] > 20 and indicators["macd_hist"] > 0
            pullback = dist_20 < 1 and dist_50 > 0 and indicators["rsi"] > 45
            failed_breakout = dist_20 < -1 and indicators["rsi"] < 45 and indicators["macd_hist"] < 0
            expansion = vol > 0.22 and indicators["adx"] > 22
            label = "consolidation"
            if trend_state and indicators["adx"] >= 20 and dist_50 > 0:
                label = "uptrend"
            elif not trend_state and dist_50 < 0:
                label = "downtrend"
            if failed_breakout:
                label = "failed breakout risk"
            elif expansion:
                label = "expansion condition"

            trend_quality_score = clamp(
                trend_state * 25
                + max(indicators["adx"] - 15, 0) * 1.6
                + max(indicators["macd_hist"], 0) * 50
                + max(min(indicators["rsi"], 70) - 50, 0) * 1.1
                + max(dist_50, -5) * 1.5
            )
            technical_state_score = clamp(
                trend_quality_score * 0.55
                + (15 if breakout else 0)
                + (8 if pullback else 0)
                - (15 if failed_breakout else 0)
                - max(vol - 0.25, 0) * 80
                + min(rel_volume, 2.0) * 5
            )
            rows.append(
                {
                    "ticker": ticker,
                    "technical_state_score": technical_state_score,
                    "trend_quality_score": trend_quality_score,
                    "setup_context_label": label,
                    "rsi": indicators["rsi"],
                    "macd_hist": indicators["macd_hist"],
                    "adx": indicators["adx"],
                    "atr_pct": indicators["atr_pct"],
                    "distance_ma20": dist_20,
                    "distance_ma50": dist_50,
                    "distance_ma200": ((current / ma200) - 1) * 100 if pd.notna(ma200) and ma200 else 0.0,
                    "realized_volatility": vol,
                    "relative_volume": rel_volume,
                    "breakout_flag": breakout,
                    "pullback_flag": pullback,
                    "failed_breakout_flag": failed_breakout,
                    "expansion_flag": expansion,
                }
            )
        return pd.DataFrame(rows).sort_values("technical_state_score", ascending=False).reset_index(drop=True)

    def run(self, prices: pd.DataFrame, volumes: pd.DataFrame | None = None, benchmark: str = "SPY") -> AgentResult:
        """Run technical structure analysis."""
        table = self.analyze_universe(prices, volumes=volumes)
        benchmark_row = table.loc[table["ticker"] == benchmark]
        state_score = float(benchmark_row["technical_state_score"].iloc[0]) if not benchmark_row.empty else 50.0
        trend_score = float(benchmark_row["trend_quality_score"].iloc[0]) if not benchmark_row.empty else 50.0
        label = str(benchmark_row["setup_context_label"].iloc[0]) if not benchmark_row.empty else "consolidation"
        summary = f"Technical structure for {benchmark} is {label} with state score {state_score:.1f} and trend quality {trend_score:.1f}."
        return AgentResult(
            name="technical_structure",
            scores={"technical_state_score": state_score, "trend_quality_score": trend_score},
            summary=summary,
            details={"setup_context_label": label, "technical_table": table},
        )
