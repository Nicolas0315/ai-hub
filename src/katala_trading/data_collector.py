"""
data_collector.py — Historical Data Pipeline for BitFlyer BTC

Features:
  - Paginated execution fetch (goes as far back as API allows)
  - OHLCV candle construction: 1m, 5m, 15m, 1h, 4h, 1d
  - Parquet storage in /Users/nicolas/work/katala/data/btc/
  - Indicators: 200MA, 50MA, RSI(14), volume profile
  - SFD (乖離率) calculation: (FX - Spot) / Spot * 100
  - External data: Fear & Greed index (alternative.me)
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pandas_ta as ta
import requests

from katala_trading.bitflyer_client import BitFlyerClient

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────
DATA_DIR = Path("/Users/nicolas/work/katala/data/btc")
JST = timezone(timedelta(hours=9))

TIMEFRAMES: Dict[str, str] = {
    "1m":  "1min",
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1D",
}

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=30&format=json"


# ── Helpers ─────────────────────────────────────────────────────

def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "logs").mkdir(exist_ok=True)


def _to_jst(ts: str) -> datetime:
    """Parse bitFlyer exec_date string to JST datetime."""
    dt = datetime.fromisoformat(ts.rstrip("Z"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JST)


# ── Execution Fetcher ───────────────────────────────────────────

class ExecutionFetcher:
    """Paginated fetcher for bitFlyer execution history.

    BitFlyer returns max 500 executions per call; we paginate
    using before= parameter to walk backwards in time.
    """

    def __init__(self, client: BitFlyerClient, product: str) -> None:
        self.client = client
        self.product = product

    def fetch_all(
        self,
        max_pages: int = 200,
        delay: float = 0.4,
    ) -> pd.DataFrame:
        """Fetch execution history as far back as possible.

        Args:
            max_pages: Max pagination rounds (200 × 500 = 100,000 trades).
            delay: Sleep between requests to respect rate limit.

        Returns:
            DataFrame with columns: id, side, price, size, exec_date (JST).
        """
        records: List[Dict] = []
        before: Optional[int] = None
        logger.info("Fetching %s executions (max %d pages)…", self.product, max_pages)

        for page in range(max_pages):
            try:
                batch = self.client.get_executions(
                    product_code=self.product, count=500, before=before
                )
            except Exception as e:
                logger.warning("Fetch error page %d: %s", page, e)
                break

            if not batch:
                logger.info("No more executions at page %d", page)
                break

            records.extend(batch)
            before = batch[-1]["id"]
            logger.debug("Page %d: %d trades, oldest id=%s", page, len(batch), before)
            time.sleep(delay)

        if not records:
            logger.warning("No executions fetched for %s", self.product)
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["exec_date"] = df["exec_date"].apply(_to_jst)
        df["price"] = df["price"].astype(float)
        df["size"] = df["size"].astype(float)
        df = df.sort_values("exec_date").reset_index(drop=True)
        logger.info(
            "Fetched %d executions (%s → %s)",
            len(df),
            df["exec_date"].iloc[0],
            df["exec_date"].iloc[-1],
        )
        return df


# ── OHLCV Builder ───────────────────────────────────────────────

def build_ohlcv(executions: pd.DataFrame, freq: str = "1min") -> pd.DataFrame:
    """Build OHLCV candles from tick data.

    Args:
        executions: DataFrame from ExecutionFetcher.fetch_all().
        freq: Pandas resample frequency string.

    Returns:
        DataFrame with OHLCV columns indexed by JST timestamp.
    """
    # Manual OHLCV construction from tick data
    grp = executions.set_index("exec_date").resample(freq)
    ohlcv = pd.DataFrame({
        "open":   grp["price"].first(),
        "high":   grp["price"].max(),
        "low":    grp["price"].min(),
        "close":  grp["price"].last(),
        "volume": grp["size"].sum(),
    }).dropna(subset=["close"])

    return ohlcv  # type: ignore[return-value]


# ── Indicator Calculator ────────────────────────────────────────

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to OHLCV DataFrame.

    Adds: MA200, MA50, MA20, RSI14, ATR14, volume_ma20.

    Args:
        df: OHLCV DataFrame with close, high, low, volume columns.

    Returns:
        DataFrame with indicator columns appended.
    """
    df = df.copy()
    close = df["close"]
    volume = df["volume"]

    # Moving averages
    df["ma200"] = ta.sma(close, length=200)
    df["ma50"] = ta.sma(close, length=50)
    df["ma20"] = ta.sma(close, length=20)

    # RSI
    df["rsi14"] = ta.rsi(close, length=14)

    # ATR
    atr = ta.atr(df["high"], df["low"], df["close"], length=14)
    df["atr14"] = atr

    # Volume MA
    df["volume_ma20"] = ta.sma(volume, length=20)

    # Golden/Death cross signal
    df["golden_cross"] = (
        (df["ma50"] > df["ma200"]) &
        (df["ma50"].shift(1) <= df["ma200"].shift(1))
    ).astype(int)
    df["death_cross"] = (
        (df["ma50"] < df["ma200"]) &
        (df["ma50"].shift(1) >= df["ma200"].shift(1))
    ).astype(int)

    return df


