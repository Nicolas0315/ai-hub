#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_theory_layer_policy import sanitize_inf_theory_output, validate_inf_theory_output  # noqa: E402


def main() -> int:
    malicious = {
        "enabled": True,
        "schema_version": "inf-theory-v1",
        "layer": "inf-theory",
        "goal": "gr_qm_unification_theory_modeling",
        "status": {
            "strict_recommended": False,
            "write_back": True,
            "kq_mutation": {"set": "bad"},
        },
        "input": {"apply_to_kq": True, "prompt": "x"},
        "unification_theory_model": {"name": "candidate"},
    }

    sanitized = sanitize_inf_theory_output(malicious)
    validation = validate_inf_theory_output(sanitized)

    leaked = False
    for key in ["write_back", "kq_mutation", "apply_to_kq", "state_update", "kq_patch"]:
        if key in (sanitized.get("status") or {}) or key in (sanitized.get("input") or {}):
            leaked = True

    ok = bool(validation.get("ok")) and not leaked and "unification_theory_model" in sanitized
    print(json.dumps({"ok": ok, "validation": validation, "leaked": leaked}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
