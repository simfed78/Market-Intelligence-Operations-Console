"""FastAPI entrypoint for the local service layer."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app_api.routes.history import build_history_router
from app_api.routes.latest import build_latest_router


def create_app(project_root: Path | None = None) -> FastAPI:
    """Create the local API application."""
    root = project_root or Path(__file__).resolve().parents[1]
    app = FastAPI(title="Market Intelligence Local API", version="0.1.0")
    app.include_router(build_latest_router(root))
    app.include_router(build_history_router(root))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
