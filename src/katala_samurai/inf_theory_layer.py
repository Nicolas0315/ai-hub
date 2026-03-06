from __future__ import annotations

from typing import Any

from .iut_counterexample_templates import counterexample_template_index
from .iut_physical_projection_map import physical_projection_index


def run_inf_theory_layer(prompt: str, unified: dict[str, Any] | None = None) -> dict[str, Any]:
    """Inf-Theory layer after KQ formal probe.

    Purpose:
    - Bridge KQ formal outputs with IUT-style theory modeling metadata
    - Produce machine-readable theory model snapshot for GR/QM unification workflows
    """
    u = unified or {}
    inv = (u.get("inter_universal_invariants") or {}) if isinstance(u, dict) else {}
    kq3 = (u.get("kq3_mode") or {}) if isinstance(u, dict) else {}

    inv_score = float(inv.get("invariant_preservation_score", 0.0) or 0.0)
    cx_ok = bool(((inv.get("counterexample_invariant") or {}).get("consistent", False)))
    truth_conflict = bool(inv.get("truth_conflict", False))
    observable_map = physical_projection_index()

    consistency_score = max(0.0, min(1.0, inv_score if not truth_conflict else inv_score * 0.5))
    counterexample_resilience = 1.0 if cx_ok else 0.0
    observable_projection_score = 1.0 if len(observable_map) > 0 else 0.0
    unified_admissibility = 1.0 if (consistency_score >= 0.72 and counterexample_resilience >= 1.0 and observable_projection_score >= 1.0) else 0.0

    weighted_total = round(
        0.35 * consistency_score
        + 0.25 * counterexample_resilience
        + 0.25 * observable_projection_score
        + 0.15 * unified_admissibility,
        4,
    )

    return {
        "enabled": True,
        "schema_version": "inf-theory-v1",
        "layer": "inf-theory",
        "goal": "gr_qm_unification_theory_modeling",
        "input": {
            "prompt": (prompt or "")[:400],
            "kq3_mode": kq3,
        },
        "scores": {
            "consistency_score": round(consistency_score, 4),
            "counterexample_resilience": round(counterexample_resilience, 4),
            "observable_projection_score": round(observable_projection_score, 4),
            "unified_admissibility": round(unified_admissibility, 4),
            "weighted_total": weighted_total,
        },
        "assets": {
            "counterexample_templates": counterexample_template_index(),
            "physical_projection_map": observable_map,
        },
        "status": {
            "strict_recommended": bool(weighted_total < 0.72),
            "truth_conflict": truth_conflict,
            "counterexample_consistent": cx_ok,
        },
        "unification_theory_model": {
            "name": "gr_qm_iut_unification_candidate",
            "adopted": bool(weighted_total >= 0.72),
            "scores": {
                "weighted_total": weighted_total,
                "consistency_score": round(consistency_score, 4),
                "counterexample_resilience": round(counterexample_resilience, 4),
                "observable_projection_score": round(observable_projection_score, 4),
                "unified_admissibility": round(unified_admissibility, 4),
            },
        },
    }
