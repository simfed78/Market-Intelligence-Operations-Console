"""Walk-forward validation helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils.helpers import clamp


@dataclass
class WalkForwardMetrics:
    """Walk-forward summary."""

    mean_directional_accuracy: float
    mean_correlation: float
    mean_spread: float
    test_windows: int


def run_walk_forward_validation(
    target: pd.Series,
    proxy: pd.Series,
    train_window: int = 126,
    test_window: int = 21,
) -> WalkForwardMetrics:
    """Use simple sign and correlation walk-forward validation."""
    aligned = pd.concat([target, proxy], axis=1).dropna()
    if len(aligned) < train_window + test_window:
        return WalkForwardMetrics(0.0, 0.0, 0.0, 0)

    direction_scores: list[float] = []
    correlations: list[float] = []
    spreads: list[float] = []
    for start in range(0, len(aligned) - train_window - test_window + 1, test_window):
        train = aligned.iloc[start : start + train_window]
        test = aligned.iloc[start + train_window : start + train_window + test_window]
        train_corr = train.iloc[:, 0].corr(train.iloc[:, 1])
        if pd.isna(train_corr):
            continue
        predicted_sign = np.sign(train_corr)
        realized_sign = np.sign(test.iloc[:, 0].mean() * test.iloc[:, 1].mean())
        direction_scores.append(float(predicted_sign == realized_sign))
        corr = test.iloc[:, 0].corr(test.iloc[:, 1])
        correlations.append(float(corr) if pd.notna(corr) else 0.0)
        spreads.append(float(abs(train_corr - (corr if pd.notna(corr) else 0.0))))

    if not direction_scores:
        return WalkForwardMetrics(0.0, 0.0, 0.0, 0)
    return WalkForwardMetrics(
        mean_directional_accuracy=float(np.mean(direction_scores)),
        mean_correlation=float(np.mean(correlations)),
        mean_spread=float(np.mean(spreads)),
        test_windows=len(direction_scores),
    )


def predictive_usefulness_score(metrics: WalkForwardMetrics) -> float:
    """Convert walk-forward metrics to a usefulness score."""
    score = metrics.mean_directional_accuracy * 55 + max(metrics.mean_correlation, 0.0) * 30 + max(0.0, 1 - metrics.mean_spread) * 15
    return clamp(score)
