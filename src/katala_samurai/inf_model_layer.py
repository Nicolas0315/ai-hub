from __future__ import annotations

from typing import Any
import json
import os


def _collect_equations(prefix: str, obj: Any, out: list[dict[str, str]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, str) and (k.endswith("_latex") or "equation" in k or "relation" in k or "line_element" in k or "commutator" in k or "uncertainty" in k):
                out.append({"id": path, "latex": v})
            else:
                _collect_equations(path, v, out)


def _load_user_model_edit_file() -> dict[str, Any]:
    """
    User-editable inf-Model override file.
    Intended for human review + manual tweaks without touching Python code.
    """
    path = os.getenv(
        "INF_MODEL_EDIT_FILE",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/inf_model_user_overrides.json",
    )
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _apply_user_overrides(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    if not overrides:
        return base

    m = dict(base)
    user_name = overrides.get("model_name")
    if isinstance(user_name, str) and user_name.strip():
        m["name"] = user_name.strip()

    sandbox = dict(m.get("axiom_sandbox") or {})
    if isinstance(overrides.get("baseline_axioms"), list):
        sandbox["baseline_axioms"] = [str(x) for x in overrides.get("baseline_axioms")]
    if isinstance(overrides.get("variant_axioms"), list):
        sandbox["variant_axioms"] = [str(x) for x in overrides.get("variant_axioms")]
    if isinstance(overrides.get("selection_rule"), str) and overrides.get("selection_rule").strip():
        sandbox["selection_rule"] = overrides.get("selection_rule").strip()
    if isinstance(overrides.get("notes"), str):
        sandbox["notes"] = overrides.get("notes")
    m["axiom_sandbox"] = sandbox

    dp = dict(m.get("decision_policy") or {})
    if isinstance(overrides.get("adoption_requires"), list):
        dp["adoption_requires"] = [str(x) for x in overrides.get("adoption_requires")]
    if isinstance(overrides.get("retain_rejected_variants"), bool):
        dp["retain_rejected_variants"] = bool(overrides.get("retain_rejected_variants"))
    if isinstance(overrides.get("rejected_variant_status"), str) and overrides.get("rejected_variant_status").strip():
        dp["rejected_variant_status"] = overrides.get("rejected_variant_status").strip()
    m["decision_policy"] = dp

    if isinstance(overrides.get("paradigm_policy"), dict):
        m["paradigm_policy"] = dict(overrides.get("paradigm_policy") or {})

    if isinstance(overrides.get("priority_targets"), list):
        m["priority_targets"] = [str(x) for x in overrides.get("priority_targets")]
    if isinstance(overrides.get("expansion_plan"), dict):
        m["expansion_plan"] = dict(overrides.get("expansion_plan") or {})

    m["user_override_file"] = {
        "path": os.getenv(
            "INF_MODEL_EDIT_FILE",
            "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/inf_model_user_overrides.json",
        ),
        "applied": True,
    }
    return m


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

    base_model = {
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
        "paradigm_policy": {
            "math_revision_drives_physics_revision": True,
            "kq_iut_is_math_revision_core": True,
            "inf_brain_inf_model_is_model_revision_core": True,
            "summary": "Katala treats mathematics-first reformulation as the driver of physics-model paradigm updates.",
        },
        "priority_targets": [
            "R3_hubble_tension",
            "R8_modified_gravity_vs_LCDM",
            "Q5_muon_gminus2_tension",
        ],
        "expansion_plan": {
            "phase": "priority_three_plus_secondary_wave",
            "goal": "improve_model_selection_power_under_math_revised_kq",
            "track_groups": {
                "relativity": ["R3_hubble_tension", "R8_modified_gravity_vs_LCDM"],
                "quantum": ["Q5_muon_gminus2_tension"],
                "secondary_wave": [
                    "Q8_neutrino_mass_origin",
                    "Q9_baryogenesis_asymmetry",
                    "Q10_dark_matter_candidate_screening",
                    "Q3_vacuum_energy",
                ],
            },
            "constraints": {
                "keep_adoption_rule": "consistency+projection+chi2_strict",
                "retain_rejected_variants": True,
            },
        },
    }

    overrides = _load_user_model_edit_file()
    model_out = _apply_user_overrides(base_model, overrides)

    return {
        "enabled": True,
        "schema_version": "inf-model-v1",
        "layer": "inf-model",
        "goal": "katala_unified_universe_modeling",
        "input": {
            "prompt": (prompt or "")[:400],
            "source_model": utm.get("name", "unknown"),
        },
        "katala_universe_model": model_out,
        "status": {
            "strict_recommended": bool(not ready),
            "writeback_forbidden": True,
        },
    }
