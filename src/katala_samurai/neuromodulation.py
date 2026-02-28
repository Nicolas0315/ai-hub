"""
Neuromodulation — Global sensitivity adjustment across all layers.

Like dopamine/serotonin: adjusts attention and learning rate globally.
- Novel/uncertain claim → lower thresholds (more careful)
- Known/routine claim → higher thresholds (faster)
- High-stakes claim → amplify all signals

Kandel Ch.40: modulatory neurotransmitters gate plasticity and attention.

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, Tuple


class Neuromodulator:
    """Global modulation of verification sensitivity."""
    
    def __init__(self):
        self._baseline = {
            "attention": 1.0,      # Overall processing depth
            "threshold": 0.5,      # Confidence threshold for decisions
            "learning_rate": 1.0,  # How fast to adapt
            "caution": 1.0,        # How much to doubt results
        }
        self._current = dict(self._baseline)
        self._history_novelty = []
    
    def modulate(self, claim_type: str, difficulty: str, prediction_error: float,
                 novelty: float = 0.5) -> Dict[str, float]:
        """Compute modulation parameters based on claim context.
        
        Returns modulation factors that all layers should apply.
        """
        # ── Dopaminergic signal: novelty/surprise → attention ──
        if prediction_error > 0.2 or novelty > 0.7:
            # Surprising/novel → increase attention, lower thresholds
            self._current["attention"] = min(2.0, 1.0 + prediction_error * 2)
            self._current["threshold"] = max(0.3, 0.5 - novelty * 0.2)
            self._current["learning_rate"] = min(2.0, 1.0 + novelty)
        else:
            # Routine → relax attention, raise thresholds for speed
            self._current["attention"] = max(0.5, 1.0 - (1 - novelty) * 0.3)
            self._current["threshold"] = min(0.7, 0.5 + (1 - novelty) * 0.2)
            self._current["learning_rate"] = max(0.5, 1.0 - (1 - novelty) * 0.3)
        
        # ── Noradrenergic signal: difficulty → caution ──
        difficulty_map = {"LOW": 0.7, "MEDIUM": 1.0, "HIGH": 1.5}
        self._current["caution"] = difficulty_map.get(difficulty, 1.0)
        
        # ── Serotonergic signal: type-specific modulation ──
        type_mods = {
            "causal": {"caution": 1.3, "attention": 1.2},     # Causal needs more care
            "statistical": {"attention": 1.4, "threshold": 0.4}, # Stats need scrutiny
            "definitional": {"attention": 0.7, "threshold": 0.6}, # Definitions are cleaner
            "normative": {"caution": 1.5, "attention": 1.1},    # Values need caution
        }
        
        if claim_type in type_mods:
            for key, factor in type_mods[claim_type].items():
                if key in ("caution", "attention", "learning_rate"):
                    self._current[key] *= factor
                else:
                    self._current[key] = factor
        
        # Clamp all values
        self._current["attention"] = round(max(0.3, min(2.5, self._current["attention"])), 4)
        self._current["threshold"] = round(max(0.2, min(0.8, self._current["threshold"])), 4)
        self._current["learning_rate"] = round(max(0.3, min(2.5, self._current["learning_rate"])), 4)
        self._current["caution"] = round(max(0.5, min(2.0, self._current["caution"])), 4)
        
        return dict(self._current)
    
    def apply_to_confidence(self, raw_confidence: float) -> float:
        """Apply neuromodulation to a raw confidence score."""
        # Caution pulls confidence toward 0.5 (more cautious = less extreme)
        caution = self._current["caution"]
        if caution > 1.0:
            # Pull toward 0.5
            modulated = raw_confidence + (0.5 - raw_confidence) * (caution - 1.0) * 0.3
        else:
            modulated = raw_confidence
        
        return round(max(0, min(1, modulated)), 4)
    
    def should_deepen(self) -> bool:
        """Should we run deeper analysis based on current modulation?"""
        return self._current["attention"] > 1.3
    
    def should_accelerate(self) -> bool:
        """Can we safely skip deeper analysis?"""
        return self._current["attention"] < 0.7 and self._current["caution"] < 0.8
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "modulation": dict(self._current),
            "mode": (
                "VIGILANT" if self._current["attention"] > 1.3
                else "RELAXED" if self._current["attention"] < 0.7
                else "NORMAL"
            ),
        }
    
    def reset(self):
        self._current = dict(self._baseline)
