"""Rust bridge for HTLF with transparent Python fallbacks."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Optional

try:
    import ks_accel as _rust
    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False


def _has(name: str) -> bool:
    return bool(RUST_AVAILABLE and _rust is not None and hasattr(_rust, name))


def _tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヴー]+", text)
        if len(t) > 1
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / (na * nb)))


def htlf_similarity_matrix(source_emb: list[list[float]], target_emb: list[list[float]]) -> list[list[float]]:
    if _has("compute_similarity_matrix"):
        return _rust.compute_similarity_matrix(source_emb, target_emb)
    return [[max(0.0, min(1.0, _cosine(a, b))) for b in target_emb] for a in source_emb]


def htlf_greedy_match(sim_matrix: list[list[float]], threshold: float) -> list[tuple[int, int, float]]:
    if _has("greedy_bipartite_match"):
        return _rust.greedy_bipartite_match(sim_matrix, threshold)
    candidates: list[tuple[float, int, int]] = []
    for i, row in enumerate(sim_matrix):
        for j, s in enumerate(row):
            candidates.append((float(s), i, j))
    candidates.sort(reverse=True)
    used_i: set[int] = set()
    used_j: set[int] = set()
    out: list[tuple[int, int, float]] = []
    for s, i, j in candidates:
        if s < threshold or i in used_i or j in used_j:
            continue
        used_i.add(i)
        used_j.add(j)
        out.append((i, j, float(s)))
    return out


def htlf_r_struct_typed(
    source_edges: list[tuple[int, int, str]],
    target_edges: list[tuple[int, int, str]],
    node_mapping: list[tuple[int, int]],
    type_weights: dict[str, float],
    mismatch_penalties: dict[tuple[str, str], float],
) -> float:
    if _has("compute_r_struct_typed"):
        return float(_rust.compute_r_struct_typed(source_edges, target_edges, node_mapping, type_weights, mismatch_penalties))

    mapping = dict(node_mapping)
    tgt_index: dict[tuple[int, int], list[str]] = {}
    for s, t, tp in target_edges:
        tgt_index.setdefault((s, t), []).append(tp)

    weighted_score = 0.0
    total_weight = 0.0
    for s, t, tp in source_edges:
        if s not in mapping or t not in mapping:
            continue
        w = float(type_weights.get(tp, 1.0))
        total_weight += w
        best = 0.0
        for ttp in tgt_index.get((mapping[s], mapping[t]), []):
            if ttp == tp:
                best = max(best, 1.0)
            else:
                best = max(best, float(mismatch_penalties.get((tp, ttp), 0.5)))
        weighted_score += w * best
    return max(0.0, min(1.0, weighted_score / total_weight)) if total_weight > 0 else 0.0


def htlf_tfidf_overlap(source_terms: list[str], target_text: str, idf_weights: dict[str, float]) -> float:
    if _has("compute_tfidf_overlap"):
        return float(_rust.compute_tfidf_overlap(source_terms, target_text, idf_weights))
    tokens = Counter(_tokenize(target_text))
    num = 0.0
    den = 0.0
    for term in source_terms:
        t = term.lower()
        w = float(idf_weights.get(t, 1.0))
        den += w
        if tokens.get(t, 0) > 0:
            num += w
    return (num / den) if den > 0 else 0.0


def htlf_distance(a: list[float], b: list[float], method: str = "cosine", cov_inv: Optional[list[list[float]]] = None) -> float:
    if _has("cosine_distance"):
        if method == "mahalanobis" and cov_inv is not None and _has("mahalanobis_distance"):
            return float(_rust.mahalanobis_distance(a, b, cov_inv))
        if method == "wasserstein" and _has("wasserstein_1d"):
            return float(_rust.wasserstein_1d(a, b))
        return float(_rust.cosine_distance(a, b))

    if method == "wasserstein":
        if not a or not b or len(a) != len(b):
            return 1.0
        sa, sb = sorted(a), sorted(b)
        return min(1.0, sum(abs(x - y) for x, y in zip(sa, sb)) / len(sa))

    if method == "mahalanobis":
        if not a or not b or len(a) != len(b):
            return 1.0
        if cov_inv is None:
            s = 0.0
            for x, y in zip(a, b):
                v = ((abs(x) + abs(y)) / 2.0) ** 2 + 1e-3
                s += ((x - y) ** 2) / max(v, 1e-6)
            return min(1.0, math.sqrt(s) / math.sqrt(len(a)))

    cos = _cosine(a, b)
    return (1.0 - cos) / 2.0


def htlf_batch_qualia_distances(source_vectors: list[list[float]], target_vectors: list[list[float]], method: str = "cosine") -> list[float]:
    if _has("batch_qualia_distances"):
        return [float(x) for x in _rust.batch_qualia_distances(source_vectors, target_vectors, method)]
    n = min(len(source_vectors), len(target_vectors))
    return [htlf_distance(source_vectors[i], target_vectors[i], method=method) for i in range(n)]


def htlf_classify_profile_batch(r_structs: list[float], r_contexts: list[float], r_qualias: list[float | None]) -> list[str]:
    if _has("classify_profile_batch"):
        return list(_rust.classify_profile_batch(r_structs, r_contexts, r_qualias))

    out: list[str] = []
    for rs, rc, rq in zip(r_structs, r_contexts, r_qualias):
        axes = {"struct": rs, "context": rc, "qualia": rq}
        defs = [
            ("P01_struct_context_sum", ["struct", "context"], "sum"),
            ("P02_struct_context_prod", ["struct", "context"], "prod"),
            ("P03_struct_qualia_sum", ["struct", "qualia"], "sum"),
            ("P04_struct_qualia_prod", ["struct", "qualia"], "prod"),
            ("P05_context_qualia_sum", ["context", "qualia"], "sum"),
            ("P06_context_qualia_prod", ["context", "qualia"], "prod"),
            ("P07_struct_sum", ["struct"], "sum"),
            ("P08_struct_prod", ["struct"], "prod"),
            ("P09_context_sum", ["context"], "sum"),
            ("P10_context_prod", ["context"], "prod"),
            ("P11_qualia_sum", ["qualia"], "sum"),
            ("P12_qualia_prod", ["qualia"], "prod"),
        ]
        best_name = "P00_unclassified"
        best = -1.0
        for name, parts, mode in defs:
            vals = [axes[p] for p in parts]
            if any(v is None for v in vals):
                continue
            nums = [float(v) for v in vals if v is not None]
            score = nums[0] if len(nums) == 1 else ((nums[0] + nums[1]) / 2.0 if mode == "sum" else math.sqrt(nums[0] * nums[1]))
            if score > best:
                best = score
                best_name = name
        out.append(best_name)
    return out


def rust_cultural_frame_distance(
    frames_a: list[tuple[str, float]], frames_b: list[tuple[str, float]]
) -> float:
    if _has("cultural_frame_distance"):
        return _rust.cultural_frame_distance(frames_a, frames_b)
    # Python fallback
    all_f = set(k for k, _ in frames_a) | set(k for k, _ in frames_b)
    if not all_f:
        return 0.0
    ma = dict(frames_a)
    mb = dict(frames_b)
    sf = sorted(all_f)
    dot = sum(ma.get(f, 0.0) * mb.get(f, 0.0) for f in sf)
    na = math.sqrt(sum(ma.get(f, 0.0) ** 2 for f in sf)) or 1e-10
    nb = math.sqrt(sum(mb.get(f, 0.0) ** 2 for f in sf)) or 1e-10
    return 1.0 - max(0.0, min(1.0, dot / (na * nb)))


def rust_paradigm_distance(era_source: str, era_target: str) -> tuple[float, int]:
    if _has("paradigm_distance"):
        return _rust.paradigm_distance(era_source, era_target)
    # Python fallback (simplified)
    ERA_ORDER = ["ancient", "medieval", "early_modern", "modern_19c",
                 "early_20c", "late_20c", "contemporary"]
    try:
        idx_s = ERA_ORDER.index(era_source)
        idx_t = ERA_ORDER.index(era_target)
    except ValueError:
        return (0.3, 0)
    if idx_s == idx_t:
        return (0.0, 0)
    chrono = abs(idx_s - idx_t) / (len(ERA_ORDER) - 1)
    return (min(1.0, chrono + 0.15), 1)


def rust_compute_cultural_loss(
    cultural_distance: float, n_concept_gaps: int, text_len: int, marker_count: int
) -> tuple[float, float, float]:
    if _has("compute_cultural_loss"):
        return _rust.compute_cultural_loss(cultural_distance, n_concept_gaps, text_len, marker_count)
    # Python fallback
    gap_f = min(1.0, n_concept_gaps / 5.0) * 0.4
    dist_f = cultural_distance * 0.35
    dens = min(1.0, marker_count / max(1, text_len / 500)) * 0.25
    hol = min(1.0, gap_f + dist_f + dens)
    gap_loss = min(1.0, n_concept_gaps / 8.0)
    loss = min(1.0, 0.35 * cultural_distance + 0.35 * gap_loss + 0.30 * hol)
    indet = min(1.0, 0.40 * cultural_distance + 0.35 * hol + 0.25 * min(1.0, n_concept_gaps / 3.0))
    return (loss, indet, hol)


def rust_compute_temporal_loss(
    paradigm_dist: float, n_incommensurable: int, semantic_drift: float
) -> tuple[float, float, float]:
    if _has("compute_temporal_loss"):
        return _rust.compute_temporal_loss(paradigm_dist, n_incommensurable, semantic_drift)
    # Python fallback
    web = min(1.0, 0.40 * paradigm_dist + 0.30 * min(1.0, n_incommensurable / 4.0) + 0.30 * semantic_drift)
    loss = min(1.0, 0.35 * paradigm_dist + 0.25 * min(1.0, n_incommensurable / 5.0) + 0.20 * semantic_drift + 0.20 * web)
    indet = min(1.0, 0.40 * paradigm_dist + 0.30 * min(1.0, n_incommensurable / 3.0) + 0.30 * web)
    return (loss, indet, web)


def status() -> dict[str, object]:
    n_funcs = 0
    if RUST_AVAILABLE and _rust:
        for name in dir(_rust):
            if not name.startswith("_"):
                n_funcs += 1
    return {
        "rust_available": RUST_AVAILABLE,
        "backend": "ks_accel (Rust/PyO3/Rayon)" if RUST_AVAILABLE else "Python fallback",
        "n_functions": n_funcs,
    }
