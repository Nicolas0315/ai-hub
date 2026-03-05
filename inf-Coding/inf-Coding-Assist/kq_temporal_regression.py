#!/usr/bin/env python3
"""KQ temporal logic fixed regression suite.

Covers operator-level smoke checks for:
!, &, |, ->, <->, X, Y, F, G, O, H, U, R, W, S, T,
and CTL aliases EX, AX, EF, AF, EG, AG.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from katala_samurai.kq_symbolic_bridge import eval_ltl_lite, solve_ctl_lite


def _long_trace_perf() -> dict:
    trace = ['p'] * 2200
    expr = f"G p @ {trace}"
    t0 = time.perf_counter()
    r = eval_ltl_lite(expr)
    ms = (time.perf_counter() - t0) * 1000.0
    mode = str(r.get("mode") or "")
    ok = bool(r.get("ok")) and bool(r.get("result")) and ("windowed" in mode)
    return {
        "name": "long-trace-auto-window",
        "ok": ok,
        "mode": mode,
        "elapsed_ms": round(ms, 3),
        "memo_entries": int(r.get("memo_entries") or 0),
        "windowed": bool(r.get("windowed")),
    }


def run_suite() -> dict:
    ltl_cases = [
        ("!", "! p @ ['q']", True),
        ("&", "(p & q) @ [['p','q']]", True),
        ("|", "(p | q) @ ['q']", True),
        ("->", "(p -> q) @ ['q']", True),
        ("<->", "(p <-> p) @ ['p']", True),
        ("X", "X p @ ['q','p']", True),
        ("Y", "Y p @ ['p','p']", False),
        ("F", "F p @ ['q','p']", True),
        ("G", "G p @ ['p','p']", True),
        ("O", "O p @ ['q','p']", False),
        ("H", "H p @ ['p','p']", True),
        ("U", "p U q @ ['p','p','q']", True),
        ("R", "p R q @ ['q','q','p']", False),
        ("W", "p W q @ ['p','p']", True),
        ("S", "p S q @ ['q','p','p']", True),
        ("T", "p T q @ ['q','q','q']", True),
    ]

    ctl_cases = [
        ("EX", "formula=EX p; trace=['q','p']", True),
        ("AX", "formula=AX p; trace=['q','p']", True),
        ("EF", "formula=EF p; trace=['q','p']", True),
        ("AF", "formula=AF p; trace=['q','p']", True),
        ("EG", "formula=EG p; trace=['p','p']", True),
        ("AG", "formula=AG p; trace=['p','p']", True),
    ]

    results = []
    passed = 0

    for op, expr, expected in ltl_cases:
        r = eval_ltl_lite(expr)
        got = bool(r.get("result")) if r.get("ok") else None
        ok = (got is expected)
        passed += 1 if ok else 0
        results.append({"family": "LTL", "op": op, "ok": ok, "expected": expected, "got": got, "mode": r.get("mode")})

    for op, expr, expected in ctl_cases:
        r = solve_ctl_lite(expr)
        got = bool(r.get("result")) if r.get("ok") else None
        ok = (got is expected)
        passed += 1 if ok else 0
        results.append({"family": "CTL", "op": op, "ok": ok, "expected": expected, "got": got, "mode": r.get("mode")})

    perf = _long_trace_perf()
    results.append({"family": "PERF", "op": perf["name"], "ok": perf["ok"], "expected": True, "got": perf["ok"], "mode": perf.get("mode")})
    passed += 1 if perf["ok"] else 0

    total = len(results)
    return {
        "suite": "kq-temporal-regression-v2",
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_ratio": round((passed / total) if total else 0.0, 4),
        "results": results,
        "perf": perf,
    }


if __name__ == "__main__":
    out = run_suite()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["failed"] == 0 else 1)
