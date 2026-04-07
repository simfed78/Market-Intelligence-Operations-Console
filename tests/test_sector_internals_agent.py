import numpy as np
import pandas as pd

from src.agents.sector_internals_agent import SectorInternalsAgent


def test_sector_internals_agent_outputs_table():
    idx = pd.bdate_range("2025-01-01", periods=220)
    rng = np.random.default_rng(3)
    prices = pd.DataFrame(
        {
            "XLK": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx)))),
            "AAPL": 120 * np.exp(np.cumsum(rng.normal(0.0005, 0.012, len(idx)))),
            "MSFT": 115 * np.exp(np.cumsum(rng.normal(0.00045, 0.011, len(idx)))),
        },
        index=idx,
    )
    result = SectorInternalsAgent({"sector_constituents": {"XLK": ["AAPL", "MSFT"]}}).run(prices, prices[["XLK"]])
    assert "sector_internal_breadth_score" in result.scores
    assert not result.details["sector_internals_table"].empty
