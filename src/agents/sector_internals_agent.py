"""Sector internals agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class SectorInternalsAgent:
    """Measure sector internal breadth and concentration."""

    config: dict

    def run(self, prices: pd.DataFrame, sector_prices: pd.DataFrame) -> AgentResult:
        """Compute sector internals in ETF or constituent mode."""
        rows = []
        sector_constituents = self.config.get("sector_constituents", {})
        for sector, members in sector_constituents.items():
            available = [ticker for ticker in members if ticker in prices.columns]
            mode = "constituent" if available else "etf_proxy"
            base_frame = prices[available] if available else sector_prices[[sector]] if sector in sector_prices.columns else pd.DataFrame()
            if base_frame.empty:
                continue
            latest = base_frame.iloc[-1]
            ma20 = base_frame.rolling(20).mean().iloc[-1]
            ma50 = base_frame.rolling(50).mean().iloc[-1]
            ma200 = base_frame.rolling(200).mean().iloc[-1] if len(base_frame) >= 200 else base_frame.rolling(min(100, len(base_frame))).mean().iloc[-1]
            pct_above_20 = float((latest > ma20).mean() * 100)
            pct_above_50 = float((latest > ma50).mean() * 100)
            pct_above_200 = float((latest > ma200).mean() * 100)
            rets20 = base_frame.pct_change(20).iloc[-1].dropna()
            participation = clamp((pct_above_20 * 0.3 + pct_above_50 * 0.4 + pct_above_200 * 0.3))
            concentration = clamp(50 + (100 if len(rets20) == 1 else abs(rets20.max() - rets20.mean()) * 150))
            dispersion = clamp(50 + (rets20.std() * 200 if len(rets20) > 1 else 20))
            new_highs = float((latest >= base_frame.rolling(60).max().iloc[-1]).mean() * 100)
            new_lows = float((latest <= base_frame.rolling(60).min().iloc[-1]).mean() * 100)
            breadth_score = clamp(participation * 0.6 + new_highs * 0.4 - new_lows * 0.2)
            rows.append(
                {
                    "sector": sector,
                    "mode": mode,
                    "sector_internal_breadth_score": breadth_score,
                    "concentration_risk_score": concentration,
                    "internal_dispersion_score": dispersion,
                    "participation_score": participation,
                    "pct_above_20dma": pct_above_20,
                    "pct_above_50dma": pct_above_50,
                    "pct_above_200dma": pct_above_200,
                }
            )
        table = pd.DataFrame(rows).sort_values("sector_internal_breadth_score", ascending=False) if rows else pd.DataFrame()
        summary = "Sector internals unavailable."
        if not table.empty:
            top = table.iloc[0]
            summary = (
                f"Sector internals favor {top['sector']} with breadth {top['sector_internal_breadth_score']:.1f}; "
                f"concentration risk averages {table['concentration_risk_score'].mean():.1f}."
            )
        return AgentResult(
            name="sector_internals",
            scores={
                "sector_internal_breadth_score": float(table["sector_internal_breadth_score"].mean()) if not table.empty else 50.0,
                "concentration_risk_score": float(table["concentration_risk_score"].mean()) if not table.empty else 50.0,
                "internal_dispersion_score": float(table["internal_dispersion_score"].mean()) if not table.empty else 50.0,
                "participation_score": float(table["participation_score"].mean()) if not table.empty else 50.0,
            },
            summary=summary,
            details={"sector_internals_table": table},
        )
