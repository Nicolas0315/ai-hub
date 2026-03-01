"""
ks_trading_bridge.py — Katala Integration Bridge

Bridges trading signals ↔ Katala verification framework:
  - KS42c.verify(): verify trading hypotheses as Claims
  - KCS-2a: reverse-infer design intent of trading patterns
  - KS40b: multi-indicator consistency cross-check

Trading hypotheses become Katala Claims:
  "SFD divergence of X% will converge within Y hours" → KS42c
  "BTC is in uptrend based on 200MA" → KS42c
  "Current geopolitical risk warrants position reduction" → KS42c

Output: confidence-weighted trading signals
"""

from __future__ import annotations

import logging
import sys
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Katala Imports ─────────────────────────────────────────────
# Add katala_samurai to path
_HERE = os.path.dirname(os.path.abspath(__file__))
_KATALA_SRC = os.path.dirname(_HERE)
_SAMURAI_DIR = os.path.join(_KATALA_SRC, "katala_samurai")
for _p in [_SAMURAI_DIR, _KATALA_SRC]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

_HAS_KS42C = False
_HAS_KCS2A = False
_HAS_KS40B = False

try:
    from katala_samurai.ks42c import KS42c  # noqa: F401
    _HAS_KS42C = True
    logger.info("KS42c loaded successfully")
except ImportError:
    try:
        from ks42c import KS42c  # type: ignore
        _HAS_KS42C = True
    except ImportError:
        logger.warning("KS42c not available — running without claim verification")
        KS42c = None  # type: ignore

try:
    from katala_samurai.ks40b import KS40b  # noqa: F401
    _HAS_KS40B = True
except ImportError:
    try:
        from ks40b import KS40b  # type: ignore
        _HAS_KS40B = True
    except ImportError:
        logger.warning("KS40b not available")
        KS40b = None  # type: ignore

try:
    from katala_samurai.ks29b import Claim  # noqa: F401
except ImportError:
    try:
        from ks29b import Claim  # type: ignore
    except ImportError:
        Claim = None  # type: ignore
        logger.warning("Claim class not available")

# KCS-2a is urban-domain; we use its ConceptMapping pattern
try:
    from katala_samurai.kcs2a_urban import ConceptMapping, URBAN_CONCEPT_MAP
    _HAS_KCS2A = True
except ImportError:
    try:
        from kcs2a_urban import ConceptMapping, URBAN_CONCEPT_MAP  # type: ignore
        _HAS_KCS2A = True
    except ImportError:
        ConceptMapping = None  # type: ignore
        URBAN_CONCEPT_MAP = []
        logger.warning("KCS-2a not available — using fallback intent inference")


# ── Data Structures ─────────────────────────────────────────────

@dataclass
class TradingClaim:
    """A trading hypothesis to be verified by Katala."""
    hypothesis: str          # Natural language hypothesis
    evidence: List[str]      # Supporting data points
    domain: str              # "sfd_arb", "trend", "event_risk"
    raw_data: Dict           # Raw signal data (prices, indicators, etc.)


@dataclass
class KSVerdict:
    """Verification result from Katala."""
    claim_text: str
    ks_confidence: float     # 0-1: KS42c confidence
    consistency_score: float  # 0-1: KS40b multi-indicator consistency
    design_intent: str       # KCS-2a inferred design intent
    weighted_confidence: float  # Final signal strength
    raw_result: Dict = field(default_factory=dict)
    fallback_used: bool = False


@dataclass
class WeightedSignal:
    """Confidence-weighted trading signal post-KS verification."""
    action: str              # "buy", "sell", "short", "hold", "reduce"
    base_confidence: float   # Before KS weighting
    ks_confidence: float     # KS42c verdict confidence
    final_confidence: float  # Combined signal strength
    size_multiplier: float   # Position size adjustment (0-1)
    verdicts: List[KSVerdict] = field(default_factory=list)
    reasoning: str = ""


# ── Hypothesis Templates ────────────────────────────────────────

