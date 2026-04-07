"""Data quality diagnostics."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.models.scoring import DataHealthReport


@dataclass
class DataQualityChecker:
    """Evaluate quality of input data frames."""

    stale_days_threshold: int = 10

    def evaluate(self, frames: dict[str, pd.DataFrame], fallback_usage_flags: dict[str, bool] | None = None) -> DataHealthReport:
        """Build a data health report across frames."""
        report = {}
        stale_flags = {}
        source_metadata = {}
        today = pd.Timestamp.today().normalize()
        for name, frame in frames.items():
            missing_ratio = float(frame.isna().mean().mean()) if not frame.empty else 1.0
            last_ts = frame.index.max() if not frame.empty else pd.NaT
            stale_days = int((today - pd.Timestamp(last_ts).normalize()).days) if pd.notna(last_ts) else 10_000
            report[name] = {
                "rows": int(len(frame)),
                "columns": int(frame.shape[1]) if not frame.empty else 0,
                "missing_ratio": missing_ratio,
                "last_update": str(last_ts) if pd.notna(last_ts) else None,
                "stale_days": stale_days,
            }
            stale_flags[name] = stale_days > self.stale_days_threshold
            source_metadata[name] = {"status": "stale" if stale_flags[name] else "ok"}
        return DataHealthReport(
            data_health_report=report,
            stale_series_flags=stale_flags,
            fallback_usage_flags=fallback_usage_flags or {},
            source_metadata=source_metadata,
        )
