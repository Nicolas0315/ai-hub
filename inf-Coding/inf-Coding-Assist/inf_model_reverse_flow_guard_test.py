#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_model_layer_policy import sanitize_inf_model_output, validate_inf_model_output  # noqa: E402


def main() -> int:
    malicious = {
        "enabled": True,
        "schema_version": "inf-model-v1",
        "layer": "inf-model",
        "goal": "katala_unified_universe_modeling",
        "status": {
            "strict_recommended": False,
            "write_back": True,
            "kq_mutation": {"set": "bad"},
            "apply_to_inf_theory": True,
        },
        "input": {"apply_to_kq": True, "prompt": "x"},
        "katala_universe_model": {"name": "candidate"},
    }

    sanitized = sanitize_inf_model_output(malicious)
    validation = validate_inf_model_output(sanitized)

    leaked = False
    for key in ["write_back", "kq_mutation", "apply_to_kq", "state_update", "kq_patch", "apply_to_inf_theory"]:
        if key in (sanitized.get("status") or {}) or key in (sanitized.get("input") or {}):
            leaked = True

    ok = bool(validation.get("ok")) and not leaked and "katala_universe_model" in sanitized
    print(json.dumps({"ok": ok, "validation": validation, "leaked": leaked}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
