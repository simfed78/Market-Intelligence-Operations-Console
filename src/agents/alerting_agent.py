"""Alerting and watchlist agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import AgentResult


@dataclass
class AlertingAgent:
    """Generate alerts and watchlists."""

    config: dict

    def run(
        self,
        validation_table: pd.DataFrame,
        unstable_proxies: pd.DataFrame,
        opportunity_table: pd.DataFrame,
        event_result: AgentResult,
        options_result: AgentResult,
        sector_result: AgentResult,
    ) -> AgentResult:
        """Generate alert center and watchlist tables."""
        alerts: list[dict] = []
        if not validation_table.empty:
            for _, row in validation_table.head(5).iterrows():
                if row["proxy_quality_score"] >= 55:
                    alerts.append({"level": "actionable research", "category": "proxy_improvement", "item": row["proxy"], "message": f"{row['proxy']} proxy quality improved to {row['proxy_quality_score']:.1f}.", "score": row["proxy_quality_score"]})
        if not unstable_proxies.empty:
            for _, row in unstable_proxies.head(5).iterrows():
                alerts.append({"level": "warning", "category": "structural_break", "item": row["proxy"], "message": f"{row['proxy']} shows structural break / decay risk.", "score": row["stability_score"]})
        if event_result.scores.get("event_risk_score", 0) >= self.config.get("thresholds", {}).get("event_risk_high", 65):
            alerts.append({"level": "watch", "category": "event_risk", "item": "macro_week", "message": event_result.summary, "score": event_result.scores.get("event_risk_score", 0)})
        if options_result.scores.get("squeeze_unwind_risk_score", 0) >= self.config.get("thresholds", {}).get("options_structure_unstable", 60):
            alerts.append({"level": "warning", "category": "options_structure", "item": "SPX", "message": options_result.summary, "score": options_result.scores.get("squeeze_unwind_risk_score", 0)})

        alert_df = pd.DataFrame(alerts).sort_values("score", ascending=False) if alerts else pd.DataFrame(columns=["level", "category", "item", "message", "score"])
        watchlist = opportunity_table.head(self.config.get("watchlist", {}).get("max_daily_items", 12)).copy() if not opportunity_table.empty else pd.DataFrame()
        if not watchlist.empty:
            watchlist["watch_reason"] = watchlist["opportunity_label"] + " | score " + watchlist["early_opportunity_score"].round(1).astype(str)
        summary = f"Generated {len(alert_df)} alerts and {len(watchlist)} watchlist items."
        return AgentResult(
            name="alerting",
            scores={"alert_count": float(len(alert_df)), "watchlist_count": float(len(watchlist))},
            summary=summary,
            details={"alerts_table": alert_df, "watchlist_table": watchlist},
        )
