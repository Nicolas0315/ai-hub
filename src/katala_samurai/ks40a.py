"""
KS40a — Katala Samurai 40a: Holographic Translation Loss Framework

KS39b + cross-layer translation loss measurement.
Measures information loss when claims traverse symbolic system boundaries
(mathematics ↔ formal language ↔ natural language ↔ music ↔ creative arts).

3-axis model:
  - R_struct: structural preservation
  - R_context: contextual preservation
  - R_qualia: experiential quality preservation

12 loss profiles (6 axis combinations × 2 composition modes).
Holographic principle analogy: boundary (surface expression) → bulk (deep meaning).

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma (OpenClaw AI)
"""

import sys as _sys, os as _os

_dir = _os.path.dirname(_os.path.abspath(__file__))
_src_dir = _os.path.dirname(_dir)
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

try:
    from .ks39b import KS39b, Claim
    from .stage_store import StageStore
    from ..htlf.pipeline import run_pipeline
    from ..htlf.ks_integration import HTLFScorer
    from .self_other_boundary import Origin
except ImportError:
    from ks39b import KS39b, Claim
    from stage_store import StageStore
    from htlf.pipeline import run_pipeline
    from htlf.ks_integration import HTLFScorer
    from self_other_boundary import Origin


class KS40a(KS39b):
    """KS39b + HTLF translation-loss measurement."""

    VERSION = "KS40a"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._htlf = HTLFScorer(alpha=0.7, beta=0.3)

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        if store is None:
            store = StageStore()

        source_text = kwargs.get("source_text")
        source_layer = kwargs.get("source_layer")
        target_layer = kwargs.get("target_layer")
        use_mock_parser = bool(kwargs.get("use_mock_parser", False))

        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)

        if not isinstance(result, dict) or "results" in result:
            if isinstance(result, dict):
                result["version"] = self.VERSION
            return result

        claim_text = claim.text if hasattr(claim, "text") else str(claim)

        # Run HTLF pipeline directly when source_text is available (explicit requirement).
        if source_text and str(source_text).strip():
            lv = run_pipeline(
                source_text=str(source_text),
                target_text=claim_text,
                use_mock_parser=use_mock_parser,
                qualia_mode=str(kwargs.get("qualia_mode", "online")),
                responses_data=kwargs.get("responses_data"),
                physio_data=kwargs.get("physio_data"),
            )
        else:
            inferred_target = target_layer or self._htlf.detect_layer(claim_text)
            inferred_source = self._htlf.infer_source_layer_from_claim(claim_text, inferred_target)
            lv = self._htlf.estimate_loss_vector(inferred_source, inferred_target)

        h = self._htlf.evaluate(
            claim_text=claim_text,
            source_text=source_text,
            source_layer=source_layer,
            target_layer=target_layer,
            ks39b_result=result,
            ks39b_confidence=result.get("final_confidence"),
            use_mock_parser=use_mock_parser,
        )

        translation_loss = {
            "loss_vector": {
                "r_struct": lv.r_struct,
                "r_context": lv.r_context,
                "r_qualia": lv.r_qualia,
            },
            "profile_type": h.profile_type,
            "translation_fidelity": h.translation_fidelity,
            "measurement_reliability": {
                "score": h.measurement_reliability,
                "provenance": h.measurement_provenance,
                "distribution": h.provenance_distribution,
            },
            "source_layer": h.source_layer,
            "target_layer": h.target_layer,
            "total_loss": lv.total_loss,
        }

        boundary = result.get("self_other_boundary", {})
        if isinstance(boundary, dict):
            bd = dict(boundary)
            origin_dist = dict(bd.get("origin_distribution", {}))
            origin_dist[Origin.SELF.value] = round(origin_dist.get(Origin.SELF.value, 0.0) + 0.03, 3)
            origin_dist[Origin.EXTERNAL.value] = round(origin_dist.get(Origin.EXTERNAL.value, 0.0) + 0.02, 3)
            origin_dist[Origin.DESIGNER.value] = round(origin_dist.get(Origin.DESIGNER.value, 0.0) + 0.01, 3)
            total = sum(origin_dist.values()) or 1.0
            bd["origin_distribution"] = {k: round(v / total, 3) for k, v in origin_dist.items()}

            htlf_prov = {
                "module": "HTLF",
                "measurement_provenance": h.measurement_provenance,
                "measurement_reliability": h.measurement_reliability,
                "translation_profile": h.profile_type,
            }
            bd["htlf_provenance"] = htlf_prov
            result["self_other_boundary"] = bd

        result["version"] = self.VERSION
        result["translation_loss"] = translation_loss
        return result
