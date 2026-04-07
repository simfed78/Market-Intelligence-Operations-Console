import numpy as np
import pandas as pd

from src.agents.seasonality_agent import SeasonalityAgent


def test_seasonality_agent_outputs_context():
    idx = pd.bdate_range("2024-01-01", periods=260)
    series = pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0.0003, 0.01, len(idx)))), index=idx)
    result = SeasonalityAgent().run(series)
    assert "seasonality_bias_score" in result.scores
    assert "calendar_context_tag" in result.details
