"""
KS36c — Katala Samurai 36c: Emergent Insight + Self-Correction

KS36b + 2 modules targeting IQ160+PhD-level metacognition:
  1) Emergent Insight: cross-layer contradiction mining, implicit assumptions, self-deception detection
  2) Self-Corrector: fragility ablation, calibration check, verdict consistency, dead-zone acknowledgment

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks36b import KS36b, Claim
    from .stage_store import StageStore
    from .emergent_insight import InsightDetector
    from .self_corrector import SelfCorrector
except ImportError:
    from ks36b import KS36b, Claim
    from stage_store import StageStore
    from emergent_insight import InsightDetector
    from self_corrector import SelfCorrector

from typing import Dict, Any, Optional


class KS36c(KS36b):
    """KS36b + Emergent Insight + Self-Correction."""
    
    VERSION = "KS36c"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.insight_detector = InsightDetector()
        self.self_corrector = SelfCorrector()
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        # KS36b (includes plan + metacognition)
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # ── Emergent Insight ──
        plan = result.get("plan", {})
        try:
            insight_result = self.insight_detector.analyze(result, plan)
            result["emergent_insights"] = {
                "count": insight_result["count"],
                "high_novelty": insight_result["high_novelty"],
                "summary": insight_result["summary"],
            }
        except Exception as e:
            result["emergent_insights"] = {"error": str(e)[:100]}
            insight_result = {"confidence_modifier": 0}
        
        # ── Self-Correction ──
        try:
            correction_result = self.self_corrector.correct(result)
            result["self_correction"] = {
                "total": correction_result["total"],
                "applied": correction_result["applied"],
                "types": correction_result["details"],
            }
            
            # Apply corrections
            if correction_result["confidence_adjustment"] != 0:
                old = result.get("confidence", 0.5)
                result["confidence"] = round(max(0, min(1, old + correction_result["confidence_adjustment"])), 4)
            
            if correction_result["verdict_override"]:
                result["verdict"] = correction_result["verdict_override"]
                result["_corrected_verdict"] = True
        except Exception as e:
            result["self_correction"] = {"error": str(e)[:100]}
            correction_result = {"confidence_adjustment": 0}
        
        # Apply insight modifier
        insight_mod = insight_result.get("confidence_modifier", 0)
        if insight_mod != 0:
            result["confidence"] = round(max(0, min(1, result.get("confidence", 0.5) + insight_mod)), 4)
        
        result["version"] = self.VERSION
        return result
