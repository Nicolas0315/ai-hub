#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_brain_layer_policy import sanitize_inf_brain_output, validate_inf_brain_output  # noqa: E402


def main() -> int:
    payload = {
        "enabled": True,
        "schema_version": "inf-brain-v1",
        "layer": "inf-brain",
        "goal": "kq_post_layers_orchestration",
        "direction_policy": {
            "kq_to_inf_brain": "full-access",
            "inf_brain_to_kq": "write",  # malicious
            "writeback_forbidden": False,
        },
        "sub_layers": {},
        "validation": {"ok": True},
    }

    s = sanitize_inf_brain_output(payload)
    v = validate_inf_brain_output(s)
    ok = bool(v.get("ok")) and str((s.get("direction_policy") or {}).get("inf_brain_to_kq")) == "no-access"
    print(json.dumps({"ok": ok, "validation": v, "direction_policy": s.get("direction_policy")}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
