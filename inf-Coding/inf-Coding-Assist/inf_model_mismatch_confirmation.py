#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSIM = ROOT / "inf-Coding" / "inf-Coding-Assist" / "observation_assimilation_prod_20260306.json"
REEVAL = ROOT / "inf-Coding" / "inf-Coding-Assist" / "observation_twenty_track_reeval_20260306.json"
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_mismatch_confirmation_20260306.json"

PRIMARY = ["R3_hubble_tension", "R8_modified_gravity_vs_LCDM", "Q5_muon_gminus2_tension"]
SECONDARY = ["Q8_neutrino_mass_origin", "Q9_baryogenesis_asymmetry", "Q10_dark_matter_candidate_screening", "Q3_vacuum_energy"]
LONG_HORIZON = ["Q2_information_problem", "R1_singularity", "R10_blackhole_interior_consistency", "R7_gravitational_wave_background_origin", "R6_global_topology", "R2_early_universe", "R4_cosmological_constant", "R9_initial_fluctuation_to_classical"]


def classify(track: dict) -> str:
    decision = track.get("decision")
    chi2r = track.get("chi2_reduced")
    if decision == "reject":
        return "confirmed_mismatch"
    if decision == "hold":
        return "candidate_mismatch"
    if decision == "adopt":
        return "currently_aligned"
    if chi2r is None:
        return "insufficient_numeric_constraints"
    return "candidate_mismatch"


def main() -> int:
    assim = json.loads(ASSIM.read_text(encoding="utf-8")) if ASSIM.exists() else {}
    reeval = json.loads(REEVAL.read_text(encoding="utf-8")) if REEVAL.exists() else {}

    tracks = reeval.get("tracks") or {}

    out_tracks = {}
    for name, t in tracks.items():
        out_tracks[name] = {
            "decision": t.get("decision"),
            "chi2_reduced": t.get("chi2_reduced"),
            "status": classify(t),
            "assigned_dataset_count": t.get("assigned_dataset_count", 0),
        }

    payload = {
        "schema": "katala-mismatch-confirmation-v1",
        "phase": "mismatch_primary_confirmation",
        "source": {
            "assimilation_bundle": str(ASSIM),
            "reevaluation": str(REEVAL),
        },
        "assimilated_records": ((assim.get("summary") or {}).get("assimilated_records")),
        "priority_axes": {
            "primary": PRIMARY,
            "secondary": SECONDARY,
            "long_horizon": LONG_HORIZON,
        },
        "tracks": out_tracks,
        "confirmed_mismatch_tracks": [k for k, v in out_tracks.items() if v.get("status") == "confirmed_mismatch"],
        "candidate_mismatch_tracks": [k for k, v in out_tracks.items() if v.get("status") == "candidate_mismatch"],
        "aligned_tracks": [k for k, v in out_tracks.items() if v.get("status") == "currently_aligned"],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "confirmed": payload["confirmed_mismatch_tracks"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
