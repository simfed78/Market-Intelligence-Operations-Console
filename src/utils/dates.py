"""Date utilities."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def now_in_tz(timezone_name: str) -> datetime:
    """Return current timestamp in the configured timezone."""
    return datetime.now(ZoneInfo(timezone_name))


def lookback_start(days: int = 365, reference: datetime | None = None) -> datetime:
    """Return a lookback start date."""
    reference = reference or datetime.utcnow()
    return reference - timedelta(days=days)
