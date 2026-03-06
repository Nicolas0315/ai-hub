from __future__ import annotations

from typing import Any

INF_BRAIN_SCHEMA_VERSION = "inf-brain-v1"
ALLOWED_TOP_KEYS = {
    "enabled",
    "schema_version",
    "layer",
    "goal",
    "direction_policy",
    "sub_layers",
    "validation",
}


def sanitize_inf_brain_output(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "enabled": False,
            "schema_version": INF_BRAIN_SCHEMA_VERSION,
            "layer": "inf-brain",
            "goal": "kq_post_layers_orchestration",
            "direction_policy": {
                "kq_to_inf_brain": "full-access",
                "inf_brain_to_kq": "no-access",
                "writeback_forbidden": True,
            },
            "sub_layers": {},
            "validation": {"ok": False},
        }

    out = {k: payload.get(k) for k in ALLOWED_TOP_KEYS if k in payload}
    out["schema_version"] = INF_BRAIN_SCHEMA_VERSION
    out.setdefault("direction_policy", {
        "kq_to_inf_brain": "full-access",
        "inf_brain_to_kq": "no-access",
        "writeback_forbidden": True,
    })
    dp = out.get("direction_policy") or {}
    if not isinstance(dp, dict):
        dp = {}
    dp["kq_to_inf_brain"] = "full-access"
    dp["inf_brain_to_kq"] = "no-access"
    dp["writeback_forbidden"] = True
    out["direction_policy"] = dp
    out.setdefault("sub_layers", {})
    out.setdefault("validation", {"ok": False})
    return out


def validate_inf_brain_output(payload: dict[str, Any]) -> dict[str, Any]:
    ok = True
    reasons: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "reasons": ["payload_not_dict"]}

    for k in payload.keys():
        if k not in ALLOWED_TOP_KEYS:
            ok = False
            reasons.append(f"unknown_top_key:{k}")

    if str(payload.get("schema_version", "")) != INF_BRAIN_SCHEMA_VERSION:
        ok = False
        reasons.append("invalid_schema_version")

    dp = payload.get("direction_policy") or {}
    if str(dp.get("inf_brain_to_kq", "")) != "no-access":
        ok = False
        reasons.append("invalid_direction_policy")

    return {"ok": ok, "reasons": reasons}
