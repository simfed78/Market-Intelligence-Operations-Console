"""Seasonality context agent."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.features.seasonality_features import build_seasonal_return_table, turn_of_month_bias
from src.models.scoring import AgentResult
from src.utils.helpers import clamp


@dataclass
class SeasonalityAgent:
    """Measure seasonal context without using it as a direct trigger."""

    def run(self, benchmark_series: pd.Series, calendar_frame: pd.DataFrame | None = None) -> AgentResult:
        """Generate seasonality context."""
        tables = build_seasonal_return_table(benchmark_series)
        today = benchmark_series.dropna().index[-1] if not benchmark_series.dropna().empty else pd.Timestamp.today()

        month_bias = float(tables["month"].get(today.month, 0.0) * 100) if not tables["month"].empty else 0.0
        wom = ((today.day - 1) // 7) + 1
        wom_bias = float(tables["week_of_month"].get(wom, 0.0) * 100) if not tables["week_of_month"].empty else 0.0
        dom_bias = float(tables["day_of_month"].get(today.day, 0.0) * 100) if not tables["day_of_month"].empty else 0.0
        dow_bias = float(tables["day_of_week"].get(today.dayofweek, 0.0) * 100) if not tables["day_of_week"].empty else 0.0
        tom_bias = turn_of_month_bias(benchmark_series)

        composite = month_bias * 0.35 + wom_bias * 0.2 + dom_bias * 0.15 + dow_bias * 0.1 + tom_bias * 0.2
        confidence = clamp(abs(month_bias) * 30 + abs(tom_bias) * 20 + 40, 0, 100)
        tag = "neutral_calendar"
        if calendar_frame is not None and not calendar_frame.empty:
            upcoming = calendar_frame.loc[calendar_frame.index >= today].head(3)
            if not upcoming.empty:
                event_names = ", ".join(upcoming["event"].astype(str).tolist())
                tag = f"event_window:{event_names}"

        summary = (
            f"Seasonality bias score {clamp(50 + composite * 10):.1f} with confidence {confidence:.1f}. "
            f"Calendar context is {tag}."
        )
        seasonality_table = pd.DataFrame(
            {
                "component": ["month", "week_of_month", "day_of_month", "day_of_week", "turn_of_month"],
                "bias_pct": [month_bias, wom_bias, dom_bias, dow_bias, tom_bias],
            }
        )
        return AgentResult(
            name="seasonality",
            scores={
                "seasonality_bias_score": clamp(50 + composite * 10),
                "seasonality_confidence": confidence,
            },
            summary=summary,
            details={"calendar_context_tag": tag, "seasonality_table": seasonality_table},
        )
