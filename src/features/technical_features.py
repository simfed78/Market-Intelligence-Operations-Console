"""Technical feature builders."""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import pandas_ta_classic as ta
except Exception:  # pragma: no cover
    ta = None


def multi_horizon_returns(prices: pd.DataFrame, windows: list[int] | None = None) -> pd.DataFrame:
    """Compute simple returns over multiple windows."""
    windows = windows or [5, 20, 60, 120]
    features = {}
    for window in windows:
        returns = prices.pct_change(window).iloc[-1]
        features[f"ret_{window}"] = returns
    return pd.DataFrame(features)


def rolling_zscore(series: pd.Series, window: int = 60) -> pd.Series:
    """Rolling z-score."""
    mean = series.rolling(window).mean()
    std = series.rolling(window).std().replace(0, np.nan)
    return (series - mean) / std


def moving_average_state(series: pd.Series, short: int = 20, long: int = 50) -> float:
    """Return 1 when short MA > long MA, otherwise 0."""
    short_ma = series.rolling(short).mean()
    long_ma = series.rolling(long).mean()
    if short_ma.dropna().empty or long_ma.dropna().empty:
        return 0.0
    return float(short_ma.iloc[-1] > long_ma.iloc[-1])


def realized_volatility(series: pd.Series, window: int = 20) -> float:
    """Annualized realized volatility from log returns."""
    returns = np.log(series).diff().dropna()
    if returns.empty:
        return 0.0
    return float(returns.tail(window).std() * np.sqrt(252))


def drawdown(series: pd.Series) -> float:
    """Current drawdown."""
    running_max = series.cummax()
    dd = (series / running_max) - 1
    return float(dd.iloc[-1]) if not dd.empty else 0.0


def rolling_trend_quality(series: pd.Series, short: int = 20, long: int = 50) -> float:
    """Approximate trend quality from slope and MA alignment."""
    if len(series.dropna()) < long:
        return 0.0
    short_ma = series.rolling(short).mean()
    long_ma = series.rolling(long).mean()
    slope = short_ma.diff(5).iloc[-1]
    alignment = float(short_ma.iloc[-1] > long_ma.iloc[-1])
    return float(alignment * 50 + max(slope, -2) * 25)


def persistence_ratio(series: pd.Series, lookback: int = 60) -> float:
    """Fraction of positive days within a lookback."""
    returns = series.pct_change().dropna().tail(lookback)
    if returns.empty:
        return 0.0
    return float((returns > 0).mean())


def add_indicator_pack(prices: pd.Series) -> dict[str, float]:
    """Compute a small indicator pack."""
    if prices.dropna().empty:
        return {"rsi": 50.0, "macd_hist": 0.0, "adx": 15.0, "atr_pct": 0.0, "roc_20": 0.0}

    result = {"rsi": 50.0, "macd_hist": 0.0, "adx": 15.0, "atr_pct": 0.0, "roc_20": float(prices.pct_change(20).iloc[-1] * 100)}
    if ta is None:
        return result

    df = pd.DataFrame({"close": prices, "high": prices * 1.01, "low": prices * 0.99})
    rsi = ta.rsi(df["close"], length=14)
    macd = ta.macd(df["close"])
    adx = ta.adx(df["high"], df["low"], df["close"])
    atr = ta.atr(df["high"], df["low"], df["close"])
    result["rsi"] = float(rsi.dropna().iloc[-1]) if rsi is not None and not rsi.dropna().empty else 50.0
    if macd is not None and not macd.dropna().empty:
        hist_cols = [col for col in macd.columns if "h" in col.lower()]
        if hist_cols:
            result["macd_hist"] = float(macd[hist_cols[0]].dropna().iloc[-1])
    if adx is not None and not adx.dropna().empty:
        result["adx"] = float(adx.iloc[:, 0].dropna().iloc[-1])
    if atr is not None and not atr.dropna().empty:
        result["atr_pct"] = float(atr.dropna().iloc[-1] / prices.dropna().iloc[-1] * 100)
    return result
