"""HTLF profile auto-classifier (Phase 4).

Classifies one translation instance into one of 12 profile patterns:
- 6 axis combinations (3 pairwise + 3 single-axis)
- 2 composition modes (sum / prod)
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from itertools import combinations
from typing import Literal

from . import rust_bridge as rb

Layer = Literal["math", "formal_language", "natural_language", "music", "creative"]
Axis = Literal["struct", "context", "qualia"]
CompositionMode = Literal["sum", "prod"]


@dataclass(slots=True)
class ProfileResult:
    dominant_axes: tuple[Axis, ...]
    composition_mode: CompositionMode
    confidence: float
    reasoning: str
    profile_type: str
    r_struct: float
    r_context: float
    r_qualia: float
    correlation: float


# Based on docs/HTLF.md translation matrix (qualia N/A -> 0.0 proxy)
AXIS_PRIOR: dict[tuple[Layer, Layer], tuple[float, float, float]] = {
    ("math", "formal_language"): (0.95, 0.80, 0.00),
    ("math", "natural_language"): (0.70, 0.50, 0.00),
    ("music", "natural_language"): (0.40, 0.30, 0.10),
    ("music", "creative"): (0.30, 0.40, 0.50),
    ("formal_language", "music"): (0.05, 0.05, 0.00),
    ("creative", "natural_language"): (0.50, 0.40, 0.15),
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


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _tokenize(text: str) -> set[str]:
    import re

    return {
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヴー]+", text)
        if len(t) > 1
    }


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _estimate_observed_metrics(source_text: str, target_text: str, prior: tuple[float, float, float]) -> tuple[float, float, float]:
    """Cheap, deterministic observed estimate blended with layer prior."""
    lexical = _jaccard(source_text, target_text)
    len_ratio = min(len(source_text), len(target_text)) / max(1, max(len(source_text), len(target_text)))

    # cue-based qualia signal (punctuation, emotive words)
    emotive_words = {"beautiful", "moving", "sad", "joy", "awe", "緊張", "感動", "美しい", "切ない"}
    src_tok = _tokenize(source_text)
    tgt_tok = _tokenize(target_text)
    qualia_overlap = len((src_tok & emotive_words) | (tgt_tok & emotive_words)) / max(1, len(emotive_words))

    struct_obs = _clamp01(0.60 * lexical + 0.25 * len_ratio + 0.15 * prior[0])
    context_obs = _clamp01(0.45 * lexical + 0.35 * len_ratio + 0.20 * prior[1])
    qualia_obs = _clamp01(0.50 * qualia_overlap + 0.20 * lexical + 0.30 * prior[2])

    return (struct_obs, context_obs, qualia_obs)


def _estimate_prior(source_layer: Layer, target_layer: Layer) -> tuple[float, float, float]:
    if source_layer == target_layer:
        return (0.95, 0.90, 0.85)

    if (source_layer, target_layer) in AXIS_PRIOR:
        return AXIS_PRIOR[(source_layer, target_layer)]

    if (target_layer, source_layer) in AXIS_PRIOR:
        s, c, q = AXIS_PRIOR[(target_layer, source_layer)]
        return (s * 0.95, c * 0.90, q * 0.85)

    return (0.45, 0.35, 0.20)


def _chunks(text: str, n: int = 4) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    step = max(1, math.ceil(len(text) / n))
    return [text[i : i + step] for i in range(0, len(text), step)]


def _corr(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(ys) < 2 or len(xs) != len(ys):
        return 0.0
    try:
        return statistics.correlation(xs, ys)
    except Exception:
        return 0.0


def _composition_from_correlation(source_text: str, target_text: str, base: tuple[float, float, float]) -> tuple[CompositionMode, float]:
    src_chunks = _chunks(source_text)
    tgt_chunks = _chunks(target_text)
    n = min(len(src_chunks), len(tgt_chunks))

    struct_series: list[float] = []
    context_series: list[float] = []
    qualia_series: list[float] = []

    for i in range(n):
        s, c, q = _estimate_observed_metrics(src_chunks[i], tgt_chunks[i], base)
        struct_series.append(s)
        context_series.append(c)
        qualia_series.append(q)

    corr_vals = [
        abs(_corr(struct_series, context_series)),
        abs(_corr(struct_series, qualia_series)),
        abs(_corr(context_series, qualia_series)),
    ]
    mean_corr = sum(corr_vals) / len(corr_vals)

    mode: CompositionMode = "prod" if mean_corr >= 0.45 else "sum"
    return mode, _clamp01(mean_corr)


def _dominant_axes(observed: tuple[float, float, float]) -> tuple[Axis, ...]:
    labels: list[Axis] = ["struct", "context", "qualia"]
    axis_order: dict[Axis, int] = {"struct": 0, "context": 1, "qualia": 2}

    # Pairwise dispersion proxy: largest axis gap pair dominates.
    pair_gaps: list[tuple[float, tuple[Axis, Axis]]] = []
    values = dict(zip(labels, observed, strict=True))
    for a, b in combinations(labels, 2):
        pair_gaps.append((abs(values[a] - values[b]), (a, b)))

    gap, pair = max(pair_gaps, key=lambda x: x[0])

    # If one axis strongly dominates all others, map to single-axis profile.
    ranked = sorted(values.items(), key=lambda x: x[1], reverse=True)
    if ranked[0][1] - ranked[1][1] >= 0.22 or gap < 0.08:
        return (ranked[0][0],)

    # Normalize pair order to PROFILE_MAP key convention, not lexicographic order.
    return tuple(sorted(pair, key=lambda a: axis_order[a]))


def _agreement_score(prior: tuple[float, float, float], observed: tuple[float, float, float]) -> float:
    diffs = [abs(a - b) for a, b in zip(prior, observed, strict=True)]
    return _clamp01(1.0 - (sum(diffs) / 3.0))


def classify_profile(
    source_text: str,
    target_text: str,
    source_layer: Layer,
    target_layer: Layer,
    *,
    observed_metrics: tuple[float, float, float] | None = None,
) -> ProfileResult:
    """Classify into one of the 12 HTLF profile patterns.

    Args:
        source_text: original expression
        target_text: translated expression
        source_layer: source modality/layer
        target_layer: target modality/layer
        observed_metrics: optional override tuple (R_struct, R_context, R_qualia)
    """
    prior = _estimate_prior(source_layer, target_layer)
    observed = observed_metrics or _estimate_observed_metrics(source_text, target_text, prior)

    mode, corr = _composition_from_correlation(source_text, target_text, observed)
    axes = _dominant_axes(observed)
    profile_type = PROFILE_MAP.get((axes, mode), "P00_unclassified")

    agreement = _agreement_score(prior, observed)
    confidence = _clamp01(0.55 * agreement + 0.30 * corr + 0.15 * (1.0 if profile_type != "P00_unclassified" else 0.0))

    reasoning = (
        f"prior={prior}, observed={tuple(round(v, 3) for v in observed)}, "
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
        correlation=corr,
    )


def classify_profile_batch(
    r_structs: list[float],
    r_contexts: list[float],
    r_qualias: list[float | None],
) -> list[str]:
    """Batch classify profile type names via Rust bridge with Python fallback."""
    return rb.htlf_classify_profile_batch(r_structs, r_contexts, r_qualias)
