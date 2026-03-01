"""
strategy_layer1_sfd.py — Layer 1: SFD Arbitrage Strategy

SFD (Swap for Difference / 乖離率) is a bitFlyer-specific mechanism:
  - BitFlyer charges a penalty when |FX_price - Spot_price| / Spot_price > 5%
  - Strategy exploits mean-reversion of this spread

Logic:
  - Entry: divergence > +5.5% → Short FX + Buy Spot (FX premium)
           divergence < -5.5% → Long FX + Sell Spot (FX discount)
  - Exit : divergence < 2% absolute OR stop-loss at 3x entry divergence
  - Sizing: Kelly criterion based on historical hit rate

Reference:
  https://bitflyer.com/en-jp/docs/sfd
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────
CONFIG = {
    "entry_threshold_pct":  5.5,    # Divergence % to trigger entry
    "exit_threshold_pct":   2.0,    # Divergence % to trigger exit (convergence)
    "stop_loss_pct":        3.0,    # Additional spread from entry (divergence worsens)
    "max_position_btc":     1.0,    # Max position size in BTC
    "kelly_fraction":       0.5,    # Fractional Kelly (conservative)
    "min_position_btc":     0.01,   # Minimum tradeable size
    "sfd_penalty_rate":     0.001,  # bitFlyer SFD charge rate (0.1% per transaction)
}


# ── Data Structures ────────────────────────────────────────────

@dataclass
class SFDSignal:
    """Signal output from Layer 1 SFD strategy."""
    timestamp: float
    spot_price: float
    fx_price: float
    divergence_pct: float
    action: str          # "long_fx", "short_fx", "close", "hold"
    size_btc: float
    confidence: float    # 0-1
    reason: str

    def is_entry(self) -> bool:
        return self.action in ("long_fx", "short_fx")

    def is_exit(self) -> bool:
        return self.action == "close"


@dataclass
class SFDPosition:
    """Open SFD position."""
    entry_divergence: float
    side: str            # "short_fx" or "long_fx"
    size_btc: float
    entry_spot: float
    entry_fx: float
    entry_time: float
    pnl_jpy: float = 0.0
    status: str = "open"


@dataclass
class BacktestResult:
    """Result of SFD backtest."""
    total_trades: int
    win_trades: int
    total_pnl_jpy: float
    max_drawdown_jpy: float
    win_rate: float
    avg_pnl_per_trade: float
    kelly_estimate: float
    equity_curve: List[float] = field(default_factory=list)
    trade_log: List[Dict] = field(default_factory=list)


# ── Kelly Criterion ────────────────────────────────────────────

def kelly_size(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
    max_btc: float,
    fraction: float = CONFIG["kelly_fraction"],
) -> float:
    """Calculate Kelly criterion position size.

    Args:
        win_rate: Historical win rate (0-1).
        avg_win: Average winning trade P&L (JPY).
        avg_loss: Average losing trade P&L (JPY, positive number).
        max_btc: Maximum allowed position in BTC.
        fraction: Fractional Kelly multiplier for risk reduction.

    Returns:
        Position size in BTC (bounded by max_btc).
    """
    if avg_loss <= 0 or win_rate <= 0:
        return CONFIG["min_position_btc"]
    b = avg_win / avg_loss  # win/loss ratio
    q = 1 - win_rate
    kelly_f = (b * win_rate - q) / b
    kelly_f = max(0.0, kelly_f * fraction)
    return min(kelly_f * max_btc, max_btc)


# ── Core Strategy ──────────────────────────────────────────────

class SFDStrategy:
    """
    Layer 1: SFD Arbitrage Strategy.

    Monitors BTC_JPY vs FX_BTC_JPY divergence and signals
    mean-reversion trades when spread exceeds threshold.

    Args:
        config: Strategy configuration dict.
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = {**CONFIG, **(config or {})}
        self._position: Optional[SFDPosition] = None
        self._trade_history: List[Dict] = []
        # Bootstrap Kelly estimates from prior performance
        self._win_rate: float = 0.65
        self._avg_win_jpy: float = 50_000.0
        self._avg_loss_jpy: float = 30_000.0

    @property
    def position(self) -> Optional[SFDPosition]:
        return self._position

    def _compute_kelly_size(self) -> float:
        """Compute current Kelly position size."""
        return kelly_size(
            self._win_rate,
            self._avg_win_jpy,
            self._avg_loss_jpy,
            self.config["max_position_btc"],
            self.config["kelly_fraction"],
        )

    def _update_kelly_estimate(self) -> None:
        """Update win rate and avg P&L from trade history."""
        if len(self._trade_history) < 5:
            return
        wins = [t for t in self._trade_history if t["pnl"] > 0]
        losses = [t for t in self._trade_history if t["pnl"] <= 0]
        if wins:
            self._avg_win_jpy = float(np.mean([t["pnl"] for t in wins]))
        if losses:
            self._avg_loss_jpy = float(abs(np.mean([t["pnl"] for t in losses])))
        self._win_rate = len(wins) / len(self._trade_history)
        logger.debug(
            "Kelly update: win_rate=%.2f avg_win=%.0f avg_loss=%.0f",
            self._win_rate, self._avg_win_jpy, self._avg_loss_jpy,
        )

    def on_tick(self, tick: Dict) -> SFDSignal:
        """Process a market tick and return trading signal.

        Args:
            tick: dict with spot_price, fx_price, divergence_pct, timestamp.

        Returns:
            SFDSignal with recommended action.
        """
        div = float(tick["divergence_pct"])
        spot = float(tick.get("spot_price", tick.get("spot", {}).get("ltp", 0)))
        fx = float(tick.get("fx_price", tick.get("fx", {}).get("ltp", 0)))
        ts = float(tick.get("timestamp", 0))

        entry_thr = self.config["entry_threshold_pct"]
        exit_thr = self.config["exit_threshold_pct"]
        stop_thr = self.config["stop_loss_pct"]

        # ── Check for exit if we have a position
        if self._position is not None:
            pos = self._position
            abs_div = abs(div)

            # Convergence exit
            if abs_div < exit_thr:
                return self._close_position(spot, fx, div, ts, "convergence")

            # Stop-loss: divergence worsened significantly
            if pos.side == "short_fx" and div > pos.entry_divergence + stop_thr:
                return self._close_position(spot, fx, div, ts, "stop_loss")
            if pos.side == "long_fx" and div < pos.entry_divergence - stop_thr:
                return self._close_position(spot, fx, div, ts, "stop_loss")

            return SFDSignal(
                timestamp=ts, spot_price=spot, fx_price=fx,
                divergence_pct=div, action="hold",
                size_btc=pos.size_btc, confidence=0.5,
                reason=f"holding position, div={div:.2f}%",
            )

        # ── Entry logic
        if div >= entry_thr:
            size = self._compute_kelly_size()
            confidence = min(1.0, (div - entry_thr) / 3.0 + 0.6)
            self._position = SFDPosition(
                entry_divergence=div, side="short_fx",
                size_btc=size, entry_spot=spot,
                entry_fx=fx, entry_time=ts,
            )
            return SFDSignal(
                timestamp=ts, spot_price=spot, fx_price=fx,
                divergence_pct=div, action="short_fx",
                size_btc=size, confidence=confidence,
                reason=f"FX premium {div:.2f}% > threshold {entry_thr}%",
            )

        if div <= -entry_thr:
            size = self._compute_kelly_size()
            confidence = min(1.0, (abs(div) - entry_thr) / 3.0 + 0.6)
            self._position = SFDPosition(
                entry_divergence=div, side="long_fx",
                size_btc=size, entry_spot=spot,
                entry_fx=fx, entry_time=ts,
            )
            return SFDSignal(
                timestamp=ts, spot_price=spot, fx_price=fx,
                divergence_pct=div, action="long_fx",
                size_btc=size, confidence=confidence,
                reason=f"FX discount {div:.2f}% < -threshold {entry_thr}%",
            )

        return SFDSignal(
            timestamp=ts, spot_price=spot, fx_price=fx,
            divergence_pct=div, action="hold",
            size_btc=0.0, confidence=0.0,
            reason=f"no signal, div={div:.2f}%",
        )

    def _close_position(
        self, spot: float, fx: float, div: float, ts: float, reason: str
    ) -> SFDSignal:
        """Close the current position and record P&L."""
        pos = self._position
        if pos is None:
            return SFDSignal(
                timestamp=ts, spot_price=spot, fx_price=fx,
                divergence_pct=div, action="hold", size_btc=0.0,
                confidence=0.0, reason="no position to close",
            )

        # P&L calculation
        if pos.side == "short_fx":
            # Short FX: profit when FX price falls
            pnl = (pos.entry_fx - fx) * pos.size_btc
            # Spot long: profit when spot price rises
            pnl += (spot - pos.entry_spot) * pos.size_btc
        else:
            # Long FX: profit when FX price rises
            pnl = (fx - pos.entry_fx) * pos.size_btc
            # Spot short: profit when spot falls
            pnl += (pos.entry_spot - spot) * pos.size_btc

        # Deduct SFD penalty (charged by bitFlyer)
        # SFD is applied at entry when divergence > 5%
        entry_abs = abs(pos.entry_divergence)
        if entry_abs > 5.0:
            sfd_cost = fx * pos.size_btc * self.config["sfd_penalty_rate"]
            pnl -= sfd_cost

        trade = {
            "side": pos.side,
            "size_btc": pos.size_btc,
            "entry_div": pos.entry_divergence,
            "exit_div": div,
            "entry_spot": pos.entry_spot,
            "entry_fx": pos.entry_fx,
            "exit_spot": spot,
            "exit_fx": fx,
            "pnl": pnl,
            "duration_s": ts - pos.entry_time,
            "reason": reason,
        }
        self._trade_history.append(trade)
        self._position = None
        self._update_kelly_estimate()

        logger.info(
            "SFD close [%s]: div %.2f%%→%.2f%%, P&L ¥%.0f (%s)",
            pos.side, pos.entry_divergence, div, pnl, reason,
        )

        return SFDSignal(
            timestamp=ts, spot_price=spot, fx_price=fx,
            divergence_pct=div, action="close",
            size_btc=pos.size_btc, confidence=1.0, reason=reason,
        )


