from __future__ import annotations

from typing import Any

INF_MODEL_SCHEMA_VERSION = "inf-model-v1"

ALLOWED_TOP_KEYS = {
    "enabled",
    "schema_version",
    "layer",
    "goal",
    "input",
    "katala_universe_model",
    "status",
}


def sanitize_inf_model_output(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "enabled": False,
            "schema_version": INF_MODEL_SCHEMA_VERSION,
            "layer": "inf-model",
            "goal": "katala_unified_universe_modeling",
            "katala_universe_model": {},
            "status": {"strict_recommended": True, "sanitized": True},
        }

    out = {k: payload.get(k) for k in ALLOWED_TOP_KEYS if k in payload}
    out["schema_version"] = INF_MODEL_SCHEMA_VERSION

    for section in ("status", "input"):
        v = out.get(section)
        if isinstance(v, dict):
            for banned in ["write_back", "kq_mutation", "kq_patch", "state_update", "apply_to_kq", "apply_to_inf_theory"]:
                v.pop(banned, None)

    out.setdefault("katala_universe_model", {})
    return out


def validate_inf_model_output(payload: dict[str, Any]) -> dict[str, Any]:
    ok = True
    reasons: list[str] = []

    if not isinstance(payload, dict):
        return {"ok": False, "reasons": ["payload_not_dict"]}

    for k in payload.keys():
        if k not in ALLOWED_TOP_KEYS:
            ok = False
            reasons.append(f"unknown_top_key:{k}")

    if "katala_universe_model" not in payload:
        ok = False
        reasons.append("missing_katala_universe_model")

    if str(payload.get("schema_version", "")) != INF_MODEL_SCHEMA_VERSION:
        ok = False
        reasons.append("invalid_schema_version")

    return {"ok": ok, "reasons": reasons}
