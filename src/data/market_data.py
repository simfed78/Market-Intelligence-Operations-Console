"""Market data adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.cache_manager import CacheManager
from src.utils.logger import get_logger

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


LOGGER = get_logger(__name__)


def _cache_key(prefix: str, tickers: list[str], period: str, interval: str) -> str:
    """Build a compact cache key."""
    joined = "|".join(sorted(tickers))
    digest = hashlib.md5(joined.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{period}_{interval}_{digest}"


@dataclass
class MarketDataFetcher:
    """Download or synthesize market data."""

    cache: CacheManager
    raw_dir: Path
    use_sample_on_failure: bool = True
    used_fallback: bool = False

    def fetch_prices(self, tickers: list[str], period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        """Fetch close prices for a list of tickers."""
        cache_key = _cache_key("prices", tickers, period, interval)
        if self.cache.is_fresh(cache_key):
            cached = self.cache.read(cache_key)
            if cached is not None and not cached.empty:
                return cached

        local = self._load_local_prices(tickers)
        if not local.empty:
            self.used_fallback = True
            self.cache.write(cache_key, local)
            return local

        if yf is not None:
            try:
                downloaded = yf.download(
                    tickers=tickers,
                    period=period,
                    interval=interval,
                    auto_adjust=True,
                    progress=False,
                    group_by="column",
                )
                if not downloaded.empty:
                    if isinstance(downloaded.columns, pd.MultiIndex):
                        closes = downloaded["Close"].copy()
                    else:
                        closes = downloaded.rename(columns={"Close": tickers[0]})[[tickers[0]]]
                    closes = closes.dropna(how="all").ffill()
                    self.cache.write(cache_key, closes)
                    self.used_fallback = False
                    return closes
            except Exception as exc:  # pragma: no cover
                LOGGER.warning("yfinance download failed: %s", exc)

        if self.use_sample_on_failure:
            self.used_fallback = True
            synthetic = self._build_synthetic_prices(tickers)
            self.cache.write(cache_key, synthetic)
            return synthetic
        return pd.DataFrame()

    def fetch_volumes(self, tickers: list[str], period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        """Fetch volume series."""
        if yf is None:
            return pd.DataFrame(index=self.fetch_prices(tickers, period, interval).index, columns=tickers).fillna(1_000_000)
        try:
            downloaded = yf.download(
                tickers=tickers,
                period=period,
                interval=interval,
                auto_adjust=True,
                progress=False,
                group_by="column",
            )
            if isinstance(downloaded.columns, pd.MultiIndex):
                volumes = downloaded["Volume"].copy()
            else:
                volumes = downloaded.rename(columns={"Volume": tickers[0]})[[tickers[0]]]
            return volumes.dropna(how="all").ffill()
        except Exception as exc:  # pragma: no cover
            LOGGER.warning("volume download failed: %s", exc)
            return pd.DataFrame(index=self.fetch_prices(tickers, period, interval).index, columns=tickers).fillna(1_000_000)

    def _load_local_prices(self, tickers: list[str]) -> pd.DataFrame:
        path = self.raw_dir / "market_prices.csv"
        if not path.exists():
            return pd.DataFrame()
        frame = pd.read_csv(path, parse_dates=["date"]).set_index("date")
        cols = [ticker for ticker in tickers if ticker in frame.columns]
        return frame[cols].sort_index() if cols else pd.DataFrame()

    def _build_synthetic_prices(self, tickers: list[str], periods: int = 520) -> pd.DataFrame:
        dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=periods)
        base_noise = np.random.default_rng(42).normal(0.0004, 0.01, len(dates))
        spy_path = 100 * np.exp(np.cumsum(base_noise))
        frame = pd.DataFrame(index=dates)
        for idx, ticker in enumerate(tickers):
            tilt = (idx - len(tickers) / 2) * 0.00003
            noise = np.random.default_rng(idx + 1).normal(tilt, 0.009 + idx * 0.0001, len(dates))
            series = spy_path * np.exp(np.cumsum(noise - base_noise * 0.35))
            frame[ticker] = series
        return frame.round(4)
