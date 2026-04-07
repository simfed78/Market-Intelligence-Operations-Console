"""Macro event context agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.macro_event_calendar import tag_event_window
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class MacroEventAgent:
    """Summarize upcoming macro event context."""

    config: dict

    def run(self, event_calendar: pd.DataFrame, prices: pd.DataFrame, benchmark: str = "SPY") -> AgentResult:
        """Generate event context and conditional stats."""
        today = prices.index.max() if not prices.empty else pd.Timestamp.today().normalize()
        upcoming = event_calendar.loc[event_calendar.index >= today].head(8) if not event_calendar.empty else pd.DataFrame()
        windows_cfg = self.config.get("windows", {})
        tags = []
        category_counts: dict[str, int] = {}
        risk_score = 20.0
        for idx, row in upcoming.iterrows():
            tag = tag_event_window(pd.Timestamp(idx), pd.Timestamp(today), windows_cfg.get("pre_event_days", 2), windows_cfg.get("post_event_days", [1, 3, 5]))
            tags.append(f"{row.get('event', 'event')}:{tag}")
            category = row.get("category", "other")
            category_counts[category] = category_counts.get(category, 0) + 1
            risk_score += 15 if row.get("importance", "medium") == "high" else 8

        event_context_label = "balanced_event_week"
        if category_counts:
            top_category = max(category_counts, key=category_counts.get)
            mapping = {
                "inflation": "inflation-heavy week",
                "growth": "growth-heavy week",
                "central_bank": "Fed-sensitive window",
                "labor": "labor-heavy week",
            }
            event_context_label = mapping.get(top_category, f"{top_category}-heavy week")

        event_window_tag = ", ".join(tags[:4]) if tags else "no_major_event_window"
        conditional = self._conditional_stats(event_calendar, prices, benchmark=benchmark)
        summary = f"Event context is {event_context_label}. Event risk score {clamp(risk_score):.1f}. Window tag: {event_window_tag}."
        return AgentResult(
            name="macro_event",
            scores={"event_risk_score": clamp(risk_score)},
            summary=summary,
            details={
                "event_context_label": event_context_label,
                "event_window_tag": event_window_tag,
                "event_conditional_stats_table": conditional,
                "upcoming_events": upcoming.reset_index(),
            },
        )

    def _conditional_stats(self, event_calendar: pd.DataFrame, prices: pd.DataFrame, benchmark: str) -> pd.DataFrame:
        """Compute simple event-conditioned return table."""
        if event_calendar.empty or prices.empty or benchmark not in prices.columns:
            return pd.DataFrame()
        returns = prices.pct_change()
        rows = []
        for event_name, group in event_calendar.groupby("event"):
            event_dates = [dt for dt in group.index if dt in returns.index]
            if not event_dates:
                continue
            sample = returns.loc[event_dates, [col for col in [benchmark, "XLF", "XLK", "XLI", "XLE"] if col in returns.columns]]
            row = {"event": event_name, "count": len(sample)}
            for col in sample.columns:
                row[f"{col}_0d_mean"] = float(sample[col].mean() * 100)
            rows.append(row)
        return pd.DataFrame(rows)
