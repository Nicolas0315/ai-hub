"""
KS36a — Katala Samurai 36a: Metacognitive Verification

KS35c + 3 metacognitive upgrades:
  1) Reasoning Tracer: DAG-based reasoning chain analysis (leap/circular/gap detection)
  2) Self-Regulation: dynamic stop conditions (oscillation/repetition/extremity/divergence)
  3) Uncertainty Quantifier: 2nd-order uncertainty with confidence intervals

Target: PhD researcher-level self-monitoring, self-regulation, uncertainty recognition.

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys
import os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks35c import KS35c, Claim
    from .stage_store import StageStore
    from .reasoning_tracer import trace_verification
    from .self_regulation import SelfRegulator
    from .uncertainty_quantifier import quantify_uncertainty
except ImportError:
    from ks35c import KS35c, Claim
    from stage_store import StageStore
    from reasoning_tracer import trace_verification
    from self_regulation import SelfRegulator
    from uncertainty_quantifier import quantify_uncertainty

from typing import Dict, Any, Optional


class KS36a(KS35c):
    """KS35c + Metacognitive Verification."""
    
    VERSION = "KS36a"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.regulator = SelfRegulator()
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        # Run KS35c
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            # PDF batch — skip metacognition for now
            result["version"] = self.VERSION
            return result
        
        # ── 1) Reasoning Trace ──
        try:
            trace_result = trace_verification(result)
            result["reasoning_trace"] = {
                "nodes": trace_result["nodes"],
                "issues": trace_result["total_issues"],
                "monitoring_score": trace_result["monitoring_score"],
                "leaps": len(trace_result["leaps"]),
                "circular": len(trace_result["circular"]),
                "gaps": len(trace_result["evidence_gaps"]),
                "baseless": len(trace_result["baseless_confidence"]),
            }
        except Exception as e:
            result["reasoning_trace"] = {"error": str(e)[:100]}
            trace_result = {"confidence_modifier": 0}
        
        # ── 2) Self-Regulation ──
        try:
            layer_confs = {}
            l6 = result.get("L6_statistical", {})
            l7 = result.get("L7_adversarial", {})
            if l6.get("modifier", 0) != 0:
                layer_confs["L6"] = 0.5 + l6["modifier"]
            if l7.get("modifier", 0) != 0:
                layer_confs["L7"] = 0.5 + l7["modifier"]
            layer_confs["core"] = result.get("confidence", 0.5)
            
            reg_result = self.regulator.observe(
                result.get("verdict", "UNKNOWN"),
                result.get("confidence", 0.5),
                layer_confs,
            )
            result["self_regulation"] = {
                "actions": len(reg_result["actions"]),
                "should_stop": reg_result["should_stop"],
                "health": reg_result["pattern_health"],
                "details": [a["type"] for a in reg_result["actions"]],
            }
            
            if reg_result["should_stop"]:
                result["verdict"] = "EXPLORING"
                result["_stop_reason"] = reg_result["actions"][0]["detail"] if reg_result["actions"] else "pattern anomaly"
        except Exception as e:
            result["self_regulation"] = {"error": str(e)[:100]}
            reg_result = {"confidence_modifier": 0}
        
        # ── 3) Uncertainty Quantification ──
        try:
            uq_result = quantify_uncertainty(result)
            result["uncertainty"] = {
                "display": uq_result["display"],
                "ci_95": uq_result["bootstrap"]["ci_95"],
                "first_order": uq_result["uncertainty"]["first_order"],
                "second_order": uq_result["uncertainty"]["second_order"],
                "calibration": uq_result["calibration"]["assessment"],
            }
        except Exception as e:
            result["uncertainty"] = {"error": str(e)[:100]}
            uq_result = {"confidence_modifier": 0}
        
        # ── Apply metacognitive modifiers ──
        trace_mod = trace_result.get("confidence_modifier", 0)
        reg_mod = reg_result.get("confidence_modifier", 0)
        uq_mod = uq_result.get("confidence_modifier", 0)
        
        total_meta_mod = max(-0.2, min(0.1, trace_mod + reg_mod + uq_mod))
        
        old_conf = result.get("confidence", 0.5)
        new_conf = max(0.0, min(1.0, old_conf + total_meta_mod))
        result["confidence"] = round(new_conf, 4)
        
        result["metacognition"] = {
            "trace_modifier": trace_mod,
            "regulation_modifier": reg_mod,
            "uncertainty_modifier": uq_mod,
            "total_modifier": round(total_meta_mod, 4),
        }
        
        result["version"] = self.VERSION
        
        try:
            store.write("ks36a_metacognition", {
                "trace_issues": result.get("reasoning_trace", {}).get("issues", 0),
                "regulation": result.get("self_regulation", {}).get("health", "?"),
                "calibration": result.get("uncertainty", {}).get("calibration", "?"),
                "meta_mod": total_meta_mod,
            })
        except (ValueError, Exception):
            pass
        
        return result
