#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_memory_inf_theory_projection_20260306_top500.json"
GAP = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_gap_fill_plan_20260306.json"
OUT = ROOT / "inf-Coding" / "inf-Coding-Assist" / "inf_model_mapping_fix_table_20260306.json"


def main() -> int:
    p = json.loads(PROJ.read_text(encoding="utf-8")) if PROJ.exists() else {}
    g = json.loads(GAP.read_text(encoding="utf-8")) if GAP.exists() else {}

    confirmed = {s.get("track"): s for s in (g.get("steps") or []) if isinstance(s, dict)}

    by_track: dict[str, list[dict]] = defaultdict(list)
    for it in (p.get("items") or []):
        for t in (it.get("suggested_inf_theory_tracks") or []):
            by_track[str(t)].append(it)

    table = []
    for track, step in confirmed.items():
        refs = by_track.get(track, [])
        genre_counts: dict[str, int] = defaultdict(int)
        for r in refs:
            genre_counts[str(r.get("genre", "unclassified"))] += 1
        table.append(
            {
                "track": track,
                "iut_patch": step.get("iut_patch"),
                "required_math_link": ((step.get("gap_block") or {}).get("required_math_link")),
                "observation_links": {
                    "count": len(refs),
                    "genre_counts": dict(sorted(genre_counts.items())),
                    "sample_doi": [r.get("doi") for r in refs[:10]],
                },
                "status": "mapped",
            }
        )

    payload = {
        "schema": "katala-observation-theory-model-mapping-v1",
        "phase": "observation_to_theory_to_model_mapping_fix",
        "rows": table,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "rows": len(table), "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
