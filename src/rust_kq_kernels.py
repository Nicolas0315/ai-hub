"""Temporary kernel module matching future Rust extension API.

This module provides the same function signatures as the planned Rust extension
so runtime wiring can be exercised now. It will be replaced by a compiled
`rust_kq_kernels` extension in phase-2+.
"""
from __future__ import annotations

import re
from typing import Any


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def mini_solver_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "") or "")
    low = text.lower()
    boosts = payload.get("complementFamilyBoost") or {}

    refs_hits = sum(1 for k in ["doi", "citation", "source", "paper", "論文", "査読", "参考"] if k in low)
    logic_hits = sum(1 for k in ["therefore", "because", "if", "then", "proof", "論理", "命題", "ゆえに"] if k in low)
    coding_hits = sum(1 for k in ["code", "test", "bug", "commit", "refactor", "実装", "修正"] if k in low)
    creative_hits = sum(1 for k in ["novel", "creative", "metaphor", "story", "独自", "創造", "比喩"] if k in low)
    risk_hits = sum(1 for k in ["ignore", "bypass", "always", "except", "絶対", "ただし"] if k in low)
    tok_n = max(1, len(re.findall(r"[\w\-\u3040-\u30ff\u4e00-\u9fff]+", low)))

    families = {
        "lexical": _clamp(0.35 + min(0.35, tok_n / 120.0)),
        "grounding": _clamp(0.30 + min(0.45, refs_hits * 0.12)),
        "logic": _clamp(0.30 + min(0.45, logic_hits * 0.10)),
        "coding": _clamp(0.25 + min(0.55, coding_hits * 0.11)),
        "creativity": _clamp(0.25 + min(0.55, creative_hits * 0.11)),
        "safety": _clamp(0.80 - min(0.55, risk_hits * 0.14)),
        "routing": _clamp(0.35 + min(0.35, (logic_hits + refs_hits) * 0.05) - min(0.20, risk_hits * 0.04)),
        "stability": _clamp(0.45 + min(0.25, tok_n / 180.0) - min(0.20, risk_hits * 0.03)),
    }
    for k, v in boosts.items():
        if k in families:
            families[k] = _clamp(float(families[k]) + float(v or 0.0))

    names = [f"{fam}_s{i:03d}" for fam in families for i in range(1, 65)]
    activated = []
    scores: dict[str, float] = {}
    family_counts = {k: 0 for k in families}
    for idx, n in enumerate(names, start=1):
        fam = n.split("_", 1)[0]
        score = _clamp(float(families[fam]) + (((idx * 13 + tok_n) % 17) / 100.0 - 0.08))
        scores[n] = round(score, 4)
        if score >= 0.48:
            activated.append(n)
            family_counts[fam] += 1

    return {
        "count": len(names),
        "activatedCount": len(activated),
        "activationRatio": round(len(activated) / max(1, len(names)), 4),
        "families": {k: {"base": round(v, 4), "activated": int(family_counts[k]), "total": 64} for k, v in families.items()},
        "scores": scores,
        "activated": activated,
    }


def triadic_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    spm_count = int(payload.get("spmTagCount", 0) or 0)
    d_ratio = float(payload.get("domainActivationRatio", 0.0) or 0.0)
    m_ratio = float(payload.get("miniActivationRatio", 0.0) or 0.0)
    pair = {
        "spm_x_28plus": _clamp(0.45 + min(0.30, spm_count * 0.08) + (0.10 if d_ratio > 0 else 0.0)),
        "spm_x_mini": _clamp(0.42 + min(0.35, m_ratio * 0.6)),
        "28plus_x_mini": _clamp(0.40 + min(0.30, d_ratio * 0.8) + min(0.20, m_ratio * 0.4)),
    }
    tri = _clamp(sum(pair.values()) / 3.0)
    return {
        "pairScores": {k: round(v, 4) for k, v in pair.items()},
        "triadicScore": round(tri, 4),
        "recommendedMode": "triadic" if tri >= 0.62 else "pairwise",
    }


def symbolic_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    from katala_samurai.kq_symbolic_bridge import eval_symbolic

    expr = str(payload.get("expr", "") or "")
    return eval_symbolic(expr)


def modal_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    from katala_samurai.kq_symbolic_bridge import eval_modal

    expr = str(payload.get("expr", "") or "")
    return eval_modal(expr)


def predicate_lite_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    from katala_samurai.kq_symbolic_bridge import eval_predicate_lite

    expr = str(payload.get("expr", "") or "")
    return eval_predicate_lite(expr)


def constraint_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    from katala_samurai.kq_symbolic_bridge import solve_constraint_lite

    expr = str(payload.get("expr", "") or "")
    return solve_constraint_lite(expr)


def spml_kernel(payload: dict[str, Any]) -> dict[str, Any]:
    # scaffold only; deterministic pass-through aggregation
    w = payload.get("weights") or {}
    comp = {
        "semantic_fidelity_loss": float(payload.get("semanticFidelityLoss", 0.0) or 0.0),
        "embodied_signal_loss": float(payload.get("embodiedSignalLoss", 0.0) or 0.0),
        "temporal_paradigm_loss": float(payload.get("temporalParadigmLoss", 0.0) or 0.0),
        "stance_context_loss": float(payload.get("stanceContextLoss", 0.0) or 0.0),
        "evidence_grounding_loss": float(payload.get("evidenceGroundingLoss", 0.0) or 0.0),
    }
    score = _clamp(sum(comp[k] * float(w.get(k, 0.0) or 0.0) for k in comp))
    if score <= 0.18:
        profile = "low-loss"
    elif score <= 0.35:
        profile = "controlled-loss"
    elif score <= 0.55:
        profile = "medium-loss"
    else:
        profile = "high-loss"
    completeness = _clamp((comp["temporal_paradigm_loss"] + comp["stance_context_loss"]) * 0.5)
    fidelity = _clamp((comp["semantic_fidelity_loss"] + comp["evidence_grounding_loss"]) * 0.5)
    return {
        "score": round(score, 4),
        "mappingCompletenessLoss": round(completeness, 4),
        "mappingFidelityLoss": round(fidelity, 4),
        "profile": profile,
    }
