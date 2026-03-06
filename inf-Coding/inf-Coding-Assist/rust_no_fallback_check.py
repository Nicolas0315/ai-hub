#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.rust_hotpath_bridge import dense_dependency_edges, invariant_preservation_score, strict_specificity_score, strict_triggered, precision_score  # noqa: E402


def main() -> int:
    os.environ["KQ_RUST_ONLY"] = "1"
    try:
        _ = invariant_preservation_score(False, 1.0, True, 1.0, 1.0, 1.0)
        _ = dense_dependency_edges(["A", "B"], ["L1", "L2"], ["m", "m"], ["i", "i"], [("A", "B")])
        _ = strict_specificity_score("forall x in [1,2,3]: x > 0")
        _ = strict_triggered(True, 0.90, True)
        _ = precision_score("d", "m", "i", "forall x in [1]: x==x")
        print(json.dumps({"ok": True, "mode": "rust-only"}, ensure_ascii=False))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "mode": "rust-only", "error": str(e)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
