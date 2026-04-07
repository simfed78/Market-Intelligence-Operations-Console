"""Validation helpers."""

from __future__ import annotations

import pandas as pd


def missing_ratio(frame: pd.DataFrame) -> float:
    """Compute missing ratio."""
    if frame.empty:
        return 1.0
    return float(frame.isna().mean().mean())


def relationship_instability(corr_frame: pd.DataFrame) -> float:
    """Proxy for cross-window correlation instability."""
    if corr_frame.empty:
        return 1.0
    if corr_frame.shape[1] < 2:
        return 0.5
    dispersion = corr_frame.std(axis=1).mean()
    return float(dispersion)
