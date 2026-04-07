from pathlib import Path

import pandas as pd

from src.models.scoring import AgentResult, DataHealthReport, FusionResult, RunArtifacts
from src.storage.db import get_db_path, init_db
from src.storage.signal_store import persist_artifacts


def _artifacts() -> RunArtifacts:
    return RunArtifacts(
        timestamp="2026-04-07T09:00:00-04:00",
        agent_results={"macro_regime": AgentResult(name="macro_regime", scores={"growth_score": 55.0}, summary="macro ok")},
        fusion=FusionResult(
            spx_regime_score=55.0,
            sector_opportunity_score=60.0,
            cyclical_opportunity_score=58.0,
            risk_environment_flag="neutral",
            explanation="test",
            contributions={"macro": 55.0},
            component_scores={"macro": 55.0},
        ),
        sector_table=pd.DataFrame([{"ticker": "XLI", "score": 61.0, "classification": "early_leadership"}]),
        cyclical_table=pd.DataFrame([{"ticker": "KRE", "score": 59.0, "classification": "early_build"}]),
        risk_rotation_table=pd.DataFrame(),
        drivers_table=pd.DataFrame(),
        seasonality_table=pd.DataFrame(),
        opportunity_table=pd.DataFrame([{"ticker": "XLI", "early_opportunity_score": 64.0, "opportunity_label": "early confirmation"}]),
        alerts_table=pd.DataFrame([{"level": "watch", "category": "sector", "item": "XLI", "message": "improving", "score": 64.0}]),
        basket_tables={"top_sector": pd.DataFrame([{"ticker": "XLI", "weight": 1.0, "weighting": "equal", "rationale": "test"}])},
        exposure_view={"exposure_stance_label": "neutral", "confidence_tag": "medium", "exposure_summary": "neutral", "supporting_components": {"macro": 55.0}},
        transition_table=pd.DataFrame([{"item": "XLI", "transition_type": "opportunity_label", "previous_value": "weak", "current_value": "early confirmation", "summary": "XLI improved"}]),
        data_health=DataHealthReport(data_health_report={}, stale_series_flags={}, fallback_usage_flags={}),
    )


def test_persist_artifacts_creates_sqlite_rows(tmp_path: Path) -> None:
    init_db(tmp_path)
    payload_path = tmp_path / "outputs" / "json" / "daily_payload.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text("{}", encoding="utf-8")

    run_id = persist_artifacts(tmp_path, _artifacts(), str(payload_path), baskets=_artifacts().basket_tables, transitions=_artifacts().transition_table)

    assert run_id > 0
    assert get_db_path(tmp_path).exists()
