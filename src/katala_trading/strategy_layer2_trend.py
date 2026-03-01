"""
strategy_layer2_trend.py — Layer 2: Trend Following Strategy

Core signal: BTC price vs 200-day moving average
  - Above 200MA → Long bias (buy dips, hold breakouts)
  - Below 200MA → Flat or short bias

Entry filters (must satisfy ≥1):
  - Golden cross: 50MA crosses above 200MA
  - RSI dip: RSI(14) < 30 while price above 200MA
  - Volume: above 20-day average volume

Exit:
  - 2 consecutive daily closes below 200MA

Risk management:
  - 2% max capital at risk per trade
  - Hard stop: -5% from entry
  - Optional macro filter: Fear & Greed extreme readings
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
    "rsi_oversold":          30,       # RSI threshold for dip buy
    "rsi_overbought":        70,       # RSI threshold for overbought warning
    "risk_per_trade_pct":    2.0,      # % of capital to risk per trade
    "stop_loss_pct":         5.0,      # Hard stop loss % from entry
    "take_profit_pct":       15.0,     # Take profit % from entry
    "consecutive_closes_exit": 2,      # # closes below 200MA to trigger exit
    "volume_multiplier":     1.0,      # Volume must exceed ma20 × this
    "fear_greed_extreme":    20,       # F&G below this → extreme fear (good buy)
    "fear_greed_euphoria":   80,       # F&G above this → reduce size
    "capital_jpy":           1_000_000,  # Default capital in JPY
    "min_ma200_days":        200,      # Min data points needed for MA200
}


# ── Data Structures ─────────────────────────────────────────────

@dataclass
class TrendSignal:
    """Signal output from Layer 2 trend strategy."""
    timestamp: object  # datetime or float
    close_price: float
    action: str           # "buy", "sell", "hold", "reduce"
    size_btc: float
    confidence: float     # 0-1
    reason: str
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    indicators: Dict = field(default_factory=dict)

    def is_long(self) -> bool:
        return self.action == "buy"

    def is_exit(self) -> bool:
        return self.action in ("sell", "reduce")


@dataclass
class TrendPosition:
    """Open trend position."""
    entry_price: float
    size_btc: float
    stop_loss: float
    take_profit: float
    entry_time: object
    consecutive_below_ma: int = 0
    pnl_jpy: float = 0.0
    status: str = "open"


# ── Core Strategy ──────────────────────────────────────────────

class TrendStrategy:
    """
    Layer 2: Trend-following strategy using 200-day MA.

    Evaluates daily candle data to determine trend bias and
    generate buy/sell signals with proper risk sizing.

    Args:
        config: Strategy configuration dict.
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = {**CONFIG, **(config or {})}
        self._position: Optional[TrendPosition] = None
        self._trade_history: List[Dict] = []

    @property
    def position(self) -> Optional[TrendPosition]:
        return self._position

    def _compute_size(
        self,
        capital_jpy: float,
        entry_price: float,
        stop_pct: float,
    ) -> float:
        """Position size based on 2% risk rule.

        Args:
            capital_jpy: Available capital in JPY.
            entry_price: Entry price in JPY.
            stop_pct: Stop loss distance as %.

        Returns:
            BTC size to trade.
        """
        risk_jpy = capital_jpy * (self.config["risk_per_trade_pct"] / 100)
        loss_per_btc = entry_price * (stop_pct / 100)
        if loss_per_btc <= 0:
            return 0.01
        return max(0.01, round(risk_jpy / loss_per_btc, 4))

    def _check_macro_filter(self, fear_greed: Optional[float]) -> Tuple[bool, float]:
        """Check macro filter adjustments.

        Args:
            fear_greed: Current Fear & Greed index (0-100), or None.

        Returns:
            (allow_entry, size_multiplier) tuple.
        """
        if fear_greed is None:
            return True, 1.0

        if fear_greed < self.config["fear_greed_extreme"]:
            return True, 1.2   # Extreme fear → slightly larger position
        if fear_greed > self.config["fear_greed_euphoria"]:
            return True, 0.5   # Euphoria → halve size
        return True, 1.0

    def evaluate_bar(
        self,
        row: pd.Series,
        fear_greed: Optional[float] = None,
        capital_jpy: float = CONFIG["capital_jpy"],
    ) -> TrendSignal:
        """Evaluate a single daily candle and generate signal.

        Args:
            row: Pandas Series with close, ma200, ma50, rsi14, volume,
                 volume_ma20, golden_cross, death_cross columns.
            fear_greed: Fear & Greed index value (0-100), optional.
            capital_jpy: Available capital in JPY.

        Returns:
            TrendSignal with recommended action.
        """
        close = float(row.get("close", 0))
        ma200 = row.get("ma200", None)
        ma50 = row.get("ma50", None)
        rsi = row.get("rsi14", None)
        volume = float(row.get("volume", 0))
        volume_ma20 = row.get("volume_ma20", None)
        golden_cross = bool(row.get("golden_cross", False))
        ts = row.name if hasattr(row, "name") else 0

        indicators = {
            "close": close,
            "ma200": float(ma200) if pd.notna(ma200) else None,
            "ma50": float(ma50) if pd.notna(ma50) else None,
            "rsi14": float(rsi) if pd.notna(rsi) else None,
            "volume": volume,
            "volume_ma20": float(volume_ma20) if pd.notna(volume_ma20) else None,
            "fear_greed": fear_greed,
        }

        # ── Insufficient data
        if pd.isna(ma200) or close == 0:
            return TrendSignal(
                timestamp=ts, close_price=close, action="hold",
                size_btc=0.0, confidence=0.0,
                reason="insufficient MA200 data",
                indicators=indicators,
            )

        above_ma200 = close > float(ma200)
        allow_entry, size_mult = self._check_macro_filter(fear_greed)

        # ── Exit logic (check position first)
        if self._position is not None:
            pos = self._position

            # Track consecutive closes below MA200
            if not above_ma200:
                pos.consecutive_below_ma += 1
            else:
                pos.consecutive_below_ma = 0

            # Hard stop
            if close <= pos.stop_loss:
                return self._close_position(close, ts, "stop_loss")

            # Take profit
            if close >= pos.take_profit:
                return self._close_position(close, ts, "take_profit")

            # Trend exit: 2 consecutive closes below MA200
            if pos.consecutive_below_ma >= self.config["consecutive_closes_exit"]:
                return self._close_position(close, ts, "ma200_breakdown")

            return TrendSignal(
                timestamp=ts, close_price=close, action="hold",
                size_btc=pos.size_btc, confidence=0.6,
                reason=f"holding, above_ma200={above_ma200}, rsi={rsi:.1f}" if pd.notna(rsi) else "holding",
                stop_loss_price=pos.stop_loss,
                take_profit_price=pos.take_profit,
                indicators=indicators,
            )

        # ── Entry logic (only when no position)
        if not above_ma200:
            return TrendSignal(
                timestamp=ts, close_price=close, action="hold",
                size_btc=0.0, confidence=0.0,
                reason=f"below MA200 ({float(ma200):.0f}), no long bias",
                indicators=indicators,
            )

        # Entry conditions
        signals: List[Tuple[str, float]] = []

        # 1. Golden cross
        if golden_cross:
            signals.append(("golden_cross", 0.9))

        # 2. RSI dip buy
        if pd.notna(rsi) and float(rsi) < self.config["rsi_oversold"]:
            signals.append(("rsi_dip", 0.75))

        # 3. Volume confirmation
        vol_ok = pd.notna(volume_ma20) and volume > float(volume_ma20) * self.config["volume_multiplier"]

        if not signals:
            return TrendSignal(
                timestamp=ts, close_price=close, action="hold",
                size_btc=0.0, confidence=0.0,
                reason="above MA200 but no entry trigger",
                indicators=indicators,
            )

        if not allow_entry:
            return TrendSignal(
                timestamp=ts, close_price=close, action="hold",
                size_btc=0.0, confidence=0.0,
                reason="macro filter blocked entry",
                indicators=indicators,
            )

        # Compute entry
        best_signal, base_conf = max(signals, key=lambda x: x[1])
        confidence = base_conf * (1.1 if vol_ok else 0.9) * size_mult
        confidence = min(1.0, confidence)

        stop_pct = self.config["stop_loss_pct"]
        stop_price = close * (1 - stop_pct / 100)
        tp_price = close * (1 + self.config["take_profit_pct"] / 100)
        size = self._compute_size(capital_jpy, close, stop_pct) * size_mult
        size = round(max(0.01, size), 4)

        self._position = TrendPosition(
            entry_price=close,
            size_btc=size,
            stop_loss=stop_price,
            take_profit=tp_price,
            entry_time=ts,
        )

        triggers = " + ".join(s[0] for s in signals)
        reason = f"{triggers} | {'vol_ok' if vol_ok else 'vol_low'} | f&g={fear_greed}"

        logger.info(
            "TrendStrategy BUY: %.0f JPY, %.4f BTC, stop=%.0f, reason=%s",
            close, size, stop_price, reason,
        )

        return TrendSignal(
            timestamp=ts, close_price=close, action="buy",
            size_btc=size, confidence=confidence,
            reason=reason,
            stop_loss_price=stop_price,
            take_profit_price=tp_price,
            indicators=indicators,
        )

    def _close_position(self, price: float, ts: object, reason: str) -> TrendSignal:
        """Close position and record trade."""
        pos = self._position
        if pos is None:
            return TrendSignal(
                timestamp=ts, close_price=price, action="hold",
                size_btc=0.0, confidence=0.0, reason="no position",
            )

        pnl = (price - pos.entry_price) * pos.size_btc
        trade = {
            "entry_price": pos.entry_price,
            "exit_price": price,
            "size_btc": pos.size_btc,
            "pnl": pnl,
            "reason": reason,
            "entry_time": str(pos.entry_time),
            "exit_time": str(ts),
        }
        self._trade_history.append(trade)
        self._position = None

        logger.info(
            "TrendStrategy SELL: %.0f→%.0f JPY, P&L ¥%.0f (%s)",
            pos.entry_price, price, pnl, reason,
        )

        return TrendSignal(
            timestamp=ts, close_price=price, action="sell",
            size_btc=pos.size_btc, confidence=0.9,
            reason=reason,
        )


