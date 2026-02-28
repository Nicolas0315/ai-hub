"""
Self-Regulation — Internal brake system for judgment quality control.

Monitors own judgment patterns and generates dynamic stop conditions:
  - Oscillation detector: confidence bouncing → stop and report uncertainty
  - Repetition detector: same pattern 3x → suspect automation bias
  - Extremity detector: too confident too fast → force re-check
  - Divergence detector: layers disagreeing wildly → flag for review

Target: Self-Regulation 45% → 90%+

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional
from collections import deque
import math


class SelfRegulator:
    """Dynamic self-regulation with pattern-based stop conditions."""
    
    def __init__(self, window_size: int = 10):
        self._history = deque(maxlen=window_size)
        self._stop_conditions = []
        self._interventions = []
    
    def observe(self, verdict: str, confidence: float, layer_confidences: Dict[str, float] = None) -> Dict[str, Any]:
        """Observe a verification result and check stop conditions.
        
        Returns action recommendations.
        """
        self._history.append({
            "verdict": verdict,
            "confidence": confidence,
            "layers": layer_confidences or {},
        })
        
        actions = []
        
        # ── 1) Oscillation Detection ──
        if len(self._history) >= 3:
            recent_confs = [h["confidence"] for h in list(self._history)[-5:]]
            oscillations = 0
            for i in range(1, len(recent_confs)):
                if abs(recent_confs[i] - recent_confs[i-1]) > 0.2:
                    oscillations += 1
            
            if oscillations >= 2:
                actions.append({
                    "type": "STOP_OSCILLATION",
                    "detail": f"Confidence oscillating: {[round(c,2) for c in recent_confs]}",
                    "recommendation": "Report high uncertainty rather than commit to a verdict",
                    "severity": "high",
                })
        
        # ── 2) Repetition Detection ──
        if len(self._history) >= 3:
            recent_verdicts = [h["verdict"] for h in list(self._history)[-3:]]
            recent_confs = [round(h["confidence"], 2) for h in list(self._history)[-3:]]
            
            if len(set(recent_verdicts)) == 1 and len(set(recent_confs)) == 1:
                actions.append({
                    "type": "SUSPECT_AUTOMATION",
                    "detail": f"3 identical results: {recent_verdicts[0]} @ {recent_confs[0]}",
                    "recommendation": "Likely stuck in a pattern. Try different approach or report limitation",
                    "severity": "medium",
                })
        
        # ── 3) Extremity Detection ──
        if confidence > 0.9 and len(self._history) <= 2:
            actions.append({
                "type": "PREMATURE_CERTAINTY",
                "detail": f"Confidence {confidence:.2f} after only {len(self._history)} verifications",
                "recommendation": "Force L7 adversarial re-check before committing to high confidence",
                "severity": "high",
            })
        
        if confidence < 0.1 and len(self._history) <= 2:
            actions.append({
                "type": "PREMATURE_REJECTION",
                "detail": f"Confidence {confidence:.2f} after only {len(self._history)} verifications",
                "recommendation": "Insufficient evidence to reject. Report as uncertain",
                "severity": "high",
            })
        
        # ── 4) Divergence Detection ──
        if layer_confidences and len(layer_confidences) >= 2:
            confs = list(layer_confidences.values())
            spread = max(confs) - min(confs)
            
            if spread > 0.5:
                max_layer = max(layer_confidences, key=layer_confidences.get)
                min_layer = min(layer_confidences, key=layer_confidences.get)
                actions.append({
                    "type": "LAYER_DIVERGENCE",
                    "detail": f"Spread {spread:.2f}: {max_layer}={layer_confidences[max_layer]:.2f} vs {min_layer}={layer_confidences[min_layer]:.2f}",
                    "recommendation": "Layers disagree significantly. Investigate why before synthesizing",
                    "severity": "medium" if spread < 0.7 else "high",
                })
        
        # Generate confidence modifier
        high_actions = sum(1 for a in actions if a["severity"] == "high")
        modifier = -0.1 * high_actions if high_actions > 0 else 0
        
        should_stop = any(a["type"].startswith("STOP") for a in actions)
        
        self._interventions.extend(actions)
        
        return {
            "actions": actions,
            "should_stop": should_stop,
            "confidence_modifier": round(modifier, 4),
            "pattern_health": "HEALTHY" if not actions else "DEGRADED" if high_actions == 0 else "CRITICAL",
            "observations": len(self._history),
        }
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "observations": len(self._history),
            "total_interventions": len(self._interventions),
            "recent_interventions": self._interventions[-5:],
            "health": "HEALTHY" if not self._interventions else "ACTIVE",
        }
    
    def reset(self):
        self._history.clear()
        self._interventions.clear()
