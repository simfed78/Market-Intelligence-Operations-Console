import pandas as pd

from src.agents.macro_regime_agent import MacroRegimeAgent


def test_macro_regime_agent_outputs_scores():
    idx = pd.date_range("2024-01-01", periods=24, freq="ME")
    frame = pd.DataFrame(
        {
            "claims": range(200, 224),
            "unemployment_rate": [3.8 + i * 0.01 for i in range(24)],
            "payrolls": range(100, 124),
            "industrial_production": range(90, 114),
            "retail_sales": range(110, 134),
            "pmi_proxy": range(50, 74),
            "cpi": [280 + i for i in range(24)],
            "ppi": [200 + i * 0.7 for i in range(24)],
            "fed_funds": [5.5 - i * 0.03 for i in range(24)],
            "reserves": [3000 + i * 5 for i in range(24)],
            "fed_balance_sheet": [8000 - i * 10 for i in range(24)],
            "nfci": [0.2 - i * 0.01 for i in range(24)],
        },
        index=idx,
    )
    result = MacroRegimeAgent().run(frame)
    assert "growth_score" in result.scores
    assert result.details["regime_label"]
