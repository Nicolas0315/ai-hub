"""
KS36b — Katala Samurai 36b: Metacognitive Planning

KS36a + strategic verification planning:
  - Pre-execution claim classification (7 types)
  - Layer priority & effort allocation
  - Pre-set success/failure thresholds
  - Fallback strategy generation
  - Post-execution plan evaluation (did reality match prediction?)

Target: Metacognitive Planning 55% → 90%+

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks36a import KS36a, Claim
    from .stage_store import StageStore
    from .metacognitive_planner import plan_verification
except ImportError:
    from ks36a import KS36a, Claim
    from stage_store import StageStore
    from metacognitive_planner import plan_verification

from typing import Dict, Any, Optional


class KS36b(KS36a):
    """KS36a + Metacognitive Planning."""
    
    VERSION = "KS36b"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._plan_history = []
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        
        # ── Phase 0: PLAN (before any verification) ──
        plan = plan_verification(claim_text)
        
        try:
            store.write("ks36b_plan", plan)
        except (ValueError, Exception):
            pass
        
        # ── Execute KS36a (full pipeline) ──
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # ── Phase N: EVALUATE plan vs reality ──
        actual_conf = result.get("confidence", 0.5)
        expected = plan["criteria"]["expected_range"]
        
        within_expected = expected[0] <= actual_conf <= expected[1]
        surprise = 0
        if actual_conf < expected[0]:
            surprise = expected[0] - actual_conf
        elif actual_conf > expected[1]:
            surprise = actual_conf - expected[1]
        
        # Did the plan correctly predict which layers would be most useful?
        plan_accuracy = "ACCURATE" if within_expected else ("SURPRISED_HIGH" if actual_conf > expected[1] else "SURPRISED_LOW")
        
        # Dead zone check — should we have forced L7?
        dead_zone = 0.4 <= actual_conf <= 0.6
        
        evaluation = {
            "plan_summary": plan["plan_summary"],
            "primary_type": plan["primary_type"],
            "difficulty": plan["difficulty"]["label"],
            "expected_range": expected,
            "actual_confidence": actual_conf,
            "within_expected": within_expected,
            "surprise": round(surprise, 3),
            "accuracy": plan_accuracy,
            "dead_zone": dead_zone,
        }
        
        # If surprised, apply correction
        if surprise > 0.2:
            evaluation["correction"] = "Large surprise — plan model needs updating for this claim type"
            result["confidence"] = round(actual_conf * 0.95, 4)  # Slight penalty for unpredicted result
        
        result["plan"] = plan
        result["plan_evaluation"] = evaluation
        result["version"] = self.VERSION
        
        # Track for learning
        self._plan_history.append(evaluation)
        if len(self._plan_history) > 50:
            self._plan_history = self._plan_history[-50:]
        
        try:
            store.write("ks36b_evaluation", evaluation)
        except (ValueError, Exception):
            pass
        
        return result
    
    def plan_only(self, claim_text: str) -> Dict[str, Any]:
        """Just plan — don't execute. For inspection/debugging."""
        return plan_verification(claim_text)
    
    def plan_accuracy_report(self) -> Dict[str, Any]:
        """How well have our plans predicted reality?"""
        if not self._plan_history:
            return {"total": 0, "accuracy": "NO_DATA"}
        
        accurate = sum(1 for p in self._plan_history if p["within_expected"])
        total = len(self._plan_history)
        
        by_type = {}
        for p in self._plan_history:
            t = p.get("primary_type", "unknown")
            if t not in by_type:
                by_type[t] = {"total": 0, "accurate": 0}
            by_type[t]["total"] += 1
            if p["within_expected"]:
                by_type[t]["accurate"] += 1
        
        return {
            "total": total,
            "accurate": accurate,
            "accuracy_pct": round(accurate / total * 100, 1),
            "by_type": by_type,
            "avg_surprise": round(sum(p["surprise"] for p in self._plan_history) / total, 3),
        }
