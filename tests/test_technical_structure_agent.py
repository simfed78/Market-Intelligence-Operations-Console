import numpy as np
import pandas as pd

from src.agents.technical_structure_agent import TechnicalStructureAgent


def test_technical_structure_agent_outputs_table():
    idx = pd.bdate_range("2024-01-01", periods=220)
    rng = np.random.default_rng(5)
    prices = pd.DataFrame(
        {
            "SPY": 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, len(idx)))),
            "XLF": 80 * np.exp(np.cumsum(rng.normal(0.0003, 0.011, len(idx)))),
        },
        index=idx,
    )
    result = TechnicalStructureAgent(weights={}).run(prices)
    assert "technical_state_score" in result.scores
    assert not result.details["technical_table"].empty
