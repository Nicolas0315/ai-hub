from __future__ import annotations

from typing import Any
import os


def _rust_only() -> bool:
    return str(os.getenv("KQ_RUST_ONLY", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _mod():
    try:
        import katala_rust_hotpath as m  # type: ignore
        return m
    except Exception:
        return None


def _py_invariant_preservation_score(
    truth_conflict: bool,
    provability_ratio: float,
    counterexample_consistent: bool,
    l2f: float,
    f2p: float,
    p2h: float,
) -> float:
    return round(
        0.45 * (1.0 - (1.0 if truth_conflict else 0.0))
        + 0.30 * float(provability_ratio)
        + 0.15 * (1.0 if counterexample_consistent else 0.0)
        + 0.10 * ((float(l2f) + float(f2p) + float(p2h)) / 3.0),
        4,
    )


def invariant_preservation_score(
    truth_conflict: bool,
    provability_ratio: float,
    counterexample_consistent: bool,
    l2f: float,
    f2p: float,
    p2h: float,
) -> float:
    m = _mod()
    if m is not None:
        try:
            return float(m.invariant_preservation_score(
                bool(truth_conflict),
                float(provability_ratio),
                bool(counterexample_consistent),
                float(l2f),
                float(f2p),
                float(p2h),
            ))
        except Exception:
            if _rust_only():
                raise RuntimeError("KQ_RUST_ONLY is enabled and rust invariant_preservation_score failed")
    if _rust_only():
        raise RuntimeError("KQ_RUST_ONLY is enabled but katala_rust_hotpath is unavailable")
    return _py_invariant_preservation_score(truth_conflict, provability_ratio, counterexample_consistent, l2f, f2p, p2h)


def _py_strict_specificity_score(spec: str) -> float:
    s = (spec or "").lower()
    return 1.0 if ("and(" in s or "forall" in s or "exists" in s or "vars:" in s) else 0.6


def strict_specificity_score(spec: str) -> float:
    m = _mod()
    if m is not None:
        try:
            return float(m.strict_specificity_score(str(spec or "")))
        except Exception:
            if _rust_only():
                raise RuntimeError("KQ_RUST_ONLY is enabled and rust strict_specificity_score failed")
    if _rust_only():
        raise RuntimeError("KQ_RUST_ONLY is enabled but katala_rust_hotpath is unavailable")
    return _py_strict_specificity_score(spec)


def _py_strict_triggered(kq3_strict_activated: bool, invariant_preservation_score: float, counterexample_consistent: bool) -> bool:
    return bool(kq3_strict_activated or float(invariant_preservation_score) < 0.72 or (not bool(counterexample_consistent)))


def strict_triggered(kq3_strict_activated: bool, invariant_preservation_score: float, counterexample_consistent: bool) -> bool:
    m = _mod()
    if m is not None:
        try:
            return bool(m.strict_triggered(bool(kq3_strict_activated), float(invariant_preservation_score), bool(counterexample_consistent)))
        except Exception:
            if _rust_only():
                raise RuntimeError("KQ_RUST_ONLY is enabled and rust strict_triggered failed")
    if _rust_only():
        raise RuntimeError("KQ_RUST_ONLY is enabled but katala_rust_hotpath is unavailable")
    return _py_strict_triggered(kq3_strict_activated, invariant_preservation_score, counterexample_consistent)


def _py_dense_dependency_edges(
    node_ids: list[str],
    node_layers: list[str],
    node_morphisms: list[str],
    node_invariants: list[str],
    explicit_edges: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    ids = set(node_ids)
    out = {(a, b) for a, b in explicit_edges if a in ids and b in ids and a != b}

    def ln(layer: str) -> int:
        try:
            return int(str(layer or "L0").replace("L", ""))
        except Exception:
            return 0

    for i, nid in enumerate(node_ids):
        for j, mid in enumerate(node_ids):
            if nid == mid:
                continue
            if ln(node_layers[j]) >= ln(node_layers[i]):
                continue
            same_m = bool(node_morphisms[j] and node_morphisms[i] and node_morphisms[j] == node_morphisms[i])
            same_inv = bool(node_invariants[j] and node_invariants[i] and node_invariants[j] == node_invariants[i])
            prev_bridge = (ln(node_layers[i]) - ln(node_layers[j])) == 1
            if same_m or same_inv or prev_bridge:
                out.add((mid, nid))
    return sorted(list(out))


def dense_dependency_edges(
    node_ids: list[str],
    node_layers: list[str],
    node_morphisms: list[str],
    node_invariants: list[str],
    explicit_edges: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    m = _mod()
    if m is not None:
        try:
            return list(m.dense_dependency_edges(node_ids, node_layers, node_morphisms, node_invariants, explicit_edges))
        except Exception:
            if _rust_only():
                raise RuntimeError("KQ_RUST_ONLY is enabled and rust dense_dependency_edges failed")
    if _rust_only():
        raise RuntimeError("KQ_RUST_ONLY is enabled but katala_rust_hotpath is unavailable")
    return _py_dense_dependency_edges(node_ids, node_layers, node_morphisms, node_invariants, explicit_edges)
