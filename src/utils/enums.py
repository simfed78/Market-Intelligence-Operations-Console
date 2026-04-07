"""Shared enums."""

from __future__ import annotations

from enum import Enum


class RiskEnvironment(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"


class RelationshipStability(str, Enum):
    STABLE = "stable"
    WATCH = "watch"
    UNSTABLE = "unstable"
