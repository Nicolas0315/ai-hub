from __future__ import annotations

from typing import Any


def _collect_equations(prefix: str, obj: Any, out: list[dict[str, str]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, str) and (k.endswith("_latex") or "equation" in k or "relation" in k or "line_element" in k or "commutator" in k or "uncertainty" in k):
                out.append({"id": path, "latex": v})
            else:
                _collect_equations(path, v, out)


def run_inf_model_layer(prompt: str, inf_theory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build universe-model candidate from Katala unification theory outputs.

    Downstream-only layer: consumes Inf-Theory, produces inf-Model artifacts.
    """
    t = inf_theory or {}
    utm = (t.get("unification_theory_model") or {}) if isinstance(t, dict) else {}
    scores = (utm.get("scores") or {}) if isinstance(utm, dict) else {}

    wt = float(scores.get("weighted_total", 0.0) or 0.0)
    ready = bool(wt >= 0.72)

    equations: list[dict[str, str]] = []
    for section in [
        "relativity_foundation",
        "quantum_foundation",
        "classical_limit_foundation",
        "standard_model_foundation",
        "effective_field_theory_bridge",
        "observational_projection_tests",
    ]:
        _collect_equations(section, utm.get(section), equations)

    equation_markdown = "\n".join([f"- `{e['id']}`: $${e['latex']}$$" for e in equations])

    return {
        "enabled": True,
        "schema_version": "inf-model-v1",
        "layer": "inf-model",
        "goal": "katala_unified_universe_modeling",
        "input": {
            "prompt": (prompt or "")[:400],
            "source_model": utm.get("name", "unknown"),
        },
        "katala_universe_model": {
            "name": "katala_unified_universe_model_v1",
            "status": ("tested" if ready else "hypothesis"),
            "allowed_statuses": ["hypothesis", "tested", "rejected_consistent_variant", "adopted"],
            "readiness_score": round(wt, 4),
            "components": {
                "relativity_core": bool("relativity_foundation" in utm),
                "quantum_core": bool("quantum_foundation" in utm),
                "classical_limit_core": bool("classical_limit_foundation" in utm),
                "standard_model_core": bool("standard_model_foundation" in utm),
                "eft_bridge": bool("effective_field_theory_bridge" in utm),
                "observation_tests": bool("observational_projection_tests" in utm),
            },
            "axiom_sandbox": {
                "baseline_axioms": [
                    "lorentz_invariance",
                    "unitary_quantum_evolution",
                    "equivalence_principle",
                ],
                "variant_axioms": [
                    "effective_lorentz_violation",
                    "scale_dependent_invariants",
                ],
                "selection_rule": "consistency+projection+chi2_strict",
                "notes": "Variants are allowed for exploration but cannot be adopted unless strict validation passes.",
            },
            "ugt_gates": {
                "UGT1": (((utm.get("step1_singularity_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT2": (((utm.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT3": (((utm.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT4": (((utm.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT5": (((utm.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False)),
            },
            "equation_catalog": {
                "count": len(equations),
                "items": equations,
                "readable_markdown": equation_markdown,
            },
            "decision_policy": {
                "adoption_requires": ["consistency", "projection", "chi_square"],
                "retain_rejected_variants": True,
                "rejected_variant_status": "rejected_consistent_variant",
            },
        },
        "status": {
            "strict_recommended": bool(not ready),
            "writeback_forbidden": True,
        },
    }
