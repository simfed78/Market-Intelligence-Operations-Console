"""Config and CSV loaders."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.utils.helpers import load_yaml


@dataclass
class ConfigBundle:
    """Application configuration bundle."""

    settings: dict[str, Any]
    tickers: dict[str, Any]
    fred_series: dict[str, Any]
    sector_map: dict[str, Any]
    weights: dict[str, Any]
    validation: dict[str, Any]
    dashboard: dict[str, Any]
    proxy_registry: dict[str, Any]
    macro_events: dict[str, Any]
    earnings_map: dict[str, Any]
    sector_constituents: dict[str, Any]
    options_proxy: dict[str, Any]
    opportunity_weights: dict[str, Any]
    alerts: dict[str, Any]
    baskets: dict[str, Any]
    exposure_rules: dict[str, Any]
    portfolio_research: dict[str, Any]


def load_config_bundle(config_dir: str | Path) -> ConfigBundle:
    """Load all configuration files."""
    config_dir = Path(config_dir)
    return ConfigBundle(
        settings=load_yaml(config_dir / "settings.yaml"),
        tickers=load_yaml(config_dir / "tickers.yaml"),
        fred_series=load_yaml(config_dir / "fred_series.yaml"),
        sector_map=load_yaml(config_dir / "sector_map.yaml"),
        weights=load_yaml(config_dir / "weights.yaml"),
        validation=load_yaml(config_dir / "validation.yaml"),
        dashboard=load_yaml(config_dir / "dashboard.yaml"),
        proxy_registry=load_yaml(config_dir / "proxy_registry.yaml"),
        macro_events=load_yaml(config_dir / "macro_events.yaml"),
        earnings_map=load_yaml(config_dir / "earnings_map.yaml"),
        sector_constituents=load_yaml(config_dir / "sector_constituents.yaml"),
        options_proxy=load_yaml(config_dir / "options_proxy.yaml"),
        opportunity_weights=load_yaml(config_dir / "opportunity_weights.yaml"),
        alerts=load_yaml(config_dir / "alerts.yaml"),
        baskets=load_yaml(config_dir / "baskets.yaml"),
        exposure_rules=load_yaml(config_dir / "exposure_rules.yaml"),
        portfolio_research=load_yaml(config_dir / "portfolio_research.yaml"),
    )


def load_csv_series(path: str | Path, date_col: str = "date") -> pd.DataFrame:
    """Load a local CSV if it exists."""
    csv_path = Path(path)
    if not csv_path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(csv_path)
    if date_col in frame.columns:
        frame[date_col] = pd.to_datetime(frame[date_col])
        frame = frame.set_index(date_col)
    return frame.sort_index()
