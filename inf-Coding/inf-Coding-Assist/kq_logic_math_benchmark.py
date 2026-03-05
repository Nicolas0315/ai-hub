#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.kq_symbolic_bridge import solve_hol_lite, solve_smt_optional  # noqa: E402

CASES = [
    {"domain": "number-theory", "solver": "hol", "expr": "exists x in [2,3,4,5]: x % 2 == 1"},
    {"domain": "number-theory", "solver": "smt", "expr": "x in [1,10]: x % 3 == 0 and x > 5"},
    {"domain": "analysis", "solver": "hol", "expr": "forall x in [-1,0,1]: x*x >= 0"},
    {"domain": "analysis", "solver": "smt", "expr": "x in [-3,3]: x*x >= 0"},
    {"domain": "algebra", "solver": "hol", "expr": "forall x in [0,1,2]: x + 0 == x"},
    {"domain": "algebra", "solver": "smt", "expr": "x in [0,5]: x + 1 > x"},
]


def run_one(c):
    if c["solver"] == "hol":
        r = solve_hol_lite(c["expr"])
    else:
        r = solve_smt_optional(c["expr"])
    ok = bool(r.get("ok")) and str(r.get("proof_status", "")).lower() != "failed"
    return {
        "domain": c["domain"],
        "solver": c["solver"],
        "ok": ok,
        "proof_status": r.get("proof_status"),
        "strategy": ((r.get("proof_trace_human") or {}).get("strategy") if isinstance(r, dict) else None),
    }


def main() -> int:
    rows = [run_one(c) for c in CASES]
    passed = sum(1 for x in rows if x["ok"])
    by_domain = {}
    for r in rows:
        d = r["domain"]
        by_domain.setdefault(d, {"total": 0, "passed": 0})
        by_domain[d]["total"] += 1
        by_domain[d]["passed"] += 1 if r["ok"] else 0
    print(json.dumps({"suite": "kq-logic-math-benchmark-v1", "passed": passed, "total": len(rows), "by_domain": by_domain}, ensure_ascii=False))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
