#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys


def run_once(env_overrides: dict[str, str]) -> dict:
    env = os.environ.copy()
    env.update(env_overrides)
    p = subprocess.run(
        [sys.executable, "inf-Coding/inf-Coding-Assist/iut_subset_scaffold.py"],
        capture_output=True,
        text=True,
        env=env,
    )
    if p.returncode != 0:
        return {"ok": False, "error": (p.stderr or p.stdout)[-1200:]}
    j = json.loads(p.stdout)
    o = j.get("optimization", {})
    return {
        "ok": bool(j.get("ok")),
        "pass_ratio": j.get("pass_ratio"),
        "strict_batch_size": o.get("strict_batch_size"),
        "cross_budget_per_layer": o.get("cross_budget_per_layer"),
        "perf": o.get("perf", {}),
    }


def main() -> int:
    baseline = run_once({
        "IUT_STAGED_CHECK": "0",
        "IUT_STRICT_BATCH_SIZE": "1",
        "IUT_CROSS_BUDGET_PER_LAYER": "999",
    })
    optimized = run_once({
        "IUT_STAGED_CHECK": "0",
        "IUT_STRICT_BATCH_SIZE": "4",
        "IUT_CROSS_BUDGET_PER_LAYER": "2",
    })
    print(json.dumps({"baseline_like": baseline, "optimized": optimized}, ensure_ascii=False, indent=2))
    return 0 if baseline.get("ok") and optimized.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
