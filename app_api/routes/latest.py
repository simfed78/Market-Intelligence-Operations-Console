"""Latest-state API routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

from app.dashboard_data import load_latest_baskets, load_payload
from app_api.schemas import LatestRegimeResponse, TableResponse


def build_latest_router(project_root: Path) -> APIRouter:
    """Create latest-state routes."""
    router = APIRouter(prefix="/latest", tags=["latest"])

    @router.get("/regime", response_model=LatestRegimeResponse)
    def latest_regime() -> LatestRegimeResponse:
        payload = load_payload(project_root)
        return LatestRegimeResponse(
            timestamp=str(payload.get("timestamp", "")),
            risk_environment_flag=str(payload.get("risk_environment_flag", "unknown")),
            scores=payload.get("scores", {}),
            exposure_view=payload.get("exposure_view", {}),
        )

    @router.get("/rankings/sectors", response_model=TableResponse)
    def latest_sector_rankings() -> TableResponse:
        payload = load_payload(project_root)
        return TableResponse(rows=payload.get("top_ranked_sectors", []))

    @router.get("/rankings/cyclicals", response_model=TableResponse)
    def latest_cyclical_rankings() -> TableResponse:
        payload = load_payload(project_root)
        return TableResponse(rows=payload.get("top_ranked_cyclicals", []))

    @router.get("/alerts", response_model=TableResponse)
    def latest_alerts() -> TableResponse:
        payload = load_payload(project_root)
        return TableResponse(rows=payload.get("alerts_table", []))

    @router.get("/baskets", response_model=TableResponse)
    def latest_baskets() -> TableResponse:
        baskets = load_latest_baskets(project_root)
        rows = [{"basket_name": name, **row} for name, table in baskets.items() for row in table.to_dict(orient="records")]
        return TableResponse(rows=rows)

    return router
