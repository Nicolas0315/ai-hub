"""
Katala_Quantum_02b (KQ02b)

KS-oriented upgrade over KQ02a:
- A: unified translation-loss metric (`kq_translation_loss`)
- B: KS40/KS44 style logic PORTED (no runtime call/import to ks40b/ks44)
- C: fixed translation_loss schema in outputs
- D: loss-aware assertiveness gate
"""
from __future__ import annotations

import re
from typing import Any

from .katala_quantum_02a import Katala_Quantum_02a

# Ported from ks44-style constants (not imported at runtime)
PRETRANSLATION_ACCURACY_LOSS_PCT = 10.0
SAOT_ANCHOR_RETENTION_TARGET = 0.95

LAYER_PATTERNS: dict[str, list[str]] = {
    "math": [r"[∀∃∈∉⊆⊂⇒⇔¬]", r"\b(theorem|lemma|proof)\b"],
    "formal_language": [r"\b(grammar|syntax|semantics|logic)\b", r"::=|->"],
    "natural_language": [r"[A-Za-z]{3,}"],
    "music": [r"\b(chord|interval|melody|harmony|rhythm)\b", r"[A-G]m?(?:7|9|11|13)?"],
    "creative": [r"\b(poem|story|novel|metaphor|creative)\b"],
}
LAYER_DETECTION_THRESHOLD = 1


class Katala_Quantum_02b(Katala_Quantum_02a):
    SYSTEM_MODEL: str = "Katala_Quantum_02b"
    ALIAS: str = "KQ02b"

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "kq_translation_loss_layer": True,
            "translation_loss_schema_fixed": True,
            "assertive_loss_gate": True,
        })
        return s

    @staticmethod
    def _detect_layer_from_features(text: str | None) -> str:
        if not text:
            return "natural_language"
        raw = str(text)
        low = raw.lower()
        scores = {k: 0 for k in LAYER_PATTERNS}
        for layer, pats in LAYER_PATTERNS.items():
            for p in pats:
                target = raw if any(c.isupper() for c in p if c.isalpha()) else low
                if re.search(p, target):
                    scores[layer] += 1
        winner = max(scores, key=lambda k: scores[k])
        return winner if scores[winner] >= LAYER_DETECTION_THRESHOLD else "natural_language"

    def _compute_translation_loss(
        self,
        text: str,
        result: dict[str, Any],
        paper_stats: dict[str, Any],
        html_pipe: dict[str, Any],
        sweep: dict[str, Any],
    ) -> dict[str, Any]:
        # A) compression loss (KQ context compression proxy)
        compression_ratio = float(result.get("context_compression_ratio", 1.0) or 1.0)
        compression_loss = min(1.0, abs(1.0 - compression_ratio))

        # B) citation grounding loss (refs + html fulltext hit quality)
        refs_count = float((paper_stats or {}).get("refs_count", 0))
        html_hits = float((html_pipe or {}).get("html_hit_count", 0))
        grounding_strength = min(1.0, refs_count / 40.0) * 0.6 + min(1.0, html_hits / 12.0) * 0.4
        citation_grounding_loss = 1.0 - grounding_strength

        # C) cross-language loss (ported, estimated mode)
        has_cjk = bool(re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text or ""))
        has_latin = bool(re.search(r"[A-Za-z]", text or ""))
        if has_cjk and has_latin:
            # SAOT-like reduction from pretranslation baseline
            cross_lang_loss = max(0.0, PRETRANSLATION_ACCURACY_LOSS_PCT / 100.0 * (1.0 - SAOT_ANCHOR_RETENTION_TARGET))
        elif has_cjk or has_latin:
            cross_lang_loss = 0.03
        else:
            cross_lang_loss = 0.08

        # D) decode consistency loss from hierarchical continuity proxy
        hdec = ((result.get("reason") or {}).get("kq_hierarchical_decode") or {})
        continuity = float(hdec.get("continuity_factor", 0.5) or 0.5)
        decode_consistency_loss = 1.0 - max(0.0, min(1.0, continuity))

        # E) readability execution loss from sweep
        pdf_target = float((sweep or {}).get("pdf_target", 1) or 1)
        text_target = float((sweep or {}).get("text_target", 1) or 1)
        pdf_read = float((sweep or {}).get("pdf_read_count", 0) or 0)
        text_read = float((sweep or {}).get("text_read_count", 0) or 0)
        read_cov = min(1.0, (pdf_read / max(1.0, pdf_target)) * 0.5 + (text_read / max(1.0, text_target)) * 0.5)
        readability_loss = 1.0 - read_cov

        # Weighted aggregate (KS-like measured/estimated hybrid)
        score = self._clamp(
            compression_loss * 0.22
            + citation_grounding_loss * 0.30
            + cross_lang_loss * 0.16
            + decode_consistency_loss * 0.18
            + readability_loss * 0.14
        )

        source_layer = self._detect_layer_from_features(text)
        target_layer = "natural_language"

        # confidence: more refs and html hits => higher confidence in measured estimate
        confidence = self._clamp(0.45 + min(0.35, refs_count / 120.0) + min(0.20, html_hits / 20.0))

        return {
            "mode": "measured" if refs_count > 0 else "estimated",
            "score": round(score, 4),
            "components": {
                "compression_loss": round(compression_loss, 4),
                "citation_grounding_loss": round(citation_grounding_loss, 4),
                "cross_lang_loss": round(cross_lang_loss, 4),
                "decode_consistency_loss": round(decode_consistency_loss, 4),
                "readability_loss": round(readability_loss, 4),
            },
            "confidence": round(confidence, 4),
            "auto_detected_layers": {
                "source": source_layer,
                "target": target_layer,
            },
        }

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if not isinstance(r, dict):
            return r

        text = ""
        if args:
            c = args[0]
            text = c.text if hasattr(c, "text") else str(c)
        elif "claim" in kwargs:
            c = kwargs.get("claim")
            text = c.text if hasattr(c, "text") else str(c)

        p = r.get("paper_stats") or {}
        htmlp = r.get("html_first_pipeline") or {}
        sweep = r.get("paper_read_sweep") or {}

        tl = self._compute_translation_loss(text, r, p, htmlp, sweep)

        # C: fixed schema
        r["translation_loss"] = tl
        r["kq_translation_loss"] = tl

        # D: loss-aware assertiveness gate
        loss_score = float(tl.get("score", 0.0) or 0.0)
        assertive_allowed = loss_score <= 0.24
        r["translation_loss_gate"] = {
            "enabled": True,
            "threshold": 0.24,
            "assertive_allowed": assertive_allowed,
        }

        if not assertive_allowed:
            # suppress over-assertive outcomes
            cur = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
            capped = min(cur, 0.64)
            r["final_score"] = capped
            r["confidence"] = capped
            if r.get("verdict") in {"SUPPORT", "LEAN_SUPPORT"}:
                r["verdict"] = "UNCERTAIN"

        fw = r.get("fusion_weights") or {}
        fw["translation_loss_score"] = round(loss_score, 4)
        fw["translation_loss_penalty"] = round(min(0.10, loss_score * 0.12), 4)
        r["fusion_weights"] = fw

        r["kq_revision"] = "02b-r1"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        return r


KQ02b = Katala_Quantum_02b

__all__ = ["Katala_Quantum_02b", "KQ02b"]
