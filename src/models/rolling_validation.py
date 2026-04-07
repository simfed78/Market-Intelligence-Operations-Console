"""Rolling validation utilities."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.utils.helpers import clamp


@dataclass
class RollingValidationMetrics:
    """Rolling validation metrics container."""

    rolling_correlation_mean: float
    rolling_correlation_std: float
    rolling_beta_mean: float
    rolling_beta_std: float
    ols_r2_mean: float
    lagged_information_coeff: float


def _rolling_beta(target: pd.Series, proxy: pd.Series, window: int) -> pd.Series:
    aligned = pd.concat([target, proxy], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    cov = aligned.iloc[:, 0].rolling(window).cov(aligned.iloc[:, 1])
    var = aligned.iloc[:, 1].rolling(window).var()
    return cov / var.replace(0, np.nan)


def _rolling_r2(target: pd.Series, proxy: pd.Series, window: int) -> pd.Series:
    corr = target.rolling(window).corr(proxy)
    return corr.pow(2)


def compute_rolling_validation(
    target: pd.Series,
    proxy: pd.Series,
    window: int = 60,
    lag: int = 1,
) -> RollingValidationMetrics:
    """Compute rolling diagnostics between target and proxy returns."""
    aligned = pd.concat([target, proxy], axis=1).dropna()
    if aligned.empty or len(aligned) < window:
        return RollingValidationMetrics(0.0, 1.0, 0.0, 1.0, 0.0, 0.0)

    target_series = aligned.iloc[:, 0]
    proxy_series = aligned.iloc[:, 1]
    rolling_corr = target_series.rolling(window).corr(proxy_series).dropna()
    rolling_beta = _rolling_beta(target_series, proxy_series, window).dropna()
    rolling_r2 = _rolling_r2(target_series, proxy_series, window).dropna()
    lagged_ic = target_series.corr(proxy_series.shift(lag))

    return RollingValidationMetrics(
        rolling_correlation_mean=float(rolling_corr.mean()) if not rolling_corr.empty else 0.0,
        rolling_correlation_std=float(rolling_corr.std()) if not rolling_corr.empty else 1.0,
        rolling_beta_mean=float(rolling_beta.mean()) if not rolling_beta.empty else 0.0,
        rolling_beta_std=float(rolling_beta.std()) if not rolling_beta.empty else 1.0,
        ols_r2_mean=float(rolling_r2.mean()) if not rolling_r2.empty else 0.0,
        lagged_information_coeff=float(lagged_ic) if pd.notna(lagged_ic) else 0.0,
    )


def stability_score_from_metrics(metrics: RollingValidationMetrics) -> float:
    """Convert metrics to a 0-100 stability score."""
    corr_consistency = max(0.0, 1 - abs(metrics.rolling_correlation_std))
    beta_consistency = max(0.0, 1 - min(abs(metrics.rolling_beta_std), 1.0))
    score = (corr_consistency * 0.5 + beta_consistency * 0.3 + metrics.ols_r2_mean * 0.2) * 100
    return clamp(score)
