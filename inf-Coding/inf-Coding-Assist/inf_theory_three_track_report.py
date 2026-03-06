#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_theory_layer import run_inf_theory_layer  # noqa: E402


def classify(pass_flag: bool, weighted_total: float) -> str:
    if pass_flag and weighted_total >= 0.72:
        return "adopt"
    if weighted_total >= 0.55:
        return "hold"
    return "reject"


def main() -> int:
    # Shared baseline input for protocol run (replace with observed/fitted inputs when available).
    unified = {
        "inter_universal_invariants": {
            "invariant_preservation_score": 0.82,
            "counterexample_invariant": {"consistent": True},
            "truth_conflict": False,
        },
        "kq3_mode": {"public_mode": "balanced+strict", "strict_activated": False},
    }

    r = run_inf_theory_layer("three-track-report", unified)
    model = r.get("unification_theory_model") or {}
    scores = model.get("scores") or {}
    wt = float(scores.get("weighted_total", 0.0) or 0.0)

    qg_pass = bool(((model.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False))
    info_pass = bool(((model.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False))
    hubble_pass = bool(
        ((model.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False)
        and ((model.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False)
    )

    report = {
        "ok": True,
        "model": model.get("name"),
        "scores": scores,
        "tracks": {
            "quantum_gravity": {
                "gates": ["UGT1", "UGT2", "UGT3", "UGT4"],
                "pass": qg_pass,
                "decision": classify(qg_pass, wt),
            },
            "information_problem": {
                "gates": ["UGT4", "UGT1"],
                "pass": info_pass,
                "decision": classify(info_pass, wt),
            },
            "hubble_tension": {
                "gates": ["UGT2", "UGT5"],
                "pass": hubble_pass,
                "decision": classify(hubble_pass, wt),
            },
        },
        "summary": {
            "adopt_count": 0,
            "hold_count": 0,
            "reject_count": 0,
        },
    }

    for t in report["tracks"].values():
        report["summary"][f"{t['decision']}_count"] += 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
