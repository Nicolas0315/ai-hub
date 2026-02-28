"""
Predictive Coding — Friston-inspired prediction-error processing.

Brain predicts input, then only processes the PREDICTION ERROR.
If prediction matches reality, skip deeper processing.

1) Planner generates prediction (verdict + confidence range)
2) Core verify runs
3) Only the DELTA between prediction and reality drives metacognition
4) If delta < threshold → skip expensive layers

Kandel/Friston: hierarchical predictive processing, precision-weighted prediction errors.

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, Tuple, Optional
from collections import defaultdict
import math


class PredictiveEngine:
    """Generate predictions and compute prediction errors."""
    
    def __init__(self, surprise_threshold: float = 0.15):
        self._threshold = surprise_threshold
        self._prediction_history = defaultdict(list)  # type → past outcomes
        self._precision_weights = defaultdict(lambda: 1.0)  # type → precision
    
    def predict(self, claim_type: str, difficulty: str, plan: Dict) -> Dict[str, Any]:
        """Generate prediction BEFORE verification runs."""
        # Base prediction from plan
        expected = plan.get("criteria", {}).get("expected_range", [0.3, 0.7])
        base_conf = (expected[0] + expected[1]) / 2
        
        # Refine with history (if we've seen this type before)
        history = self._prediction_history.get(claim_type, [])
        if len(history) >= 2:
            avg_actual = sum(h["actual"] for h in history[-5:]) / min(len(history), 5)
            avg_error = sum(h["error"] for h in history[-5:]) / min(len(history), 5)
            # Correct prediction toward historical mean
            base_conf = base_conf * 0.6 + avg_actual * 0.4
            # Tighten range based on variance
            if len(history) >= 3:
                variance = sum((h["actual"] - avg_actual)**2 for h in history[-5:]) / min(len(history), 5)
                std = math.sqrt(variance)
                expected = [max(0, base_conf - 2*std), min(1, base_conf + 2*std)]
        
        # Predict verdict
        if base_conf > 0.65:
            predicted_verdict = "VERIFIED"
        elif base_conf < 0.35:
            predicted_verdict = "UNVERIFIED"
        else:
            predicted_verdict = "EXPLORING"
        
        precision = self._precision_weights[claim_type]
        
        return {
            "predicted_confidence": round(base_conf, 4),
            "predicted_verdict": predicted_verdict,
            "predicted_range": [round(expected[0], 4), round(expected[1], 4)],
            "precision": round(precision, 4),
            "based_on_history": len(history),
        }
    
    def compute_error(self, prediction: Dict, actual_confidence: float,
                      actual_verdict: str) -> Dict[str, Any]:
        """Compute prediction error — only this drives metacognition."""
        predicted_conf = prediction["predicted_confidence"]
        error = actual_confidence - predicted_conf
        abs_error = abs(error)
        
        # Is the error surprising?
        surprising = abs_error > self._threshold
        
        # Precision-weighted error (Friston)
        precision = prediction["precision"]
        weighted_error = abs_error * precision
        
        # Verdict match
        verdict_match = actual_verdict == prediction["predicted_verdict"]
        
        # Within predicted range?
        in_range = prediction["predicted_range"][0] <= actual_confidence <= prediction["predicted_range"][1]
        
        # How much metacognition is needed?
        if not surprising and verdict_match and in_range:
            meta_depth = "MINIMAL"  # Skip most metacognition
        elif surprising and not verdict_match:
            meta_depth = "FULL"  # Run everything
        else:
            meta_depth = "PARTIAL"  # Run subset
        
        return {
            "error": round(error, 4),
            "abs_error": round(abs_error, 4),
            "weighted_error": round(weighted_error, 4),
            "surprising": surprising,
            "verdict_match": verdict_match,
            "in_range": in_range,
            "meta_depth": meta_depth,
        }
    
    def update(self, claim_type: str, prediction: Dict, actual_confidence: float):
        """Update internal model with actual outcome."""
        predicted = prediction["predicted_confidence"]
        error = actual_confidence - predicted
        
        self._prediction_history[claim_type].append({
            "predicted": predicted,
            "actual": actual_confidence,
            "error": error,
        })
        
        # Update precision (inverse variance of recent errors)
        history = self._prediction_history[claim_type]
        if len(history) >= 3:
            recent_errors = [h["error"] for h in history[-10:]]
            variance = sum(e**2 for e in recent_errors) / len(recent_errors)
            self._precision_weights[claim_type] = round(1.0 / max(variance, 0.01), 4)
        
        # Keep history bounded
        if len(history) > 50:
            self._prediction_history[claim_type] = history[-50:]
