"""Signal persistence helpers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.storage.run_history import RunHistoryStore


def persist_artifacts(project_root: Path, artifacts, payload_path: str, baskets: dict[str, pd.DataFrame] | None = None, transitions: pd.DataFrame | None = None) -> int:
    """Persist run and signal artifacts."""
    store = RunHistoryStore(project_root)
    run_id = store.runs.insert_run(
        artifacts.timestamp,
        artifacts.run_type,
        artifacts.fusion.risk_environment_flag,
        artifacts.fusion.spx_regime_score,
        artifacts.fusion.sector_opportunity_score,
        artifacts.fusion.cyclical_opportunity_score,
        payload_path,
    )
    store.signals.insert_agent_scores(run_id, artifacts.agent_results)
    store.signals.insert_ranking_table(run_id, "sectors", artifacts.sector_table)
    store.signals.insert_ranking_table(run_id, "cyclicals", artifacts.cyclical_table)
    store.signals.insert_ranking_table(run_id, "opportunity", artifacts.opportunity_table, label_col="opportunity_label", score_col="early_opportunity_score")
    store.signals.insert_alerts(run_id, artifacts.alerts_table)
    store.signals.insert_baskets(run_id, baskets or {})
    store.signals.insert_transitions(run_id, transitions if transitions is not None else pd.DataFrame())
    return run_id
