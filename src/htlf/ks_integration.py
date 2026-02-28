"""HTLF ↔ KS integration interface (KS39b Self-Other Boundary aware)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .pipeline import LossVector

Layer = Literal["math", "formal_language", "natural_language", "music", "creative"]
ProvenanceOrigin = Literal["SELF", "DESIGNER", "EXTERNAL", "AMBIGUOUS"]


@dataclass(slots=True)
class HTLFResult:
    """Unified result payload for KS39b + HTLF scoring."""

    translation_fidelity: float
    loss_vector: LossVector
    profile_type: str
    confidence: float
    ks39b_confidence: float
    measurement_provenance: dict[str, ProvenanceOrigin]
    provenance_distribution: dict[str, float]
    measurement_reliability: float
    self_other_boundary: dict[str, Any]
    final_score: float
    source_layer: Layer
    target_layer: Layer


AXIS_PRIOR: dict[tuple[Layer, Layer], tuple[float, float, float]] = {
    ("math", "formal_language"): (0.95, 0.80, 0.05),
    ("math", "natural_language"): (0.70, 0.50, 0.05),
    ("music", "natural_language"): (0.40, 0.30, 0.10),
    ("music", "creative"): (0.30, 0.40, 0.50),
    ("formal_language", "music"): (0.05, 0.05, 0.00),
    ("creative", "natural_language"): (0.50, 0.40, 0.15),
}


class HTLFScorer:
    """KS39bの信頼性にHTLF翻訳忠実度をSelf-Other Boundary考慮で統合。"""

    def __init__(self, alpha: float = 0.7, beta: float = 0.3) -> None:
        if alpha < 0 or beta < 0 or (alpha + beta) <= 0:
            raise ValueError("alpha/beta must be non-negative and not both zero")
        norm = alpha + beta
        self.alpha = alpha / norm
        self.beta = beta / norm

    def evaluate(
        self,
        claim_text: str,
        source_text: str | None = None,
        source_layer: Layer | None = None,
        target_layer: Layer | None = None,
        ks39b_result: dict[str, Any] | None = None,
        ks39b_confidence: float | None = None,
        use_mock_parser: bool = False,
    ) -> HTLFResult:
        if not claim_text.strip():
            raise ValueError("claim_text must not be empty")

        inferred_target = target_layer or self.detect_layer(claim_text)

        if source_text and source_text.strip():
            inferred_source = source_layer or self.detect_layer(source_text)
            from .pipeline import run_pipeline

            lv = run_pipeline(source_text=source_text, target_text=claim_text, use_mock_parser=use_mock_parser)
            fidelity = self._clamp01(1.0 - lv.total_loss)
            conf = 0.85
        else:
            inferred_source = source_layer or self._infer_source_layer_from_claim(claim_text, inferred_target)
            lv = self._estimate_loss_vector(inferred_source, inferred_target)
            fidelity = self._clamp01(1.0 - lv.total_loss)
            conf = 0.55

        measurement_provenance = self._measurement_provenance(lv)
        provenance_distribution = self._distribution_from_tags(measurement_provenance)
        measurement_reliability = self._measurement_reliability(provenance_distribution)

        boundary = (ks39b_result or {}).get("self_other_boundary") if ks39b_result else {}
        base_ks39b = self._extract_ks39b_confidence(ks39b_result, ks39b_confidence, claim_text)

        # final = α × ks39b_confidence + β × translation_fidelity × measurement_reliability
        final_score = self._clamp01(
            self.alpha * base_ks39b + self.beta * fidelity * measurement_reliability
        )

        return HTLFResult(
            translation_fidelity=fidelity,
            loss_vector=lv,
            profile_type=lv.profile_type,
            confidence=conf,
            ks39b_confidence=base_ks39b,
            measurement_provenance=measurement_provenance,
            provenance_distribution=provenance_distribution,
            measurement_reliability=measurement_reliability,
            self_other_boundary=boundary if isinstance(boundary, dict) else {},
            final_score=final_score,
            source_layer=inferred_source,
            target_layer=inferred_target,
        )

    def evaluate_dict(self, *args: object, **kwargs: object) -> dict[str, object]:
        return asdict(self.evaluate(*args, **kwargs))

    # Public interface for KS40 integration
    def detect_layer(self, text: str) -> Layer:
        return self._infer_layer(text)

    def estimate_loss_vector(self, source_layer: Layer, target_layer: Layer) -> "LossVector":
        return self._estimate_loss_vector(source_layer, target_layer)

    def infer_source_layer_from_claim(self, claim_text: str, target: Layer) -> Layer:
        return self._infer_source_layer_from_claim(claim_text, target)

    def check_multilayer_consistency(self, texts: list[str]) -> dict[str, object]:
        """Heuristic cross-layer consistency check for KS40b."""
        non_empty = [t for t in texts if isinstance(t, str) and t.strip()]
        if not non_empty:
            return {"layer_set": [], "consistency_score": 0.0, "contradictions": []}

        layers = [self.detect_layer(t) for t in non_empty]
        has_neg = any(re.search(r"\b(not|never|no|cannot|isn't|aren't|ない|ではない)\b", t.lower()) for t in non_empty)
        has_pos = any(re.search(r"\b(is|are|can|will|does|できる|である|なる)\b", t.lower()) for t in non_empty)

        contradictions: list[dict[str, str]] = []
        if len(set(layers)) > 1 and has_neg and has_pos:
            contradictions.append({
                "type": "cross_layer_polarity_conflict",
                "detail": "positive/negative assertion markers co-exist across layers",
            })

        token_sets = [set(re.findall(r"[\w\-\u3040-\u30ff\u4e00-\u9faf]+", t.lower())) for t in non_empty]
        if len(token_sets) >= 2:
            inter = set.intersection(*token_sets)
            union = set.union(*token_sets)
            overlap = len(inter) / max(1, len(union))
        else:
            overlap = 1.0

        score = max(0.0, min(1.0, 0.8 * overlap + (0.2 if not contradictions else 0.0)))
        return {
            "layer_set": sorted(set(layers)),
            "consistency_score": round(score, 4),
            "contradictions": contradictions,
        }

    def _extract_ks39b_confidence(
        self,
        ks39b_result: dict[str, Any] | None,
        ks39b_confidence: float | None,
        claim_text: str,
    ) -> float:
        if ks39b_confidence is not None:
            return self._clamp01(ks39b_confidence)
        if ks39b_result and isinstance(ks39b_result, dict):
            if "final_confidence" in ks39b_result:
                return self._clamp01(float(ks39b_result.get("final_confidence", 0.5)))
            if "confidence" in ks39b_result:
                return self._clamp01(float(ks39b_result.get("confidence", 0.5)))
        return self._clamp01(self._estimate_ks39b_confidence(claim_text))

    def _measurement_provenance(self, lv: LossVector) -> dict[str, ProvenanceOrigin]:
        parser_backend = getattr(lv, "parser_backend", "llm")
        context_backend = getattr(lv, "context_backend", "llm_reader")
        qualia_backend = getattr(lv, "qualia_backend", "online_approximation")
        matcher_backend = getattr(lv, "matcher_backend", "sentence_transformers")

        if qualia_backend in {"behavioral_experiment", "physiological_proxy"}:
            qualia_origin: ProvenanceOrigin = "SELF"
        elif qualia_backend == "online_approximation":
            qualia_origin = "DESIGNER"
        else:
            qualia_origin = "EXTERNAL"

        return {
            "R_struct": "SELF" if parser_backend == "mock" else "EXTERNAL",
            "R_context": "SELF" if context_backend == "heuristic" else "EXTERNAL",
            "R_qualia": qualia_origin,
            "matcher": "SELF" if matcher_backend == "sentence_transformers" else ("EXTERNAL" if matcher_backend == "api" else "SELF"),
        }

    def _distribution_from_tags(self, tags: dict[str, ProvenanceOrigin]) -> dict[str, float]:
        counts = {"SELF": 0, "DESIGNER": 0, "EXTERNAL": 0, "AMBIGUOUS": 0}
        for origin in tags.values():
            counts[origin] = counts.get(origin, 0) + 1
        total = max(1, sum(counts.values()))
        return {k: v / total for k, v in counts.items() if v > 0}

    def _measurement_reliability(self, distribution: dict[str, float]) -> float:
        self_w = distribution.get("SELF", 0.0)
        ext_w = distribution.get("EXTERNAL", 0.0)
        amb_w = distribution.get("AMBIGUOUS", 0.0)
        des_w = distribution.get("DESIGNER", 0.0)
        # SELF寄りほど高信頼、EXTERNAL/AMBIGUOUSで減衰
        reliability = 0.25 + 0.85 * self_w - 0.35 * ext_w - 0.20 * amb_w - 0.10 * des_w
        return self._clamp01(reliability)

    def _infer_layer(self, text: str) -> Layer:
        t = text.strip().lower()

        if re.search(r"(∑|∫|∀|∃|→|\btheorem\b|\blemma\b|\bproof\b)", t) or re.search(r"\b\d+\s*[=<>]\s*\d+", t):
            return "math"
        if "```" in text or re.search(r"\b(def |class |return |import |SELECT |FROM |WHERE)\b", text):
            return "formal_language"
        if re.search(r"\b(chord|tempo|melody|harmony|rhythm|crescendo|frisson)\b", t):
            return "music"
        if re.search(r"\b(color|texture|composition|canvas|aesthetic|installation|brushstroke)\b", t):
            return "creative"
        return "natural_language"

    def _infer_source_layer_from_claim(self, claim_text: str, target: Layer) -> Layer:
        t = claim_text.lower()
        if target == "natural_language" and re.search(r"\[(\d+)\]|doi:|arxiv|p\s*[<=>]", t):
            return "math"
        if target == "natural_language" and "```" in claim_text:
            return "formal_language"
        return target

    def _estimate_loss_vector(self, source_layer: Layer, target_layer: Layer) -> LossVector:
        if source_layer == target_layer:
            r_struct, r_context, r_qualia = 0.95, 0.90, 0.80
        else:
            pair = (source_layer, target_layer)
            if pair in AXIS_PRIOR:
                r_struct, r_context, r_qualia = AXIS_PRIOR[pair]
            elif (target_layer, source_layer) in AXIS_PRIOR:
                a, b, c = AXIS_PRIOR[(target_layer, source_layer)]
                r_struct, r_context, r_qualia = a * 0.95, b * 0.90, c * 0.85
            else:
                r_struct, r_context, r_qualia = 0.45, 0.35, 0.20

        total = 1.0 - self._clamp01((r_struct + r_context + r_qualia) / 3.0)
        if r_qualia >= max(r_struct, r_context):
            profile = "P11_qualia_sum"
        elif r_struct >= r_context:
            profile = "P01_struct_context_sum"
        else:
            profile = "P09_context_sum"

        return LossVector(
            r_struct=self._clamp01(r_struct),
            r_context=self._clamp01(r_context),
            r_qualia=self._clamp01(r_qualia),
            total_loss=self._clamp01(total),
            profile_type=profile,
            parser_backend="mock",
            context_backend="heuristic",
            qualia_backend="online_approximation",
            matcher_backend="sentence_transformers",
        )

    def _estimate_ks39b_confidence(self, claim_text: str) -> float:
        text = claim_text.lower()
        score = 0.52

        evidence_hits = len(re.findall(r"(doi:|arxiv|http|https|\[(\d+)\]|according to)", text))
        score += min(0.20, evidence_hits * 0.04)

        if re.search(r"\b(always|never|100%|guaranteed|絶対|必ず)\b", text):
            score -= 0.12
        if re.search(r"\b(may|might|suggests|possibly|可能性|示唆)\b", text):
            score += 0.04
        if re.search(r"\b(n\s*=\s*\d+|p\s*[<=>]|confidence interval|95%)\b", text):
            score += 0.08

        return self._clamp01(score)

    @staticmethod
    def _clamp01(v: float) -> float:
        return max(0.0, min(1.0, float(v)))
