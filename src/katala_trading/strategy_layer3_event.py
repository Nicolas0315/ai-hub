"""
strategy_layer3_event.py — Layer 3: Event Risk Management

Risk reduction around high-impact macro events:
  - FOMC meetings → reduce position 50% before
  - BOJ meetings → reduce position 50% before
  - Volatility spikes (1h ATR > 3× 20d avg) → auto-reduce
  - Cool-down: 24h after major event before normal sizing
  - No new entries during extreme volatility

Event sources:
  - Hardcoded 2026 FOMC/BOJ schedule (updated annually)
  - Geopolitical keyword detection (simple text scan)
  - Real-time ATR-based volatility detection
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd
import pandas_ta as ta

logger = logging.getLogger(__name__)

JST = timezone(timedelta(hours=9))

# ── Config ─────────────────────────────────────────────────────
CONFIG = {
    "pre_event_hours":       24,      # Hours before event to reduce
    "post_event_cooldown_h": 24,      # Cool-down after event
    "position_reduce_ratio": 0.5,     # Reduce to 50% before events
    "atr_spike_multiplier":  3.0,     # ATR > 3× avg → spike
    "atr_window":            14,      # ATR period
    "atr_avg_window":        20,      # Days for baseline ATR average
    "extreme_vol_reduce":    0.25,    # Reduce to 25% during extreme vol
    "no_entry_during_spike": True,    # Block new entries during vol spike
}

# ── 2026 FOMC Schedule (projected) ──────────────────────────────
FOMC_DATES_2026 = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

# ── 2026 BOJ Schedule (projected) ───────────────────────────────
BOJ_DATES_2026 = [
    "2026-01-24", "2026-03-19", "2026-04-28", "2026-06-16",
    "2026-07-28", "2026-09-22", "2026-10-29", "2026-12-18",
]

# ── Geopolitical Risk Keywords ───────────────────────────────────
GEO_RISK_KEYWORDS: Set[str] = {
    "war", "invasion", "nuclear", "sanctions", "bank run", "crisis",
    "collapse", "hack", "exchange hack", "regulation ban", "sec", "lawsuit",
    "戦争", "制裁", "規制", "禁止", "ハック", "危機",
}


# ── Data Structures ─────────────────────────────────────────────

@dataclass
class EventRisk:
    """Represents a detected risk event."""
    event_type: str       # "fomc", "boj", "geo", "vol_spike"
    description: str
    detected_at: datetime
    event_date: Optional[datetime]
    severity: float       # 0-1 (1 = most severe)
    action: str           # "reduce", "block_entry", "cooldown"


@dataclass
class RiskState:
    """Current risk management state."""
    size_multiplier: float = 1.0       # Applied to position sizes
    allow_new_entry: bool = True        # Block entries during spikes
    active_events: List[EventRisk] = field(default_factory=list)
    cooldown_until: Optional[datetime] = None
    in_cooldown: bool = False


# ── Event Calendar ──────────────────────────────────────────────

def get_upcoming_events(
    now: Optional[datetime] = None,
    lookahead_hours: int = CONFIG["pre_event_hours"],
) -> List[EventRisk]:
    """Find upcoming FOMC/BOJ events within lookahead window.

    Args:
        now: Current time (defaults to JST now).
        lookahead_hours: How many hours ahead to scan.

    Returns:
        List of EventRisk objects for upcoming events.
    """
    if now is None:
        now = datetime.now(JST)

    events: List[EventRisk] = []
    horizon = now + timedelta(hours=lookahead_hours)

    all_events = [
        ("fomc", d) for d in FOMC_DATES_2026
    ] + [
        ("boj", d) for d in BOJ_DATES_2026
    ]

    for event_type, date_str in all_events:
        event_dt = datetime.fromisoformat(date_str).replace(
            hour=14, minute=0, tzinfo=JST
        )
        if now <= event_dt <= horizon:
            hours_until = (event_dt - now).total_seconds() / 3600
            severity = min(1.0, 1.0 - hours_until / lookahead_hours)
            events.append(EventRisk(
                event_type=event_type,
                description=f"{event_type.upper()} meeting on {date_str}",
                detected_at=now,
                event_date=event_dt,
                severity=severity,
                action="reduce",
            ))
            logger.info(
                "Upcoming %s in %.1f hours → reduce position",
                event_type.upper(), hours_until,
            )

    return events


def check_geo_risk(headline: str) -> Optional[EventRisk]:
    """Check a news headline for geopolitical risk keywords.

    Args:
        headline: News headline text.

    Returns:
        EventRisk if a keyword is found, else None.
    """
    headline_lower = headline.lower()
    for kw in GEO_RISK_KEYWORDS:
        if kw.lower() in headline_lower:
            logger.warning("Geopolitical risk keyword detected: '%s'", kw)
            return EventRisk(
                event_type="geo",
                description=f"Keyword '{kw}' in headline",
                detected_at=datetime.now(JST),
                event_date=None,
                severity=0.7,
                action="reduce",
            )
    return None


# ── Volatility Spike Detection ──────────────────────────────────

def detect_vol_spike(
    hourly_df: pd.DataFrame,
    config: Optional[Dict] = None,
) -> Optional[EventRisk]:
    """Detect ATR-based volatility spike.

    A spike is detected when the latest 1h ATR exceeds the
    20-day average ATR by the configured multiplier.

    Args:
        hourly_df: Hourly OHLCV DataFrame with high, low, close.
        config: Override config.

    Returns:
        EventRisk if spike detected, else None.
    """
    cfg = {**CONFIG, **(config or {})}
    if len(hourly_df) < cfg["atr_avg_window"] * 24 + cfg["atr_window"]:
        return None

    atr = ta.atr(
        hourly_df["high"], hourly_df["low"], hourly_df["close"],
        length=cfg["atr_window"],
    )
    if atr is None or atr.isna().all():
        return None

    current_atr = float(atr.iloc[-1])
    # 20-day average ATR (20 × 24 hourly candles)
    baseline_window = cfg["atr_avg_window"] * 24
    avg_atr = float(atr.iloc[-baseline_window:-cfg["atr_window"]].mean())

    if avg_atr <= 0:
        return None

    ratio = current_atr / avg_atr
    if ratio > cfg["atr_spike_multiplier"]:
        logger.warning(
            "Volatility spike: ATR %.0f / avg %.0f = %.1f× (threshold %.1f×)",
            current_atr, avg_atr, ratio, cfg["atr_spike_multiplier"],
        )
        return EventRisk(
            event_type="vol_spike",
            description=f"ATR spike {ratio:.1f}× average (ATR={current_atr:.0f})",
            detected_at=datetime.now(JST),
            event_date=None,
            severity=min(1.0, (ratio - cfg["atr_spike_multiplier"]) / 3 + 0.5),
            action="block_entry" if cfg["no_entry_during_spike"] else "reduce",
        )

    return None


# ── Risk Manager ────────────────────────────────────────────────

class EventRiskManager:
    """
    Layer 3: Event Risk Management.

    Evaluates upcoming events and current volatility to
    determine position size adjustments and entry restrictions.

    Args:
        config: Strategy configuration dict.
    """

    def __init__(self, config: Optional[Dict] = None) -> None:
        self.config = {**CONFIG, **(config or {})}
        self._state = RiskState()
        self._recent_events: List[EventRisk] = []

    @property
    def state(self) -> RiskState:
        return self._state

    def evaluate(
        self,
        hourly_df: Optional[pd.DataFrame] = None,
        headlines: Optional[List[str]] = None,
        now: Optional[datetime] = None,
    ) -> RiskState:
        """Evaluate all risk sources and return current risk state.

        Args:
            hourly_df: Hourly OHLCV for volatility calculation.
            headlines: Recent news headlines to scan.
            now: Current time (defaults to JST now).

        Returns:
            Updated RiskState with size_multiplier and allow_new_entry.
        """
        if now is None:
            now = datetime.now(JST)

        active_events: List[EventRisk] = []
        size_mult = 1.0
        allow_entry = True

        # ── Check cooldown
        if self._state.cooldown_until and now < self._state.cooldown_until:
            remaining = (self._state.cooldown_until - now).total_seconds() / 3600
            logger.debug("In cooldown for %.1f more hours", remaining)
            self._state.in_cooldown = True
            size_mult *= 0.75  # Reduced size during cooldown
        else:
            self._state.in_cooldown = False

        # ── Calendar events
        calendar_events = get_upcoming_events(now, self.config["pre_event_hours"])
        for ev in calendar_events:
            active_events.append(ev)
            mult = self.config["position_reduce_ratio"] + (
                1 - self.config["position_reduce_ratio"]
            ) * (1 - ev.severity)
            size_mult = min(size_mult, mult)
            logger.info(
                "Event risk [%s]: size_mult → %.2f", ev.description, size_mult
            )

        # ── Volatility spike
        if hourly_df is not None and not hourly_df.empty:
            spike = detect_vol_spike(hourly_df, self.config)
            if spike is not None:
                active_events.append(spike)
                if spike.action == "block_entry":
                    allow_entry = False
                    size_mult = min(size_mult, self.config["extreme_vol_reduce"])
                else:
                    size_mult = min(size_mult, self.config["position_reduce_ratio"])

        # ── Geopolitical risk
        for headline in (headlines or []):
            geo_risk = check_geo_risk(headline)
            if geo_risk:
                active_events.append(geo_risk)
                size_mult = min(size_mult, self.config["position_reduce_ratio"])

        # ── Update state
        self._state.size_multiplier = round(max(0.0, size_mult), 3)
        self._state.allow_new_entry = allow_entry
        self._state.active_events = active_events
        self._recent_events = active_events

        if active_events:
            logger.info(
                "EventRisk: size_mult=%.2f, allow_entry=%s, events=%d",
                size_mult, allow_entry, len(active_events),
            )

        return self._state

    def record_event_passed(self, event_type: str = "major") -> None:
        """Record that a major event passed, starting cooldown.

        Args:
            event_type: Event type label for logging.
        """
        cooldown_hours = self.config["post_event_cooldown_h"]
        self._state.cooldown_until = datetime.now(JST) + timedelta(hours=cooldown_hours)
        self._state.in_cooldown = True
        logger.info("Post-%s cooldown for %dh", event_type, cooldown_hours)

    def apply_to_size(self, size_btc: float) -> float:
        """Apply risk multiplier to a proposed position size.

        Args:
            size_btc: Proposed BTC position size.

        Returns:
            Adjusted BTC size.
        """
        return max(0.0, size_btc * self._state.size_multiplier)

    def summary(self) -> Dict:
        """Return current risk state summary."""
        return {
            "size_multiplier": self._state.size_multiplier,
            "allow_new_entry": self._state.allow_new_entry,
            "in_cooldown": self._state.in_cooldown,
            "cooldown_until": str(self._state.cooldown_until) if self._state.cooldown_until else None,
            "active_events": [
                {
                    "type": ev.event_type,
                    "description": ev.description,
                    "severity": ev.severity,
                    "action": ev.action,
                }
                for ev in self._state.active_events
            ],
        }


# ── Backtesting ────────────────────────────────────────────────

def backtest_event_filter(
    base_results: Dict,
    daily_df: pd.DataFrame,
    config: Optional[Dict] = None,
) -> Dict:
    """Apply event risk filter to existing backtest results.

    This wraps Layer 2 results and adjusts trade P&L
    based on event-period size reductions.

    Args:
        base_results: Output from strategy_layer2_trend.backtest_trend().
        daily_df: Daily OHLCV with ATR indicators.
        config: Override event risk config.

    Returns:
        Modified results dict with event-adjusted metrics.
    """
    cfg = {**CONFIG, **(config or {})}
    manager = EventRiskManager(cfg)
    trades = base_results.get("trade_log", [])
    capital = base_results.get("equity_curve", [1_000_000])[0]

    adjusted_trades = []
    equity = float(capital)
    peak = equity
    max_dd = 0.0
    equity_curve = [equity]

    for trade in trades:
        entry_ts = pd.Timestamp(trade.get("entry_time", "2026-01-01"))
        # Check risk state at trade entry
        state = manager.evaluate(now=entry_ts.to_pydatetime())
        # Adjust size by risk multiplier
        orig_size = float(trade["size_btc"])
        adj_size = manager.apply_to_size(orig_size)
        # Scale P&L by size adjustment
        scale = adj_size / orig_size if orig_size > 0 else 1.0
        adj_pnl = float(trade["pnl"]) * scale

        adjusted_trades.append({
            **trade,
            "adj_size_btc": adj_size,
            "adj_pnl": adj_pnl,
            "risk_multiplier": state.size_multiplier,
        })

        equity += adj_pnl
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        equity_curve.append(equity)

    n = len(adjusted_trades)
    wins = [t for t in adjusted_trades if t["adj_pnl"] > 0]
    total_pnl = sum(t["adj_pnl"] for t in adjusted_trades)
    win_pnl = [t["adj_pnl"] for t in wins]
    loss_pnl = [abs(t["adj_pnl"]) for t in adjusted_trades if t["adj_pnl"] <= 0]
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
        "total_return_pct": (equity - float(capital)) / float(capital) * 100,
        "max_drawdown_jpy": max_dd,
        "max_drawdown_pct": max_dd / peak * 100 if peak > 0 else 0.0,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "equity_curve": equity_curve,
        "trade_log": adjusted_trades,
    }
