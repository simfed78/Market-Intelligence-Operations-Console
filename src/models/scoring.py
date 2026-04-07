"""Shared score models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

@dataclass
class AgentResult:
    """Generic agent output."""

    name: str
    scores: dict[str, float]
    summary: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionResult:
    """Final fused output."""

    spx_regime_score: float
    sector_opportunity_score: float
    cyclical_opportunity_score: float
    risk_environment_flag: str
    explanation: str
    contributions: dict[str, float]
    component_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Proxy validation output."""

    proxy: str
    target: str
    horizon: int
    proxy_quality_score: float
    stability_score: float
    predictive_usefulness_score: float
    decay_flag: bool
    full_sample_metrics: dict[str, Any]
    regime_specific_metrics: dict[str, Any]
    proxy_use_case_summary: str
    recommended_usage_context: str
    structural_break_flag: bool = False
    recent_break_dates: list[str] = field(default_factory=list)
    stability_warning: str = ""
    proxy_retire_or_reduce_weight: str = "keep"


@dataclass
class DataHealthReport:
    """Data quality summary."""

    data_health_report: dict[str, Any]
    stale_series_flags: dict[str, bool]
    fallback_usage_flags: dict[str, bool]
    source_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OpportunityResult:
    """Early opportunity output."""

    spx_tactical_opportunity_score: float
    sector_early_opportunity_score: float
    cyclical_early_opportunity_score: float
    breakout_quality_score: float
    classification: str
    explanation: str


@dataclass
class AlertRecord:
    """Alert output row."""

    level: str
    category: str
    item: str
    message: str
    score: float = 0.0


@dataclass
class RunArtifacts:
    """Collected outputs from a single run."""

    timestamp: str
    agent_results: dict[str, AgentResult]
    fusion: FusionResult
    sector_table: pd.DataFrame
    cyclical_table: pd.DataFrame
    risk_rotation_table: pd.DataFrame
    drivers_table: pd.DataFrame
    seasonality_table: pd.DataFrame
    validation_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    unstable_proxies_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    opportunity_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    watchlist_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    alerts_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    macro_event_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    earnings_watch_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    sector_internals_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    options_context_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    basket_tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    exposure_view: dict[str, Any] = field(default_factory=dict)
    portfolio_summary: dict[str, Any] = field(default_factory=dict)
    transition_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    run_history_table: pd.DataFrame = field(default_factory=pd.DataFrame)
    data_health: DataHealthReport | None = None
    run_type: str = "daily"
    change_log: dict[str, Any] = field(default_factory=dict)