# ── Backtesting ────────────────────────────────────────────────

def backtest_sfd(
    sfd_df: pd.DataFrame,
    config: Optional[Dict] = None,
) -> BacktestResult:
    """Run SFD strategy backtest on historical divergence data.

    Args:
        sfd_df: DataFrame with spot_close, fx_close, divergence_pct columns.
                Index should be datetime.
        config: Override strategy config.

    Returns:
        BacktestResult with performance metrics.
    """
    strategy = SFDStrategy(config)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    equity_curve: List[float] = []

    for idx, row in sfd_df.iterrows():
        tick = {
            "spot_price": float(row["spot_close"]),
            "fx_price": float(row["fx_close"]),
            "divergence_pct": float(row["divergence_pct"]),
            "timestamp": idx.timestamp() if hasattr(idx, "timestamp") else float(idx),
        }
        signal = strategy.on_tick(tick)
        if signal.action == "close" and strategy._trade_history:
            pnl = strategy._trade_history[-1]["pnl"]
            equity += pnl
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    # Final metrics
    trades = strategy._trade_history
    n = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    win_rate = len(wins) / n if n > 0 else 0.0
    total_pnl = sum(t["pnl"] for t in trades)
    avg_pnl = total_pnl / n if n > 0 else 0.0

    return BacktestResult(
        total_trades=n,
        win_trades=len(wins),
        total_pnl_jpy=total_pnl,
        max_drawdown_jpy=max_dd,
        win_rate=win_rate,
        avg_pnl_per_trade=avg_pnl,
        kelly_estimate=strategy._win_rate,
        equity_curve=equity_curve,
        trade_log=trades,
    )
