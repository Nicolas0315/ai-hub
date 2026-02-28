"""
KS40b — Katala Samurai 40b: HTLF Extended Multi-Layer Consistency

KS40a +
- 5-layer automatic detection from text features
- Estimated-loss mode when source text is missing
- Multi-layer consistency checks for cross-representation contradictions

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma (OpenClaw AI)
"""

import re
import sys as _sys, os as _os
from typing import Dict, List

_dir = _os.path.dirname(_os.path.abspath(__file__))
_src_dir = _os.path.dirname(_dir)
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

try:
    from .ks40a import KS40a
except ImportError:
    from ks40a import KS40a


class KS40b(KS40a):
    """KS40a with auto-layer detection and consistency diagnostics."""

    VERSION = "KS40b"

    _LAYER_PATTERNS: Dict[str, List[str]] = {
        "math": [r"∑", r"∫", r"∀", r"∃", r"\btheorem\b", r"\blemma\b", r"\bproof\b", r"\bn\s*=\s*\d+\b"],
        "formal_language": [r"```", r"\bdef\s+", r"\bclass\s+", r"\breturn\b", r"\bimport\b", r"\bSELECT\b", r"\bFROM\b", r"\bWHERE\b"],
        "natural_language": [r"\b(therefore|because|however|according to|つまり|なぜなら)\b"],
        "music": [r"\b(chord|tempo|melody|harmony|rhythm|crescendo|timbre)\b"],
        "creative": [r"\b(color|texture|composition|canvas|aesthetic|installation|brushstroke)\b"],
    }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        claim_text = claim.text if hasattr(claim, "text") else str(claim)
        source_text = kwargs.get("source_text")

        auto_target = self._detect_layer_from_features(claim_text)
        auto_source = self._detect_layer_from_features(source_text) if source_text else None

        kwargs = dict(kwargs)
        kwargs.setdefault("target_layer", auto_target)
        kwargs.setdefault("source_layer", auto_source or self._htlf.infer_source_layer_from_claim(claim_text, auto_target))

        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)

        if not isinstance(result, dict) or "results" in result:
            if isinstance(result, dict):
                result["version"] = self.VERSION
            return result

        no_source_mode = not (source_text and str(source_text).strip())
        consistency = self._check_multilayer_consistency(claim_text, source_text)

        result.setdefault("translation_loss", {})
        result["translation_loss"]["mode"] = "estimated" if no_source_mode else "measured"
        result["translation_loss"]["auto_detected_layers"] = {
            "source": kwargs.get("source_layer"),
            "target": kwargs.get("target_layer"),
        }

        result["multi_layer_consistency"] = consistency
        result["version"] = self.VERSION
        return result

    def _detect_layer_from_features(self, text: str | None) -> str:
        if not text:
            return "natural_language"

        raw = str(text)
        lowered = raw.lower()
        scores = {k: 0 for k in self._LAYER_PATTERNS.keys()}

        for layer, patterns in self._LAYER_PATTERNS.items():
            for p in patterns:
                if re.search(p, raw if p.isupper() else lowered):
                    scores[layer] += 1

        winner = max(scores, key=scores.get)
        return winner if scores[winner] > 0 else "natural_language"

    def _check_multilayer_consistency(self, claim_text: str, source_text: str | None = None) -> dict:
        texts = [claim_text]
        if source_text and str(source_text).strip():
            texts.append(str(source_text))
        result = self._htlf.check_multilayer_consistency(texts)
        result["contradiction_count"] = len(result.get("contradictions", []))
        return result
