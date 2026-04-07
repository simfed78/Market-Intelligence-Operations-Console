from pathlib import Path

import pandas as pd

from src.models.signal_registry import build_state_transitions


def test_build_state_transitions_detects_label_changes() -> None:
    previous = pd.DataFrame([{"ticker": "XLI", "opportunity_label": "weak"}])
    current = pd.DataFrame([{"ticker": "XLI", "opportunity_label": "early confirmation"}])

    transitions = build_state_transitions(previous, current)

    assert transitions.iloc[0]["item"] == "XLI"
    assert "moved from weak" in transitions.iloc[0]["summary"]
