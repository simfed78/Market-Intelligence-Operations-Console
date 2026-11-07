"""Versioned research registry. Instruments are proxies, not execution eligibility."""
from pathlib import Path
import json
import pandas as pd

def load_universe(root: Path) -> pd.DataFrame:
    rows = json.loads((Path(root) / "config/research_universe.json").read_text())
    frame = pd.DataFrame(rows)
    if frame.symbol.duplicated().any():
        raise ValueError("Duplicate research symbol")
    return frame
