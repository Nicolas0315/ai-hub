"""
katala_trading — BitFlyer BTC Trading System with Katala KS/KCS Integration

3-Layer Trading System:
  L1: SFD (Swap for Difference) Arbitrage — bitFlyer FX/Spot divergence
  L2: Trend Following — 200-day MA + RSI + volume
  L3: Event Risk Management — FOMC/BOJ calendar + volatility spikes

Katala Integration:
  KS42c: Claim verification for trading hypotheses
  KCS-2a: Reverse-inference of design intent
  KS40b: Multi-indicator consistency cross-check

Design: Nicolas Ogoshi / Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
"""

VERSION = "0.1.0"
__version__ = VERSION
__all__ = [
    "bitflyer_client",
    "data_collector",
    "strategy_layer1_sfd",
    "strategy_layer2_trend",
    "strategy_layer3_event",
    "backtest_engine",
    "ks_trading_bridge",
    "trading_bot",
]
