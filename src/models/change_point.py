"""Structural break detection utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    import ruptures as rpt
except Exception:  # pragma: no cover
    rpt = None


@dataclass
class ChangePointResult:
    """Structural break output."""

    structural_break_flag: bool
    recent_break_dates: list[str]
    stability_warning: str
    proxy_retire_or_reduce_weight: str


def detect_change_points(series: pd.Series, min_size: int = 20, jump: int = 5) -> ChangePointResult:
    """Detect change points using ruptures when available and a rolling fallback otherwise."""
    clean = series.dropna()
    if len(clean) < max(40, min_size * 2):
        return ChangePointResult(False, [], "Insufficient history for break detection.", "keep")

    dates: list[str] = []
    if rpt is not None:
        signal = clean.to_numpy().reshape(-1, 1)
        try:
            model = rpt.Binseg(model="l2", min_size=min_size, jump=jump).fit(signal)
            breakpoints = model.predict(n_bkps=2)
            dates = [str(clean.index[idx - 1].date()) for idx in breakpoints[:-1] if 0 < idx <= len(clean)]
        except Exception:
            dates = []

    if not dates:
        short = clean.rolling(20).mean()
        long = clean.rolling(60).mean()
        gap = (short - long).abs()
        threshold = gap.dropna().quantile(0.9) if not gap.dropna().empty else 0.0
        flagged = gap[gap >= threshold].tail(2)
        dates = [str(idx.date()) for idx in flagged.index]

    recent_break_dates = dates[-2:]
    flag = bool(recent_break_dates)
    warning = "Recent structural break detected." if flag else "No major structural break detected."
    recommendation = "reduce_weight" if flag else "keep"
    return ChangePointResult(flag, recent_break_dates, warning, recommendation)
