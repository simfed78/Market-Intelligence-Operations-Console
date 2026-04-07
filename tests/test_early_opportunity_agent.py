import pandas as pd

from src.agents.early_opportunity_agent import EarlyOpportunityAgent
from src.models.scoring import AgentResult


def test_early_opportunity_agent_outputs_rankings():
    sector_table = pd.DataFrame([{"ticker": "XLK", "relative_strength_20d": 5, "relative_strength_60d": 7, "trend_quality": 65, "rsi": 58}])
    cyclical_table = pd.DataFrame([{"ticker": "XLI", "relative_strength_20d": 3, "relative_strength_60d": 5, "trend_quality": 60, "rsi": 55}])
    technical = AgentResult("technical_structure", {"technical_state_score": 60, "trend_quality_score": 58}, "ok", {})
    internals = AgentResult("sector_internals", {"participation_score": 62}, "ok", {"sector_internals_table": pd.DataFrame([{"sector": "XLK", "sector_internal_breadth_score": 64, "participation_score": 62}])})
    macro = AgentResult("macro_regime", {"growth_score": 55}, "ok", {})
    liquidity = AgentResult("liquidity", {"liquidity_score": 57}, "ok", {})
    event = AgentResult("macro_event", {"event_risk_score": 35}, "ok", {})
    options = AgentResult("options_proxy", {"options_structure_score": 60}, "ok", {})
    earnings = AgentResult("earnings_revision", {"earnings_tone_score": 58}, "ok", {"sector_earnings_table": pd.DataFrame([{"sector": "XLK", "earnings_tone_score": 58}])})
    sentiment = AgentResult("sentiment", {"breadth_score": 60, "fragility_score": 40, "squeeze_risk_score": 42}, "ok", {})
    validation = pd.DataFrame([{"proxy": "XLK", "proxy_quality_score": 61}])
    result = EarlyOpportunityAgent({"spx": {}, "sector": {"relative_strength_improvement": 0.5, "internal_breadth": 0.5}, "cyclical": {"relative_strength_improvement": 0.5, "internal_breadth": 0.5}}).run(
        sector_table, cyclical_table, technical, internals, macro, liquidity, event, options, earnings, sentiment, validation
    )
    assert "spx_tactical_opportunity_score" in result.scores
    assert not result.details["sector_opportunity_table"].empty
