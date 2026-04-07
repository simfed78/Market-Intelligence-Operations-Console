from pathlib import Path

import numpy as np
import pandas as pd

from src.agents.macro_event_agent import MacroEventAgent
from src.data.loaders import load_config_bundle
from src.data.macro_event_calendar import MacroEventCalendarLoader, tag_event_window


def test_macro_event_loader_and_agent():
    root = Path(__file__).resolve().parents[1]
    config = load_config_bundle(root / "config")
    loader = MacroEventCalendarLoader(root / "data" / "raw", config.macro_events)
    frame = loader.load()
    assert not frame.empty
    idx = pd.bdate_range("2025-01-01", periods=260)
    prices = pd.DataFrame({"SPY": 100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0.0003, 0.01, len(idx))))}, index=idx)
    result = MacroEventAgent(config=config.macro_events).run(frame, prices)
    assert "event_risk_score" in result.scores
    assert tag_event_window(pd.Timestamp("2025-01-10"), pd.Timestamp("2025-01-09")) == "pre_event"
