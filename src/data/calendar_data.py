"""Event calendar loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.loaders import load_csv_series


@dataclass
class CalendarDataLoader:
    """Load a simple event calendar."""

    raw_dir: Path

    def load(self, path: str | Path | None = None) -> pd.DataFrame:
        """Load event calendar data."""
        candidate = Path(path) if path else self.raw_dir / "event_calendar.csv"
        frame = load_csv_series(candidate)
        if frame.empty:
            return self._default_calendar()
        return frame

    def _default_calendar(self) -> pd.DataFrame:
        today = pd.Timestamp.today().normalize()
        records = [
            {"date": today + pd.Timedelta(days=2), "event": "CPI", "importance": "high"},
            {"date": today + pd.Timedelta(days=9), "event": "FOMC", "importance": "high"},
            {"date": today + pd.Timedelta(days=16), "event": "OPEX", "importance": "medium"},
        ]
        return pd.DataFrame(records).set_index("date")
