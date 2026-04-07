import numpy as np
import pandas as pd

from src.agents.earnings_revision_agent import EarningsRevisionAgent


def test_earnings_revision_agent_outputs_scores():
    idx = pd.bdate_range("2025-01-01", periods=60)
    rng = np.random.default_rng(2)
    prices = pd.DataFrame(
        {
            "XLK": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx)))),
            "XLF": 80 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, len(idx)))),
        },
        index=idx,
    )
    vols = pd.DataFrame({"XLK": 1_000_000, "XLF": 900_000}, index=idx)
    cal = pd.DataFrame([{"date": idx[-2], "symbol": "AAPL", "sector": "XLK", "importance": "high"}]).set_index("date")
    rev = pd.DataFrame({"XLK": [0.4], "XLF": [0.1]}, index=[idx[-1]])
    result = EarningsRevisionAgent({"sectors": {"XLK": {}, "XLF": {}}}).run(prices, vols, cal, rev)
    assert "earnings_tone_score" in result.scores
