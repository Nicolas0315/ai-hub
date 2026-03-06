from __future__ import annotations

from typing import Any

INF_MEMORY_SCHEMA_VERSION = "inf-memory-v1"
ALLOWED_TOP_KEYS = {
    "enabled",
    "schema_version",
    "layer",
    "goal",
    "input",
    "peer_review_memory",
    "status",
}
TRUSTED_SOURCES = {"openalex", "crossref", "pubmed"}


def sanitize_inf_memory_output(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {
            "enabled": False,
            "schema_version": INF_MEMORY_SCHEMA_VERSION,
            "layer": "inf-memory",
            "goal": "peer_review_memory_only",
            "peer_review_memory": {"policy": "peer-reviewed-only", "count": 0, "papers": []},
            "status": {"writeback_forbidden": True, "sanitized": True},
        }

    out = {k: payload.get(k) for k in ALLOWED_TOP_KEYS if k in payload}
    out["schema_version"] = INF_MEMORY_SCHEMA_VERSION

    for section in ("status", "input"):
        v = out.get(section)
        if isinstance(v, dict):
            for banned in ["write_back", "kq_mutation", "kq_patch", "state_update", "apply_to_kq", "apply_to_inf_theory", "apply_to_inf_model"]:
                v.pop(banned, None)

    prm = out.get("peer_review_memory")
    if not isinstance(prm, dict):
        prm = {"policy": "peer-reviewed-only", "count": 0, "papers": []}
    papers = prm.get("papers") or []
    filtered = []
    for p in papers:
        if not isinstance(p, dict):
            continue
        src = str(p.get("source", "")).lower().strip()
        if src in TRUSTED_SOURCES:
            filtered.append(p)
    prm["policy"] = "peer-reviewed-only"
    prm["trusted_sources"] = sorted(list(TRUSTED_SOURCES))
    prm["papers"] = filtered
    prm["count"] = len(filtered)
    out["peer_review_memory"] = prm
    return out


def validate_inf_memory_output(payload: dict[str, Any]) -> dict[str, Any]:
    ok = True
    reasons: list[str] = []

    if not isinstance(payload, dict):
        return {"ok": False, "reasons": ["payload_not_dict"]}

    for k in payload.keys():
        if k not in ALLOWED_TOP_KEYS:
            ok = False
            reasons.append(f"unknown_top_key:{k}")

    if "peer_review_memory" not in payload:
        ok = False
        reasons.append("missing_peer_review_memory")
    elif isinstance(payload.get("peer_review_memory"), dict):
        for p in (payload["peer_review_memory"].get("papers") or []):
            src = str((p or {}).get("source", "")).lower().strip()
            if src not in TRUSTED_SOURCES:
                ok = False
                reasons.append(f"untrusted_source:{src}")

    if str(payload.get("schema_version", "")) != INF_MEMORY_SCHEMA_VERSION:
        ok = False
        reasons.append("invalid_schema_version")

    return {"ok": ok, "reasons": reasons}
