#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVR = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_user_overrides.json"
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_parallel_discovery_run_20260306.json"


def _load_overrides() -> dict:
    if not OVR.exists():
        return {}
    return json.loads(OVR.read_text(encoding="utf-8"))


def main() -> int:
    o = _load_overrides()

    # Initial candidate pool (can be expanded by user later)
    candidates = [
        {
            "id": "ax_gravity_causal_primacy_v1",
            "statement": "Maximum causal reference is gravity-defined; light is derived signal layer.",
            "euclid_anchor": "comparison-morphism over Euclidean baseline",
        },
        {
            "id": "ax_add_mul_layer_separation_v1",
            "statement": "Additive and multiplicative geometric invariants are independently defined and only joined at projection.",
            "euclid_anchor": "metric/area relation separation",
        },
        {
            "id": "ax_continuous_dimension_effective_field_v1",
            "statement": "Dimension is continuous as effective parameter and recovers integer value in classical limit.",
            "euclid_anchor": "dimension handled via layer mapping, not fixed primitive",
        },
    ]

    # Track A: independent-axiom discovery under Euclidean baseline
    track_a = [c["id"] for c in candidates if c.get("euclid_anchor")]

    # Track B: requirements for gravity-referenced max speed statement
    track_b = [
        c["id"]
        for c in candidates
        if ("gravity" in c["statement"].lower())
        or ("causal" in c["statement"].lower())
        or ("dimension" in c["statement"].lower())
    ]

    # Track C: derivability classification (initial hypothesis pass)
    # False => not derivable from current baseline (treated as independent candidate)
    derivability = {
        "ax_gravity_causal_primacy_v1": False,
        "ax_add_mul_layer_separation_v1": False,
        "ax_continuous_dimension_effective_field_v1": False,
    }
    track_c = [cid for cid, derivable in derivability.items() if derivable is False]

    intersection = sorted(list(set(track_a) & set(track_b) & set(track_c)))

    payload = {
        "schema": "inf-model-parallel-discovery-run-v1",
        "policy": (o.get("expansion_plan") or {}).get("parallel_discovery_tracks", {}),
        "tracks": {
            "A_independent_axiom_discovery": track_a,
            "B_gravity_speed_requirements": track_b,
            "C_derivability_filter": {
                "accepted_as_independent": track_c,
                "derivability_map": derivability,
            },
        },
        "intersection_A_B_C": intersection,
        "candidates": candidates,
        "next_action": "promote intersection candidates into inf-model candidate_axioms for observational stress tests",
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "intersection_count": len(intersection), "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
