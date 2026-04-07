"""Simple local cache utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


@dataclass
class CacheManager:
    """Manage CSV-based cache files."""

    cache_dir: Path
    ttl_hours: int = 12

    def get_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.csv"

    def is_fresh(self, key: str) -> bool:
        path = self.get_path(key)
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        return datetime.now() - modified < timedelta(hours=self.ttl_hours)

    def read(self, key: str) -> pd.DataFrame | None:
        path = self.get_path(key)
        if not path.exists():
            return None
        return pd.read_csv(path, index_col=0, parse_dates=True)

    def write(self, key: str, frame: pd.DataFrame) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        frame.to_csv(self.get_path(key))