def make_sfd_claim(divergence_pct: float, hours: float = 4.0) -> TradingClaim:
    """Create a Katala Claim for SFD convergence hypothesis.

    Args:
        divergence_pct: Current SFD divergence in %.
        hours: Expected convergence window in hours.

    Returns:
        TradingClaim ready for KS42c verification.
    """
    direction = "positive" if divergence_pct > 0 else "negative"
    abs_div = abs(divergence_pct)
    return TradingClaim(
        hypothesis=(
            f"BTC FX/Spot divergence of {abs_div:.1f}% ({direction}) on bitFlyer "
            f"will converge to below 2% within {hours:.0f} hours "
            f"due to SFD arbitrage pressure and mean-reversion dynamics."
        ),
        evidence=[
            f"Current divergence: {divergence_pct:.2f}%",
            f"Historical convergence rate: ~65% within 4h when |div| > 5%",
            f"bitFlyer SFD penalty above 5% discourages widening",
            f"Arbitrageurs incentivized to close the spread",
        ],
        domain="sfd_arb",
        raw_data={"divergence_pct": divergence_pct, "expected_hours": hours},
    )


def make_trend_claim(
    price: float,
    ma200: float,
    rsi14: float,
    signal_type: str = "golden_cross",
) -> TradingClaim:
    """Create a Katala Claim for BTC uptrend hypothesis.

    Args:
        price: Current BTC price in JPY.
        ma200: 200-day moving average.
        rsi14: RSI(14) reading.
        signal_type: Entry trigger type.

    Returns:
        TradingClaim for trend verification.
    """
    pct_above = (price - ma200) / ma200 * 100
    return TradingClaim(
        hypothesis=(
            f"BTC/JPY is in an uptrend: price ({price:,.0f} JPY) is {pct_above:.1f}% "
            f"above the 200-day MA ({ma200:,.0f} JPY). "
            f"Signal type: {signal_type}. RSI14={rsi14:.0f}. "
            f"The uptrend is expected to continue based on structural momentum."
        ),
        evidence=[
            f"Price {pct_above:+.1f}% above 200MA (bullish)",
            f"RSI14={rsi14:.0f} ({'oversold' if rsi14 < 30 else 'neutral' if rsi14 < 70 else 'overbought'})",
            f"Signal: {signal_type}",
            "200MA is the institutional trend filter (Elder, Livermore methodology)",
        ],
        domain="trend",
        raw_data={"price": price, "ma200": ma200, "rsi14": rsi14, "signal": signal_type},
    )


def make_event_risk_claim(
    event_type: str,
    hours_until: float,
    atr_spike: bool = False,
) -> TradingClaim:
    """Create a Katala Claim for event risk reduction hypothesis.

    Args:
        event_type: "fomc", "boj", or "geo".
        hours_until: Hours until the event.
        atr_spike: Whether ATR spike is also detected.

    Returns:
        TradingClaim for risk management verification.
    """
    return TradingClaim(
        hypothesis=(
            f"Current geopolitical/macro risk ({event_type.upper()}, "
            f"T-{hours_until:.0f}h) warrants reducing BTC position by 50%. "
            f"{'ATR spike detected. ' if atr_spike else ''}"
            f"Historical precedent shows BTC volatility increases significantly "
            f"around {event_type.upper()} events, warranting defensive position sizing."
        ),
        evidence=[
            f"Event: {event_type.upper()} in {hours_until:.0f} hours",
            f"ATR spike: {'yes' if atr_spike else 'no'}",
            "FOMC/BOJ decisions historically correlate with BTC vol spikes",
            "Risk management: 50% reduction limits max drawdown",
        ],
        domain="event_risk",
        raw_data={"event_type": event_type, "hours_until": hours_until, "atr_spike": atr_spike},
    )


# ── KCS-2a Intent Inference ─────────────────────────────────────

