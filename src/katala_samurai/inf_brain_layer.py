from __future__ import annotations

from typing import Any

from .inf_theory_layer import run_inf_theory_layer
from .inf_theory_layer_policy import sanitize_inf_theory_output, validate_inf_theory_output
from .inf_model_layer import run_inf_model_layer
from .inf_model_layer_policy import sanitize_inf_model_output, validate_inf_model_output
from .inf_memory_layer import run_inf_memory_layer
from .inf_memory_layer_policy import sanitize_inf_memory_output, validate_inf_memory_output


def run_inf_brain_layer(prompt: str, unified: dict[str, Any] | None = None) -> dict[str, Any]:
    u = unified if isinstance(unified, dict) else {}
    gate = (u.get("kq_access_gate") or {}) if isinstance(u, dict) else {}
    granted = bool(gate.get("granted", False)) and str(gate.get("source", "")) == "kq"
    if not granted:
        return {
            "enabled": False,
            "schema_version": "inf-brain-v1",
            "layer": "inf-brain",
            "goal": "kq_post_layers_orchestration",
            "direction_policy": {
                "kq_to_inf_brain": "full-access",
                "inf_brain_to_kq": "no-access",
                "inf_brain_to_inf_bridge": "no-access",
                "inf_brain_to_inf_coding": "no-access",
                "writeback_forbidden": True,
                "upstream_mutation_forbidden": True,
                "inf_brain_retention": "manual-delete-only",
                "kq_mediated_access_required": True,
            },
            "status": {
                "blocked": True,
                "reason": "kq_mediated_access_required",
            },
            "validation": {"ok": False},
        }

    theory_raw = run_inf_theory_layer(prompt, unified)
    theory = sanitize_inf_theory_output(theory_raw)
    theory_validation = validate_inf_theory_output(theory)

    model_raw = run_inf_model_layer(prompt, theory)
    model = sanitize_inf_model_output(model_raw)
    model_validation = validate_inf_model_output(model)

    memory_raw = run_inf_memory_layer(prompt, unified)
    memory = sanitize_inf_memory_output(memory_raw)
    memory_validation = validate_inf_memory_output(memory)

    return {
        "enabled": True,
        "schema_version": "inf-brain-v1",
        "layer": "inf-brain",
        "goal": "kq_post_layers_orchestration",
        "direction_policy": {
            "kq_to_inf_brain": "full-access",
            "kq_unilateral_reference": "allowed_read_write",
            "inf_brain_to_kq": "no-access",
            "inf_brain_to_inf_bridge": "no-access",
            "inf_brain_to_inf_coding": "no-access",
            "writeback_forbidden": True,
            "upstream_mutation_forbidden": True,
            "inf_brain_retention": "manual-delete-only",
            "kq_mediated_access_required": True,
        },
        "sub_layers": {
            "inf_theory": theory,
            "inf_model": model,
            "inf_memory": memory,
        },
        "validation": {
            "inf_theory": theory_validation,
            "inf_model": model_validation,
            "inf_memory": memory_validation,
            "ok": bool(theory_validation.get("ok") and model_validation.get("ok") and memory_validation.get("ok")),
        },
    }
