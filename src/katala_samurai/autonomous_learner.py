"""
Autonomous Learner — Enhanced session-scoped self-improvement.

Combines failure_learner feedback with strategy adaptation to create
genuine autonomous learning within a session:
  - Transfer learning: apply lessons from one claim type to similar types
  - Confidence recalibration: adjust prediction models based on outcomes
  - Strategy evolution: promote successful strategies, demote failing ones
  - Pattern generalization: abstract specific failures into general rules

Session-scoped. Anti-accumulation compliant. Ephemeral by design.

Target: Autonomous Learning 82% → 90%+

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
import math


# Type similarity matrix for transfer learning
_TYPE_SIMILARITY = {
    ("causal", "empirical"): 0.7,
    ("causal", "statistical"): 0.5,
    ("statistical", "empirical"): 0.6,
    ("definitional", "logical"): 0.6,
    ("normative", "logical"): 0.4,
    ("historical", "empirical"): 0.5,
}


def _type_similarity(t1: str, t2: str) -> float:
    if t1 == t2:
        return 1.0
    key = tuple(sorted([t1, t2]))
    return _TYPE_SIMILARITY.get(key, 0.1)


class AutonomousLearner:
    """Session-scoped autonomous learning engine."""
    
    def __init__(self):
        self._outcomes = []
        self._confidence_model = {}  # type → (bias, scale)
        self._strategy_scores = defaultdict(lambda: {"wins": 0, "total": 0})
        self._generalized_rules = []
    
    def record(self, claim_type: str, strategy: str, predicted_range: List[float],
               actual_confidence: float, corrections: int, verdict: str):
        """Record an outcome for learning."""
        predicted_mid = (predicted_range[0] + predicted_range[1]) / 2
        error = actual_confidence - predicted_mid
        
        self._outcomes.append({
            "type": claim_type, "strategy": strategy,
            "predicted": predicted_range, "actual": actual_confidence,
            "error": error, "corrections": corrections, "verdict": verdict,
        })
        
        # Update confidence model
        if claim_type not in self._confidence_model:
            self._confidence_model[claim_type] = {"bias": 0, "samples": 0, "errors": []}
        
        model = self._confidence_model[claim_type]
        model["errors"].append(error)
        model["samples"] += 1
        model["bias"] = sum(model["errors"]) / len(model["errors"])
        
        # Update strategy scores
        key = f"{strategy}:{claim_type}"
        self._strategy_scores[key]["total"] += 1
        if corrections <= 1 and abs(error) < 0.15:
            self._strategy_scores[key]["wins"] += 1
        
        # Try to generalize
        self._try_generalize()
    
    def get_learned_adjustments(self, claim_type: str) -> Dict[str, Any]:
        """Get adjustments based on what we've learned this session."""
        adjustments = {
            "confidence_bias": 0,
            "strategy_recommendation": None,
            "transfer_warnings": [],
            "generalized_rules": [],
        }
        
        # ── Direct learning ──
        if claim_type in self._confidence_model:
            model = self._confidence_model[claim_type]
            if model["samples"] >= 2:
                adjustments["confidence_bias"] = round(-model["bias"] * 0.5, 4)  # Counter the bias
        
        # ── Transfer learning from similar types ──
        for other_type, model in self._confidence_model.items():
            if other_type == claim_type:
                continue
            sim = _type_similarity(claim_type, other_type)
            if sim >= 0.5 and model["samples"] >= 2 and abs(model["bias"]) > 0.1:
                transfer_adj = round(-model["bias"] * sim * 0.3, 4)
                adjustments["confidence_bias"] += transfer_adj
                adjustments["transfer_warnings"].append(
                    f"Transfer from '{other_type}' (sim={sim:.1f}): bias={model['bias']:+.2f} → adj={transfer_adj:+.3f}"
                )
        
        # ── Strategy recommendation ──
        best_strat = None
        best_rate = 0
        for key, scores in self._strategy_scores.items():
            strat, stype = key.split(":", 1)
            sim = _type_similarity(claim_type, stype)
            if sim >= 0.5 and scores["total"] >= 2:
                rate = (scores["wins"] / scores["total"]) * sim
                if rate > best_rate:
                    best_rate = rate
                    best_strat = strat
        
        if best_strat and best_rate > 0.5:
            adjustments["strategy_recommendation"] = best_strat
        
        # ── Generalized rules ──
        adjustments["generalized_rules"] = [
            r for r in self._generalized_rules
            if r.get("applies_to", "ALL") in ("ALL", claim_type)
        ]
        
        adjustments["confidence_bias"] = round(max(-0.15, min(0.15, adjustments["confidence_bias"])), 4)
        
        return adjustments
    
    def _try_generalize(self):
        """Try to create generalized rules from patterns in outcomes."""
        if len(self._outcomes) < 3:
            return
        
        # Pattern: consistent overconfidence across types
        recent = self._outcomes[-5:]
        overconfident = sum(1 for o in recent if o["error"] < -0.1)
        if overconfident >= 3:
            rule = {
                "type": "systematic_overconfidence",
                "applies_to": "ALL",
                "adjustment": -0.05,
                "evidence": f"{overconfident}/{len(recent)} recent outcomes were overconfident",
            }
            if not any(r["type"] == "systematic_overconfidence" for r in self._generalized_rules):
                self._generalized_rules.append(rule)
        
        # Pattern: specific type always needs corrections
        type_corrections = defaultdict(list)
        for o in self._outcomes:
            type_corrections[o["type"]].append(o["corrections"])
        
        for t, corrs in type_corrections.items():
            if len(corrs) >= 2 and sum(corrs) / len(corrs) >= 2.5:
                rule = {
                    "type": "high_correction_type",
                    "applies_to": t,
                    "adjustment": -0.05,
                    "evidence": f"'{t}' avg corrections: {sum(corrs)/len(corrs):.1f}",
                }
                if not any(r["type"] == "high_correction_type" and r["applies_to"] == t for r in self._generalized_rules):
                    self._generalized_rules.append(rule)
    
    def learning_report(self) -> Dict[str, Any]:
        """Session learning summary."""
        return {
            "outcomes": len(self._outcomes),
            "confidence_models": {k: {"bias": round(v["bias"], 3), "samples": v["samples"]}
                                  for k, v in self._confidence_model.items()},
            "generalized_rules": len(self._generalized_rules),
            "rules": self._generalized_rules,
            "strategy_performance": {k: {"win_rate": round(v["wins"]/max(v["total"],1), 2), "total": v["total"]}
                                     for k, v in self._strategy_scores.items()},
        }
    
    def reset(self):
        self._outcomes.clear()
        self._confidence_model.clear()
        self._strategy_scores.clear()
        self._generalized_rules.clear()
