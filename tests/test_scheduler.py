from datetime import datetime
from pathlib import Path

from src.orchestrator.scheduler import build_jobs, next_run_at


def test_scheduler_builds_default_jobs(tmp_path: Path) -> None:
    jobs = build_jobs(tmp_path)
    assert {job.mode for job in jobs} == {"daily", "weekly"}


def test_next_run_at_adds_interval() -> None:
    start = datetime(2026, 4, 7, 9, 0, 0)
    assert next_run_at(start, 24).day == 8
