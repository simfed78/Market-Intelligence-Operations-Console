import numpy as np
import pandas as pd

from src.models.proxy_diagnostics import evaluate_proxy


def test_evaluate_proxy_returns_scores():
    idx = pd.bdate_range("2024-01-01", periods=260)
    rng = np.random.default_rng(7)
    proxy = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, len(idx)))), index=idx, name="HYG")
    target = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.00025, 0.009, len(idx)))), index=idx, name="SPY")
    result = evaluate_proxy("HYG", proxy, target, horizon=5)
    assert 0 <= result.proxy_quality_score <= 100
    assert isinstance(result.recommended_usage_context, str)
