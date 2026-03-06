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


DEFAULT_PROTOCOL = {
    "protocol": "katala_kq_observation_pruning_protocol_v1",
    "run_id": "QG-REVIEW-001",
    "theory_model": {"name": "grand_unification_katala_v1", "status": "hypothesis"},
    "gates": {"required": ["UGT1", "UGT2", "UGT3", "UGT4", "UGT5"], "all_must_pass": True},
    "fit": {"metric": "chi_square", "threshold_config": {"chi2_reduced_max": 1.5}},
    "decision": {
        "on_pass_all": "status_hypothesis_to_tested",
        "on_any_fail": "keep_hypothesis_and_record_failure",
    },
}


def _gate_results(model: dict) -> dict[str, bool]:
    return {
        "UGT1": bool(((model.get("step1_singularity_resolution") or {}).get("result") or {}).get("pass", False)),
        "UGT2": bool(((model.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False)),
        "UGT3": bool(((model.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False)),
        "UGT4": bool(((model.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False)),
        "UGT5": bool(((model.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False)),
    }


def main() -> int:
    protocol = DEFAULT_PROTOCOL
    if len(sys.argv) > 1:
        protocol = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    # Placeholder unified input for protocol dry-run
    unified = {
        "inter_universal_invariants": {
            "invariant_preservation_score": 0.82,
            "counterexample_invariant": {"consistent": True},
            "truth_conflict": False,
        },
        "kq3_mode": {"public_mode": "balanced+strict", "strict_activated": False},
    }

    result = run_inf_theory_layer(protocol.get("run_id", "run"), unified)
    model = result.get("unification_theory_model") or {}
    gates = _gate_results(model)

    all_pass = all(gates.values())
    current_status = str(model.get("current_status", "hypothesis"))
    final_status = "tested" if all_pass else current_status

    out = {
        "ok": True,
        "protocol": protocol.get("protocol"),
        "run_id": protocol.get("run_id"),
        "model": model.get("name"),
        "gates": gates,
        "all_pass": all_pass,
        "status_before": current_status,
        "status_after": final_status,
        "scores": model.get("scores"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
