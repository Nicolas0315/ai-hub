from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _safe_load_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None
        with p.open("r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def run_inf_blender_layer(
    prompt: str,
    unified: dict[str, Any] | None = None,
    inf_memory: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    inf-Blender: executes observation assimilation step using inf-Memory references.

    Control plane comes from inf-Bridge via unified["observation_assimilation_control"].
    Data-plane references come from inf-Memory peer-reviewed records.
    """
    u = unified or {}
    mem = inf_memory or {}
    ctl = (u.get("observation_assimilation_control") or {}) if isinstance(u, dict) else {}

    job = (ctl.get("recommended_job") or {}) if isinstance(ctl, dict) else {}
    out_path = job.get("output") if isinstance(job, dict) else None
    loaded_bundle = _safe_load_json(str(out_path) if out_path else None)

    peer = (mem.get("peer_review_memory") or {}) if isinstance(mem, dict) else {}
    papers = peer.get("papers") or []

    if isinstance(loaded_bundle, dict):
        summary = (loaded_bundle.get("summary") or {}) if isinstance(loaded_bundle, dict) else {}
        mode = "bundle_loaded"
        assimilated = int(summary.get("assimilated_records", 0) or 0)
    else:
        mode = "memory_reference_only"
        assimilated = len(papers)

    return {
        "enabled": True,
        "schema_version": "inf-blender-v1",
        "layer": "inf-blender",
        "goal": "observation_assimilation_execution",
        "input": {
            "prompt": (prompt or "")[:400],
            "control_plane": "inf-bridge",
            "data_plane": "inf-memory",
        },
        "assimilation": {
            "mode": mode,
            "control": ctl,
            "bundle_path": out_path,
            "assimilated_records": assimilated,
            "memory_reference_count": len(papers),
        },
        "status": {
            "writeback_forbidden": True,
            "upstream_mutation_forbidden": True,
        },
    }
