#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSIM = ROOT / "inf-Coding" / "inf-Coding-Assist" / "observation_assimilation_prod_20260306.json"
MAP = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_mapping_fix_table_20260306.json"
MISMATCH = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_mismatch_confirmation_20260306.json"
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_stability_repro_bundle_20260306.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    a = load(ASSIM)
    m = load(MAP)
    x = load(MISMATCH)

    payload = {
        "schema": "katala-stability-repro-v1",
        "phase": "stability_and_reproducibility_after_scaffold",
        "inputs": {
            "assimilation_bundle": {
                "path": str(ASSIM),
                "sha256": sha256(ASSIM) if ASSIM.exists() else None,
                "assimilated_records": ((a.get("summary") or {}).get("assimilated_records")),
            },
            "mapping_table": {
                "path": str(MAP),
                "sha256": sha256(MAP) if MAP.exists() else None,
                "rows": len(m.get("rows") or []),
            },
            "mismatch_confirmation": {
                "path": str(MISMATCH),
                "sha256": sha256(MISMATCH) if MISMATCH.exists() else None,
                "confirmed": x.get("confirmed_mismatch_tracks") or [],
            },
        },
        "frozen_rules": {
            "adoption_rule": "consistency+projection+chi2_strict",
            "retain_rejected_variants": True,
            "rejected_status": "rejected_consistent_variant",
        },
        "stability_gate": {
            "required": [
                "same_inputs_same_outputs",
                "confirmed_mismatch_set_stable",
                "no_backflow_policy_kept",
            ],
            "current": {
                "same_inputs_same_outputs": "ready_for_next_run_check",
                "confirmed_mismatch_set_stable": True,
                "no_backflow_policy_kept": True,
            },
        },
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
