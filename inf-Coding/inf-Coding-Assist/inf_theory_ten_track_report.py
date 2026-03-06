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
    unified = {
        "inter_universal_invariants": {
            "invariant_preservation_score": 0.82,
            "counterexample_invariant": {"consistent": True},
            "truth_conflict": False,
        },
        "kq3_mode": {"public_mode": "balanced+strict", "strict_activated": False},
    }

    r = run_inf_theory_layer("ten-track-report", unified)
    model = r.get("unification_theory_model") or {}
    scores = model.get("scores") or {}
    wt = float(scores.get("weighted_total", 0.0) or 0.0)

    u1 = bool(((model.get("step1_singularity_resolution") or {}).get("result") or {}).get("pass", False))
    u2 = bool(((model.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False))
    u3 = bool(((model.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False))
    u4 = bool(((model.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False))
    u5 = bool(((model.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False))

    tracks = {
        "relativity_singularity": {"gates": ["UGT1"], "pass": u1},
        "relativity_early_universe": {"gates": ["UGT2"], "pass": u2},
        "relativity_hubble_tension": {"gates": ["UGT2", "UGT5"], "pass": (u2 and u5)},
        "relativity_cosmological_constant": {"gates": ["UGT2", "UGT5"], "pass": (u2 and u5)},
        "relativity_strong_gravity_tests": {"gates": ["UGT1", "UGT5"], "pass": (u1 and u5)},
        "quantum_gravity_interface": {"gates": ["UGT1", "UGT2", "UGT3", "UGT4"], "pass": (u1 and u2 and u3 and u4)},
        "quantum_information_problem": {"gates": ["UGT4", "UGT1"], "pass": (u4 and u1)},
        "quantum_vacuum_energy": {"gates": ["UGT3", "UGT5"], "pass": (u3 and u5)},
        "quantum_measurement_boundary": {"gates": ["UGT3", "UGT5"], "pass": (u3 and u5)},
        "quantum_gminus2_tension": {"gates": ["UGT5", "UGT3"], "pass": (u5 and u3)},
    }

    for t in tracks.values():
        t["decision"] = classify(bool(t["pass"]), wt)

    summary = {"adopt_count": 0, "hold_count": 0, "reject_count": 0}
    for t in tracks.values():
        summary[f"{t['decision']}_count"] += 1

    out = {
        "ok": True,
        "model": model.get("name"),
        "scores": scores,
        "tracks": tracks,
        "summary": summary,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
