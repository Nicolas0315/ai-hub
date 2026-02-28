"""
KS40c — Katala Samurai 40c: HTLF 5-Axis Multi-Layer Consistency Engine

Extends KS40a with:
- 5-layer automatic detection from text features (math/formal/NL/music/creative)
- Estimated-loss mode when source text is missing
- Multi-layer consistency checks for cross-representation contradictions
- 5-axis HTLF: R_struct × R_context × R_qualia × R_cultural × R_temporal

Philosophical basis:
- Quine's Indeterminacy: translation between layers is underdetermined
- Kuhn's Paradigm Theory: temporal incommensurability detection
- Barthes' Textual Arbitrariness: meaning drifts across contexts
- Duhem-Quine Thesis: concepts cannot be isolated from their web

Design: Youta Hilono, 2026-02-28 / 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import re
import sys as _sys, os as _os
from dataclasses import dataclass
from typing import Any, Dict, List

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

# Layer detection thresholds — pattern hit count required to classify
_LAYER_THRESHOLD = 1


class KS40b(KS40a):
    """KS40c: 5-axis HTLF with auto-layer detection and consistency diagnostics.

    Adds three capabilities on top of KS40a:
    1. **Auto-layer detection**: Classifies text into math/formal/NL/music/creative
       based on regex pattern matching (no LLM required).
    2. **Estimated-loss mode**: When source text is unavailable, uses axis priors
       from ``HTLFScorer._estimate_loss_vector()``.
    3. **Multi-layer consistency**: Detects cross-representation contradictions
       (e.g. positive claim in NL vs negative evidence in formal language).

    The 5-axis loss vector now includes R_cultural and R_temporal (KS40c extension).
    """

    VERSION = "KS40c"

    # Regex patterns for automatic symbolic-layer classification.
    # Keys must match the ``Layer`` literal in ``ks_integration.py``.
    _LAYER_PATTERNS: Dict[str, List[str]] = {
        "math": [
            r"∑", r"∫", r"∀", r"∃",
            r"\btheorem\b", r"\blemma\b", r"\bproof\b",
            r"\bn\s*=\s*\d+\b",
        ],
        "formal_language": [
            r"```", r"\bdef\s+", r"\bclass\s+", r"\breturn\b",
            r"\bimport\b", r"\bSELECT\b", r"\bFROM\b", r"\bWHERE\b",
        ],
        "natural_language": [
            r"\b(therefore|because|however|according to|つまり|なぜなら)\b",
        ],
        "music": [
            r"\b(chord|tempo|melody|harmony|rhythm|crescendo|timbre)\b",
        ],
        "creative": [
            r"\b(color|texture|composition|canvas|aesthetic|installation|brushstroke)\b",
        ],
    }

    # ── Public API ───────────────────────────────────────────────

    def verify(self, claim: Any, store: Any = None, skip_s28: bool = True,
               **kwargs: Any) -> dict[str, Any]:
        """Run KS40c verification with auto-layer detection and consistency check.

        Parameters
        ----------
        claim : str or Claim
            The claim text (or Claim object) to verify.
        store : optional
            Evidence store for KS29b+ layers.
        skip_s28 : bool
            Whether to skip stage-28 in the pipeline (default True).
        **kwargs :
            ``source_text``, ``source_layer``, ``target_layer``,
            ``use_mock_parser`` — forwarded to KS40a.verify().

        Returns
        -------
        dict
            Verification result with ``translation_loss``, ``multi_layer_consistency``,
            ``version`` = "KS40c", and the full 5-axis loss vector.
        """
        claim_text = claim.text if hasattr(claim, "text") else str(claim)
        source_text = kwargs.get("source_text")

        # Auto-detect symbolic layers
        auto_target = self._detect_layer_from_features(claim_text)
        auto_source = (
            self._detect_layer_from_features(source_text)
            if source_text
            else None
        )

        kwargs = dict(kwargs)
        kwargs.setdefault("target_layer", auto_target)
        kwargs.setdefault(
            "source_layer",
            auto_source or self._htlf.infer_source_layer_from_claim(claim_text, auto_target),
        )

        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)

        # Batch results pass through without modification
        if not isinstance(result, dict) or "results" in result:
            if isinstance(result, dict):
                result["version"] = self.VERSION
            return result

        # Enrich with multi-layer consistency
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

    # ── Private helpers ──────────────────────────────────────────

    def _detect_layer_from_features(self, text: str | None) -> str:
        """Classify text into a symbolic layer via regex pattern matching.

        Returns one of: ``math``, ``formal_language``, ``natural_language``,
        ``music``, ``creative``.  Falls back to ``natural_language`` when
        no patterns match above ``_LAYER_THRESHOLD``.
        """
        if not text:
            return "natural_language"

        raw = str(text)
        lowered = raw.lower()
        scores: dict[str, int] = {k: 0 for k in self._LAYER_PATTERNS}

        for layer, patterns in self._LAYER_PATTERNS.items():
            for p in patterns:
                target = raw if any(c.isupper() for c in p if c.isalpha()) else lowered
                if re.search(p, target):
                    scores[layer] += 1

        winner = max(scores, key=lambda k: scores[k])
        return winner if scores[winner] >= _LAYER_THRESHOLD else "natural_language"

    def _check_multilayer_consistency(
        self, claim_text: str, source_text: str | None = None,
    ) -> dict[str, Any]:
        """Check cross-layer consistency between claim and source texts.

        Uses ``HTLFScorer.check_multilayer_consistency()`` to detect
        polarity conflicts across symbolic layers.

        Returns dict with ``layer_set``, ``consistency_score``,
        ``contradictions``, and ``contradiction_count``.
        """
        texts = [claim_text]
        if source_text and str(source_text).strip():
            texts.append(str(source_text))

        result = self._htlf.check_multilayer_consistency(texts)
        result["contradiction_count"] = len(result.get("contradictions", []))
        return result
