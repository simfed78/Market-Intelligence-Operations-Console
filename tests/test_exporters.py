from pathlib import Path

import pandas as pd

from src.models.scoring import FusionResult, RunArtifacts
from src.reports.exporters import export_latest_outputs


def test_exporters_write_latest_files(tmp_path: Path) -> None:
    artifacts = RunArtifacts(
        timestamp="2026-04-07T09:00:00-04:00",
        agent_results={},
        fusion=FusionResult(55.0, 60.0, 58.0, "neutral", "test", {"macro": 55.0}, {"macro": 55.0}),
        sector_table=pd.DataFrame([{"ticker": "XLI", "score": 61.0}]),
        cyclical_table=pd.DataFrame([{"ticker": "KRE", "score": 59.0}]),
        risk_rotation_table=pd.DataFrame(),
        drivers_table=pd.DataFrame(),
        seasonality_table=pd.DataFrame(),
        watchlist_table=pd.DataFrame([{"ticker": "XLI"}]),
        alerts_table=pd.DataFrame([{"item": "XLI"}]),
    )
    baskets = {"top_sector": pd.DataFrame([{"ticker": "XLI", "weight": 1.0}])}

    export_latest_outputs(tmp_path, artifacts, baskets, {"exposure_stance_label": "neutral"})

    assert (tmp_path / "outputs" / "exports" / "latest_summary.json").exists()
    assert (tmp_path / "outputs" / "exports" / "top_sector_basket.csv").exists()
