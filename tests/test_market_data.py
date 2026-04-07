from pathlib import Path

from src.data.cache_manager import CacheManager
from src.data.market_data import MarketDataFetcher


def test_market_data_fetcher_returns_frame():
    root = Path(__file__).resolve().parents[1]
    fetcher = MarketDataFetcher(cache=CacheManager(root / "data" / "cache", ttl_hours=1), raw_dir=root / "data" / "raw")
    frame = fetcher.fetch_prices(["SPY", "QQQ"], period="6mo")
    assert not frame.empty
    assert "SPY" in frame.columns
