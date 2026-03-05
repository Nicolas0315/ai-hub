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

from katala_samurai.iut_core_subset_v1 import (  # noqa: E402
    evaluate_iut_core_subset_v1,
    evaluate_iut_core_subset_v1_staged,
)


def main() -> int:
    staged = str(os.getenv("IUT_STAGED_CHECK", "1")).strip().lower() not in {"0", "false", "no", "off"}
    out = evaluate_iut_core_subset_v1_staged() if staged else evaluate_iut_core_subset_v1()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
