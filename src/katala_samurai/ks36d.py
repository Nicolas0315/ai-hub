"""
KS36d — Katala Samurai 36d: Adaptive Strategy + Failure Learning

KS36c + 2 modules to surpass IQ160 PhD on ALL metacognition axes:
  1) Adaptive Strategy: mid-verification strategy switching + backtracking
  2) Failure Learner: session-scoped failure analysis + blind spot detection

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks36c import KS36c, Claim
    from .stage_store import StageStore
    from .adaptive_strategy import AdaptiveStrategy
    from .failure_learner import FailureLearner
except ImportError:
    from ks36c import KS36c, Claim
    from stage_store import StageStore
    from adaptive_strategy import AdaptiveStrategy
    from failure_learner import FailureLearner

from typing import Dict, Any, Optional


class KS36d(KS36c):
    """KS36c + Adaptive Strategy + Failure Learning."""
    
    VERSION = "KS36d"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.strategy_engine = AdaptiveStrategy()
        self.failure_learner = FailureLearner()
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        
        # ── Pre-phase: Get failure-based adjustments ──
        plan = self.plan_only(claim_text) if hasattr(self, 'plan_only') else {}
        claim_type = plan.get("primary_type", "unknown")
        difficulty = plan.get("difficulty", {}).get("label", "MEDIUM") if isinstance(plan.get("difficulty"), dict) else "MEDIUM"
        
        adjustments = self.failure_learner.get_adjustments(claim_type)
        
        # ── Select strategy ──
        strategy_name, strategy = self.strategy_engine.select_initial(claim_type, difficulty)
        
        if adjustments.get("strategy_override"):
            strategy_name = adjustments["strategy_override"]
            strategy = AdaptiveStrategy.__init__  # just use the name
            from adaptive_strategy import STRATEGIES
            strategy = STRATEGIES.get(strategy_name, {})
        
        # ── Execute KS36c ──
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # ── Mid-verification strategy check ──
        switch = self.strategy_engine.evaluate_switch(strategy_name, result)
        if switch:
            new_strat, reason = switch
            result["strategy_switch"] = {"from": strategy_name, "to": new_strat, "reason": reason}
            strategy_name = new_strat
        
        # ── Apply failure-based adjustments ──
        if adjustments["confidence_bias"] != 0:
            old = result.get("confidence", 0.5)
            result["confidence"] = round(max(0, min(1, old + adjustments["confidence_bias"])), 4)
            result["_failure_adjusted"] = True
        
        if adjustments["warnings"]:
            result["failure_warnings"] = adjustments["warnings"]
        
        # ── Backtrack check ──
        backtrack = self.strategy_engine.should_backtrack(strategy_name, result)
        if backtrack:
            new_strat, reason = backtrack
            result["backtrack"] = {"to": new_strat, "reason": reason}
        
        # ── Record for learning ──
        corrections = result.get("self_correction", {}).get("types", [])
        surprise = result.get("plan_evaluation", {}).get("surprise", 0)
        plan_acc = result.get("plan_evaluation", {}).get("accuracy", "ACCURATE")
        
        self.failure_learner.record_outcome(
            claim_type=claim_type,
            verdict=result.get("verdict", "UNKNOWN"),
            confidence=result.get("confidence", 0.5),
            corrections=corrections,
            surprise=surprise,
            plan_accuracy=plan_acc,
        )
        
        self.strategy_engine.record(
            strategy=strategy_name,
            claim_type=claim_type,
            result_confidence=result.get("confidence", 0.5),
            corrections=len(corrections),
        )
        
        result["strategy"] = {
            "name": strategy_name,
            "switched": "strategy_switch" in result,
            "backtracked": "backtrack" in result,
        }
        
        result["version"] = self.VERSION
        return result
    
    def session_summary(self) -> Dict[str, Any]:
        """Full session performance summary."""
        return {
            "failure_report": self.failure_learner.session_report(),
            "strategy_report": self.strategy_engine.strategy_report(),
            "blind_spots": self.failure_learner.detect_systematic_blind_spots(),
        }
