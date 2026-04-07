"""Shared helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def ensure_dir(path: str | Path) -> Path:
    """Ensure a directory exists."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def safe_divide(left: float, right: float, default: float = 0.0) -> float:
    """Divide safely."""
    if right in (0, 0.0) or pd.isna(right):
        return default
    return float(left / right)


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    """Clamp a value into a range."""
    return float(max(lower, min(upper, value)))


def scale_centered(value: float, scale: float = 1.0, center: float = 0.0) -> float:
    """Convert a continuous value to a 0-100 score."""
    normalized = 50 + ((value - center) / scale) * 10
    return clamp(normalized)


def latest_valid(series: pd.Series, default: float = 0.0) -> float:
    """Return the latest non-null value."""
    if series is None:
        return default
    cleaned = series.dropna()
    return float(cleaned.iloc[-1]) if not cleaned.empty else default


def serialize_payload(payload: Any) -> Any:
    """Convert dataclasses and pandas objects into JSON-serializable structures."""
    if is_dataclass(payload):
        return serialize_payload(asdict(payload))
    if isinstance(payload, dict):
        return {key: serialize_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [serialize_payload(item) for item in payload]
    if isinstance(payload, pd.DataFrame):
        return payload.reset_index().to_dict(orient="records")
    if isinstance(payload, pd.Series):
        return payload.to_dict()
    if isinstance(payload, (np.integer, np.floating)):
        return payload.item()
    return payload


def write_json(path: str | Path, payload: Any) -> None:
    """Write JSON output."""
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(serialize_payload(payload), handle, indent=2, default=str)
