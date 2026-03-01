"""
KS40a — Katala Samurai 40a: Holographic Translation Loss Framework (HTLF).

Extends KS39b with cross-layer translation loss measurement.
Measures information loss when claims traverse symbolic system boundaries
(mathematics ↔ formal language ↔ natural language ↔ music ↔ creative arts).

Architecture:
  KS40a inherits KS39b (Self-Other Boundary with provenance tracking)
  and adds HTLF pipeline integration via HTLFScorer.

3-axis model:
  - R_struct: structural preservation (graph topology)
  - R_context: contextual preservation (TF-IDF / embedding similarity)
  - R_qualia: experiential quality preservation (behavioral proxy)

5-axis extension (KS40c):
  - R_cultural: cultural frame translation loss (Quine indeterminacy)
  - R_temporal: temporal context drift (domain-specific half-life decay)

12 loss profiles: 6 axis combinations × 2 composition modes
(weighted sum vs product). Profile auto-classification based on
source→target layer pair.

Holographic principle analogy:
  boundary (surface expression) encodes bulk (deep meaning).
  Translation loss = information that fails to survive the boundary crossing.

Provenance integration:
  HTLF measurement reliability feeds back into KS39b's self-other
  boundary origin_distribution, increasing SELF/EXTERNAL/DESIGNER
  weights based on translation fidelity confidence.

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
    """KS39b + HTLF translation-loss measurement.

    Adds cross-layer translation loss to the verification pipeline.
    When source_text is provided, runs the full HTLF pipeline
    (parser → matcher → scorer → classifier). Otherwise, estimates
    loss from inferred source/target layer pair using AXIS_PRIOR.

    Attributes:
        _htlf: HTLFScorer instance for loss evaluation.
    """

    VERSION = "KS40a"

    # HTLFScorer weights: alpha controls structural vs contextual balance
    HTLF_ALPHA = 0.7  # R_struct weight in combined score
    HTLF_BETA = 0.3   # R_context weight in combined score

    # Provenance boost increments for HTLF integration
    PROVENANCE_SELF_BOOST = 0.03
    PROVENANCE_EXTERNAL_BOOST = 0.02
    PROVENANCE_DESIGNER_BOOST = 0.01

    def __init__(self, **kwargs):
        """Initialize KS40a with HTLF scorer.

        Args:
            **kwargs: Passed to KS39b.__init__().
        """
        super().__init__(**kwargs)
        self._htlf = HTLFScorer(alpha=self.HTLF_ALPHA, beta=self.HTLF_BETA)

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        """Verify claim with HTLF translation loss measurement.

        Extends KS39b.verify() by:
        1. Running the HTLF pipeline (if source_text provided) or
           estimating loss from layer pair inference
        2. Computing translation fidelity and profile classification
        3. Feeding measurement reliability into provenance tracking

        Args:
            claim: Claim object or text string.
            store: StageStore for intermediate results (created if None).
            skip_s28: Skip S28 solver (default True for speed).
            **kwargs: HTLF-specific params:
                source_text: Original text before translation.
                source_layer: Source symbolic layer (e.g. "mathematics").
                target_layer: Target symbolic layer (e.g. "natural_language").
                use_mock_parser: Use mock HTLF parser for testing.
                qualia_mode: "online"|"behavioral"|"physio".
                responses_data: Behavioral response data for R_qualia.
                physio_data: Physiological data for R_qualia.

        Returns:
            dict with KS39b results + 'translation_loss' section.
        """
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
                "r_cultural": getattr(lv, "r_cultural", None),
                "r_cultural_indeterminacy": getattr(lv, "r_cultural_indeterminacy", None),
                "r_temporal": getattr(lv, "r_temporal", None),
                "r_temporal_indeterminacy": getattr(lv, "r_temporal_indeterminacy", None),
            },
            "cultural_detail": getattr(lv, "cultural_detail", None),
            "temporal_detail": getattr(lv, "temporal_detail", None),
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
            origin_dist[Origin.SELF.value] = round(
                origin_dist.get(Origin.SELF.value, 0.0) + self.PROVENANCE_SELF_BOOST, 3
            )
            origin_dist[Origin.EXTERNAL.value] = round(
                origin_dist.get(Origin.EXTERNAL.value, 0.0) + self.PROVENANCE_EXTERNAL_BOOST, 3
            )
            origin_dist[Origin.DESIGNER.value] = round(
                origin_dist.get(Origin.DESIGNER.value, 0.0) + self.PROVENANCE_DESIGNER_BOOST, 3
            )
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
