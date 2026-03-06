#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

GENRE_TO_TRACKS = {
    "cosmology_tensions": ["R2_early_universe", "R3_hubble_tension", "R8_modified_gravity_vs_LCDM"],
    "precision_anomalies": ["Q5_muon_gminus2_tension", "Q3_vacuum_energy"],
    "flavor_physics": ["Q7_strong_CP_problem", "Q9_baryogenesis_asymmetry"],
    "neutrino_sector": ["Q8_neutrino_mass_origin", "Q9_baryogenesis_asymmetry"],
    "gw_strong_gravity": ["R5_strong_gravity_tests", "R10_blackhole_interior_consistency"],
    "dark_sector": ["Q10_dark_matter_candidate_screening", "R8_modified_gravity_vs_LCDM"],
    "early_universe_bbn": ["R2_early_universe", "Q9_baryogenesis_asymmetry"],
    "unclassified": ["R2_early_universe"],
}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: inf_memory_to_inf_theory_projection.py <latest_json> <out_json>")
        return 2

    latest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_path = Path(sys.argv[2])

    projections = []
    genres = latest.get("genres") or {}
    for genre, blob in genres.items():
        tracks = GENRE_TO_TRACKS.get(genre, GENRE_TO_TRACKS["unclassified"])
        for rec in (blob.get("latest") or []):
            projections.append({
                "genre": genre,
                "doi": rec.get("doi"),
                "title": rec.get("title"),
                "published_at": rec.get("published_at"),
                "analysis_generation": rec.get("analysis_generation"),
                "suggested_inf_theory_tracks": tracks,
            })

    payload = {
        "schema": "inf-memory-to-inf-theory-projection-v1",
        "projection_count": len(projections),
        "items": projections,
        "mapping": GENRE_TO_TRACKS,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "projection_count": len(projections), "out": str(out_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
