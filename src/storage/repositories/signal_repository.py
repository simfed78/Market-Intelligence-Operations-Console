"""Signal repository."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.storage.db import get_connection


class SignalRepository:
    """Persist signals, rankings, alerts, baskets, and transitions."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def insert_agent_scores(self, run_id: int, agent_results: dict) -> None:
        with get_connection(self.project_root) as conn:
            for agent_name, agent_result in agent_results.items():
                for score_name, score_value in agent_result.scores.items():
                    conn.execute(
                        "INSERT INTO agent_scores(run_id, agent_name, score_name, score_value) VALUES(?,?,?,?)",
                        (run_id, agent_name, score_name, float(score_value)),
                    )
            conn.commit()

    def insert_ranking_table(self, run_id: int, ranking_type: str, table: pd.DataFrame, item_col: str = "ticker", label_col: str = "classification", score_col: str = "score") -> None:
        if table.empty:
            return
        with get_connection(self.project_root) as conn:
            for idx, row in table.reset_index(drop=True).iterrows():
                conn.execute(
                    "INSERT INTO rankings(run_id, ranking_type, item, score, label, rank_order) VALUES(?,?,?,?,?,?)",
                    (run_id, ranking_type, str(row.get(item_col, "")), float(row.get(score_col, 0.0)), str(row.get(label_col, "")), idx + 1),
                )
            conn.commit()

    def insert_alerts(self, run_id: int, alerts: pd.DataFrame) -> None:
        if alerts.empty:
            return
        with get_connection(self.project_root) as conn:
            for _, row in alerts.iterrows():
                state_hash = hashlib.md5(f"{row.get('level')}|{row.get('category')}|{row.get('item')}|{row.get('message')}".encode("utf-8")).hexdigest()
                exists = conn.execute("SELECT 1 FROM alerts WHERE state_hash = ? ORDER BY id DESC LIMIT 1", (state_hash,)).fetchone()
                if exists:
                    continue
                conn.execute(
                    "INSERT INTO alerts(run_id, level, category, item, message, score, state_hash) VALUES(?,?,?,?,?,?,?)",
                    (run_id, str(row.get("level", "")), str(row.get("category", "")), str(row.get("item", "")), str(row.get("message", "")), float(row.get("score", 0.0)), state_hash),
                )
            conn.commit()

    def insert_baskets(self, run_id: int, baskets: dict[str, pd.DataFrame]) -> None:
        with get_connection(self.project_root) as conn:
            for basket_name, table in baskets.items():
                if table.empty:
                    continue
                for _, row in table.iterrows():
                    conn.execute(
                        "INSERT INTO baskets(run_id, basket_name, weighting, item, weight, rationale) VALUES(?,?,?,?,?,?)",
                        (run_id, basket_name, str(row.get("weighting", "")), str(row.get("ticker", row.get("item", ""))), float(row.get("weight", 0.0)), str(row.get("rationale", ""))),
                    )
            conn.commit()

    def insert_transitions(self, run_id: int, transitions: pd.DataFrame) -> None:
        if transitions.empty:
            return
        with get_connection(self.project_root) as conn:
            for _, row in transitions.iterrows():
                conn.execute(
                    "INSERT INTO transitions(run_id, item, transition_type, previous_value, current_value, summary) VALUES(?,?,?,?,?,?)",
                    (run_id, str(row.get("item", "")), str(row.get("transition_type", "")), str(row.get("previous_value", "")), str(row.get("current_value", "")), str(row.get("summary", ""))),
                )
            conn.commit()

    def history_scores(self, score_name: str) -> pd.DataFrame:
        with get_connection(self.project_root) as conn:
            rows = conn.execute(
                """
                SELECT runs.timestamp, agent_scores.agent_name, agent_scores.score_name, agent_scores.score_value
                FROM agent_scores
                JOIN runs ON runs.id = agent_scores.run_id
                WHERE agent_scores.score_name = ?
                ORDER BY runs.timestamp
                """,
                (score_name,),
            ).fetchall()
        return pd.DataFrame([dict(row) for row in rows])

    def rank_transitions(self, limit: int = 100) -> pd.DataFrame:
        with get_connection(self.project_root) as conn:
            rows = conn.execute("SELECT * FROM transitions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return pd.DataFrame([dict(row) for row in rows])
