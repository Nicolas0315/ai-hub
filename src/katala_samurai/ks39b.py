"""
KS39b — Katala Samurai 39b: Self-Other Boundary Model

KS39a + provenance tracking for all judgments.
Tracks whether each judgment originates from:
  - SELF: KS's own solver computation
  - DESIGNER: Youta's hardcoded thresholds/rules/matrices
  - EXTERNAL: LLM API, ConceptNet, OpenAlex
  - AMBIGUOUS: Can't determine

Measures fusion risk (designer-system boundary blur).

Design: Youta Hilono, 2026-02-28
"""

import sys as _sys, os as _os, time
_dir = _os.path.dirname(_os.path.abspath(__file__))
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)

try:
    from .ks39a import KS39a, Claim
    from .stage_store import StageStore
    from .self_other_boundary import SelfOtherBoundary, Origin
    from . import rust_bridge as rb
except ImportError:
    from ks39a import KS39a, Claim
    from stage_store import StageStore
    from self_other_boundary import SelfOtherBoundary, Origin
    import rust_bridge as rb

from typing import Dict, Any


class KS39b(KS39a):
    """KS39a + Self-Other Boundary tracking."""

    VERSION = "KS39b"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()

        boundary = SelfOtherBoundary()

        claim_text = claim.text if hasattr(claim, 'text') else str(claim)

        # ── Run KS39a pipeline ──
                # Filter out HTLF-specific kwargs before passing to KS33b (which doesn't accept **kwargs)
        _htlf_keys = {"source_text", "source_layer", "target_layer", "use_mock_parser", "qualia_mode", "responses_data", "physio_data"}
        parent_kwargs = {k: v for k, v in kwargs.items() if k not in _htlf_keys}
        result = super().verify(claim, store=store, skip_s28=skip_s28, **parent_kwargs)

        if isinstance(result, dict) and "results" in result:
            result["version"] = self.VERSION
            return result

        # ── Track provenance from result ──

        # 1) Solver outputs (SELF)
        stages = result.get("_meta", {}).get("stages", {})
        for stage_name, stage_data in stages.items():
            if stage_name.startswith("S") and stage_name[1:].isdigit():
                conf = 0.5
                if isinstance(stage_data, dict):
                    conf = stage_data.get("confidence", stage_data.get("score", 0.5))
                boundary.register("solver_output", Origin.SELF, conf,
                                  f"{stage_name} computation")

        # 2) Rust-computed features (SELF — computed, not designed)
        rust_data = result.get("rust", {})
        if rust_data.get("available"):
            boundary.register("rust_classify", Origin.SELF,
                              max(rust_data.get("type_scores", {}).values(), default=0.5),
                              "Rust regex classification")
            boundary.register("rust_neuro", Origin.SELF,
                              rust_data.get("modulated_confidence", 0.5),
                              "Rust neuromodulation")

        # 3) Designer-embedded decisions (DESIGNER)
        # These are Youta's choices hardcoded into the system
        boundary.register("threshold_0.65", Origin.DESIGNER, 0.65,
                          "VERIFIED threshold", "verdict_thresholds")
        boundary.register("threshold_0.35", Origin.DESIGNER, 0.35,
                          "UNVERIFIED threshold", "verdict_thresholds")

        plan = result.get("plan", {})
        if plan:
            boundary.register("planner_matrix", Origin.DESIGNER, 0.8,
                              "7x7 effectiveness matrix", "type_effectiveness_matrix")
            boundary.register("planner_strategy", Origin.DESIGNER, 0.7,
                              "strategy selection rules", "strategy_repertoire")

        # Predictive coding thresholds
        pred = result.get("prediction", {})
        if pred:
            boundary.register("surprise_threshold", Origin.DESIGNER, 0.15,
                              "Friston surprise cutoff", "surprise_threshold")

        # Anti-accumulation principle
        boundary.register("anti_accumulation", Origin.DESIGNER, 1.0,
                          "蓄積しない設計原則", "anti_accumulation")

        # 4) Claim-type patterns (DESIGNER — Youta chose the regex patterns)
        boundary.register("claim_patterns", Origin.DESIGNER,
                          max(rust_data.get("type_scores", {}).values(), default=0.5),
                          "regex pattern selection", "claim_patterns")

        # 5) External sources (EXTERNAL)
        # Check if any solver used external APIs
        for stage_name, stage_data in stages.items():
            if isinstance(stage_data, dict):
                src = stage_data.get("source", "")
                if any(ext in str(src).lower() for ext in
                       ["conceptnet", "openlex", "wordnet", "api", "web", "pdf"]):
                    boundary.register(stage_name, Origin.EXTERNAL,
                                      stage_data.get("confidence", 0.5),
                                      f"external: {src}")

        # 6) Confidence aggregation logic (AMBIGUOUS — mix of self+designer)
        final_conf = result.get("final_confidence", 0.5)
        boundary.register("confidence_aggregation", Origin.AMBIGUOUS, final_conf,
                          "weighted combination (self computation + designer weights)")

        # ── Analyze boundary ──
        boundary_analysis = boundary.analyze()

        # ── Inject into result ──
        result["version"] = self.VERSION
        result["self_other_boundary"] = boundary_analysis

        return result
