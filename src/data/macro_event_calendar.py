"""Macro event calendar loaders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.loaders import load_csv_series


@dataclass
class MacroEventCalendarLoader:
    """Load a macro event calendar from CSV or config defaults."""

    raw_dir: Path
    config: dict

    def load(self) -> pd.DataFrame:
        """Load macro event calendar."""
        csv_path = self.raw_dir / Path(self.config.get("manual_calendar_csv", "macro_events.csv")).name
        frame = load_csv_series(csv_path)
        if not frame.empty:
            return frame
        today = pd.Timestamp.today().normalize()
        records = [
            {"date": today + pd.Timedelta(days=1), "event": "CPI", "category": "inflation", "importance": "high"},
            {"date": today + pd.Timedelta(days=3), "event": "Jobless Claims", "category": "labor", "importance": "medium"},
            {"date": today + pd.Timedelta(days=4), "event": "Retail Sales", "category": "growth", "importance": "medium"},
            {"date": today + pd.Timedelta(days=8), "event": "FOMC", "category": "central_bank", "importance": "high"},
        ]
        return pd.DataFrame(records).set_index("date").sort_index()


def tag_event_window(event_date: pd.Timestamp, current_date: pd.Timestamp, pre_event_days: int = 2, post_event_days: list[int] | None = None) -> str:
    """Tag relative position to an event."""
    post_event_days = post_event_days or [1, 3, 5]
    delta = (current_date.normalize() - event_date.normalize()).days
    if delta < 0 and abs(delta) <= pre_event_days:
        return "pre_event"
    if delta == 0:
        return "event_day"
    if delta in post_event_days:
        return f"post_event_{delta}d"
    return "outside_window"
