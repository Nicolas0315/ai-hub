#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import sys
from pathlib import Path

sys.path.insert(0, "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src")
from katala_samurai.kq_symbolic_bridge import (  # noqa: E402
    solve_sat_lite,
    solve_smt_optional,
    solve_bitvec_lite,
    solve_array_lite,
    solve_uf_lite,
    solve_nra_lite,
    solve_zfc_lite,
    solve_hol_lite,
    solve_ctl_lite,
    solve_mu_lite,
)


def run_case(name: str, fn, expr: str):
    t0 = time.perf_counter()
    out = fn(expr)
    dt = (time.perf_counter() - t0) * 1000
    ok = bool(out.get("ok")) and str(out.get("proof_status", "")) in {"checked", "machine-verified"}
    return {
        "name": name,
        "ok": ok,
        "ms": round(dt, 3),
        "solver": out.get("solver"),
        "brief": {k: out.get(k) for k in ["result", "satisfiable", "solution_count", "consistent", "proof_status"] if k in out},
    }


def main():
    cases = [
        ("sat", solve_sat_lite, "(a or b) and (not a or c)"),
        ("smt", solve_smt_optional, "vars: x in [-3,3], y in [0,3]; formula: and(x+y==2, x>=0, y>=0)"),
        ("bitvec", solve_bitvec_lite, "width=8; x=250; y=10; op=add"),
        ("array", solve_array_lite, "size=4; store=1:7,2:9; select=2"),
        ("uf", solve_uf_lite, "eq: f(a)=b, f(a)=c, b!=c"),
        ("nra", solve_nra_lite, "vars: x in [-5,5], y in [-5,5]; formula: x*x + y*y == 25"),
        ("zfc", solve_zfc_lite, "A={1,2}; B={2}; check=subset(B,A)"),
        ("hol", solve_hol_lite, "forall x in [1,2,3]. x > 0"),
        ("ctl", solve_ctl_lite, "op=EF; p=[q,r,p]"),
        ("mu", solve_mu_lite, "mu X. p or X ; trace=[q,p]"),
    ]

    t0 = time.perf_counter()
    rows = [run_case(*c) for c in cases]
    total_ms = (time.perf_counter() - t0) * 1000
    success = sum(1 for r in rows if r["ok"])

    report = {
        "schema": "formal-upgrade-report-v1",
        "added_rule_families": ["sat-cdcl-lite", "smt-lite", "zfc-lite", "hol-lite", "ctl-lite", "mu-lite"],
        "success_cases": success,
        "failed_cases": len(rows) - success,
        "total_cases": len(rows),
        "total_infer_ms": round(total_ms, 3),
        "improvement_note": "operational-lite coverage expanded across SAT/SMT/foundation logic",
        "cases": rows,
    }

    out = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/formal_upgrade_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(out))


if __name__ == "__main__":
    main()
