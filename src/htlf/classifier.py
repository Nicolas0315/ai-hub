"""
HTLF Profile Auto-Classifier (Phase 4) — 5-Axis Extension.

Classifies a translation instance into one of 12 profile patterns
based on the 5-axis HTLF loss model:

  3 original axes: R_struct, R_context, R_qualia
  2 extended axes: R_cultural, R_temporal (KS40c)

Profile classification uses the **3 primary axes** for pattern
selection (12 profiles = 6 pairwise + 3 single × 2 composition modes),
while R_cultural and R_temporal act as **modifiers** that can shift
confidence and trigger cross-cultural/temporal warnings.

Design: Youta Hilono + Shirokuma, 2026-02
5-axis extension: 2026-03 (KS40c → classifier)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from itertools import combinations
from typing import Literal

from . import rust_bridge as rb

Layer = Literal["math", "formal_language", "natural_language", "music", "creative"]
Axis = Literal["struct", "context", "qualia"]
CompositionMode = Literal["sum", "prod"]

# --- Named constants ---
CONFIDENCE_AGREEMENT_WEIGHT: float = 0.55
"""Weight of prior-observed agreement in confidence score."""

CONFIDENCE_CORRELATION_WEIGHT: float = 0.30
"""Weight of inter-axis correlation in confidence score."""

CONFIDENCE_MATCH_WEIGHT: float = 0.15
"""Weight of successful profile match in confidence score."""

SINGLE_AXIS_GAP_THRESHOLD: float = 0.22
"""Minimum gap between top axis and second to trigger single-axis profile."""

PAIR_GAP_THRESHOLD: float = 0.08
"""Below this gap, pair dominance is ambiguous → single-axis fallback."""

CORRELATION_MODE_THRESHOLD: float = 0.45
"""Mean inter-axis correlation above this → product mode (coupled axes)."""

CULTURAL_PENALTY_THRESHOLD: float = 0.40
"""R_cultural below this triggers cultural warning."""

TEMPORAL_PENALTY_THRESHOLD: float = 0.40
"""R_temporal below this triggers temporal warning."""

CULTURAL_CONFIDENCE_PENALTY: float = 0.10
"""Confidence reduction when R_cultural is low."""

TEMPORAL_CONFIDENCE_PENALTY: float = 0.08
"""Confidence reduction when R_temporal is low."""


@dataclass(slots=True)
class ProfileResult:
    """Result of profile classification.

    Attributes:
        dominant_axes: The axis or axis-pair driving the translation pattern.
        composition_mode: Whether axes combine additively (sum) or multiplicatively (prod).
        confidence: Overall classification confidence (0-1).
        reasoning: Human-readable explanation of classification logic.
        profile_type: Canonical profile name (P01-P12 or P00_unclassified).
        r_struct: Observed structural preservation score.
        r_context: Observed contextual preservation score.
        r_qualia: Observed experiential quality preservation score.
        r_cultural: Cultural translation loss score (KS40c).
        r_temporal: Temporal translation loss score (KS40c).
        correlation: Mean inter-axis correlation.
        warnings: Cultural/temporal warnings if applicable.
    """

    dominant_axes: tuple[Axis, ...]
    composition_mode: CompositionMode
    confidence: float
    reasoning: str
    profile_type: str
    r_struct: float
    r_context: float
    r_qualia: float
    r_cultural: float = 1.0
    r_temporal: float = 1.0
    correlation: float = 0.0
    warnings: list[str] = field(default_factory=list)


# 5D AXIS_PRIOR: (R_struct, R_context, R_qualia, R_cultural, R_temporal)
# Based on docs/HTLF.md full 20-directional layer pair matrix.
# Qualia N/A → 0.0 proxy. Cultural/temporal default to 0.8 for same-culture/era.
AXIS_PRIOR: dict[tuple[Layer, Layer], tuple[float, float, float, float, float]] = {
    # Math ↔ others
    ("math", "formal_language"): (0.95, 0.80, 0.00, 0.90, 0.85),
    ("formal_language", "math"): (0.90, 0.75, 0.00, 0.90, 0.85),
    ("math", "natural_language"): (0.70, 0.50, 0.00, 0.70, 0.80),
    ("natural_language", "math"): (0.65, 0.45, 0.00, 0.70, 0.80),
    ("math", "music"): (0.30, 0.20, 0.05, 0.60, 0.70),
    ("music", "math"): (0.25, 0.15, 0.05, 0.60, 0.70),
    ("math", "creative"): (0.20, 0.15, 0.10, 0.50, 0.65),
    ("creative", "math"): (0.15, 0.10, 0.10, 0.50, 0.65),
    # Formal ↔ others
    ("formal_language", "natural_language"): (0.80, 0.60, 0.10, 0.75, 0.80),
    ("natural_language", "formal_language"): (0.75, 0.55, 0.10, 0.75, 0.80),
    ("formal_language", "music"): (0.05, 0.05, 0.00, 0.40, 0.50),
    ("music", "formal_language"): (0.05, 0.05, 0.00, 0.40, 0.50),
    ("formal_language", "creative"): (0.10, 0.10, 0.05, 0.45, 0.55),
    ("creative", "formal_language"): (0.10, 0.10, 0.05, 0.45, 0.55),
    # NL ↔ others
    ("music", "natural_language"): (0.40, 0.30, 0.10, 0.65, 0.75),
    ("natural_language", "music"): (0.35, 0.25, 0.10, 0.65, 0.75),
    ("creative", "natural_language"): (0.50, 0.40, 0.15, 0.70, 0.80),
    ("natural_language", "creative"): (0.45, 0.35, 0.15, 0.70, 0.80),
    # Music ↔ Creative
    ("music", "creative"): (0.30, 0.40, 0.50, 0.75, 0.80),
    ("creative", "music"): (0.25, 0.35, 0.50, 0.75, 0.80),
}


PROFILE_MAP: dict[tuple[tuple[Axis, ...], CompositionMode], str] = {
    (("struct", "context"), "sum"): "P01_struct_context_sum",
    (("struct", "context"), "prod"): "P02_struct_context_prod",
    (("struct", "qualia"), "sum"): "P03_struct_qualia_sum",
    (("struct", "qualia"), "prod"): "P04_struct_qualia_prod",
    (("context", "qualia"), "sum"): "P05_context_qualia_sum",
    (("context", "qualia"), "prod"): "P06_context_qualia_prod",
    (("struct",), "sum"): "P07_struct_sum",
    (("struct",), "prod"): "P08_struct_prod",
    (("context",), "sum"): "P09_context_sum",
    (("context",), "prod"): "P10_context_prod",
    (("qualia",), "sum"): "P11_qualia_sum",
    (("qualia",), "prod"): "P12_qualia_prod",
}
"""Canonical mapping from (axis tuple, composition mode) to profile name."""


def _clamp01(v: float) -> float:
    """Clamp a value to the [0, 1] range."""
    return max(0.0, min(1.0, float(v)))


def _tokenize(text: str) -> set[str]:
    """Extract lowercase alpha/CJK tokens (length > 1) from text."""
    import re

    return {
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヴー]+", text)
        if len(t) > 1
    }


def _jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity between tokenized texts."""
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _estimate_observed_metrics(
    source_text: str,
    target_text: str,
    prior: tuple[float, float, float, float, float],
) -> tuple[float, float, float, float, float]:
    """Compute cheap deterministic 5-axis estimate blended with layer prior.

    Returns (R_struct, R_context, R_qualia, R_cultural, R_temporal).
    """
    lexical = _jaccard(source_text, target_text)
    len_ratio = min(len(source_text), len(target_text)) / max(1, max(len(source_text), len(target_text)))

    # Cue-based qualia signal (punctuation, emotive words)
    emotive_words = {"beautiful", "moving", "sad", "joy", "awe", "緊張", "感動", "美しい", "切ない"}
    src_tok = _tokenize(source_text)
    tgt_tok = _tokenize(target_text)
    qualia_overlap = len((src_tok & emotive_words) | (tgt_tok & emotive_words)) / max(1, len(emotive_words))

    struct_obs = _clamp01(0.60 * lexical + 0.25 * len_ratio + 0.15 * prior[0])
    context_obs = _clamp01(0.45 * lexical + 0.35 * len_ratio + 0.20 * prior[1])
    qualia_obs = _clamp01(0.50 * qualia_overlap + 0.20 * lexical + 0.30 * prior[2])

    # Cultural estimation: script/language overlap as proxy
    # If both texts share the same script family, cultural distance is lower
    src_cjk = sum(1 for c in source_text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    tgt_cjk = sum(1 for c in target_text if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff')
    src_latin = sum(1 for c in source_text if 'a' <= c.lower() <= 'z')
    tgt_latin = sum(1 for c in target_text if 'a' <= c.lower() <= 'z')
    src_script = "cjk" if src_cjk > src_latin else "latin"
    tgt_script = "cjk" if tgt_cjk > tgt_latin else "latin"
    script_match = 1.0 if src_script == tgt_script else 0.5
    cultural_obs = _clamp01(0.40 * script_match + 0.30 * lexical + 0.30 * prior[3])

    # Temporal estimation: use prior (heuristic has no timestamp information)
    temporal_obs = _clamp01(0.30 * lexical + 0.70 * prior[4])

    return (struct_obs, context_obs, qualia_obs, cultural_obs, temporal_obs)


def _estimate_prior(
    source_layer: Layer,
    target_layer: Layer,
) -> tuple[float, float, float, float, float]:
    """Look up 5-axis prior for a given layer pair.

    Falls back to symmetric approximation or generic defaults.
    """
    if source_layer == target_layer:
        return (0.95, 0.90, 0.85, 0.95, 0.95)

    if (source_layer, target_layer) in AXIS_PRIOR:
        return AXIS_PRIOR[(source_layer, target_layer)]

    if (target_layer, source_layer) in AXIS_PRIOR:
        s, c, q, cl, t = AXIS_PRIOR[(target_layer, source_layer)]
        return (s * 0.95, c * 0.90, q * 0.85, cl * 0.95, t * 0.95)

    return (0.45, 0.35, 0.20, 0.60, 0.70)


def _chunks(text: str, n: int = 4) -> list[str]:
    """Split text into n roughly equal chunks for correlation analysis."""
    text = text.strip()
    if not text:
        return [""]
    step = max(1, math.ceil(len(text) / n))
    return [text[i : i + step] for i in range(0, len(text), step)]


def _corr(xs: list[float], ys: list[float]) -> float:
    """Compute Pearson correlation, returning 0.0 on failure."""
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return 0.0
    try:
        return statistics.correlation(xs, ys)
    except Exception:
        return 0.0


def _composition_from_correlation(
    source_text: str,
    target_text: str,
    base: tuple[float, float, float, float, float],
) -> tuple[CompositionMode, float]:
    """Determine composition mode (sum vs prod) from inter-axis correlation.

    High correlation between axes → product mode (axes are coupled).
    Low correlation → sum mode (axes are independent).
    """
    src_chunks = _chunks(source_text)
    tgt_chunks = _chunks(target_text)
    n = min(len(src_chunks), len(tgt_chunks))

    struct_series: list[float] = []
    context_series: list[float] = []
    qualia_series: list[float] = []

    for i in range(n):
        obs = _estimate_observed_metrics(src_chunks[i], tgt_chunks[i], base)
        struct_series.append(obs[0])
        context_series.append(obs[1])
        qualia_series.append(obs[2])

    corr_vals = [
        abs(_corr(struct_series, context_series)),
        abs(_corr(struct_series, qualia_series)),
        abs(_corr(context_series, qualia_series)),
    ]
    mean_corr = sum(corr_vals) / len(corr_vals)

    mode: CompositionMode = "prod" if mean_corr >= CORRELATION_MODE_THRESHOLD else "sum"
    return mode, _clamp01(mean_corr)


def _dominant_axes(observed: tuple[float, float, float, float, float]) -> tuple[Axis, ...]:
    """Identify the dominant axis or axis-pair from 5-axis observations.

    Uses the 3 primary axes (struct, context, qualia) for profile selection.
    R_cultural and R_temporal are modifiers, not profile determinants.
    """
    labels: list[Axis] = ["struct", "context", "qualia"]
    axis_order: dict[Axis, int] = {"struct": 0, "context": 1, "qualia": 2}

    # Use only the 3 primary axes for dominance analysis
    values = dict(zip(labels, observed[:3], strict=True))

    # Pairwise dispersion proxy: largest axis gap pair dominates
    pair_gaps: list[tuple[float, tuple[Axis, Axis]]] = []
    for a, b in combinations(labels, 2):
        pair_gaps.append((abs(values[a] - values[b]), (a, b)))

    gap, pair = max(pair_gaps, key=lambda x: x[0])

    # If one axis strongly dominates all others → single-axis profile
    ranked = sorted(values.items(), key=lambda x: x[1], reverse=True)
    if ranked[0][1] - ranked[1][1] >= SINGLE_AXIS_GAP_THRESHOLD or gap < PAIR_GAP_THRESHOLD:
        return (ranked[0][0],)

    # Normalize pair order to PROFILE_MAP key convention
    return tuple(sorted(pair, key=lambda a: axis_order[a]))


def _agreement_score(
    prior: tuple[float, float, float, float, float],
    observed: tuple[float, float, float, float, float],
) -> float:
    """Compute agreement between prior expectations and observed scores.

    Uses all 5 axes for a comprehensive agreement measure.
    """
    diffs = [abs(a - b) for a, b in zip(prior, observed, strict=True)]
    return _clamp01(1.0 - (sum(diffs) / len(diffs)))


def _cultural_temporal_warnings(
    r_cultural: float,
    r_temporal: float,
) -> list[str]:
    """Generate warnings for low cultural/temporal scores."""
    warnings: list[str] = []
    if r_cultural < CULTURAL_PENALTY_THRESHOLD:
        warnings.append(
            f"R_cultural={r_cultural:.2f} below threshold ({CULTURAL_PENALTY_THRESHOLD}): "
            "significant cultural translation loss detected"
        )
    if r_temporal < TEMPORAL_PENALTY_THRESHOLD:
        warnings.append(
            f"R_temporal={r_temporal:.2f} below threshold ({TEMPORAL_PENALTY_THRESHOLD}): "
            "significant temporal translation loss detected"
        )
    return warnings


def classify_profile(
    source_text: str,
    target_text: str,
    source_layer: Layer,
    target_layer: Layer,
    *,
    observed_metrics: tuple[float, float, float] | tuple[float, float, float, float, float] | None = None,
) -> ProfileResult:
    """Classify a translation into one of the 12 HTLF profile patterns.

    Supports both 3-axis (legacy) and 5-axis observed_metrics input.
    When 3-axis input is provided, R_cultural and R_temporal are estimated
    from the layer pair prior.

    Args:
        source_text: Original expression text.
        target_text: Translated expression text.
        source_layer: Source modality/layer.
        target_layer: Target modality/layer.
        observed_metrics: Optional override — 3-tuple or 5-tuple of axis scores.

    Returns:
        ProfileResult with classification, confidence, and 5-axis scores.
    """
    prior = _estimate_prior(source_layer, target_layer)

    # Handle both 3-axis and 5-axis observed_metrics input
    if observed_metrics is not None:
        if len(observed_metrics) == 3:
            # Legacy 3-axis: estimate cultural/temporal from prior
            observed = (
                observed_metrics[0],
                observed_metrics[1],
                observed_metrics[2],
                prior[3],
                prior[4],
            )
        else:
            observed = observed_metrics  # type: ignore[assignment]
    else:
        observed = _estimate_observed_metrics(source_text, target_text, prior)

    mode, corr = _composition_from_correlation(source_text, target_text, observed)
    axes = _dominant_axes(observed)
    profile_type = PROFILE_MAP.get((axes, mode), "P00_unclassified")

    agreement = _agreement_score(prior, observed)

    # Base confidence from 3 primary axes
    confidence = _clamp01(
        CONFIDENCE_AGREEMENT_WEIGHT * agreement
        + CONFIDENCE_CORRELATION_WEIGHT * corr
        + CONFIDENCE_MATCH_WEIGHT * (1.0 if profile_type != "P00_unclassified" else 0.0)
    )

    # Apply cultural/temporal penalties to confidence
    warnings = _cultural_temporal_warnings(observed[3], observed[4])
    if observed[3] < CULTURAL_PENALTY_THRESHOLD:
        confidence = _clamp01(confidence - CULTURAL_CONFIDENCE_PENALTY)
    if observed[4] < TEMPORAL_PENALTY_THRESHOLD:
        confidence = _clamp01(confidence - TEMPORAL_CONFIDENCE_PENALTY)

    reasoning = (
        f"prior={tuple(round(v, 3) for v in prior)}, "
        f"observed={tuple(round(v, 3) for v in observed)}, "
        f"corr={corr:.3f} -> mode={mode}, dominant_axes={axes}, "
        f"agreement={agreement:.3f}"
    )

    return ProfileResult(
        dominant_axes=axes,
        composition_mode=mode,
        confidence=confidence,
        reasoning=reasoning,
        profile_type=profile_type,
        r_struct=_clamp01(observed[0]),
        r_context=_clamp01(observed[1]),
        r_qualia=_clamp01(observed[2]),
        r_cultural=_clamp01(observed[3]),
        r_temporal=_clamp01(observed[4]),
        correlation=corr,
        warnings=warnings,
    )


def classify_profile_batch(
    r_structs: list[float],
    r_contexts: list[float],
    r_qualias: list[float | None],
) -> list[str]:
    """Batch classify profile type names via Rust bridge with Python fallback.

    Note: This uses the 3-axis fast path for batch processing.
    For 5-axis classification, use classify_profile() individually.
    """
    return rb.htlf_classify_profile_batch(r_structs, r_contexts, r_qualias)
