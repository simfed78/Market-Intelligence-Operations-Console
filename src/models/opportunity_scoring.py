"""Opportunity scoring helpers."""

from __future__ import annotations

from typing import Iterable

from src.utils.helpers import clamp


def weighted_score(components: dict[str, float], weights: dict[str, float]) -> float:
    """Compute transparent weighted score."""
    return clamp(sum(components.get(name, 0.0) * weights.get(name, 0.0) for name in weights))


def classify_opportunity(score: float, crowding: float, fragility: float, breadth: float) -> str:
    """Map scores into early opportunity buckets."""
    if score >= 75 and crowding < 65 and fragility < 45:
        return "early confirmation"
    if score >= 65 and breadth >= 55 and crowding < 60:
        return "early build"
    if score >= 70 and crowding >= 65:
        return "mature trend"
    if score >= 55 and fragility >= 55:
        return "fragile bounce"
    if crowding >= 75:
        return "crowded / late"
    return "avoid"


def explain_components(label: str, top_components: Iterable[tuple[str, float]]) -> str:
    """Create compact explanation."""
    top = ", ".join(f"{name} {value:.1f}" for name, value in top_components)
    return f"{label} because the strongest supporting components are {top}."
