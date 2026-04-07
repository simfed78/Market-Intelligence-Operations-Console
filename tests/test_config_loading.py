from pathlib import Path

from src.data.loaders import load_config_bundle


def test_load_config_bundle():
    root = Path(__file__).resolve().parents[1]
    bundle = load_config_bundle(root / "config")
    assert bundle.settings["project"]["benchmark"] == "SPY"
    assert "core_index" in bundle.tickers
    assert "growth" in bundle.fred_series
    assert "fusion" in bundle.weights
    assert "windows" in bundle.validation
    assert "defaults" in bundle.dashboard
    assert "events" in bundle.macro_events
    assert "sectors" in bundle.earnings_map
    assert "sector_constituents" in bundle.sector_constituents
    assert "mode" in bundle.options_proxy
    assert "spx" in bundle.opportunity_weights
    assert "thresholds" in bundle.alerts
