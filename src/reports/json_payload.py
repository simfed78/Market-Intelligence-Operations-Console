"""JSON payload builder."""

from __future__ import annotations

from src.models.scoring import RunArtifacts
from src.utils.helpers import serialize_payload


def build_json_payload(artifacts: RunArtifacts) -> dict:
    """Create a JSON-serializable payload."""
    return serialize_payload(
        {
            "timestamp": artifacts.timestamp,
            "scores": {
                "spx_regime_score": artifacts.fusion.spx_regime_score,
                "sector_opportunity_score": artifacts.fusion.sector_opportunity_score,
                "cyclical_opportunity_score": artifacts.fusion.cyclical_opportunity_score,
            },
            "risk_environment_flag": artifacts.fusion.risk_environment_flag,
            "explanation": artifacts.fusion.explanation,
            "component_scores": artifacts.fusion.component_scores,
            "agent_results": artifacts.agent_results,
            "top_ranked_sectors": artifacts.sector_table.head(10),
            "top_ranked_cyclicals": artifacts.cyclical_table.head(10),
            "risk_rotation_table": artifacts.risk_rotation_table.head(10),
            "validation_table": artifacts.validation_table.head(20),
            "unstable_proxies_table": artifacts.unstable_proxies_table.head(20),
            "opportunity_table": artifacts.opportunity_table.head(20),
            "watchlist_table": artifacts.watchlist_table.head(20),
            "alerts_table": artifacts.alerts_table.head(20),
            "macro_event_table": artifacts.macro_event_table.head(20),
            "earnings_watch_table": artifacts.earnings_watch_table.head(20),
            "sector_internals_table": artifacts.sector_internals_table.head(20),
            "options_context_table": artifacts.options_context_table.head(20),
            "basket_tables": {name: table.head(20) for name, table in artifacts.basket_tables.items()},
            "exposure_view": artifacts.exposure_view,
            "portfolio_summary": artifacts.portfolio_summary,
            "transition_table": artifacts.transition_table.head(50),
            "run_history_table": artifacts.run_history_table.head(50),
            "change_log": artifacts.change_log,
            "data_health": artifacts.data_health,
        }
    )
