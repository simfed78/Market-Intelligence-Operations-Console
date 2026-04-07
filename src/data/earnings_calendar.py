"""Earnings calendar and proxy loaders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.loaders import load_csv_series


@dataclass
class EarningsCalendarLoader:
    """Load earnings calendar and revision proxy inputs."""

    raw_dir: Path
    config: dict

    def load_calendar(self) -> pd.DataFrame:
        """Load earnings calendar."""
        csv_path = self.raw_dir / Path(self.config.get("manual_calendar_csv", "earnings_calendar.csv")).name
        frame = load_csv_series(csv_path)
        if not frame.empty:
            return frame
        today = pd.Timestamp.today().normalize()
        records = [
            {"date": today + pd.Timedelta(days=2), "symbol": "AAPL", "sector": "XLK", "importance": "high"},
            {"date": today + pd.Timedelta(days=2), "symbol": "MSFT", "sector": "XLK", "importance": "high"},
            {"date": today + pd.Timedelta(days=4), "symbol": "JPM", "sector": "XLF", "importance": "high"},
            {"date": today + pd.Timedelta(days=5), "symbol": "XOM", "sector": "XLE", "importance": "medium"},
        ]
        return pd.DataFrame(records).set_index("date").sort_index()

    def load_revision_proxy(self) -> pd.DataFrame:
        """Load manual revision proxy file when available."""
        csv_path = self.raw_dir / Path(self.config.get("manual_revision_csv", "earnings_revision_proxy.csv")).name
        return load_csv_series(csv_path)
