"""Earnings and revision proxy agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class EarningsRevisionAgent:
    """Approximate sector earnings and revision tone."""

    earnings_map: dict

    def run(self, prices: pd.DataFrame, volumes: pd.DataFrame, earnings_calendar: pd.DataFrame, revision_proxy: pd.DataFrame | None = None) -> AgentResult:
        """Build earnings and reaction quality proxies."""
        rows = []
        revision_proxy = revision_proxy if revision_proxy is not None else pd.DataFrame()
        for sector, meta in self.earnings_map.get("sectors", {}).items():
            if sector not in prices.columns:
                continue
            sector_ret_5 = float(prices[sector].pct_change(5).iloc[-1] * 100)
            sector_ret_20 = float(prices[sector].pct_change(20).iloc[-1] * 100)
            vol_ratio = 1.0
            if sector in volumes.columns and not volumes[sector].dropna().empty:
                vol_ratio = float(volumes[sector].iloc[-1] / max(volumes[sector].tail(20).mean(), 1))
            cluster_count = int((earnings_calendar["sector"] == sector).sum()) if not earnings_calendar.empty and "sector" in earnings_calendar.columns else 0
            manual_revision = float(revision_proxy[sector].iloc[-1]) if not revision_proxy.empty and sector in revision_proxy.columns else 0.0
            tone = clamp(50 + sector_ret_5 * 2 + vol_ratio * 4 + cluster_count * 2)
            revision = clamp(50 + manual_revision * 10 + sector_ret_20 * 1.5)
            reaction_quality = clamp(50 + sector_ret_5 * 2.4 - abs(sector_ret_20 - sector_ret_5) * 0.4)
            dispersion = clamp(50 + abs(sector_ret_20 - sector_ret_5) * 2.2)
            rows.append(
                {
                    "sector": sector,
                    "earnings_tone_score": tone,
                    "revision_proxy_score": revision,
                    "reaction_quality_score": reaction_quality,
                    "earnings_dispersion_score": dispersion,
                    "cluster_count": cluster_count,
                }
            )
        table = pd.DataFrame(rows).sort_values(["earnings_tone_score", "reaction_quality_score"], ascending=False) if rows else pd.DataFrame()
        avg_tone = float(table["earnings_tone_score"].mean()) if not table.empty else 50.0
        avg_revision = float(table["revision_proxy_score"].mean()) if not table.empty else 50.0
        avg_quality = float(table["reaction_quality_score"].mean()) if not table.empty else 50.0
        avg_dispersion = float(table["earnings_dispersion_score"].mean()) if not table.empty else 50.0
        summary = (
            f"Earnings tone score {avg_tone:.1f}, revision proxy score {avg_revision:.1f}, "
            f"reaction quality {avg_quality:.1f}, dispersion {avg_dispersion:.1f}."
        )
        watch = earnings_calendar.reset_index().sort_values("date").head(12) if not earnings_calendar.empty else pd.DataFrame()
        return AgentResult(
            name="earnings_revision",
            scores={
                "earnings_tone_score": avg_tone,
                "revision_proxy_score": avg_revision,
                "reaction_quality_score": avg_quality,
                "earnings_dispersion_score": avg_dispersion,
            },
            summary=summary,
            details={"sector_earnings_table": table, "earnings_calendar_watchlist": watch},
        )
