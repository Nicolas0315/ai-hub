#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_theory_layer import run_inf_theory_layer  # noqa: E402

TRACKS = [
    "R1_singularity", "R2_early_universe", "R3_hubble_tension", "R4_cosmological_constant", "R5_strong_gravity_tests",
    "R6_global_topology", "R7_gravitational_wave_background_origin", "R8_modified_gravity_vs_LCDM", "R9_initial_fluctuation_to_classical", "R10_blackhole_interior_consistency",
    "Q1_quantum_gravity_interface", "Q2_information_problem", "Q3_vacuum_energy", "Q4_measurement_boundary", "Q5_muon_gminus2_tension",
    "Q6_hierarchy_problem", "Q7_strong_CP_problem", "Q8_neutrino_mass_origin", "Q9_baryogenesis_asymmetry", "Q10_dark_matter_candidate_screening",
]

MODEL_EXPECTED = {
    "obs_h0_cmb_inferred": 67.4,
    "obs_h0_local_distance_ladder": 67.4,
    "obs_s8_lss": 0.83,
    "obs_gw_strong_field_ringdown": 0.0,
    "obs_cmb_bao_early_universe_constraints": 0.699,
    "obs_muon_gminus2_fnal": 0.0011659200,
}


def _classify(ugt_pass: bool, chi2_red: float | None, wt: float) -> str:
    if chi2_red is None:
        return "hold"
    if ugt_pass and wt >= 0.72 and chi2_red <= 1.5:
        return "adopt"
    if chi2_red <= 3.0 and wt >= 0.55:
        return "hold"
    return "reject"


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: observation_twenty_track_reeval.py <observation_vector.json> <out.json>")
        return 2

    vec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    items = {it["dataset_id"]: it for it in vec.get("items", []) if isinstance(it, dict)}

    unified = {
        "inter_universal_invariants": {
            "invariant_preservation_score": 0.82,
            "counterexample_invariant": {"consistent": True},
            "truth_conflict": False,
        },
        "kq3_mode": {"public_mode": "balanced+strict", "strict_activated": False},
    }
    r = run_inf_theory_layer("twenty-track-observation-reeval", unified)
    model = r.get("unification_theory_model") or {}
    wt = float((model.get("scores") or {}).get("weighted_total", 0.0) or 0.0)
    gates_ok = bool(((model.get("step1_singularity_resolution") or {}).get("result") or {}).get("pass", False)) and \
               bool(((model.get("step2_early_universe_resolution") or {}).get("result") or {}).get("pass", False)) and \
               bool(((model.get("step3_quantum_gravity_resolution") or {}).get("result") or {}).get("pass", False)) and \
               bool(((model.get("step4_information_consistency_resolution") or {}).get("result") or {}).get("pass", False)) and \
               bool(((model.get("step5_experimental_validation_resolution") or {}).get("result") or {}).get("pass", False))

    by_track = {}
    for dsid, it in items.items():
        tr = it.get("used_by_track")
        if not tr:
            continue
        by_track.setdefault(tr, []).append(it)

    out_tracks = {}
    for tr in TRACKS:
        assigned = by_track.get(tr, [])
        contrib = []
        chi2 = 0.0
        dof = 0
        for a in assigned:
            dsid = a.get("dataset_id")
            if dsid not in MODEL_EXPECTED:
                continue
            sigma = a.get("sigma")
            val = a.get("value")
            if sigma in (None, 0) or val is None:
                continue
            z = (float(val) - float(MODEL_EXPECTED[dsid])) / float(sigma)
            chi2 += z * z
            dof += 1
            contrib.append({"dataset_id": dsid, "z": z})
        chi2_red = (chi2 / dof) if dof > 0 else None
        dec = _classify(gates_ok, chi2_red, wt)
        out_tracks[tr] = {
            "assigned_dataset_count": len(assigned),
            "dof": dof,
            "chi2": chi2 if dof > 0 else None,
            "chi2_reduced": chi2_red,
            "contrib": contrib,
            "decision": dec,
        }

    summary = {"adopt": 0, "hold": 0, "reject": 0}
    for v in out_tracks.values():
        summary[v["decision"]] += 1

    out = {
        "ok": True,
        "schema": "katala-observation-reeval-v1",
        "weighted_total": wt,
        "all_ugt_pass": gates_ok,
        "tracks": out_tracks,
        "summary": summary,
    }
    Path(sys.argv[2]).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "summary": summary, "out": str(Path(sys.argv[2]).resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
