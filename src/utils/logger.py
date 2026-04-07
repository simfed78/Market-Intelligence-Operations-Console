"""Logging helpers."""

from __future__ import annotations

import logging
import os


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger."""
    level = os.getenv("MIE_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(name)
