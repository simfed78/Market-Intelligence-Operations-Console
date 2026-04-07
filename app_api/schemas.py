"""Pydantic schemas for the local API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LatestRegimeResponse(BaseModel):
    """Latest regime endpoint payload."""

    timestamp: str
    risk_environment_flag: str
    scores: dict[str, float]
    exposure_view: dict[str, Any]


class TableResponse(BaseModel):
    """Tabular payload."""

    rows: list[dict[str, Any]]


class HistoryResponse(BaseModel):
    """History payload."""

    rows: list[dict[str, Any]]
