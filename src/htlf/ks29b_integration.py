"""HTLF ↔ KS29B integration interface (Phase 3)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

from .pipeline import LossVector, run_pipeline

Layer = Literal["math", "formal_language", "natural_language", "music", "creative"]


@dataclass(slots=True)
class HTLFResult:
    """Unified result payload for KS29B + HTLF scoring."""

    translation_fidelity: float
    loss_vector: LossVector
    profile_type: str
    confidence: float
    ks29b_score: float
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
    """KS29Bの信頼性スコアにHTLF翻訳忠実度を統合。"""

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
        ks29b_score: float | None = None,
    ) -> HTLFResult:
        """Evaluate one claim with optional source text.

        Returns HTLFResult with:
        - translation_fidelity: float (0-1)
        - loss_vector: LossVector
        - profile_type: str
        - confidence: float
        """
        if not claim_text.strip():
            raise ValueError("claim_text must not be empty")

        inferred_target = target_layer or self._infer_layer(claim_text)

        if source_text and source_text.strip():
            inferred_source = source_layer or self._infer_layer(source_text)
            lv = run_pipeline(source_text=source_text, target_text=claim_text)
            fidelity = self._clamp01(1.0 - lv.total_loss)
            conf = 0.85
        else:
            inferred_source = source_layer or self._infer_source_layer_from_claim(claim_text, inferred_target)
            lv = self._estimate_loss_vector(inferred_source, inferred_target)
            fidelity = self._clamp01(1.0 - lv.total_loss)
            conf = 0.55

        base_ks29b = self._clamp01(ks29b_score if ks29b_score is not None else self._estimate_ks29b_score(claim_text))
        final_score = self._clamp01(self.alpha * base_ks29b + self.beta * fidelity)

        return HTLFResult(
            translation_fidelity=fidelity,
            loss_vector=lv,
            profile_type=lv.profile_type,
            confidence=conf,
            ks29b_score=base_ks29b,
            final_score=final_score,
            source_layer=inferred_source,
            target_layer=inferred_target,
        )

    def evaluate_dict(self, *args: object, **kwargs: object) -> dict[str, object]:
        """JSON-friendly helper."""
        return asdict(self.evaluate(*args, **kwargs))

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
                # reverse direction slightly degrades context/qualia
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
        )

    def _estimate_ks29b_score(self, claim_text: str) -> float:
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