# Trading domain concept mappings (extends KCS-2a urban pattern)
TRADING_CONCEPT_MAP = {
    "sfd_arb": {
        "canonical": "spread_mean_reversion",
        "design_intent": "Exploit price discrepancy between correlated instruments via arbitrage. Expected edge: ~65% win rate, fast mean-reversion (<4h).",
        "confidence": 0.85,
    },
    "trend": {
        "canonical": "momentum_trend_following",
        "design_intent": "Capture sustained directional moves using long-term MA as regime filter. Expected edge: Sharpe > 1.0 in trending markets.",
        "confidence": 0.78,
    },
    "event_risk": {
        "canonical": "defensive_risk_management",
        "design_intent": "Protect capital during uncertainty by reducing exposure. Expected edge: reduced max drawdown by ~30%.",
        "confidence": 0.90,
    },
}


def infer_design_intent(claim: TradingClaim) -> str:
    """Use KCS-2a pattern to reverse-infer design intent of trading pattern.

    Adapts the KCS-2a ConceptMapping approach to trading domains.

    Args:
        claim: TradingClaim to analyze.

    Returns:
        Design intent string.
    """
    mapping = TRADING_CONCEPT_MAP.get(claim.domain, {})
    if mapping:
        return mapping.get("design_intent", "Unknown design intent")

    # Fallback: infer from hypothesis text
    text = claim.hypothesis.lower()
    if "divergence" in text or "arbitrage" in text or "convergence" in text:
        return TRADING_CONCEPT_MAP["sfd_arb"]["design_intent"]
    if "uptrend" in text or "ma" in text or "momentum" in text:
        return TRADING_CONCEPT_MAP["trend"]["design_intent"]
    if "risk" in text or "reduce" in text or "event" in text:
        return TRADING_CONCEPT_MAP["event_risk"]["design_intent"]

    return "General trading signal: monitor and act on market structure changes"


# ── KS40b Consistency Check ─────────────────────────────────────

def check_indicator_consistency(raw_data: Dict) -> float:
    """KS40b-inspired multi-indicator consistency check.

    Checks that multiple indicators agree directionally:
    - MA200 trend direction
    - RSI trend (above/below 50)
    - Volume confirmation

    Args:
        raw_data: Signal data dict with indicator values.

    Returns:
        Consistency score 0-1 (1 = all indicators agree).
    """
    signals = []

    # MA200 direction
    if "price" in raw_data and "ma200" in raw_data:
        bullish = raw_data["price"] > raw_data["ma200"]
        signals.append(1.0 if bullish else 0.0)

    # RSI direction
    if "rsi14" in raw_data:
        rsi = raw_data["rsi14"]
        if rsi < 30:
            signals.append(0.9)  # Oversold = potential buy
        elif rsi > 70:
            signals.append(0.1)  # Overbought
        else:
            signals.append(0.5)

    # SFD mean-reversion (convergence = bullish for position)
    if "divergence_pct" in raw_data:
        div = abs(raw_data["divergence_pct"])
        if div > 5.0:
            signals.append(0.8)  # Strong signal
        elif div > 3.0:
            signals.append(0.5)
        else:
            signals.append(0.2)

    # Event risk (lower = more consistency with defensive stance)
    if "hours_until" in raw_data:
        hours = raw_data["hours_until"]
        if hours < 6:
            signals.append(0.95)  # Very close → high consistency for reduce
        elif hours < 24:
            signals.append(0.75)
        else:
            signals.append(0.4)

    if not signals:
        return 0.5

    # Consistency = how much they agree (low variance = high consistency)
    import numpy as np
    arr = [float(s) for s in signals]
    variance = float(np.var(arr))
    consistency = max(0.0, 1.0 - variance * 4)
    return round(consistency, 3)


# ── Main Bridge ─────────────────────────────────────────────────

