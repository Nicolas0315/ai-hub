#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.kq_symbolic_bridge import (  # noqa: E402
    _apply_family_grammar_templates,
    solve_hol_lite,
    solve_sat_lite,
    solve_smt_optional,
)

TRANSFORM_CASES = [
    {"solver": "sat", "family": "indo-european", "expr": "if p then q", "contains": "->"},
    {"solver": "sat", "family": "japonic", "expr": "もし p なら q", "contains": "->"},
    {"solver": "sat", "family": "sino-tibetan", "expr": "如果 p 那么 q", "contains": "->"},
    {"solver": "sat", "family": "koreanic", "expr": "만약 p 이면 q", "contains": "->"},
    {"solver": "sat", "family": "indo-european", "expr": "p unless q", "contains": "->"},
    {"solver": "sat", "family": "indo-european", "expr": "p only if q", "contains": "->"},
    {"solver": "sat", "family": "indo-european", "expr": "p iff q", "contains": "<->"},
]

SOLVER_CASES = [
    {"solver": "sat", "expr": "(p or q) and (not p or q)", "expect_ok": True},
    {"solver": "sat", "expr": "(p) and (not p)", "expect_ok": True},
    {"solver": "smt", "expr": "x in [0,5]: x between 2 and 4", "expect_ok": True},
    {"solver": "smt", "expr": "vars: x in [0,5], y in [0,5]; formula: and(x+y==4, x>=1)", "expect_ok": True},
]


def run_transform_case(c: dict[str, Any]) -> dict[str, Any]:
    out, notes = _apply_family_grammar_templates(c["expr"], c["family"], c["solver"])
    ok = c["contains"] in out
    return {"kind": "transform", "ok": ok, "expr": c["expr"], "out": out, "notes": notes}


def run_solver_case(c: dict[str, Any]) -> dict[str, Any]:
    if c["solver"] == "sat":
        r = solve_sat_lite(c["expr"])
    elif c["solver"] == "smt":
        r = solve_smt_optional(c["expr"])
    else:
        r = solve_hol_lite(c["expr"])
    ok = bool(r.get("ok")) and str(r.get("proof_status", "")).lower() != "failed"
    return {
        "kind": "solver",
        "solver": c["solver"],
        "ok": ok,
        "expr": c["expr"],
        "proof_status": r.get("proof_status"),
    }


def main() -> int:
    rows = [run_transform_case(c) for c in TRANSFORM_CASES] + [run_solver_case(c) for c in SOLVER_CASES]
    passed = sum(1 for r in rows if r["ok"])
    total = len(rows)
    print(json.dumps({"suite": "kq-deep-grammar-regression-v2", "passed": passed, "total": total, "pass_ratio": round(passed/max(1,total),4)}, ensure_ascii=False))
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
