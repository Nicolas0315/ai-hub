from __future__ import annotations

from typing import Any

INF_THEORY_SCHEMA_VERSION = "inf-theory-v1"

ALLOWED_TOP_KEYS = {
    "enabled",
    "schema_version",
    "layer",
    "goal",
    "input",
    "scores",
    "assets",
    "status",
    "unification_theory_model",
}


def sanitize_inf_theory_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Enforce one-way boundary: inf-Theory output cannot carry write-back directives.

    Keeps only schema-approved keys and strips any control/writeback hints.
    """
    if not isinstance(payload, dict):
        return {
            "enabled": False,
            "schema_version": INF_THEORY_SCHEMA_VERSION,
            "layer": "inf-theory",
            "goal": "gr_qm_unification_theory_modeling",
            "unification_theory_model": {},
            "status": {"strict_recommended": True, "sanitized": True},
        }

    out = {k: payload.get(k) for k in ALLOWED_TOP_KEYS if k in payload}
    out["schema_version"] = INF_THEORY_SCHEMA_VERSION

    # hard-strip possible write-back hints even if nested in status/input
    for section in ("status", "input"):
        v = out.get(section)
        if isinstance(v, dict):
            for banned in ["write_back", "kq_mutation", "kq_patch", "state_update", "apply_to_kq"]:
                v.pop(banned, None)

    out.setdefault("unification_theory_model", {})
    return out


def validate_inf_theory_output(payload: dict[str, Any]) -> dict[str, Any]:
    ok = True
    reasons: list[str] = []

    if not isinstance(payload, dict):
        return {"ok": False, "reasons": ["payload_not_dict"]}

    for k in payload.keys():
        if k not in ALLOWED_TOP_KEYS:
            ok = False
            reasons.append(f"unknown_top_key:{k}")

    if "unification_theory_model" not in payload:
        ok = False
        reasons.append("missing_unification_theory_model")

    sv = str(payload.get("schema_version", ""))
    if sv != INF_THEORY_SCHEMA_VERSION:
        ok = False
        reasons.append("invalid_schema_version")

    return {"ok": ok, "reasons": reasons}
