import pandas as pd

from src.agents.candidate_basket_agent import CandidateBasketAgent
from src.models.exposure_model import build_exposure_view
from src.models.scoring import AgentResult, FusionResult


def test_candidate_basket_agent_builds_named_baskets() -> None:
    cfg = {
        "baskets": {
            "top_sector": {"source": "sector", "max_names": 2, "weighting": "equal"},
            "watch": {"source": "opportunity", "max_names": 2, "weighting": "score"},
        },
        "controls": {"max_single_weight": 0.7},
    }
    sectors = pd.DataFrame([{"ticker": "XLI", "score": 60.0}, {"ticker": "XLK", "score": 58.0}])
    opp = pd.DataFrame(
        [
            {"ticker": "XLI", "early_opportunity_score": 64.0, "opportunity_label": "early confirmation"},
            {"ticker": "KRE", "early_opportunity_score": 55.0, "opportunity_label": "early build"},
        ]
    )

    result = CandidateBasketAgent(cfg).run(sectors, pd.DataFrame(), opp)

    assert "top_sector" in result.details["baskets"]
    assert not result.details["baskets"]["watch"].empty


def test_exposure_model_returns_label() -> None:
    fusion = FusionResult(62.0, 58.0, 57.0, "neutral", "balanced", {"macro": 62.0}, {"macro": 62.0})
    macro = AgentResult("macro_regime", {"growth_score": 58.0}, "macro")
    liquidity = AgentResult("liquidity", {"liquidity_score": 55.0}, "liq")
    sentiment = AgentResult("sentiment", {"breadth_score": 63.0, "fragility_score": 48.0}, "sent")
    options = AgentResult("options", {"options_structure_score": 52.0}, "opt")
    event = AgentResult("event", {"event_risk_score": 40.0}, "evt")

    result = build_exposure_view(
        {"thresholds": {"offensive": 70, "moderately_offensive": 60, "neutral": 50, "selective_risk": 42}, "modifiers": {"strong_breadth_bonus": 6}},
        fusion,
        macro,
        liquidity,
        sentiment,
        options,
        event,
    )

    assert result.exposure_stance_label in {"offensive", "moderately offensive", "neutral", "selective risk", "defensive", "capital preservation"}
