#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def infer_genres(text: str) -> list[str]:
    t = (text or "").lower()
    rules = [
        ("cosmology_tensions", ["hubble", "h0", "s8", "sigma8", "bao", "cmb", "cosmolog"]),
        ("precision_anomalies", ["g-2", "g2", "muon", "w boson", "electric dipole", "edm"]),
        ("flavor_physics", ["flavor", "rare decay", "rk", "rk*", "ckm", "b meson"]),
        ("neutrino_sector", ["neutrino", "pmns", "delta m", "oscillation"]),
        ("gw_strong_gravity", ["gravitational wave", "ligo", "virgo", "kagra", "ringdown", "black hole"]),
        ("dark_sector", ["dark matter", "dark sector", "wimp", "axion", "xenon", "luxe"]),
        ("early_universe_bbn", ["bbn", "n_eff", "primordial", "helium", "deuterium", "recombination"]),
    ]
    out = []
    for g, kws in rules:
        if any(k in t for k in kws):
            out.append(g)
    if not out:
        out = ["unclassified"]
    return out


def normalize(in_path: Path, out_path: Path) -> dict:
    count = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            title = str(rec.get("title") or "")
            year = rec.get("year")
            doi = str(rec.get("doi") or "").lower().strip()
            openalex_id = rec.get("openalex_id")

            normalized = {
                "doi": doi,
                "title": title,
                "source": rec.get("source", "openalex"),
                "openalex_id": openalex_id,
                "published_at": f"{int(year)}-01-01" if isinstance(year, int) else None,
                "observation_epoch": {
                    "start_year": int(year) if isinstance(year, int) else None,
                    "end_year": int(year) if isinstance(year, int) else None,
                    "kind": "publication-proxy",
                },
                "analysis_generation": f"openalex-{int(year)}" if isinstance(year, int) else "openalex-unknown",
                "supersedes": [],
                "duplicate_flag": False,
                "genre_tags": infer_genres(title + " " + str(rec.get("query") or "")),
                "query_seed": rec.get("query"),
            }
            fout.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            count += 1
    return {"ok": True, "count": count, "out": str(out_path)}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: inf_memory_timeseries_normalize.py <input_jsonl> <output_jsonl>")
        return 2
    res = normalize(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
