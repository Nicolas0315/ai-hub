"""
KS39a — Katala Samurai 39a: Self-Other Boundary

KS38c + Self-Other Boundary Model:
  1) Provenance Tracker: tags every judgment with SELF/DESIGNER/EXTERNAL/INHERITED
  2) Boundary Detector: fusion risk assessment (FUSED/BLURRED/PARTIAL/CLEAR)
  3) Attribution Auditor: post-hoc "who decided the final verdict?"

Addresses KS38c structural deficiency: no distinction between
designer cognition and system's own processing.

Design request: Youta Hilono, 2026-02-28
Implementation: Shirokuma, 2026-02-28
"""

import sys as _sys, os as _os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks38c import KS38c, Claim
    from .stage_store import StageStore
    from .self_other_boundary import ProvenanceTracker, BoundaryDetector, AttributionAuditor, Origin
except ImportError:
    from ks38c import KS38c, Claim
    from stage_store import StageStore
    from self_other_boundary import ProvenanceTracker, BoundaryDetector, AttributionAuditor, Origin

from typing import Dict, Any, Optional


class KS39a(KS38c):
    """KS38c + Self-Other Boundary Model."""
    
    VERSION = "KS39a"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._provenance = None  # Created per-verification
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        # Fresh provenance tracker per verification
        self._provenance = ProvenanceTracker()
        boundary = BoundaryDetector(self._provenance)
        auditor = AttributionAuditor(self._provenance)
        
        t0 = time.time()
        
        # Record: architectural decisions are DESIGNER origin
        self._provenance.record("anti_accumulation", 1.0,
                                "Design principle: ephemeral > accumulated", Origin.DESIGNER)
        self._provenance.record("layer_priority", 1.0,
                                "L1-L7 ordering defined by designer", Origin.DESIGNER)
        self._provenance.record("inhibition_params", 1.0,
                                "Lateral inhibition parameters from neuroscience model", Origin.DESIGNER)
        
        # Core verification (KS38c)
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # Record solver-level provenance from trace
        for step in result.get("trace", []):
            stage = step.get("stage", step.get("layer", "unknown"))
            conf = step.get("confidence", 0.5)
            detail = str(step.get("detail", step.get("reason", "")))[:200]
            self._provenance.record(stage, conf, detail)
        
        # Record predictive coding (mixed: DESIGNER architecture + SELF computation)
        pred = result.get("predictive_coding", {})
        if pred:
            self._provenance.record("predictive_coding_prediction", 
                                    pred.get("predicted", 0.5),
                                    f"Predicted before verify", Origin.SELF)
            if pred.get("surprising"):
                self._provenance.record("prediction_surprise",
                                        pred.get("actual", 0.5),
                                        "Prediction error detected", Origin.SELF)
        
        # Record neuromodulation state
        neuro = result.get("neuromodulation", {})
        if neuro:
            self._provenance.record("neuromod_state",
                                    neuro.get("gain", 1.0),
                                    f"Sensitivity: {neuro.get('sensitivity', 'N/A')}", Origin.SELF)
        
        # Record reason space coherence
        rs = result.get("reason_space", {})
        if rs:
            self._provenance.record("reason_space_coherence",
                                    rs.get("coherence", 0.5),
                                    f"Conflicts: {rs.get('conflicts', 0)}", Origin.SELF)
        
        # === BOUNDARY ANALYSIS ===
        fusion = boundary.detect_fusion()
        
        final_verdict = result.get("verdict", "UNKNOWN")
        final_conf = result.get("confidence", 0.5)
        attribution = auditor.audit(final_verdict, final_conf)
        
        t_end = time.time()
        
        # Assemble
        result["version"] = self.VERSION
        result["self_other_boundary"] = {
            "provenance_summary": self._provenance.summary(),
            "fusion": fusion,
            "attribution": attribution,
        }
        
        if "pipeline" in result:
            result["pipeline"]["boundary_ms"] = int((t_end - t0) * 1000)
        
        return result