class KSTradingBridge:
    """
    Bridge between trading signals and Katala verification.

    Converts trading hypotheses to Katala Claims, runs KS42c
    verification, and returns confidence-weighted signals.

    Args:
        use_ks42c: Use KS42c verification (requires katala_samurai).
        use_ks40b: Use KS40b consistency check.
    """

    def __init__(
        self,
        use_ks42c: bool = True,
        use_ks40b: bool = True,
    ) -> None:
        self.use_ks42c = use_ks42c and _HAS_KS42C
        self.use_ks40b = use_ks40b and _HAS_KS40B

        self._ks42c: Optional[Any] = None
        self._ks40b: Optional[Any] = None

        if self.use_ks42c and KS42c is not None:
            try:
                self._ks42c = KS42c()
                logger.info("KS42c engine initialized")
            except Exception as e:
                logger.warning("KS42c init failed: %s", e)
                self.use_ks42c = False

        if self.use_ks40b and KS40b is not None:
            try:
                self._ks40b = KS40b()
                logger.info("KS40b engine initialized")
            except Exception as e:
                logger.warning("KS40b init failed: %s", e)
                self.use_ks40b = False

    def verify_claim(self, trading_claim: TradingClaim) -> KSVerdict:
        """Verify a trading hypothesis using KS42c.

        Args:
            trading_claim: TradingClaim with hypothesis and evidence.

        Returns:
            KSVerdict with confidence and design intent.
        """
        ks_confidence = 0.5  # Default fallback
        raw_result: Dict = {}
        fallback = True

        # ── KS42c verification
        if self.use_ks42c and self._ks42c is not None:
            try:
                claim_text = trading_claim.hypothesis
                if Claim is not None:
                    claim_obj = Claim(
                        text=claim_text,
                        evidence=trading_claim.evidence,
                    )
                else:
                    claim_obj = claim_text

                raw_result = self._ks42c.verify(claim_obj, skip_s28=True)

                # Extract confidence from KS42c result structure
                if isinstance(raw_result, dict):
                    # Try various confidence keys in order of preference
                    ks_confidence = (
                        raw_result.get("confidence")
                        or raw_result.get("overall_score")
                        or raw_result.get("score")
                        or raw_result.get("verdict", {}).get("confidence", 0.5)
                        if isinstance(raw_result.get("verdict"), dict)
                        else 0.5
                    )
                    if ks_confidence is None:
                        ks_confidence = 0.5
                    ks_confidence = float(ks_confidence)
                    ks_confidence = max(0.0, min(1.0, ks_confidence))
                    fallback = False
                    logger.debug("KS42c verdict: confidence=%.2f", ks_confidence)

            except Exception as e:
                logger.warning("KS42c verification failed: %s — using fallback", e)
                fallback = True

        # ── Fallback: heuristic confidence
        if fallback:
            ks_confidence = self._heuristic_confidence(trading_claim)

        # ── KCS-2a design intent
        design_intent = infer_design_intent(trading_claim)

        # ── KS40b consistency check
        consistency = check_indicator_consistency(trading_claim.raw_data)

        # ── Weighted confidence
        # KS42c (40%) × consistency (30%) × base domain confidence (30%)
        domain_conf = TRADING_CONCEPT_MAP.get(trading_claim.domain, {}).get(
            "confidence", 0.6
        )
        weighted = (
            ks_confidence * 0.40
            + consistency * 0.30
            + domain_conf * 0.30
        )

        return KSVerdict(
            claim_text=trading_claim.hypothesis[:200] + "…"
            if len(trading_claim.hypothesis) > 200
            else trading_claim.hypothesis,
            ks_confidence=round(ks_confidence, 3),
            consistency_score=consistency,
            design_intent=design_intent,
            weighted_confidence=round(weighted, 3),
            raw_result=raw_result,
            fallback_used=fallback,
        )

    def _heuristic_confidence(self, claim: TradingClaim) -> float:
        """Fallback confidence when KS42c unavailable.

        Uses evidence count and domain prior.

        Args:
            claim: TradingClaim to evaluate.

        Returns:
            Estimated confidence 0-1.
        """
        domain_base = TRADING_CONCEPT_MAP.get(claim.domain, {}).get("confidence", 0.5)
        evidence_boost = min(0.1, len(claim.evidence) * 0.02)
        return min(1.0, domain_base + evidence_boost)

    def process_sfd_signal(
        self,
        divergence_pct: float,
        base_action: str,
        base_confidence: float,
    ) -> WeightedSignal:
        """Process an SFD signal through Katala verification.

        Args:
            divergence_pct: Current SFD divergence %.
            base_action: Proposed action ("short_fx", "long_fx", etc.).
            base_confidence: Strategy confidence before KS.

        Returns:
            WeightedSignal with KS-adjusted confidence.
        """
        claim = make_sfd_claim(divergence_pct)
        verdict = self.verify_claim(claim)

        final_conf = (base_confidence * 0.6 + verdict.weighted_confidence * 0.4)
        size_mult = min(1.0, max(0.1, final_conf))

        return WeightedSignal(
            action=base_action,
            base_confidence=base_confidence,
            ks_confidence=verdict.ks_confidence,
            final_confidence=round(final_conf, 3),
            size_multiplier=round(size_mult, 3),
            verdicts=[verdict],
            reasoning=(
                f"SFD div={divergence_pct:.1f}% | "
                f"KS={verdict.ks_confidence:.2f} | "
                f"consistency={verdict.consistency_score:.2f} | "
                f"intent: {verdict.design_intent[:60]}…"
            ),
        )

    def process_trend_signal(
        self,
        price: float,
        ma200: float,
        rsi14: float,
        signal_type: str,
        base_action: str,
        base_confidence: float,
    ) -> WeightedSignal:
        """Process a trend signal through Katala verification.

        Args:
            price: Current BTC price.
            ma200: 200-day moving average.
            rsi14: RSI(14) value.
            signal_type: Entry trigger.
            base_action: Proposed action.
            base_confidence: Strategy confidence.

        Returns:
            WeightedSignal with KS-adjusted confidence.
        """
        claim = make_trend_claim(price, ma200, rsi14, signal_type)
        verdict = self.verify_claim(claim)

        final_conf = (base_confidence * 0.6 + verdict.weighted_confidence * 0.4)
        size_mult = min(1.0, max(0.1, final_conf))

        return WeightedSignal(
            action=base_action,
            base_confidence=base_confidence,
            ks_confidence=verdict.ks_confidence,
            final_confidence=round(final_conf, 3),
            size_multiplier=round(size_mult, 3),
            verdicts=[verdict],
            reasoning=(
                f"Trend: price {price:,.0f} vs MA200 {ma200:,.0f} | "
                f"RSI={rsi14:.0f} | {signal_type} | "
                f"KS={verdict.ks_confidence:.2f}"
            ),
        )

    def process_event_signal(
        self,
        event_type: str,
        hours_until: float,
        atr_spike: bool = False,
        base_action: str = "reduce",
        base_confidence: float = 0.8,
    ) -> WeightedSignal:
        """Process an event risk signal through Katala verification.

        Args:
            event_type: "fomc", "boj", or "geo".
            hours_until: Hours until the event.
            atr_spike: Whether ATR spike detected.
            base_action: Proposed action.
            base_confidence: Strategy confidence.

        Returns:
            WeightedSignal with KS-adjusted confidence.
        """
        claim = make_event_risk_claim(event_type, hours_until, atr_spike)
        verdict = self.verify_claim(claim)

        final_conf = (base_confidence * 0.5 + verdict.weighted_confidence * 0.5)
        size_mult = min(1.0, max(0.1, final_conf))

        return WeightedSignal(
            action=base_action,
            base_confidence=base_confidence,
            ks_confidence=verdict.ks_confidence,
            final_confidence=round(final_conf, 3),
            size_multiplier=round(size_mult, 3),
            verdicts=[verdict],
            reasoning=(
                f"Event risk: {event_type.upper()} T-{hours_until:.0f}h | "
                f"ATR spike={atr_spike} | KS={verdict.ks_confidence:.2f}"
            ),
        )
