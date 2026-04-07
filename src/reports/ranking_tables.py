"""Tabular report writers."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_csv_table(table: pd.DataFrame, path: str | Path) -> None:
    """Write a table to CSV."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