# ── Backtesting ────────────────────────────────────────────────

def backtest_trend(
    daily_df: pd.DataFrame,
    fear_greed_df: Optional[pd.DataFrame] = None,
    config: Optional[Dict] = None,
    capital_jpy: float = CONFIG["capital_jpy"],
) -> Dict:
    """Run trend strategy backtest on historical daily OHLCV.

    Args:
        daily_df: Daily OHLCV + indicators DataFrame.
        fear_greed_df: Optional Fear & Greed indexed DataFrame.
        config: Override strategy config.
        capital_jpy: Starting capital in JPY.

    Returns:
        dict with metrics and equity_curve, trade_log.
    """
    strategy = TrendStrategy(config)
    equity = capital_jpy
    peak = equity
    max_dd = 0.0
    equity_curve: List[float] = [equity]

    for ts, row in daily_df.iterrows():
        fg = None
        if fear_greed_df is not None and not fear_greed_df.empty:
            # Find closest fear_greed reading
            fg_idx = fear_greed_df.index.searchsorted(ts)
            if 0 < fg_idx <= len(fear_greed_df):
                fg = float(fear_greed_df.iloc[fg_idx - 1]["fear_greed"])

        signal = strategy.evaluate_bar(row, fear_greed=fg, capital_jpy=equity)

        if signal.action == "sell" and strategy._trade_history:
            pnl = strategy._trade_history[-1]["pnl"]
            equity += pnl
            peak = max(peak, equity)
            dd = peak - equity
            max_dd = max(max_dd, dd)

        equity_curve.append(equity)

    trades = strategy._trade_history
    n = len(trades)
    wins = [t for t in trades if t["pnl"] > 0]
    total_pnl = sum(t["pnl"] for t in trades)
    win_pnl = [t["pnl"] for t in wins]
    loss_pnl = [abs(t["pnl"]) for t in trades if t["pnl"] <= 0]
    profit_factor = sum(win_pnl) / sum(loss_pnl) if loss_pnl else float("inf")

    returns = np.diff(equity_curve) / np.array(equity_curve[:-1])
    sharpe = (
        float(np.mean(returns) / np.std(returns) * np.sqrt(252))
        if len(returns) > 1 and np.std(returns) > 0
        else 0.0
    )

    return {
        "total_trades": n,
        "win_trades": len(wins),
        "win_rate": len(wins) / n if n else 0.0,
        "total_pnl_jpy": total_pnl,
        "total_return_pct": (equity - capital_jpy) / capital_jpy * 100,
        "max_drawdown_jpy": max_dd,
        "max_drawdown_pct": max_dd / peak * 100 if peak > 0 else 0.0,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "equity_curve": equity_curve,
        "trade_log": trades,
    }
