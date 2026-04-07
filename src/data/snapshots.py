"""Snapshot storage helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class SnapshotStore:
    """Persist point-in-time snapshots locally."""

    snapshot_dir: Path

    def save_frame(self, name: str, frame: pd.DataFrame, stamp: str) -> Path:
        """Save a dated CSV snapshot."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{name}_{stamp.replace(':', '-').replace('+', '_')}.csv"
        frame.to_csv(path)
        return path