# ── Volume Profile ───────────────────────────────────────────────

def compute_volume_profile(
    df: pd.DataFrame, bins: int = 20
) -> Dict[str, float]:
    """Compute price-volume profile (POC, VAH, VAL).

    Args:
        df: OHLCV DataFrame.
        bins: Number of price buckets.

    Returns:
        dict with poc (Point of Control), vah, val, profile_data.
    """
    price_range = np.linspace(df["low"].min(), df["high"].max(), bins + 1)
    volumes = np.zeros(bins)
    for i in range(bins):
        lo, hi = price_range[i], price_range[i + 1]
        mask = (df["close"] >= lo) & (df["close"] < hi)
        volumes[i] = df.loc[mask, "volume"].sum()

    total_vol = volumes.sum()
    poc_idx = int(np.argmax(volumes))
    poc = float((price_range[poc_idx] + price_range[poc_idx + 1]) / 2)

    # Value area: 70% of total volume centered on POC
    cumulative = np.cumsum(volumes[poc_idx::-1]) + np.cumsum(volumes[poc_idx:])
    cumulative -= volumes[poc_idx]  # avoid double-counting POC
    target = total_vol * 0.70
    lo_idx = poc_idx
    hi_idx = poc_idx
    for j in range(1, bins):
        lo_idx = max(0, poc_idx - j)
        hi_idx = min(bins - 1, poc_idx + j)
        if volumes[lo_idx:hi_idx + 1].sum() >= target:
            break

    return {
        "poc": poc,
        "vah": float(price_range[hi_idx + 1]),
        "val": float(price_range[lo_idx]),
    }


# ── SFD Calculator ──────────────────────────────────────────────

def compute_sfd_series(
    spot_df: pd.DataFrame,
    fx_df: pd.DataFrame,
    freq: str = "1h",
) -> pd.DataFrame:
    """Compute historical SFD divergence series.

    Args:
        spot_df: OHLCV for BTC_JPY.
        fx_df: OHLCV for FX_BTC_JPY.
        freq: Resample frequency to align both series.

    Returns:
        DataFrame with spot_close, fx_close, divergence_pct columns.
    """
    spot = spot_df["close"].resample(freq).last().rename("spot_close")
    fx = fx_df["close"].resample(freq).last().rename("fx_close")
    merged = pd.concat([spot, fx], axis=1).dropna()
    merged["divergence_pct"] = (
        (merged["fx_close"] - merged["spot_close"]) / merged["spot_close"] * 100
    )
    return merged


# ── External Data ────────────────────────────────────────────────

def fetch_fear_greed() -> pd.DataFrame:
    """Fetch Fear & Greed index from alternative.me.

    Returns:
        DataFrame with date, value, value_classification columns.
    """
    try:
        r = requests.get(FEAR_GREED_URL, timeout=10)
        r.raise_for_status()
        data = r.json()["data"]
        records = [
            {
                "date": pd.Timestamp(int(d["timestamp"]), unit="s", tz=JST),
                "fear_greed": int(d["value"]),
                "fg_label": d["value_classification"],
            }
            for d in data
        ]
        df = pd.DataFrame(records).set_index("date").sort_index()
        logger.info("Fear & Greed: fetched %d rows", len(df))
        return df
    except Exception as e:
        logger.warning("Fear & Greed fetch failed: %s", e)
        return pd.DataFrame(columns=["fear_greed", "fg_label"])


# ── Synthetic Data Generator ─────────────────────────────────────

