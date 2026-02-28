"""
KS39a — Katala Samurai 39a: Rust-Integrated Pipeline

KS38c + direct Rust acceleration via rust_bridge.
All hot paths route through ks_accel (Rust/PyO3) when available.

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks38b import KS38b, Claim
    from .stage_store import StageStore
    from .turbo_engine import TurboContext, PipelineState
    from . import rust_bridge as rb
except ImportError:
    from ks38b import KS38b, Claim
    from stage_store import StageStore
    from turbo_engine import TurboContext, PipelineState
    import rust_bridge as rb

from typing import Dict, Any


class KS39a(KS38b):
    """KS38b + Rust-accelerated hot paths."""

    VERSION = "KS39a"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.turbo = TurboContext()
        self._rust_status = rb.status()

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()

        state = PipelineState()
        state.time_start("total")

        claim_text = claim.text if hasattr(claim, 'text') else str(claim)

        # ═══ RUST: Precompute features (5.5μs in Rust vs ~50μs Python) ═══
        state.time_start("rust_features")
        features = rb.extract_features(claim_text)
        state.time_end("rust_features")

        # ═══ RUST: Classify claim type (6.7μs in Rust) ═══
        state.time_start("rust_classify")
        type_scores = rb.classify_claim(claim_text)
        primary_type = max(type_scores, key=type_scores.get) if type_scores else "unknown"
        state.time_end("rust_classify")

        # ═══ RUST: Check cache before full verify ═══
        state.time_start("rust_cache")
        cached = rb.cache_get("verify", claim_text)
        state.time_end("rust_cache")

        if cached and isinstance(cached, dict):
            cached["version"] = self.VERSION
            cached["cache_hit"] = True
            state.time_end("total")
            cached["pipeline"] = {
                "rust_features_ms": state._timing.get("rust_features_ms", 0),
                "rust_classify_ms": state._timing.get("rust_classify_ms", 0),
                "rust_cache_ms": state._timing.get("rust_cache_ms", 0),
                "total_ms": state._timing.get("total_ms", 0),
                "source": "rust_cache",
            }
            return cached

        # ═══ Core verify (KS38b) ═══
        state.time_start("core")
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)
        state.time_end("core")

        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result

        # ═══ RUST: Post-process with Rust-accelerated modules ═══

        # Lateral inhibition on solver confidences
        if "solver_confidences" in result:
            confs = result["solver_confidences"]
            if isinstance(confs, list) and len(confs) >= 2:
                state.time_start("rust_inhibit")
                result["solver_confidences_inhibited"] = rb.lateral_inhibit(confs)
                state.time_end("rust_inhibit")

        # Neuromodulation
        pred_error = result.get("prediction_error", {}).get("abs_error", 0.0)
        state.time_start("rust_neuro")
        neuro = rb.neuromodulate(primary_type, result.get("difficulty", "MEDIUM"),
                                 pred_error, 0.5)
        state.time_end("rust_neuro")

        # Apply neuro to final confidence
        raw_conf = result.get("final_confidence", 0.5)
        caution = neuro.get("caution", 1.0)
        modulated_conf = rb.neuro_apply_confidence(raw_conf, caution)

        # Cache result for future calls
        rb.cache_put("verify", claim_text, result)

        # ═══ Inject metadata ═══
        result["version"] = self.VERSION
        result["rust"] = {
            "available": rb.RUST_AVAILABLE,
            "type_scores": type_scores,
            "primary_type": primary_type,
            "features": {k: v for k, v in features.items()
                        if k in ("word_count", "has_numbers", "has_causal", "has_statistical")},
            "neuro": neuro,
            "modulated_confidence": modulated_conf,
            "cache_stats": rb.cache_stats(),
        }

        state.time_end("total")

        if "pipeline" not in result:
            result["pipeline"] = {}
        result["pipeline"].update({
            "rust_features_ms": state._timing.get("rust_features_ms", 0),
            "rust_classify_ms": state._timing.get("rust_classify_ms", 0),
            "rust_cache_ms": state._timing.get("rust_cache_ms", 0),
            "rust_inhibit_ms": state._timing.get("rust_inhibit_ms", 0),
            "rust_neuro_ms": state._timing.get("rust_neuro_ms", 0),
            "core_ms": state._timing.get("core_ms", 0),
            "total_ms": state._timing.get("total_ms", 0),
        })

        return result

    def rust_status(self) -> Dict[str, Any]:
        return {
            **self._rust_status,
            "cache": rb.cache_stats(),
        }
