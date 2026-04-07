"""Lightweight scheduler helpers for local runs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from src.data.loaders import ConfigBundle, load_config_bundle
from src.orchestrator.run_daily_cycle import DailyCycleRunner
from src.orchestrator.run_weekly_cycle import WeeklyCycleRunner


@dataclass
class ScheduledJob:
    """Simple job definition."""

    name: str
    mode: str
    interval_hours: int
    log_file: str


def build_jobs(project_root: Path) -> list[ScheduledJob]:
    """Create default local jobs."""
    return [
        ScheduledJob(name="daily_cycle", mode="daily", interval_hours=24, log_file="logs/daily.log"),
        ScheduledJob(name="weekly_cycle", mode="weekly", interval_hours=24 * 7, log_file="logs/weekly.log"),
    ]


def next_run_at(started_at: datetime, interval_hours: int) -> datetime:
    """Compute the next run timestamp."""
    return started_at + timedelta(hours=interval_hours)


def run_mode(project_root: Path, mode: str):
    """Run one mode immediately."""
    config: ConfigBundle = load_config_bundle(project_root / "config")
    if mode == "weekly":
        return WeeklyCycleRunner(config=config, project_root=project_root).run()
    return DailyCycleRunner(config=config, project_root=project_root).run(run_type=mode)
