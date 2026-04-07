import numpy as np
import pandas as pd

from src.agents.sentiment_internals_agent import SentimentInternalsAgent


def test_sentiment_agent_outputs_scores():
    idx = pd.bdate_range("2024-01-01", periods=180)
    rng = np.random.default_rng(2)
    frame = pd.DataFrame(
        {
            "SPY": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx)))),
            "RSP": 95 * np.exp(np.cumsum(rng.normal(0.00045, 0.011, len(idx)))),
            "HYG": 80 * np.exp(np.cumsum(rng.normal(0.0002, 0.006, len(idx)))),
            "VIXY": 30 * np.exp(np.cumsum(rng.normal(-0.0003, 0.02, len(idx)))),
        },
        index=idx,
    )
    result = SentimentInternalsAgent().run(frame)
    assert "breadth_score" in result.scores
    assert "fragility_score" in result.scores