def generate_synthetic_data(
    n_days: int = 365,
    start_price: float = 5_000_000.0,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Generate realistic synthetic BTC OHLCV data for backtesting.

    Uses geometric Brownian motion with trend + volatility clusters.

    Args:
        n_days: Number of days to generate.
        start_price: Starting BTC price in JPY.
        seed: Random seed.

    Returns:
        Tuple of (spot_df, fx_df) with daily OHLCV and indicators.
    """
    rng = np.random.default_rng(seed)
    n = n_days * 24  # hourly candles

    # GBM parameters based on historical BTC behavior
    mu = 0.0003      # hourly drift (~3% monthly)
    sigma = 0.018    # hourly volatility (~18% annualized base)

    # Regime changes: bull/bear cycles
    regimes = np.ones(n)
    bear_start = int(n * 0.35)
    bear_end = int(n * 0.60)
    regimes[bear_start:bear_end] = -0.5  # bear market
    mu_arr = mu * regimes

    # Volatility clusters (GARCH-like)
    vol_arr = np.full(n, sigma)
    spike_idxs = rng.choice(n, size=20, replace=False)
    for idx in spike_idxs:
        duration = rng.integers(12, 72)
        end = min(idx + duration, n)
        vol_arr[idx:end] *= rng.uniform(2.0, 4.0)

    # Price path
    returns = rng.normal(mu_arr, vol_arr)
    log_prices = np.log(start_price) + np.cumsum(returns)
    prices = np.exp(log_prices)

    # Build hourly OHLCV
    end_time = datetime.now(JST).replace(minute=0, second=0, microsecond=0)
    start_time = end_time - timedelta(hours=n - 1)
    idx = pd.date_range(start=start_time, periods=n, freq="h", tz=JST)

    noise = rng.uniform(0.995, 1.005, n)
    spot_df = pd.DataFrame({
        "open":   prices * rng.uniform(0.997, 1.003, n),
        "high":   prices * rng.uniform(1.003, 1.015, n),
        "low":    prices * rng.uniform(0.985, 0.997, n),
        "close":  prices,
        "volume": rng.exponential(50, n),
    }, index=idx)

    # FX price with synthetic divergence (mean-reverting spread)
    divergence = np.zeros(n)
    div = 0.0
    for i in range(n):
        div = div * 0.98 + rng.normal(0, 0.3)  # mean-reverting
        # Occasional large divergences
        if rng.random() < 0.005:
            div += rng.choice([-1, 1]) * rng.uniform(5.0, 8.0)
        divergence[i] = np.clip(div, -12, 12)

    fx_prices = prices * (1 + divergence / 100)
    fx_df = pd.DataFrame({
        "open":   fx_prices * rng.uniform(0.997, 1.003, n),
        "high":   fx_prices * rng.uniform(1.003, 1.015, n),
        "low":    fx_prices * rng.uniform(0.985, 0.997, n),
        "close":  fx_prices,
        "volume": rng.exponential(30, n),
    }, index=idx)

    spot_df = add_indicators(spot_df)
    fx_df = add_indicators(fx_df)

    logger.info(
        "Synthetic data: %d hourly candles, price %.0f → %.0f JPY",
        n, prices[0], prices[-1],
    )
    return spot_df, fx_df


# ── Parquet I/O ─────────────────────────────────────────────────

def save_parquet(df: pd.DataFrame, name: str) -> Path:
    """Save DataFrame to parquet in DATA_DIR.

    Args:
        df: DataFrame to save.
        name: File base name (without extension).

    Returns:
        Path to saved file.
    """
    _ensure_dirs()
    path = DATA_DIR / f"{name}.parquet"
    df.to_parquet(path)
    logger.info("Saved %s (%d rows) → %s", name, len(df), path)
    return path


def load_parquet(name: str) -> Optional[pd.DataFrame]:
    """Load parquet from DATA_DIR.

    Args:
        name: File base name.

    Returns:
        DataFrame or None if file doesn't exist.
    """
    path = DATA_DIR / f"{name}.parquet"
    if not path.exists():
        return None
    df = pd.read_parquet(path)
    logger.info("Loaded %s (%d rows) from %s", name, len(df), path)
    return df


# ── Main Collection Pipeline ────────────────────────────────────

def collect_and_store(
    use_synthetic: bool = False,
    max_pages: int = 50,
) -> Dict[str, pd.DataFrame]:
    """Full data collection pipeline.

    Args:
        use_synthetic: Use synthetic data instead of live API.
        max_pages: Max pagination pages for execution fetch.

    Returns:
        dict with keys: spot_1h, fx_1h, spot_1d, fx_1d, sfd_1h, fear_greed.
    """
    _ensure_dirs()
    results: Dict[str, pd.DataFrame] = {}

    if use_synthetic:
        logger.info("Using synthetic data")
        spot_df, fx_df = generate_synthetic_data(n_days=400)
    else:
        client = BitFlyerClient()
        spot_fetcher = ExecutionFetcher(client, "BTC_JPY")
        fx_fetcher = ExecutionFetcher(client, "FX_BTC_JPY")

        spot_execs = spot_fetcher.fetch_all(max_pages=max_pages)
        fx_execs = fx_fetcher.fetch_all(max_pages=max_pages)

        if spot_execs.empty:
            logger.warning("No spot data — falling back to synthetic")
            spot_df, fx_df = generate_synthetic_data(n_days=400)
        else:
            spot_df = build_ohlcv(spot_execs, "1h")
            fx_df = build_ohlcv(fx_execs, "1h")
            spot_df = add_indicators(spot_df)
            fx_df = add_indicators(fx_df)

    # Daily resample
    def _to_daily(df: pd.DataFrame) -> pd.DataFrame:
        d = df.resample("1D").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna()
        return add_indicators(d)

    spot_1d = _to_daily(spot_df)
    fx_1d = _to_daily(fx_df)
    sfd_1h = compute_sfd_series(spot_df, fx_df, "1h")

    results = {
        "spot_1h": spot_df,
        "fx_1h": fx_df,
        "spot_1d": spot_1d,
        "fx_1d": fx_1d,
        "sfd_1h": sfd_1h,
    }

    # Fear & Greed
    fg = fetch_fear_greed()
    if not fg.empty:
        results["fear_greed"] = fg

    # Persist
    for key, df in results.items():
        save_parquet(df, key)

    return results
