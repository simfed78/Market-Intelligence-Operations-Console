import pandas as pd

from src.agents.alerting_agent import AlertingAgent
from src.models.scoring import AgentResult


def test_alerting_agent_generates_alerts():
    validation = pd.DataFrame([{"proxy": "QQQ", "proxy_quality_score": 60, "stability_score": 70, "decay_flag": False, "structural_break_flag": False}])
    unstable = pd.DataFrame([{"proxy": "HYG", "stability_score": 35}])
    opp = pd.DataFrame([{"ticker": "XLI", "early_opportunity_score": 68, "opportunity_label": "early build"}])
    event = AgentResult("macro_event", {"event_risk_score": 70}, "event risk", {})
    options = AgentResult("options_proxy", {"squeeze_unwind_risk_score": 65}, "options risk", {})
    sector = AgentResult("sector_rotation", {}, "sector", {})
    result = AlertingAgent({"thresholds": {"event_risk_high": 65, "options_structure_unstable": 60}, "watchlist": {"max_daily_items": 5}}).run(validation, unstable, opp, event, options, sector)
    assert result.scores["alert_count"] >= 1
