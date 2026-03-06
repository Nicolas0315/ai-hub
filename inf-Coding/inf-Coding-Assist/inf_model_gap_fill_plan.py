#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MISMATCH = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_mismatch_confirmation_20260306.json"
OVR = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_user_overrides.json"
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_gap_fill_plan_20260306.json"


def main() -> int:
    m = json.loads(MISMATCH.read_text(encoding="utf-8")) if MISMATCH.exists() else {}
    o = json.loads(OVR.read_text(encoding="utf-8")) if OVR.exists() else {}

    confirmed = m.get("confirmed_mismatch_tracks") or []
    xp = (o.get("expansion_plan") or {}) if isinstance(o, dict) else {}
    patch_map = (xp.get("mismatch_to_iut_patch_map") or {}) if isinstance(xp, dict) else {}
    gap_blocks = (xp.get("theory_gap_blocks") or {}) if isinstance(xp, dict) else {}

    steps = []
    for t in confirmed:
        steps.append(
            {
                "track": t,
                "iut_patch": patch_map.get(t),
                "gap_block": gap_blocks.get(t),
                "action": "implement_math_link_then_reproject",
            }
        )

    payload = {
        "schema": "katala-gap-fill-plan-v1",
        "phase": "theory_scaffold_gap_fill",
        "confirmed_mismatch_tracks": confirmed,
        "steps": steps,
        "next": "observation_to_theory_to_model_mapping_fix",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "steps": len(steps)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
