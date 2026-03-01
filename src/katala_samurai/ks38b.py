from __future__ import annotations
"""
KS38b — Katala Samurai 38b: Hardware-Optimized Pipeline

KS38a + intelligent CPU/GPU workload distribution:
  - GPU (MPS): bootstrap sampling, batch similarity, lateral inhibition matrix
  - CPU: regex, graph analysis, string processing, external APIs
  - Parallel: independent solvers via ThreadPool

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os, os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks38a import KS38a, Claim
    from .stage_store import StageStore
    from .compute_router import (
        gpu_bootstrap_confidence, gpu_lateral_inhibition,
        device_info, get_device, benchmark
    )
    from .uncertainty_quantifier import quantify_uncertainty
except ImportError:
    from ks38a import KS38a, Claim
    from stage_store import StageStore
    from compute_router import (
        gpu_bootstrap_confidence, gpu_lateral_inhibition,
        device_info, get_device, benchmark
    )
    from uncertainty_quantifier import quantify_uncertainty

from typing import Dict, Any, Optional


class KS38b(KS38a):
    """KS38a + Hardware-Optimized Pipeline."""
    
    VERSION = "KS38b"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hw_info = device_info()
        self._gpu_ops = 0
        self._cpu_ops = 0
    
    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()
        
        t0 = time.time()
        
        # Run KS38a
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        
        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result
        
        # ═══ GPU-accelerated uncertainty (replace CPU bootstrap) ═══
        layer_scores = self._extract_layer_scores(result)
        if layer_scores and len(layer_scores) >= 2:
            gpu_result = gpu_bootstrap_confidence(layer_scores, n_samples=1000)
            
            old_unc = result.get("uncertainty", {})
            result["uncertainty"] = {
                "display": f"{gpu_result['mean']:.2f} +/- {gpu_result['std']:.2f}",
                "ci_95": [gpu_result["ci_low"], gpu_result["ci_high"]],
                "calibration": old_unc.get("calibration", "N/A"),
                "compute_device": gpu_result.get("device", "cpu"),
            }
            self._gpu_ops += 1
        
        # ═══ GPU-accelerated lateral inhibition ═══
        trace = result.get("trace", [])
        if trace and len(trace) >= 2:
            confs = [s.get("confidence", 0.5) for s in trace]
            # Find contradictions
            contradictions = []
            for i in range(len(trace)):
                for j in range(i+1, len(trace)):
                    ci, cj = confs[i], confs[j]
                    if (ci > 0.65 and cj < 0.35) or (ci < 0.35 and cj > 0.65):
                        contradictions.append((i, j))
            
            if contradictions:
                inhibited_confs = gpu_lateral_inhibition(confs, contradictions)
                result["lateral_inhibition"]["gpu_inhibited"] = True
                result["lateral_inhibition"]["contradictions"] = len(contradictions)
                self._gpu_ops += 1
            else:
                self._cpu_ops += 1
        
        t_end = time.time()
        
        result["version"] = self.VERSION
        result["hardware"] = {
            "device": self._hw_info.get("device", "cpu"),
            "gpu": self._hw_info.get("gpu", "none"),
            "gpu_ops": self._gpu_ops,
            "cpu_ops": self._cpu_ops,
        }
        
        if "pipeline" in result:
            result["pipeline"]["total_ms"] = int((t_end - t0) * 1000)
        
        return result
    
    def _extract_layer_scores(self, result: Dict) -> list:
        """Extract all confidence signals for GPU bootstrap."""
        scores = []
        scores.append(result.get("confidence", 0.5))
        
        l6 = result.get("L6_statistical", {})
        if l6.get("modifier", 0) != 0:
            scores.append(0.5 + l6["modifier"])
        
        l7 = result.get("L7_adversarial", {})
        if l7.get("modifier", 0) != 0:
            scores.append(0.5 + l7["modifier"])
        
        deep = result.get("deep_causal", {})
        adj = deep.get("adjustment", deep.get("confidence_adjustment", 0))
        if adj != 0:
            scores.append(0.5 + adj)
        
        for step in result.get("trace", []):
            if "confidence" in step:
                scores.append(step["confidence"])
        
        return scores
    
    def hw_benchmark(self) -> Dict[str, Any]:
        """Run hardware benchmark."""
        return benchmark()
    
    def hw_report(self) -> Dict[str, Any]:
        return {
            "info": self._hw_info,
            "gpu_ops": self._gpu_ops,
            "cpu_ops": self._cpu_ops,
            "ratio": f"{self._gpu_ops}:{self._cpu_ops}" if self._cpu_ops else "all_gpu",
        }
