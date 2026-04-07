"""Historical API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from app.dashboard_data import load_run_history, load_score_history_frame, load_transition_history
from app_api.schemas import HistoryResponse


def build_history_router(project_root: Path) -> APIRouter:
    """Create history routes."""
    router = APIRouter(prefix="/history", tags=["history"])

    @router.get("/scores", response_model=HistoryResponse)
    def score_history(score_name: str = Query(default="breadth_score")) -> HistoryResponse:
        frame = load_score_history_frame(project_root, score_name=score_name)
        return HistoryResponse(rows=frame.to_dict(orient="records"))

    @router.get("/rank-transitions", response_model=HistoryResponse)
    def rank_transitions(limit: int = Query(default=100, ge=1, le=500)) -> HistoryResponse:
        frame = load_transition_history(project_root, limit=limit)
        return HistoryResponse(rows=frame.to_dict(orient="records"))

    @router.get("/runs", response_model=HistoryResponse)
    def run_history(limit: int = Query(default=30, ge=1, le=365)) -> HistoryResponse:
        frame = load_run_history(project_root, limit=limit)
        return HistoryResponse(rows=frame.to_dict(orient="records"))

    return router
