#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')

from katala_samurai.inf_coding_adapter import emit_bridge_output


def run_ks47(query: str, report: str) -> dict:
    from katala_samurai.ks47_deep_research import KS47

    engine = KS47()
    r = engine.verify(query=query, report=report, fetch_urls=False)
    d = r.to_dict()

    solver_results = {
        "query_coverage": d["query_coverage"]["score"],
        "search_depth": d["search_depth"]["score"],
        "synthesis_quality": d["synthesis_quality"]["score"],
        "citation_verify": d["citation_verify"]["score"],
        "orchestration": d["orchestration"]["score"],
    }

    verdict = "SUPPORT" if d["overall_score"] >= 0.66 else ("UNCERTAIN" if d["overall_score"] >= 0.45 else "LEAN_REJECT")

    out = {
        "model": "KS47",
        "verdict": verdict,
        "confidence": round(float(d["overall_score"]), 3),
        "final_score": round(float(d["overall_score"]), 3),
        "route": "fast" if d["overall_score"] >= 0.66 else "strict",
        "mode": "ks47-direct",
        "grade": d.get("grade"),
        "solver_results": solver_results,
        "raw": d,
    }

    emit_bridge_output("KS47", {
        "alias": "KS47",
        "verdict": out["verdict"],
        "final_score": out["final_score"],
        "confidence": out["confidence"],
        "mode": out["mode"],
        "route": out["route"],
        "solver_results": solver_results,
    })

    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="inf-Coding KS bridge")
    ap.add_argument("--model", required=True, choices=["KS47"], help="Target KS model")
    ap.add_argument("--query", required=True)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    report = args.report if args.report else args.query

    try:
        if args.model == "KS47":
            out = run_ks47(query=args.query, report=report)
        else:
            raise RuntimeError(f"Unsupported model: {args.model}")
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:
        err = {"ok": False, "model": args.model, "error": str(e)}
        print(json.dumps(err, ensure_ascii=False), file=sys.stderr)
        return 70


if __name__ == "__main__":
    raise SystemExit(main())
