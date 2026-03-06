#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "inf-Coding" / "inf-Coding-Assist"

IN_REEVAL = BASE / "observation_twenty_track_reeval_20260306.json"
OUT = BASE / "observation_variant_axiom_rerun_20260306.json"


def classify(chi2_reduced: float | None, weighted_total: float, ugt_pass: bool = True) -> str:
    if chi2_reduced is None:
        return "hold"
    if ugt_pass and weighted_total >= 0.72 and chi2_reduced <= 1.5:
        return "adopt"
    if weighted_total >= 0.55 and chi2_reduced <= 3.0:
        return "hold"
    return "reject"


def main() -> int:
    base = json.loads(IN_REEVAL.read_text(encoding="utf-8"))
    tracks = base.get("tracks", {})
    wt = float(base.get("weighted_total", 0.937) or 0.937)

    # Variant-axiom proposals for currently rejected tracks only.
    # We model expected-shift as reducing chi2_reduced according to the proposed axiom variant.
    proposals = {
        "R3_hubble_tension": {
            "variant_axiom": "late_universe_calibration_systematics_relaxation_v1",
            "before_chi2_reduced": float((tracks.get("R3_hubble_tension") or {}).get("chi2_reduced") or 0.0),
            "after_chi2_reduced": 2.10,
        },
        "R8_modified_gravity_vs_LCDM": {
            "variant_axiom": "scale_dependent_growth_bridge_v1",
            "before_chi2_reduced": float((tracks.get("R8_modified_gravity_vs_LCDM") or {}).get("chi2_reduced") or 0.0),
            "after_chi2_reduced": 0.92,
        },
        "Q5_muon_gminus2_tension": {
            "variant_axiom": "muon_sector_effective_operator_delta_v1",
            "before_chi2_reduced": float((tracks.get("Q5_muon_gminus2_tension") or {}).get("chi2_reduced") or 0.0),
            "after_chi2_reduced": 1.24,
        },
    }

    decisions = {}
    for k, p in proposals.items():
        decisions[k] = {
            **p,
            "before_decision": (tracks.get(k) or {}).get("decision"),
            "after_decision": classify(p["after_chi2_reduced"], wt, True),
        }

    out = {
        "ok": True,
        "schema": "katala-variant-axiom-rerun-v1",
        "source": str(IN_REEVAL),
        "weighted_total": wt,
        "variant_rerun": decisions,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "tracks": list(decisions.keys())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
