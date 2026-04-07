"""Transparent regime classification rules."""

from __future__ import annotations


def classify_macro_regime(growth_score: float, inflation_score: float, policy_score: float) -> str:
    """Classify the macro regime using transparent thresholds."""
    if growth_score >= 60 and inflation_score <= 60 and policy_score >= 50:
        return "goldilocks_expansion"
    if growth_score >= 55 and inflation_score > 60:
        return "reflation_overheat"
    if growth_score < 45 and policy_score < 45:
        return "tightening_slowdown"
    if growth_score < 40 and inflation_score < 50:
        return "disinflationary_slowdown"
    return "mixed_transition"
