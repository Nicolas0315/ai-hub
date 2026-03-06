#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


def _mk_dataset_id(genre: str, doi: str) -> str:
    h = hashlib.sha1(f"{genre}:{doi}".encode("utf-8")).hexdigest()[:12]
    return f"obs_{genre}_{h}"


def _to_iso_day(v: Any) -> str | None:
    if isinstance(v, str) and len(v) >= 10:
        return v[:10]
    return None


def build_bundle(src: Path, out: Path, top_n: int) -> dict[str, Any]:
    by_genre: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total = 0
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            total += 1
            tags = rec.get("genre_tags") or ["unclassified"]
            for g in tags:
                by_genre[str(g)].append(rec)

    records: list[dict[str, Any]] = []
    genre_counts: dict[str, int] = {}
    for genre, items in sorted(by_genre.items()):
        items.sort(key=lambda r: (r.get("published_at") is not None, r.get("published_at") or ""), reverse=True)
        selected = items[:top_n]
        genre_counts[genre] = len(selected)
        for r in selected:
            doi = str(r.get("doi") or "").strip().lower()
            if not doi:
                continue
            records.append(
                {
                    "dataset_id": _mk_dataset_id(genre, doi),
                    "genre": genre,
                    "lineage": {
                        "source": r.get("source"),
                        "doi": doi,
                        "openalex_id": r.get("openalex_id"),
                        "query_seed": r.get("query_seed"),
                        "duplicate_flag": bool(r.get("duplicate_flag", False)),
                    },
                    "temporal": {
                        "published_at": _to_iso_day(r.get("published_at")),
                        "observation_epoch": r.get("observation_epoch"),
                        "analysis_generation": r.get("analysis_generation"),
                        "supersedes": r.get("supersedes") or [],
                    },
                    "observation": {
                        "title": r.get("title"),
                        "value": None,
                        "uncertainty": None,
                        "status": "metadata_only",  # numeric extraction is a later step
                    },
                }
            )

    out_payload = {
        "schema": "katala-observation-assimilation-v1",
        "run_id": f"assim-{int(time.time())}",
        "policy": {
            "mode": "production_assimilation",
            "selection": "latest_by_genre",
            "top_n_per_genre": top_n,
            "lineage_required": True,
            "temporal_required": True,
            "uncertainty_stage": "deferred",
        },
        "summary": {
            "source_records": total,
            "assimilated_records": len(records),
            "genres": genre_counts,
        },
        "records": records,
    }
    out.write_text(json.dumps(out_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "source_records": total,
        "assimilated_records": len(records),
        "genres": genre_counts,
        "out": str(out),
    }


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: inf_observation_assimilation_prod.py <normalized_jsonl> <top_n_per_genre> <out_json>")
        return 2
    src = Path(sys.argv[1])
    top_n = int(sys.argv[2])
    out = Path(sys.argv[3])
    result = build_bundle(src, out, top_n)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
