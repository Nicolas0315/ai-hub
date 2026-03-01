"""
Anticipatory Action Engine — Predictive action before events occur.

Target: Interactive Environment 90% → 95% (closing the last 🟡 axis)

What was missing:
  RealtimeObserver detects events AFTER they happen.
  AdaptivePlanner reacts to detected events.
  But NO module PREDICTS what will happen and acts BEFORE it occurs.

  Key difference:
  - Reactive: event → detect → plan → act (latency = detection + planning + execution)
  - Anticipatory: predict → pre-act → event → verify prediction (latency ≈ 0)

Mechanisms:
  A1: Pattern Prediction — recurring event patterns (e.g., "every N steps, X happens")
  A2: Trajectory Extrapolation — metrics trending toward threshold → pre-empt
  A3: Causal Anticipation — if A causes B, and A just happened, prepare for B
  A4: Risk Preemption — high-variance metrics → defensive action before spike

Philosophical basis:
  - Predictive processing (Clark): brain as prediction engine
  - Model-based RL (Dyna/Dreamer): plan in a world model before acting
  - Youta: 予測符号化 — brain sees 0.5s ahead; we should too

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Constants ──
VERSION = "1.0.0"

# Prediction
MIN_HISTORY_FOR_PREDICTION = 5      # Minimum data points to make predictions
TREND_WINDOW = 10                   # Rolling window for trend analysis
PREDICTION_CONFIDENCE_FLOOR = 0.3   # Below this, don't act on predictions
PREDICTION_HORIZON_STEPS = 3        # How many steps ahead to predict

# Pattern detection
MIN_PATTERN_OCCURRENCES = 3         # Minimum repetitions to confirm pattern
PATTERN_TOLERANCE = 0.15            # How much variation a pattern tolerates

# Thresholds
CRITICAL_THRESHOLD = 0.95           # Approaching maximum — act now
WARNING_THRESHOLD = 0.85            # Getting close — prepare
RECOVERY_THRESHOLD = 0.20           # Approaching minimum — prepare recovery

# Persistence
ANTICIPATORY_STATE_FILE = "anticipatory_state.json"

# Causal chains
MAX_CAUSAL_CHAIN_LENGTH = 5         # Max hops in causal chain prediction
CAUSAL_CONFIDENCE_DECAY = 0.8       # Confidence decay per causal hop
STATE_CHANGE_THRESHOLD = 0.1        # Minimum change to trigger causal attention


@dataclass
class Prediction:
    """A prediction about future system state."""
    prediction_id: str
    metric: str
    predicted_value: float
    confidence: float               # 0.0-1.0
    horizon_steps: int              # How many steps ahead
    basis: str                      # Which mechanism made this prediction
    recommended_action: str
    urgency: float                  # 0.0-1.0
    created_at: float = 0.0
    verified: bool = False
    actual_value: Optional[float] = None

    @property
    def accuracy(self) -> Optional[float]:
        """How accurate was this prediction (after verification)."""
        if self.actual_value is None:
            return None
        if self.predicted_value == 0:
            return 1.0 if self.actual_value == 0 else 0.0
        error = abs(self.predicted_value - self.actual_value) / max(abs(self.predicted_value), 1e-9)
        return max(0.0, 1.0 - error)


@dataclass
class CausalRule:
    """A learned causal relationship between events."""
    cause_event: str
    effect_event: str
    delay_steps: int = 1
    confidence: float = 0.5
    observations: int = 0

    def observe(self, confirmed: bool) -> None:
        """Update confidence based on new observation."""
        self.observations += 1
        if confirmed:
            self.confidence = self.confidence + 0.1 * (1 - self.confidence)
        else:
            self.confidence = self.confidence * 0.9


@dataclass
class RecurringPattern:
    """A detected recurring pattern in metrics."""
    metric: str
    period: int                     # Steps between occurrences
    expected_value: float           # Expected value at peak
    confidence: float
    last_occurrence_step: int
    occurrences: int = 0


class AnticipatoryEngine:
    """
    Predicts future events and recommends preemptive actions.

    Usage:
        engine = AnticipatoryEngine()
        engine.observe({"score": 0.82, "errors": 3, "latency": 150})
        predictions = engine.predict()
        for p in predictions:
            if p.confidence > 0.5:
                execute(p.recommended_action)
    """

    def __init__(self, checkpoint_dir: Optional[str] = None):
        self._checkpoint_dir = Path(checkpoint_dir or ".katala_checkpoints")
        self._history: Dict[str, List[float]] = defaultdict(list)  # metric → values
        self._step = 0
        self._causal_rules: List[CausalRule] = []
        self._patterns: List[RecurringPattern] = []
        self._predictions: List[Prediction] = []
        self._prediction_accuracy: List[float] = []
        self._load_state()

    def observe(self, metrics: Dict[str, float]) -> None:
        """Record an observation (called each step/cycle)."""
        self._step += 1
        for key, value in metrics.items():
            self._history[key].append(value)
            # Keep bounded history
            if len(self._history[key]) > 200:
                self._history[key] = self._history[key][-200:]

        # Verify past predictions
        self._verify_predictions(metrics)

        # Learn patterns
        self._detect_patterns()

        # Learn causal rules
        self._update_causal_rules(metrics)

        self._save_state()

    def predict(self) -> List[Prediction]:
        """Generate predictions for the next few steps."""
        predictions: List[Prediction] = []
        now = time.time()

        # A1: Pattern-based predictions
        predictions.extend(self._predict_from_patterns())

        # A2: Trajectory extrapolation
        predictions.extend(self._predict_from_trends())

        # A3: Causal chain predictions
        predictions.extend(self._predict_from_causality())

        # A4: Risk preemption
        predictions.extend(self._predict_risk())

        # Filter by confidence
        predictions = [p for p in predictions if p.confidence >= PREDICTION_CONFIDENCE_FLOOR]

        # Assign IDs and timestamps
        for p in predictions:
            p.created_at = now
            p.prediction_id = hashlib.md5(
                f"{p.metric}_{p.predicted_value}_{p.basis}_{self._step}".encode()
            ).hexdigest()[:10]

        # Store for later verification
        self._predictions.extend(predictions)

        # Sort by urgency × confidence
        predictions.sort(key=lambda p: p.urgency * p.confidence, reverse=True)
        return predictions

    # ── A1: Pattern-Based Prediction ──

    def _predict_from_patterns(self) -> List[Prediction]:
        """Predict based on detected recurring patterns."""
        predictions = []

        for pattern in self._patterns:
            if pattern.confidence < PREDICTION_CONFIDENCE_FLOOR:
                continue

            steps_since = self._step - pattern.last_occurrence_step
            steps_until = pattern.period - (steps_since % pattern.period)

            if steps_until <= PREDICTION_HORIZON_STEPS:
                predictions.append(Prediction(
                    prediction_id="",
                    metric=pattern.metric,
                    predicted_value=pattern.expected_value,
                    confidence=pattern.confidence,
                    horizon_steps=steps_until,
                    basis="pattern",
                    recommended_action=self._recommend_for_pattern(pattern),
                    urgency=1.0 - (steps_until / max(PREDICTION_HORIZON_STEPS, 1)),
                ))

        return predictions

    # ── A2: Trend Extrapolation ──

    def _predict_from_trends(self) -> List[Prediction]:
        """Extrapolate current trends to predict threshold crossings."""
        predictions = []

        for metric, values in self._history.items():
            if len(values) < MIN_HISTORY_FOR_PREDICTION:
                continue

            window = values[-TREND_WINDOW:]
            if len(window) < 3:
                continue

            # Linear regression (simple: slope of last N points)
            n = len(window)
            x_mean = (n - 1) / 2
            y_mean = sum(window) / n
            numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(window))
            denominator = sum((i - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                continue

            slope = numerator / denominator
            current = window[-1]

            # Predict forward
            for step in range(1, PREDICTION_HORIZON_STEPS + 1):
                predicted = current + slope * step

                # Check threshold crossings
                if current < CRITICAL_THRESHOLD <= predicted:
                    predictions.append(Prediction(
                        prediction_id="",
                        metric=metric,
                        predicted_value=predicted,
                        confidence=self._trend_confidence(values),
                        horizon_steps=step,
                        basis="trend_extrapolation",
                        recommended_action=f"Prepare for {metric} reaching critical ({predicted:.3f})",
                        urgency=0.8,
                    ))
                elif current > RECOVERY_THRESHOLD >= predicted:
                    predictions.append(Prediction(
                        prediction_id="",
                        metric=metric,
                        predicted_value=predicted,
                        confidence=self._trend_confidence(values),
                        horizon_steps=step,
                        basis="trend_extrapolation",
                        recommended_action=f"Prevent {metric} drop to {predicted:.3f} — initiate recovery",
                        urgency=0.9,
                    ))

        return predictions

    def _trend_confidence(self, values: List[float]) -> float:
        """Confidence in trend prediction based on R² of recent values."""
        if len(values) < 3:
            return 0.3
        window = values[-TREND_WINDOW:]
        n = len(window)
        y_mean = sum(window) / n
        ss_tot = sum((v - y_mean) ** 2 for v in window)
        if ss_tot == 0:
            return 0.5

        # Simple linear fit
        x_mean = (n - 1) / 2
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(window))
        den = sum((i - x_mean) ** 2 for i in range(n))
        if den == 0:
            return 0.3
        slope = num / den
        intercept = y_mean - slope * x_mean

        ss_res = sum((v - (intercept + slope * i)) ** 2 for i, v in enumerate(window))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        return max(0.3, min(0.95, r_squared))

    # ── A3: Causal Chain Prediction ──

    def _predict_from_causality(self) -> List[Prediction]:
        """If A causes B (with delay), and A just happened, predict B."""
        predictions = []

        for rule in self._causal_rules:
            if rule.confidence < PREDICTION_CONFIDENCE_FLOOR:
                continue

            cause_values = self._history.get(rule.cause_event, [])
            if len(cause_values) < 2:
                continue

            # Check if cause event just changed significantly
            if len(cause_values) >= 2:
                delta = abs(cause_values[-1] - cause_values[-2])
                if delta > STATE_CHANGE_THRESHOLD:
                    # Predict effect
                    effect_values = self._history.get(rule.effect_event, [])
                    predicted = effect_values[-1] if effect_values else 0.5

                    # Direction: if cause went up, effect likely goes up (or down if inverse)
                    if len(effect_values) >= 2 and len(cause_values) >= 2:
                        cause_dir = cause_values[-1] - cause_values[-2]
                        # Use historical correlation direction
                        predicted += cause_dir * 0.5

                    predictions.append(Prediction(
                        prediction_id="",
                        metric=rule.effect_event,
                        predicted_value=max(0, min(1, predicted)),
                        confidence=rule.confidence * CAUSAL_CONFIDENCE_DECAY,
                        horizon_steps=rule.delay_steps,
                        basis="causal_chain",
                        recommended_action=f"Prepare for {rule.effect_event} change (caused by {rule.cause_event})",
                        urgency=0.6,
                    ))

        return predictions

    # ── A4: Risk Preemption ──

    def _predict_risk(self) -> List[Prediction]:
        """Detect high-variance metrics and preemptively guard."""
        predictions = []

        for metric, values in self._history.items():
            if len(values) < MIN_HISTORY_FOR_PREDICTION:
                continue

            window = values[-TREND_WINDOW:]
            mean = sum(window) / len(window)
            variance = sum((v - mean) ** 2 for v in window) / len(window)
            std = variance ** 0.5

            # High variance + approaching threshold = high risk
            current = window[-1]

            if std > 0.1 and current > WARNING_THRESHOLD:
                # Could spike above critical
                worst_case = current + 2 * std
                predictions.append(Prediction(
                    prediction_id="",
                    metric=metric,
                    predicted_value=worst_case,
                    confidence=0.4,  # Low confidence but worth watching
                    horizon_steps=2,
                    basis="risk_preemption",
                    recommended_action=f"High variance in {metric} (σ={std:.3f}) near threshold — add guard",
                    urgency=0.5,
                ))

            if std > 0.1 and current < RECOVERY_THRESHOLD + 2 * std:
                # Could drop below recovery
                worst_case = current - 2 * std
                predictions.append(Prediction(
                    prediction_id="",
                    metric=metric,
                    predicted_value=worst_case,
                    confidence=0.4,
                    horizon_steps=2,
                    basis="risk_preemption",
                    recommended_action=f"High variance in {metric} (σ={std:.3f}) near floor — prepare recovery",
                    urgency=0.6,
                ))

        return predictions

    # ── Pattern Detection ──

    def _detect_patterns(self) -> None:
        """Detect recurring patterns in metric history."""
        for metric, values in self._history.items():
            if len(values) < MIN_PATTERN_OCCURRENCES * 3:
                continue

            # Simple periodicity detection via autocorrelation
            max_period = min(len(values) // 3, 50)
            best_period = 0
            best_corr = 0.0

            for period in range(2, max_period + 1):
                corr = self._autocorrelation(values, period)
                if corr > best_corr and corr > 0.5:
                    best_corr = corr
                    best_period = period

            if best_period > 0 and best_corr > 0.5:
                # Found a pattern
                existing = next((p for p in self._patterns if p.metric == metric), None)
                if existing:
                    existing.period = best_period
                    existing.confidence = best_corr
                    existing.last_occurrence_step = self._step
                    existing.occurrences += 1
                else:
                    self._patterns.append(RecurringPattern(
                        metric=metric,
                        period=best_period,
                        expected_value=max(values[-best_period:]),
                        confidence=best_corr,
                        last_occurrence_step=self._step,
                        occurrences=1,
                    ))

    def _autocorrelation(self, values: List[float], lag: int) -> float:
        """Simple autocorrelation at given lag."""
        n = len(values)
        if n < lag + 3:
            return 0.0

        mean = sum(values) / n
        var = sum((v - mean) ** 2 for v in values) / n
        if var == 0:
            return 0.0

        cov = sum(
            (values[i] - mean) * (values[i + lag] - mean)
            for i in range(n - lag)
        ) / (n - lag)

        return cov / var

    # ── Causal Rule Learning ──

    def _update_causal_rules(self, metrics: Dict[str, float]) -> None:
        """Learn causal relationships from co-occurring changes."""
        if self._step < 3:
            return

        keys = list(metrics.keys())
        for i, cause_key in enumerate(keys):
            cause_vals = self._history.get(cause_key, [])
            if len(cause_vals) < 3:
                continue

            cause_changed = abs(cause_vals[-1] - cause_vals[-2]) > STATE_CHANGE_THRESHOLD

            if cause_changed:
                for effect_key in keys[i + 1:]:
                    effect_vals = self._history.get(effect_key, [])
                    if len(effect_vals) < 3:
                        continue

                    # Check if effect changed 1 step after cause
                    effect_changed = abs(effect_vals[-1] - effect_vals[-2]) > STATE_CHANGE_THRESHOLD

                    # Find or create rule
                    existing = next(
                        (r for r in self._causal_rules
                         if r.cause_event == cause_key and r.effect_event == effect_key),
                        None,
                    )
                    if existing:
                        existing.observe(effect_changed)
                    elif effect_changed:
                        self._causal_rules.append(CausalRule(
                            cause_event=cause_key,
                            effect_event=effect_key,
                            delay_steps=1,
                            confidence=0.3,
                            observations=1,
                        ))

        # Prune low-confidence rules
        self._causal_rules = [
            r for r in self._causal_rules
            if r.confidence > 0.1 or r.observations < 5
        ]

    # ── Prediction Verification ──

    def _verify_predictions(self, metrics: Dict[str, float]) -> None:
        """Check past predictions against actual values."""
        for pred in self._predictions:
            if pred.verified:
                continue
            if pred.metric in metrics:
                steps_elapsed = self._step - pred.created_at  # approximate
                if pred.horizon_steps <= 1:  # Due for verification
                    pred.verified = True
                    pred.actual_value = metrics[pred.metric]
                    acc = pred.accuracy
                    if acc is not None:
                        self._prediction_accuracy.append(acc)

        # Trim
        if len(self._prediction_accuracy) > 100:
            self._prediction_accuracy = self._prediction_accuracy[-100:]

    # ── Utility ──

    def _recommend_for_pattern(self, pattern: RecurringPattern) -> str:
        """Generate action recommendation for a predicted pattern."""
        return f"Recurring pattern in {pattern.metric} (period={pattern.period}): prepare for value ~{pattern.expected_value:.3f}"

    @property
    def overall_accuracy(self) -> float:
        """Average prediction accuracy."""
        if not self._prediction_accuracy:
            return 0.5
        return sum(self._prediction_accuracy) / len(self._prediction_accuracy)

    # ── Persistence ──

    def _save_state(self) -> None:
        """Save state for cross-session persistence."""
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "step": self._step,
            "history": {k: v[-50:] for k, v in self._history.items()},
            "causal_rules": [asdict(r) for r in self._causal_rules],
            "patterns": [asdict(p) for p in self._patterns],
            "prediction_accuracy": self._prediction_accuracy[-50:],
            "saved_at": time.time(),
        }
        path = self._checkpoint_dir / ANTICIPATORY_STATE_FILE
        path.write_text(json.dumps(state, indent=2, default=str))

    def _load_state(self) -> None:
        """Load previous state."""
        path = self._checkpoint_dir / ANTICIPATORY_STATE_FILE
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._step = data.get("step", 0)
            for k, v in data.get("history", {}).items():
                self._history[k] = v
            self._causal_rules = [CausalRule(**r) for r in data.get("causal_rules", [])]
            self._patterns = [RecurringPattern(**p) for p in data.get("patterns", [])]
            self._prediction_accuracy = data.get("prediction_accuracy", [])
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # ── Module Identity ──

    def get_status(self) -> Dict[str, Any]:
        """Module status for KCS diagnosis."""
        return {
            "module": "anticipatory_engine",
            "version": VERSION,
            "step": self._step,
            "tracked_metrics": len(self._history),
            "causal_rules": len(self._causal_rules),
            "detected_patterns": len(self._patterns),
            "prediction_accuracy": f"{self.overall_accuracy:.1%}",
            "total_predictions": len(self._predictions),
        }


def get_status() -> Dict[str, Any]:
    """Module-level status for KCS."""
    return {
        "module": "anticipatory_engine",
        "version": VERSION,
        "targets": {
            "interactive_environment": "90% → 95%",
            "mechanism": "Predictive action (pattern/trend/causal/risk) before events occur",
        },
    }
