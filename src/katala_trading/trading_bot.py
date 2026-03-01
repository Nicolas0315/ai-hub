"""
trading_bot.py — Main Trading Bot Orchestrator

Combines all 3 strategy layers with Katala KS verification:
  L1: SFD Arbitrage (poll every 10 seconds)
  L2: Trend Following (evaluate every 1 hour)
  L3: Event Risk Management (check on every cycle)

Modes:
  --paper (default): simulate trades, no real orders
  --live: execute real orders via bitFlyer API

Logging:
  All trades, signals, KS verdicts → /Users/nicolas/work/katala/data/btc/logs/

Discord notifications:
  Formatted messages printed to stdout (OpenClaw routes them)

Usage:
  python trading_bot.py              # paper trading mode
  python trading_bot.py --live      # live trading (requires API keys)
  python trading_bot.py --cycles 5  # run N cycles then exit
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# ── Path Setup ─────────────────────────────────────────────────
_HERE = Path(__file__).parent
_SRC = _HERE.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from katala_trading.bitflyer_client import BitFlyerClient, TickerStream
from katala_trading.data_collector import (
    load_parquet, fetch_fear_greed, add_indicators, generate_synthetic_data,
    DATA_DIR,
)
from katala_trading.strategy_layer1_sfd import SFDStrategy, SFDSignal
from katala_trading.strategy_layer2_trend import TrendStrategy, TrendSignal
from katala_trading.strategy_layer3_event import EventRiskManager
from katala_trading.ks_trading_bridge import KSTradingBridge

JST = timezone(timedelta(hours=9))
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ─────────────────────────────────────────────────────
CONFIG = {
    "l1_poll_s":         10,       # L1 poll interval (seconds)
    "l2_poll_h":         1,        # L2 evaluation interval (hours)
    "capital_jpy":       1_000_000, # Paper trading capital
    "max_position_btc":  0.5,      # Max position size
    "use_ks_bridge":     True,     # Use Katala KS verification
    "discord_prefix":    "🤖 **BitFlyer Bot**",
}

# ── Logging Setup ───────────────────────────────────────────────

def setup_logging(verbose: bool = False) -> None:
    """Configure dual logging: console + rotating file."""
    level = logging.DEBUG if verbose else logging.INFO
    log_file = LOG_DIR / f"bot_{datetime.now(JST).strftime('%Y%m%d')}.log"

    handlers: List[logging.Handler] = [
        logging.FileHandler(log_file, encoding="utf-8"),
    ]
    if verbose:
        handlers.append(logging.StreamHandler(sys.stderr))

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )

logger = logging.getLogger(__name__)


# ── Trade Logger ────────────────────────────────────────────────

class TradeLogger:
    """JSON-line trade journal."""

    def __init__(self, path: Path = LOG_DIR / "trades.jsonl") -> None:
        self.path = path

    def log(self, record: Dict) -> None:
        """Append a trade record to the journal."""
        record["logged_at"] = datetime.now(JST).isoformat()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── Discord Notification ─────────────────────────────────────────

def notify(message: str, level: str = "INFO") -> None:
    """Print a formatted notification (OpenClaw routes to Discord).

    Args:
        message: Notification body.
        level: "INFO", "WARN", "ALERT", "TRADE".
    """
    icons = {"INFO": "ℹ️", "WARN": "⚠️", "ALERT": "🚨", "TRADE": "💹"}
    icon = icons.get(level, "📌")
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    print(f"\n{CONFIG['discord_prefix']} {icon} [{ts}]")
    print(message)
    print()
    sys.stdout.flush()


# ── Main Bot ─────────────────────────────────────────────────────

class TradingBot:
    """
    Main trading bot orchestrator.

    Integrates L1/L2/L3 strategies with Katala KS verification
    and executes (or simulates) trades via BitFlyerClient.

    Args:
        live: If True, execute real orders (requires API keys).
        config: Override default config.
    """

    def __init__(self, live: bool = False, config: Optional[Dict] = None) -> None:
        self.live = live
        self.config = {**CONFIG, **(config or {})}
        self.paper = not live

        # ── Clients
        self.client = BitFlyerClient(dry_run=not live)

        # ── Strategies
        self.l1 = SFDStrategy()
        self.l2 = TrendStrategy()
        self.l3 = EventRiskManager()

        # ── KS Bridge
        self.ks = KSTradingBridge() if self.config["use_ks_bridge"] else None

        # ── State
        self._trade_logger = TradeLogger()
        self._last_l2_eval: Optional[datetime] = None
        self._daily_data: Optional[pd.DataFrame] = None
        self._hourly_data: Optional[pd.DataFrame] = None
        self._fear_greed: Optional[pd.DataFrame] = None
        self._cycle_count = 0
        self._running = False

        # Equity tracking
        self._capital = float(self.config["capital_jpy"])
        self._peak_capital = self._capital

    # ── Data Loading ───────────────────────────────────────────

    def _load_data(self) -> None:
        """Load or generate market data for L2/L3."""
        self._daily_data = load_parquet("spot_1d")
        self._hourly_data = load_parquet("spot_1h")
        self._fear_greed = load_parquet("fear_greed")

        if self._daily_data is None or len(self._daily_data) < 200:
            logger.info("Generating synthetic data for L2 evaluation")
            spot_1h, _ = generate_synthetic_data(n_days=400)
            self._hourly_data = spot_1h
            self._daily_data = spot_1h.resample("1D").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum",
            }).dropna()
            self._daily_data = add_indicators(self._daily_data)

        logger.info(
            "Data loaded: %d daily, %d hourly candles",
            len(self._daily_data) if self._daily_data is not None else 0,
            len(self._hourly_data) if self._hourly_data is not None else 0,
        )

    # ── L1: SFD Tick Handler ───────────────────────────────────

    def on_tick(self, tick: Dict) -> None:
        """Process a market tick for L1 SFD strategy.

        Called every ~10 seconds by the ticker stream or poll loop.

        Args:
            tick: dict with spot_price/spot, fx_price/fx, divergence_pct, timestamp.
        """
        self._cycle_count += 1

        # Normalize tick format
        if "spot" in tick and isinstance(tick["spot"], dict):
            tick["spot_price"] = float(tick["spot"].get("ltp", 0))
            tick["fx_price"] = float(tick["fx"].get("ltp", 0))

        # ── L3 Risk Check (every cycle)
        risk_state = self.l3.evaluate(
            hourly_df=self._hourly_data,
            now=datetime.now(JST),
        )

        # ── L1 Signal
        l1_signal = self.l1.on_tick(tick)

        if l1_signal.is_entry() and not risk_state.allow_new_entry:
            logger.info("L1 entry blocked by L3 (vol spike)")
            return

        if l1_signal.is_entry():
            # Apply risk size multiplier
            adj_size = risk_state.size_multiplier * l1_signal.size_btc
            l1_signal.size_btc = max(0.01, adj_size)

            # ── KS Verification
            weighted_signal = None
            if self.ks is not None:
                try:
                    weighted_signal = self.ks.process_sfd_signal(
                        divergence_pct=tick["divergence_pct"],
                        base_action=l1_signal.action,
                        base_confidence=l1_signal.confidence,
                    )
                    # Further adjust size by KS confidence
                    l1_signal.size_btc *= weighted_signal.size_multiplier
                except Exception as e:
                    logger.warning("KS bridge error: %s", e)

            self._execute_l1(l1_signal, tick, weighted_signal)

        elif l1_signal.is_exit():
            self._execute_l1_close(l1_signal, tick)

        # ── Periodic L2 evaluation (every hour)
        now = datetime.now(JST)
        if (self._last_l2_eval is None or
                (now - self._last_l2_eval).total_seconds() >= self.config["l2_poll_h"] * 3600):
            self._evaluate_l2(now)

    def _execute_l1(
        self,
        signal: SFDSignal,
        tick: Dict,
        ks_signal: Optional[object] = None,
    ) -> None:
        """Execute (or simulate) L1 SFD entry order."""
        spot_price = tick.get("spot_price", 0)
        fx_price = tick.get("fx_price", 0)
        div = tick.get("divergence_pct", 0)
        size = round(signal.size_btc, 4)

        ks_info = ""
        if ks_signal is not None:
            ks_info = f" | KS confidence: {ks_signal.final_confidence:.2f}"

        msg = (
            f"**L1 SFD ENTRY** {'[PAPER]' if self.paper else '[LIVE]'}\n"
            f"Action: `{signal.action}`\n"
            f"Divergence: `{div:+.2f}%`\n"
            f"Spot: `¥{spot_price:,.0f}` | FX: `¥{fx_price:,.0f}`\n"
            f"Size: `{size:.4f} BTC`\n"
            f"Reason: {signal.reason}{ks_info}"
        )
        notify(msg, "TRADE")

        trade_record = {
            "layer": "L1",
            "type": "entry",
            "action": signal.action,
            "size_btc": size,
            "spot_price": spot_price,
            "fx_price": fx_price,
            "divergence_pct": div,
            "paper": self.paper,
        }
        self._trade_logger.log(trade_record)

        if self.live:
            try:
                # L1: Short FX + Long Spot (or reverse)
                if signal.action == "short_fx":
                    self.client.send_child_order(
                        "FX_BTC_JPY", "MARKET", "SELL", None, size
                    )
                    self.client.send_child_order(
                        "BTC_JPY", "MARKET", "BUY", None, size
                    )
                else:  # long_fx
                    self.client.send_child_order(
                        "FX_BTC_JPY", "MARKET", "BUY", None, size
                    )
                    self.client.send_child_order(
                        "BTC_JPY", "MARKET", "SELL", None, size
                    )
            except Exception as e:
                logger.error("Order failed: %s", e)
                notify(f"⚠️ Order failed: {e}", "ALERT")

    def _execute_l1_close(self, signal: SFDSignal, tick: Dict) -> None:
        """Execute (or simulate) L1 SFD exit order."""
        msg = (
            f"**L1 SFD EXIT** {'[PAPER]' if self.paper else '[LIVE]'}\n"
            f"Reason: {signal.reason}\n"
            f"Divergence: `{tick.get('divergence_pct', 0):+.2f}%`"
        )
        notify(msg, "TRADE")
        self._trade_logger.log({
            "layer": "L1", "type": "exit",
            "reason": signal.reason,
            "divergence_pct": tick.get("divergence_pct", 0),
            "paper": self.paper,
        })

    # ── L2: Trend Evaluation ───────────────────────────────────

    def _evaluate_l2(self, now: datetime) -> None:
        """Evaluate L2 trend signal on latest daily candle."""
        self._last_l2_eval = now

        if self._daily_data is None or self._daily_data.empty:
            logger.warning("No daily data for L2 evaluation")
            return

        row = self._daily_data.iloc[-1]

        # Fear & Greed lookup
        fg = None
        if self._fear_greed is not None and not self._fear_greed.empty:
            try:
                fg = float(self._fear_greed["fear_greed"].iloc[-1])
            except Exception:
                pass

        signal = self.l2.evaluate_bar(
            row, fear_greed=fg, capital_jpy=self._capital
        )

        if signal.action in ("buy", "sell"):
            risk_state = self.l3.evaluate(now=now)
            adj_size = risk_state.apply_to_size(signal.size_btc)

            # KS verification
            ks_info = ""
            if self.ks is not None and signal.action == "buy":
                try:
                    ma200 = float(row.get("ma200", 0) or 0)
                    rsi14 = float(row.get("rsi14", 50) or 50)
                    close = float(row.get("close", 0) or 0)
                    ws = self.ks.process_trend_signal(
                        price=close, ma200=ma200, rsi14=rsi14,
                        signal_type=signal.reason[:20],
                        base_action=signal.action,
                        base_confidence=signal.confidence,
                    )
                    adj_size *= ws.size_multiplier
                    ks_info = f" | KS: {ws.final_confidence:.2f}"
                except Exception as e:
                    logger.warning("KS trend bridge error: %s", e)

            close = float(row.get("close", 0) or 0)
            msg = (
                f"**L2 Trend {signal.action.upper()}** {'[PAPER]' if self.paper else '[LIVE]'}\n"
                f"Price: `¥{close:,.0f}`\n"
                f"MA200: `¥{float(row.get('ma200', 0) or 0):,.0f}`\n"
                f"RSI14: `{float(row.get('rsi14', 0) or 0):.1f}`\n"
                f"Size: `{adj_size:.4f} BTC`\n"
                f"Reason: {signal.reason}{ks_info}"
            )
            notify(msg, "TRADE")

            self._trade_logger.log({
                "layer": "L2", "type": signal.action,
                "price": close,
                "size_btc": adj_size,
                "reason": signal.reason,
                "paper": self.paper,
            })

        logger.info(
            "L2 eval: action=%s, close=%.0f, ma200=%s, rsi=%.1f",
            signal.action,
            float(row.get("close", 0) or 0),
            f"{float(row.get('ma200', 0) or 0):.0f}" if pd.notna(row.get("ma200")) else "N/A",
            float(row.get("rsi14", 0) or 0),
        )

    # ── Main Loop ──────────────────────────────────────────────

    def run(self, max_cycles: int = 0, poll_mode: bool = True) -> None:
        """Start the main trading loop.

        Args:
            max_cycles: Stop after N L1 cycles (0 = run forever).
            poll_mode: Use polling instead of WebSocket.
        """
        self._running = True
        self._load_data()

        mode_str = "PAPER TRADING" if self.paper else "⚡ LIVE TRADING ⚡"
        notify(
            f"**Bot started** — {mode_str}\n"
            f"Capital: ¥{self._capital:,.0f}\n"
            f"L1 poll: {self.config['l1_poll_s']}s | L2 eval: {self.config['l2_poll_h']}h\n"
            f"KS Bridge: {'✅' if self.ks else '❌'}",
            "INFO",
        )

        if poll_mode:
            self._poll_loop(max_cycles)
        else:
            self._ws_loop(max_cycles)

    def _poll_loop(self, max_cycles: int) -> None:
        """Polling-based main loop."""
        logger.info("Starting poll loop (interval=%ds)", self.config["l1_poll_s"])
        cycle = 0

        while self._running:
            try:
                tick = self.client.get_sfd_divergence()
                self.on_tick(tick)
                cycle += 1

                if max_cycles > 0 and cycle >= max_cycles:
                    logger.info("Reached max_cycles=%d, stopping", max_cycles)
                    break

                time.sleep(self.config["l1_poll_s"])

            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error("Poll loop error: %s", e)
                time.sleep(30)

        self._shutdown()

    def _ws_loop(self, max_cycles: int) -> None:
        """WebSocket-based main loop."""
        count = [0]

        def on_tick(tick: Dict) -> None:
            self.on_tick(tick)
            count[0] += 1
            if max_cycles > 0 and count[0] >= max_cycles:
                stream.stop()
                self._running = False

        stream = TickerStream(on_tick=on_tick, client=self.client)
        stream.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            stream.stop()
            self._shutdown()

    def _shutdown(self) -> None:
        """Graceful shutdown."""
        self._running = False
        notify(
            f"**Bot stopped**\n"
            f"Cycles: {self._cycle_count}\n"
            f"Capital: ¥{self._capital:,.0f}",
            "INFO",
        )
        logger.info("Bot shutdown complete")

    def status(self) -> Dict:
        """Return current bot status."""
        return {
            "mode": "live" if self.live else "paper",
            "running": self._running,
            "cycles": self._cycle_count,
            "capital_jpy": self._capital,
            "l1_position": {
                "side": self.l1.position.side if self.l1.position else None,
                "size": self.l1.position.size_btc if self.l1.position else 0.0,
            },
            "l2_position": {
                "entry_price": self.l2.position.entry_price if self.l2.position else None,
                "size": self.l2.position.size_btc if self.l2.position else 0.0,
            },
            "risk_state": self.l3.summary(),
        }


# ── CLI Entry Point ──────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BitFlyer BTC Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trading_bot.py                    # paper mode, run forever
  python trading_bot.py --cycles 3        # 3 L1 cycles then exit
  python trading_bot.py --live            # live trading (needs API keys)
  python trading_bot.py --verbose         # debug logging
        """,
    )
    parser.add_argument("--live", action="store_true",
                        help="Enable live trading (default: paper)")
    parser.add_argument("--cycles", type=int, default=0,
                        help="Stop after N L1 cycles (0 = forever)")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable debug logging")
    parser.add_argument("--no-ks", action="store_true",
                        help="Disable Katala KS verification")
    parser.add_argument("--poll", action="store_true", default=True,
                        help="Use polling (default; WS is alternative)")
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    config = {**CONFIG}
    if args.no_ks:
        config["use_ks_bridge"] = False

    if args.live:
        print("⚡ LIVE TRADING MODE ⚡")
        print("This will execute real orders on bitFlyer!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            print("Aborted.")
            return

    bot = TradingBot(live=args.live, config=config)
    bot.run(max_cycles=args.cycles, poll_mode=args.poll)


if __name__ == "__main__":
    main()
