from __future__ import annotations

from typing import Any


def run_inf_model_layer(prompt: str, inf_theory: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build universe-model candidate from Katala unification theory outputs.

    Downstream-only layer: consumes Inf-Theory, produces inf-Model artifacts.
    """
    t = inf_theory or {}
    utm = (t.get("unification_theory_model") or {}) if isinstance(t, dict) else {}
    scores = (utm.get("scores") or {}) if isinstance(utm, dict) else {}

    wt = float(scores.get("weighted_total", 0.0) or 0.0)
    ready = bool(wt >= 0.72)

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
            "status": "candidate" if ready else "hold",
            "readiness_score": round(wt, 4),
            "components": {
                "relativity_core": bool("relativity_foundation" in utm),
                "quantum_core": bool("quantum_foundation" in utm),
                "classical_limit_core": bool("classical_limit_foundation" in utm),
                "standard_model_core": bool("standard_model_foundation" in utm),
                "eft_bridge": bool("effective_field_theory_bridge" in utm),
                "observation_tests": bool("observational_projection_tests" in utm),
            },
            "ugt_gates": {
                "UGT1": (((utm.get("step1_singularity_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT2": (((utm.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT3": (((utm.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT4": (((utm.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False)),
                "UGT5": (((utm.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False)),
            },
        },
        "status": {
            "strict_recommended": bool(not ready),
            "writeback_forbidden": True,
        },
    }
