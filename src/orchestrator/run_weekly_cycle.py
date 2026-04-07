"""Weekly orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.data.loaders import ConfigBundle
from src.orchestrator.run_daily_cycle import DailyCycleRunner
from src.reports.exporters import export_latest_outputs
from src.reports.json_payload import build_json_payload
from src.reports.weekly_report import build_weekly_markdown_report
from src.storage.signal_store import persist_artifacts
from src.utils.helpers import ensure_dir, write_json


@dataclass
class WeeklyCycleRunner:
    """Run the weekly deep-dive cycle."""

    config: ConfigBundle
    project_root: Path

    def run(self):
        """Reuse daily flow and persist weekly outputs."""
        artifacts = DailyCycleRunner(config=self.config, project_root=self.project_root).run(run_type="weekly", persist=False)
        reports_dir = ensure_dir(self.project_root / "outputs" / "reports")
        json_dir = ensure_dir(self.project_root / "outputs" / "json")
        weekly_md = build_weekly_markdown_report(artifacts)
        (reports_dir / "weekly_report.md").write_text(weekly_md, encoding="utf-8")
        payload_path = json_dir / "weekly_payload.json"
        write_json(payload_path, build_json_payload(artifacts))
        persist_artifacts(self.project_root, artifacts, str(payload_path), baskets=artifacts.basket_tables, transitions=artifacts.transition_table)
        export_latest_outputs(self.project_root, artifacts, artifacts.basket_tables, exposure_view=artifacts.exposure_view)
        return artifacts
