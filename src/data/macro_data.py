"""Macro data adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.cache_manager import CacheManager
from src.data.loaders import load_csv_series
from src.utils.logger import get_logger

try:
    from fredapi import Fred
except Exception:  # pragma: no cover
    Fred = None


LOGGER = get_logger(__name__)


@dataclass
class MacroDataFetcher:
    """Fetch macro data from FRED or local files."""

    cache: CacheManager
    raw_dir: Path
    use_sample_on_failure: bool = True
    used_fallback: bool = False

    def fetch_series_map(self, series_map: dict[str, str]) -> pd.DataFrame:
        """Fetch a named map of FRED series."""
        frames: list[pd.Series] = []
        for name, fred_code in series_map.items():
            series = self.fetch_single_series(name, fred_code)
            if not series.empty:
                frames.append(series.rename(name))
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=1).sort_index()

    def fetch_single_series(self, name: str, fred_code: str) -> pd.Series:
        """Fetch a single series with cache and CSV fallback."""
        cache_key = f"fred_{name}_{fred_code}"
        if self.cache.is_fresh(cache_key):
            cached = self.cache.read(cache_key)
            if cached is not None and not cached.empty:
                return cached.iloc[:, 0]

        local = self._load_local_series(name, fred_code)
        if not local.empty:
            self.used_fallback = True
            self.cache.write(cache_key, local.to_frame(name))
            return local

        api_key = os.getenv("FRED_API_KEY")
        if Fred is not None and api_key:
            try:
                client = Fred(api_key=api_key)
                series = client.get_series(fred_code).dropna().sort_index()
                if not series.empty:
                    self.cache.write(cache_key, series.to_frame(name))
                    self.used_fallback = False
                    return series.rename(name)
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("fred download failed for %s: %s", fred_code, exc)

        if self.use_sample_on_failure:
            self.used_fallback = True
            synthetic = self._build_synthetic_macro(name)
            self.cache.write(cache_key, synthetic.to_frame(name))
            return synthetic
        return pd.Series(dtype=float, name=name)

    def _load_local_series(self, name: str, fred_code: str) -> pd.Series:
        for candidate in (
            self.raw_dir / f"{name}.csv",
            self.raw_dir / f"{fred_code}.csv",
            self.raw_dir / "macro_manual.csv",
        ):
            frame = load_csv_series(candidate)
            if name in frame.columns:
                return frame[name].dropna()
            if fred_code in frame.columns:
                return frame[fred_code].dropna().rename(name)
        return pd.Series(dtype=float, name=name)

    def _build_synthetic_macro(self, name: str, periods: int = 84) -> pd.Series:
        end = pd.Timestamp.today().normalize().to_period("M").to_timestamp("M")
        dates = pd.date_range(end=end, periods=periods, freq="ME")
        rng = np.random.default_rng(abs(hash(name)) % (2**32))
        if "claims" in name:
            values = 230 + np.cumsum(rng.normal(0, 2, periods))
        elif "inflation" in name or "cpi" in name or "ppi" in name:
            values = 2.5 + np.cumsum(rng.normal(0, 0.02, periods))
        elif "fed" in name or "gs" in name or "yield" in name:
            values = 3.5 + np.cumsum(rng.normal(0, 0.04, periods))
        elif "nfci" in name:
            values = np.cumsum(rng.normal(0, 0.03, periods))
        else:
            values = 100 + np.cumsum(rng.normal(0, 0.6, periods))
        return pd.Series(values, index=dates, name=name).round(4)
