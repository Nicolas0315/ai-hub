"""
KS38a — Katala Samurai 38a: Neuroscience-Inspired Architecture

KS37b + 4 brain-inspired mechanisms:
  1) Predictive Coding (Friston): predict-then-correct, skip if prediction matches
  2) Lateral Inhibition (Kandel Ch.21): sharpen solver signals
  3) Neuromodulation (Kandel Ch.40): global sensitivity adjustment
  4) Space of Reasons (Sellars/Brandom): inter-solver coherence network

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os, os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks37b import KS37b, Claim
    from .stage_store import StageStore
    from .predictive_coding import PredictiveEngine
    from .lateral_inhibition import inhibit, compute_sharpness
    from .neuromodulation import Neuromodulator
    from .reason_space import ReasonSpace
except ImportError:
    from ks37b import KS37b, Claim
    from stage_store import StageStore
    from predictive_coding import PredictiveEngine
    from lateral_inhibition import inhibit, compute_sharpness
    from neuromodulation import Neuromodulator
    from reason_space import ReasonSpace

from typing import Dict, Any, Optional
from metacognitive_planner import plan_verification


class KS38a(KS37b):
    """KS37b + Neuroscience-Inspired Architecture."""
    
    VERSION = "KS38a"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.predictor = PredictiveEngine()
        self.neuromod = Neuromodulator()
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        t0 = time.time()
        claim_text = claim.text if hasattr(claim, 'text') else str(claim)
        
        # ═══ PLAN ═══
        plan = plan_verification(claim_text)
        claim_type = plan["primary_type"]
        difficulty = plan["difficulty"]["label"]
        
        # ═══ ① PREDICTIVE CODING: predict before verify ═══
        prediction = self.predictor.predict(claim_type, difficulty, plan)
        
        # ═══ ③ NEUROMODULATION: set global sensitivity ═══
        # Novelty = inverse of prediction precision (less precise = more novel)
        novelty = max(0, min(1, 1.0 - prediction["precision"] / 100))
        modulation = self.neuromod.modulate(
            claim_type, difficulty,
            prediction_error=0,  # Pre-verify, use 0
            novelty=novelty,
        )
        
        t_pre = time.time()
        
        # ═══ CORE VERIFY (KS37b with cache + pruning) ═══
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        t_core = time.time()
        
        actual_conf = result.get("confidence", 0.5)
        actual_verdict = result.get("verdict", "UNKNOWN")
        
        # ═══ ① PREDICTION ERROR: how surprised are we? ═══
        pred_error = self.predictor.compute_error(prediction, actual_conf, actual_verdict)
        
        # Update neuromodulation with actual prediction error
        self.neuromod.modulate(claim_type, difficulty, pred_error["abs_error"], novelty)
        
        # ═══ ② LATERAL INHIBITION: sharpen solver signals ═══
        # Extract solver-level results from trace
        solver_results = []
        for step in result.get("trace", []):
            solver_results.append({
                "solver": step.get("stage", step.get("layer", "?")),
                "confidence": step.get("confidence", 0.5),
                "verdict": str(step.get("result", step.get("verdict", ""))),
                "reason": str(step.get("detail", step.get("reason", "")))[:200],
            })
        
        if solver_results:
            inhibited = inhibit(solver_results)
            sharpness = compute_sharpness(inhibited)
            
            # Recalculate confidence from inhibited results
            if inhibited:
                inhibited_confs = [r.get("confidence", 0.5) for r in inhibited]
                inhibited_mean = sum(inhibited_confs) / len(inhibited_confs)
                # Blend: 70% original + 30% inhibited
                actual_conf = actual_conf * 0.7 + inhibited_mean * 0.3
        else:
            sharpness = {"sharpness": 0, "inhibited_count": 0, "signal_clarity": "N/A"}
        
        # ═══ ④ SPACE OF REASONS: coherence check ═══
        reason_space = ReasonSpace()
        for step in result.get("trace", []):
            reason_space.register(
                solver_id=step.get("stage", step.get("layer", "?")),
                reason=str(step.get("detail", step.get("reason", "")))[:200],
                confidence=step.get("confidence", 0.5),
                verdict=str(step.get("result", step.get("verdict", ""))),
            )
        coherence = reason_space.analyze_coherence()
        
        # ═══ ③ NEUROMODULATION: apply to final confidence ═══
        actual_conf = self.neuromod.apply_to_confidence(actual_conf)
        
        # Apply coherence modifier
        actual_conf = max(0, min(1, actual_conf + coherence.get("confidence_modifier", 0)))
        
        # ═══ METACOGNITION: conditional depth based on prediction ═══
        meta_depth = pred_error["meta_depth"]
        
        if meta_depth == "MINIMAL" and self.neuromod.should_accelerate():
            # Prediction matched → skip most metacognition (already done in parent)
            result["_meta_skipped"] = True
        
        # Update prediction model
        self.predictor.update(claim_type, prediction, actual_conf)
        
        t_end = time.time()
        
        # ═══ ASSEMBLE ═══
        result["confidence"] = round(actual_conf, 4)
        result["version"] = self.VERSION
        
        result["predictive_coding"] = {
            "predicted": prediction["predicted_confidence"],
            "actual": round(actual_conf, 4),
            "error": pred_error["error"],
            "surprising": pred_error["surprising"],
            "meta_depth": meta_depth,
        }
        
        result["lateral_inhibition"] = {
            "clarity": sharpness.get("signal_clarity", "N/A"),
            "inhibited": sharpness.get("inhibited_count", 0),
            "sharpness": sharpness.get("sharpness", 0),
        }
        
        result["neuromodulation"] = self.neuromod.get_state()
        
        result["reason_space"] = {
            "coherence": coherence["coherence"],
            "conflicts": coherence["conflict_count"],
            "isolated": len(coherence["isolated_solvers"]),
            "assessment": coherence["assessment"],
        }
        
        if "pipeline" in result:
            result["pipeline"]["neuro_ms"] = int((t_end - t_core) * 1000)
            result["pipeline"]["total_ms"] = int((t_end - t0) * 1000)
        
        return result
