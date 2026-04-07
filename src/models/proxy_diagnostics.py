"""Proxy diagnostic framework."""

from __future__ import annotations

from dataclasses import asdict

import numpy as np
import pandas as pd

from src.models.change_point import detect_change_points
from src.models.rolling_validation import compute_rolling_validation, stability_score_from_metrics
from src.models.scoring import ValidationResult
from src.models.walk_forward import predictive_usefulness_score, run_walk_forward_validation
from src.utils.helpers import clamp


def bootstrap_correlation(target: pd.Series, proxy: pd.Series, samples: int = 50) -> float:
    """Estimate bootstrap stability of correlation."""
    aligned = pd.concat([target, proxy], axis=1).dropna()
    if aligned.empty:
        return 0.0
    rng = np.random.default_rng(42)
    corrs: list[float] = []
    for _ in range(samples):
        sample_idx = rng.choice(len(aligned), size=len(aligned), replace=True)
        sampled = aligned.iloc[sample_idx]
        corr = sampled.iloc[:, 0].corr(sampled.iloc[:, 1])
        corrs.append(float(corr) if pd.notna(corr) else 0.0)
    return float(np.std(corrs))


def build_regime_masks(
    index: pd.Index,
    macro_result: dict | None = None,
    liquidity_result: dict | None = None,
    volatility_regime: pd.Series | None = None,
    benchmark_returns: pd.Series | None = None,
) -> dict[str, pd.Series]:
    """Create simple regime masks."""
    default_mask = pd.Series(True, index=index)
    macro_growth = (macro_result or {}).get("growth_score", 50)
    liquidity = (liquidity_result or {}).get("liquidity_score", 50)
    masks = {
        "full_sample": default_mask,
        "macro_supportive": pd.Series(macro_growth >= 55, index=index),
        "liquidity_easy": pd.Series(liquidity >= 55, index=index),
        "vol_high": volatility_regime.reindex(index).fillna(False) if volatility_regime is not None else pd.Series(False, index=index),
        "bull_market": (benchmark_returns.reindex(index).rolling(20).mean() > 0).fillna(False) if benchmark_returns is not None else pd.Series(False, index=index),
    }
    return masks


def evaluate_proxy(
    proxy_name: str,
    proxy_series: pd.Series,
    target_series: pd.Series,
    horizon: int,
    regime_masks: dict[str, pd.Series] | None = None,
    rolling_window: int = 60,
    train_window: int = 126,
    test_window: int = 21,
    bootstrap_samples: int = 50,
) -> ValidationResult:
    """Evaluate a proxy against a forward target."""
    target_forward = target_series.pct_change(horizon).shift(-horizon)
    proxy_returns = proxy_series.pct_change().rename(proxy_name)
    aligned = pd.concat([target_forward.rename("target"), proxy_returns], axis=1).dropna()
    if aligned.empty:
        return ValidationResult(
            proxy=proxy_name,
            target=target_series.name or "target",
            horizon=horizon,
            proxy_quality_score=0.0,
            stability_score=0.0,
            predictive_usefulness_score=0.0,
            decay_flag=True,
            full_sample_metrics={},
            regime_specific_metrics={},
            proxy_use_case_summary="No aligned history available.",
            recommended_usage_context="Do not use until history is available.",
            stability_warning="Missing data.",
        )

    rolling = compute_rolling_validation(aligned["target"], aligned[proxy_name], window=min(rolling_window, max(20, len(aligned) // 3)))
    walk = run_walk_forward_validation(aligned["target"], aligned[proxy_name], train_window=min(train_window, max(40, len(aligned) - test_window)), test_window=min(test_window, max(5, len(aligned) // 6)))
    bootstrap_std = bootstrap_correlation(aligned["target"], aligned[proxy_name], samples=bootstrap_samples)
    stability_score = clamp(stability_score_from_metrics(rolling) - bootstrap_std * 50)
    usefulness = predictive_usefulness_score(walk)
    quality = clamp(stability_score * 0.45 + usefulness * 0.45 + max(rolling.lagged_information_coeff, 0.0) * 10)
    decay_flag = bool(rolling.rolling_correlation_mean < 0.05 or walk.mean_directional_accuracy < 0.48 or stability_score < 35)

    cp_result = detect_change_points(aligned[proxy_name].rolling(20).corr(aligned["target"]).dropna())
    regime_specific_metrics = {}
    masks = regime_masks or {"full_sample": pd.Series(True, index=aligned.index)}
    for name, mask in masks.items():
        sample = aligned.loc[mask.reindex(aligned.index).fillna(False)]
        if len(sample) < 20:
            continue
        regime_specific_metrics[name] = {
            "correlation": float(sample["target"].corr(sample[proxy_name])) if pd.notna(sample["target"].corr(sample[proxy_name])) else 0.0,
            "hit_rate": float(((np.sign(sample["target"]) == np.sign(sample[proxy_name])).mean())),
            "observations": int(len(sample)),
        }

    recommended_usage_context = "Use cautiously across all regimes."
    if regime_specific_metrics.get("macro_supportive", {}).get("correlation", 0) > 0.1:
        recommended_usage_context = "Most useful in supportive macro regimes."
    elif regime_specific_metrics.get("vol_high", {}).get("correlation", 0) > 0.1:
        recommended_usage_context = "Most useful during high-volatility risk episodes."

    summary = (
        f"{proxy_name} vs {target_series.name or 'target'} ({horizon}d) scored {quality:.1f} with "
        f"stability {stability_score:.1f} and predictive usefulness {usefulness:.1f}."
    )
    return ValidationResult(
        proxy=proxy_name,
        target=target_series.name or "target",
        horizon=horizon,
        proxy_quality_score=quality,
        stability_score=stability_score,
        predictive_usefulness_score=usefulness,
        decay_flag=decay_flag,
        full_sample_metrics={
            "rolling": asdict(rolling),
            "walk_forward": asdict(walk),
            "bootstrap_corr_std": bootstrap_std,
        },
        regime_specific_metrics=regime_specific_metrics,
        proxy_use_case_summary=summary,
        recommended_usage_context=recommended_usage_context,
        structural_break_flag=cp_result.structural_break_flag,
        recent_break_dates=cp_result.recent_break_dates,
        stability_warning=cp_result.stability_warning,
        proxy_retire_or_reduce_weight=cp_result.proxy_retire_or_reduce_weight,
    )
