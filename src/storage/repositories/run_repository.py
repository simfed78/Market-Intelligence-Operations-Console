"""Run repository."""

from __future__ import annotations

from pathlib import Path

from src.storage.db import get_connection


class RunRepository:
    """Persist and load run rows."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def insert_run(self, timestamp: str, run_type: str, risk_flag: str, spx_score: float, sector_score: float, cyclical_score: float, payload_path: str) -> int:
        with get_connection(self.project_root) as conn:
            cursor = conn.execute(
                """
                INSERT OR REPLACE INTO runs(timestamp, run_type, risk_flag, spx_regime_score, sector_opportunity_score, cyclical_opportunity_score, payload_path)
                VALUES(?,?,?,?,?,?,?)
                """,
                (timestamp, run_type, risk_flag, spx_score, sector_score, cyclical_score, payload_path),
            )
            conn.commit()
            row = conn.execute("SELECT id FROM runs WHERE timestamp = ?", (timestamp,)).fetchone()
            return int(row["id"])

    def latest_run(self, run_type: str = "daily"):
        with get_connection(self.project_root) as conn:
            return conn.execute("SELECT * FROM runs WHERE run_type = ? ORDER BY timestamp DESC LIMIT 1", (run_type,)).fetchone()

    def run_history(self, limit: int = 30):
        with get_connection(self.project_root) as conn:
            return conn.execute("SELECT * FROM runs ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
