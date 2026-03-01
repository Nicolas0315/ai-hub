"""
backtest_engine.py — Backtesting Framework

Runs each strategy independently and combined:
  - L1: SFD Arbitrage
  - L2: Trend Following
  - L1+L2: Combined
  - L1+L2+L3: Full 3-layer system

Metrics:
  - Total return, Sharpe ratio, max drawdown, win rate, profit factor
  - Equity curve (JSON-serializable)
  - Side-by-side comparison table

Usage:
  python backtest_engine.py
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from katala_trading.data_collector import (
    generate_synthetic_data,
    compute_sfd_series,
    add_indicators,
    load_parquet,
    DATA_DIR,
)
from katala_trading.strategy_layer1_sfd import backtest_sfd, SFDStrategy
from katala_trading.strategy_layer2_trend import backtest_trend
from katala_trading.strategy_layer3_event import backtest_event_filter

logger = logging.getLogger(__name__)

CAPITAL_JPY = 1_000_000  # Starting capital: ¥1,000,000

# ── Metrics ─────────────────────────────────────────────────────

def compute_sharpe(equity_curve: List[float], periods_per_year: int = 252) -> float:
    """Compute annualized Sharpe ratio from equity curve.

    Args:
        equity_curve: List of equity values over time.
        periods_per_year: Trading periods per year (252 for daily).

    Returns:
        Annualized Sharpe ratio.
    """
    arr = np.array(equity_curve)
    if len(arr) < 2:
        return 0.0
    returns = np.diff(arr) / arr[:-1]
    if np.std(returns) == 0:
        return 0.0
    return float(np.mean(returns) / np.std(returns) * np.sqrt(periods_per_year))


def compute_max_drawdown(equity_curve: List[float]) -> Tuple[float, float]:
    """Compute maximum drawdown in JPY and %.

    Args:
        equity_curve: List of equity values.

    Returns:
        (max_drawdown_jpy, max_drawdown_pct) tuple.
    """
    arr = np.array(equity_curve)
    peak = np.maximum.accumulate(arr)
    drawdown = peak - arr
    max_dd_jpy = float(np.max(drawdown))
    max_dd_pct = float(np.max(drawdown / peak) * 100) if peak.max() > 0 else 0.0
    return max_dd_jpy, max_dd_pct


def compute_profit_factor(trade_log: List[Dict]) -> float:
    """Compute profit factor (gross profit / gross loss).

    Args:
        trade_log: List of trade dicts with pnl key.

    Returns:
        Profit factor (>1 = profitable).
    """
    pnl_key = "adj_pnl" if trade_log and "adj_pnl" in trade_log[0] else "pnl"
    wins = sum(t[pnl_key] for t in trade_log if t[pnl_key] > 0)
    losses = abs(sum(t[pnl_key] for t in trade_log if t[pnl_key] <= 0))
    return wins / losses if losses > 0 else float("inf")


# ── Combined L1+L2 Engine ────────────────────────────────────────

def _run_combined_backtest(
    sfd_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    fear_greed_df: Optional[pd.DataFrame] = None,
    capital_jpy: float = CAPITAL_JPY,
) -> Dict:
    """Run L1 + L2 combined backtest.

    L1 (SFD) generates short-term P&L on the 1h SFD series.
    L2 (Trend) generates directional P&L on daily candles.
    Combined equity = CAPITAL + L1_pnl + L2_pnl

    Args:
        sfd_df: Hourly SFD DataFrame.
        daily_df: Daily OHLCV + indicators DataFrame.
        fear_greed_df: Optional Fear & Greed DataFrame.
        capital_jpy: Starting capital.

    Returns:
        Combined metrics dict.
    """
    l1 = backtest_sfd(sfd_df)
    l2 = backtest_trend(daily_df, fear_greed_df, capital_jpy=capital_jpy)

    # Merge equity curves (align to daily by subsampling L1)
    l2_curve = l2["equity_curve"]
    n_days = len(l2_curve)

    # Redistribute L1 equity curve to match daily length
    l1_curve = l1.equity_curve
    if len(l1_curve) > n_days:
        # Downsample L1 to daily
        step = len(l1_curve) / n_days
        l1_sampled = [l1_curve[min(int(i * step), len(l1_curve) - 1)] for i in range(n_days)]
    elif len(l1_curve) < n_days:
        # Pad with last value
        l1_sampled = l1_curve + [l1_curve[-1]] * (n_days - len(l1_curve))
    else:
        l1_sampled = l1_curve

    # Combined equity
    combined = [
        capital_jpy + l2_v - capital_jpy + l1_v
        for l2_v, l1_v in zip(l2_curve, l1_sampled)
    ]

    max_dd_jpy, max_dd_pct = compute_max_drawdown(combined)
    sharpe = compute_sharpe(combined)
    total_pnl = combined[-1] - capital_jpy if combined else 0.0
    total_return_pct = total_pnl / capital_jpy * 100

    # Merge trade logs
    all_trades = l1.trade_log + l2["trade_log"]
    n = len(all_trades)
    wins = sum(1 for t in all_trades if t.get("pnl", t.get("adj_pnl", 0)) > 0)

    return {
        "total_trades": n,
        "win_trades": wins,
        "win_rate": wins / n if n else 0.0,
        "total_pnl_jpy": total_pnl,
        "total_return_pct": total_return_pct,
        "max_drawdown_jpy": max_dd_jpy,
        "max_drawdown_pct": max_dd_pct,
        "profit_factor": compute_profit_factor(all_trades),
        "sharpe_ratio": sharpe,
        "equity_curve": combined,
        "l1_pnl_jpy": l1.total_pnl_jpy,
        "l2_pnl_jpy": l2["total_pnl_jpy"],
    }


# ── Main Backtest Runner ────────────────────────────────────────

@dataclass
class BacktestSuite:
    """Results from full backtest suite comparison."""
    l1_only: Dict
    l2_only: Dict
    l1_l2: Dict
    l1_l2_l3: Dict
    metadata: Dict


def run_full_backtest(
    use_cache: bool = True,
    capital_jpy: float = CAPITAL_JPY,
    verbose: bool = True,
) -> BacktestSuite:
    """Run complete backtest suite across all strategy combinations.

    Args:
        use_cache: Load cached parquet data if available.
        capital_jpy: Starting capital in JPY.
        verbose: Print progress to stdout.

    Returns:
        BacktestSuite with all comparison results.
    """
    start_t = time.time()

    if verbose:
        print("=" * 60)
        print("  BitFlyer BTC Trading System — Backtest Engine")
        print("=" * 60)
        print(f"  Capital: ¥{capital_jpy:,.0f}")
        print()

    # ── Load or generate data
    spot_1h = load_parquet("spot_1h") if use_cache else None
    fx_1h = load_parquet("fx_1h") if use_cache else None
    spot_1d = load_parquet("spot_1d") if use_cache else None
    fear_greed = load_parquet("fear_greed") if use_cache else None

    if spot_1h is None or fx_1h is None:
        if verbose:
            print("  Generating synthetic data (400 days × hourly)…")
        spot_1h, fx_1h = generate_synthetic_data(n_days=400, seed=42)

    if spot_1d is None:
        spot_1d = spot_1h.resample("1D").agg({
            "open": "first", "high": "max", "low": "min",
            "close": "last", "volume": "sum",
        }).dropna()
        spot_1d = add_indicators(spot_1d)

    # Compute SFD series
    sfd_1h = compute_sfd_series(spot_1h, fx_1h, "1h")

    if verbose:
        print(f"  Data: {len(spot_1h)} hourly candles, "
              f"{len(spot_1d)} daily candles")
        print(f"  Date range: {spot_1h.index[0]} → {spot_1h.index[-1]}")
        print()

    # ── L1: SFD Only
    if verbose:
        print("  Running L1 (SFD Arbitrage)…")
    l1_result = backtest_sfd(sfd_1h)
    l1_ec = l1_result.equity_curve
    l1_dd_jpy, l1_dd_pct = compute_max_drawdown(
        [capital_jpy + v for v in l1_ec]
    )

    l1_dict = {
        "total_trades": l1_result.total_trades,
        "win_trades": l1_result.win_trades,
        "win_rate": l1_result.win_rate,
        "total_pnl_jpy": l1_result.total_pnl_jpy,
        "total_return_pct": l1_result.total_pnl_jpy / capital_jpy * 100,
        "max_drawdown_jpy": l1_dd_jpy,
        "max_drawdown_pct": l1_dd_pct,
        "profit_factor": compute_profit_factor(l1_result.trade_log),
        "sharpe_ratio": compute_sharpe([capital_jpy + v for v in l1_ec], 365 * 24),
        "equity_curve": [capital_jpy + v for v in l1_ec],
    }

    # ── L2: Trend Only
    if verbose:
        print("  Running L2 (Trend Following)…")
    l2_dict = backtest_trend(spot_1d, fear_greed, capital_jpy=capital_jpy)

    # ── L1+L2 Combined
    if verbose:
        print("  Running L1+L2 (Combined)…")
    l1l2_dict = _run_combined_backtest(sfd_1h, spot_1d, fear_greed, capital_jpy)

    # ── L1+L2+L3 (with event risk filter)
    if verbose:
        print("  Running L1+L2+L3 (Full System)…")
    l1l2l3_dict = backtest_event_filter(l1l2_dict, spot_1d)

    elapsed = time.time() - start_t

    suite = BacktestSuite(
        l1_only=l1_dict,
        l2_only=l2_dict,
        l1_l2=l1l2_dict,
        l1_l2_l3=l1l2l3_dict,
        metadata={
            "capital_jpy": capital_jpy,
            "data_rows_hourly": len(spot_1h),
            "data_rows_daily": len(spot_1d),
            "date_start": str(spot_1h.index[0]),
            "date_end": str(spot_1h.index[-1]),
            "elapsed_s": round(elapsed, 2),
            "synthetic": True,
        },
    )

    if verbose:
        _print_results(suite)

    # Save equity curves to JSON
    _save_equity_curves(suite)

    return suite


def _print_results(suite: BacktestSuite) -> None:
    """Print formatted comparison table."""
    strategies = [
        ("L1 (SFD)", suite.l1_only),
        ("L2 (Trend)", suite.l2_only),
        ("L1+L2", suite.l1_l2),
        ("L1+L2+L3", suite.l1_l2_l3),
    ]

    print()
    print("=" * 60)
    print("  BACKTEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"  Capital: ¥{suite.metadata['capital_jpy']:>15,.0f}")
    print(f"  Period:  {suite.metadata['date_start'][:10]} → {suite.metadata['date_end'][:10]}")
    print(f"  Data:    {suite.metadata['data_rows_daily']} daily candles (synthetic)")
    print()
    print(f"  {'Strategy':<14} {'Return%':>8} {'Sharpe':>7} {'MaxDD%':>7} "
          f"{'WinRate':>8} {'PF':>6} {'Trades':>7}")
    print(f"  {'-'*14} {'-'*8} {'-'*7} {'-'*7} {'-'*8} {'-'*6} {'-'*7}")

    for name, r in strategies:
        ret = r.get("total_return_pct", 0)
        sharpe = r.get("sharpe_ratio", 0)
        dd = r.get("max_drawdown_pct", 0)
        wr = r.get("win_rate", 0) * 100
        pf = r.get("profit_factor", 0)
        trades = r.get("total_trades", 0)
        pf_str = f"{pf:.2f}" if pf != float("inf") else "  ∞"
        print(f"  {name:<14} {ret:>7.1f}% {sharpe:>7.2f} {dd:>6.1f}% "
              f"{wr:>7.1f}% {pf_str:>6} {trades:>7}")

    print()
    best = max(strategies, key=lambda x: x[1].get("sharpe_ratio", 0))
    print(f"  Best Sharpe: {best[0]}")
    print(f"  Elapsed: {suite.metadata['elapsed_s']:.2f}s")
    print("=" * 60)


def _save_equity_curves(suite: BacktestSuite) -> None:
    """Save equity curves to JSON for visualization."""
    output = {
        "L1": suite.l1_only.get("equity_curve", [])[:500],
        "L2": suite.l2_only.get("equity_curve", [])[:500],
        "L1+L2": suite.l1_l2.get("equity_curve", [])[:500],
        "L1+L2+L3": suite.l1_l2_l3.get("equity_curve", [])[:500],
    }
    path = DATA_DIR / "equity_curves.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    logger.info("Equity curves saved to %s", path)


# ── Entry Point ─────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    suite = run_full_backtest(use_cache=True, verbose=True)
