"""Regime-based exposure view."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.scoring import AgentResult


@dataclass
class ExposureView:
    """Exposure output."""

    exposure_stance_label: str
    exposure_summary: str
    supporting_components: dict[str, float]
    confidence_tag: str


def build_exposure_view(config: dict, fusion_result, macro_result: AgentResult, liquidity_result: AgentResult, sentiment_result: AgentResult, options_result: AgentResult, event_result: AgentResult):
    """Translate signals into a discretionary exposure stance."""
    base = fusion_result.spx_regime_score
    modifiers = config.get("modifiers", {})
    adjusted = base
    if event_result.scores.get("event_risk_score", 0) >= 65:
        adjusted -= modifiers.get("high_event_risk_penalty", 10)
    if options_result.scores.get("options_structure_score", 50) < 40:
        adjusted -= modifiers.get("unstable_options_penalty", 12)
    if sentiment_result.scores.get("breadth_score", 50) > 60:
        adjusted += modifiers.get("strong_breadth_bonus", 6)
    if sentiment_result.scores.get("fragility_score", 50) > 55:
        adjusted -= modifiers.get("fragile_market_penalty", 8)

    thresholds = config.get("thresholds", {})
    if adjusted >= thresholds.get("offensive", 70):
        label = "offensive"
    elif adjusted >= thresholds.get("moderately_offensive", 60):
        label = "moderately offensive"
    elif adjusted >= thresholds.get("neutral", 50):
        label = "neutral"
    elif adjusted >= thresholds.get("selective_risk", 42):
        label = "selective risk"
    elif adjusted >= 35:
        label = "defensive"
    else:
        label = "capital preservation"
    confidence_tag = "high" if abs(adjusted - 50) >= 15 else "medium"
    components = {
        "fusion": fusion_result.spx_regime_score,
        "macro": macro_result.scores.get("growth_score", 50),
        "liquidity": liquidity_result.scores.get("liquidity_score", 50),
        "breadth": sentiment_result.scores.get("breadth_score", 50),
        "options": options_result.scores.get("options_structure_score", 50),
        "event_risk_inverse": 100 - event_result.scores.get("event_risk_score", 50),
    }
    summary = f"Exposure stance is {label} with {confidence_tag} confidence."
    return ExposureView(label, summary, components, confidence_tag)
