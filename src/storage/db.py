"""SQLite helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_db_path(project_root: Path) -> Path:
    """Return the default SQLite path."""
    db_dir = project_root / "data" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "market_intelligence.db"


def get_connection(project_root: Path) -> sqlite3.Connection:
    """Open a SQLite connection."""
    conn = sqlite3.connect(get_db_path(project_root))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(project_root: Path) -> None:
    """Initialize schema."""
    from src.storage.models import SCHEMA

    with get_connection(project_root) as conn:
        conn.executescript(SCHEMA)
        conn.commit()
