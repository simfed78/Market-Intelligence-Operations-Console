"""Run history persistence."""

from __future__ import annotations

from pathlib import Path

from src.storage.db import init_db
from src.storage.repositories.run_repository import RunRepository
from src.storage.repositories.signal_repository import SignalRepository


class RunHistoryStore:
    """Persist run metadata and artifacts."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        init_db(project_root)
        self.runs = RunRepository(project_root)
        self.signals = SignalRepository(project_root)
