"""Export helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.helpers import ensure_dir, write_json


def export_latest_outputs(project_root: Path, artifacts, baskets: dict[str, pd.DataFrame], exposure_view: dict[str, Any]) -> None:
    """Write export snapshots for external workflows."""
    export_dir = ensure_dir(project_root / "outputs" / "exports")
    write_json(export_dir / "latest_summary.json", {
        "timestamp": artifacts.timestamp,
        "risk_flag": artifacts.fusion.risk_environment_flag,
        "scores": artifacts.fusion.component_scores,
        "exposure_stance": exposure_view.get("exposure_stance_label", "unknown"),
    })
    artifacts.sector_table.to_csv(export_dir / "latest_rankings_sectors.csv", index=False)
    artifacts.cyclical_table.to_csv(export_dir / "latest_rankings_cyclicals.csv", index=False)
    artifacts.watchlist_table.to_csv(export_dir / "latest_watchlist.csv", index=False)
    for name, basket in baskets.items():
        basket.to_csv(export_dir / f"{name}_basket.csv", index=False)
        write_json(export_dir / f"{name}_basket.json", basket.to_dict(orient="records"))
    write_json(export_dir / "tradingview_summary.json", {
        "watchlist": artifacts.watchlist_table.head(10).to_dict(orient="records"),
        "alerts": artifacts.alerts_table.head(10).to_dict(orient="records"),
    })
