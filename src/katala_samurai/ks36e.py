"""
KS36e — Katala Samurai 36e: Autonomous Learning Enhancement

KS36d + Autonomous Learner:
  - Transfer learning across claim types (similarity-weighted)
  - Confidence recalibration from session outcomes
  - Strategy evolution (promote winners, demote losers)
  - Pattern generalization (specific → abstract rules)
  - All session-scoped, anti-accumulation compliant

Targets: Autonomous Learning 82% → 90%, Autonomous Goal 60% → 68%

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks36d import KS36d, Claim
    from .stage_store import StageStore
    from .autonomous_learner import AutonomousLearner
except ImportError:
    from ks36d import KS36d, Claim
    from stage_store import StageStore
    from autonomous_learner import AutonomousLearner

from typing import Dict, Any, Optional


class KS36e(KS36d):
    """KS36d + Autonomous Learning Enhancement."""
    
    VERSION = "KS36e"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.auto_learner = AutonomousLearner()
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        plan = self.plan_only(claim_text) if hasattr(self, 'plan_only') else {}
        claim_type = plan.get("primary_type", "unknown")
        
        # ── Pre-phase: Get learned adjustments ──
        learned = self.auto_learner.get_learned_adjustments(claim_type)
        
        # ── Execute KS36d ──
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # ── Apply learned confidence bias ──
        if learned["confidence_bias"] != 0:
            old = result.get("confidence", 0.5)
            result["confidence"] = round(max(0, min(1, old + learned["confidence_bias"])), 4)
            result["_learning_adjusted"] = True
        
        if learned["transfer_warnings"]:
            result["transfer_warnings"] = learned["transfer_warnings"]
        
        if learned["generalized_rules"]:
            for rule in learned["generalized_rules"]:
                adj = rule.get("adjustment", 0)
                if adj:
                    result["confidence"] = round(max(0, min(1, result["confidence"] + adj)), 4)
        
        # ── Record for learning ──
        predicted = result.get("plan", {}).get("criteria", {}).get("expected_range", [0.3, 0.7])
        corrections = result.get("self_correction", {}).get("types", [])
        strategy = result.get("strategy", {}).get("name", "unknown")
        
        self.auto_learner.record(
            claim_type=claim_type,
            strategy=strategy,
            predicted_range=predicted,
            actual_confidence=result.get("confidence", 0.5),
            corrections=len(corrections),
            verdict=result.get("verdict", "UNKNOWN"),
        )
        
        result["autonomous_learning"] = {
            "outcomes_so_far": len(self.auto_learner._outcomes),
            "bias_applied": learned["confidence_bias"],
            "transfers": len(learned["transfer_warnings"]),
            "rules_active": len(learned["generalized_rules"]),
            "strategy_recommended": learned.get("strategy_recommendation"),
        }
        
        result["version"] = self.VERSION
        return result
    
    def learning_report(self) -> Dict[str, Any]:
        return self.auto_learner.learning_report()
    
    def full_session_summary(self) -> Dict[str, Any]:
        base = self.session_summary()
        base["autonomous_learning"] = self.auto_learner.learning_report()
        return base
