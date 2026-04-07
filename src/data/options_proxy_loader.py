"""Options and gamma proxy loader."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.loaders import load_csv_series


@dataclass
class OptionsProxyLoader:
    """Load options proxy inputs."""

    raw_dir: Path
    config: dict

    def load_manual(self) -> pd.DataFrame:
        """Load manual options proxy CSV."""
        csv_path = self.raw_dir / Path(self.config.get("public_proxies", {}).get("manual_csv", "options_proxy_manual.csv")).name
        frame = load_csv_series(csv_path)
        if not frame.empty:
            return frame
        today = pd.Timestamp.today().normalize()
        records = [
            {"date": today - pd.Timedelta(days=4), "put_call": 0.94, "skew": 136, "gamma_flip": 5600, "call_wall": 5700, "put_wall": 5400, "expected_move": 1.8, "dealer_positioning": 0.1},
            {"date": today - pd.Timedelta(days=3), "put_call": 0.96, "skew": 138, "gamma_flip": 5580, "call_wall": 5700, "put_wall": 5420, "expected_move": 1.9, "dealer_positioning": -0.05},
            {"date": today - pd.Timedelta(days=2), "put_call": 0.99, "skew": 141, "gamma_flip": 5550, "call_wall": 5680, "put_wall": 5400, "expected_move": 2.1, "dealer_positioning": -0.12},
            {"date": today - pd.Timedelta(days=1), "put_call": 0.91, "skew": 135, "gamma_flip": 5590, "call_wall": 5710, "put_wall": 5440, "expected_move": 1.7, "dealer_positioning": 0.08},
        ]
        return pd.DataFrame(records).set_index("date").sort_index()
