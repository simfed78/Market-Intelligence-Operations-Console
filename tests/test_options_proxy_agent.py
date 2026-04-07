import numpy as np
import pandas as pd

from src.agents.options_proxy_agent import OptionsProxyAgent
from src.data.options_proxy_loader import OptionsProxyLoader


def test_options_proxy_loader_and_agent():
    idx = pd.bdate_range("2025-01-01", periods=40)
    prices = pd.DataFrame(
        {
            "SPY": 100 * np.exp(np.cumsum(np.random.default_rng(4).normal(0.0004, 0.01, len(idx)))),
            "^VIX": np.linspace(18, 22, len(idx)),
        },
        index=idx,
    )
    manual = pd.DataFrame({"put_call": [0.95], "skew": [138], "gamma_flip": [5550], "call_wall": [5700], "put_wall": [5400], "expected_move": [1.8], "dealer_positioning": [0.1]}, index=[idx[-1]])
    result = OptionsProxyAgent({"mode": "public_proxy"}).run(prices, manual)
    assert "options_structure_score" in result.scores
