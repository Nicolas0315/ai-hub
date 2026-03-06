#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def build_index(in_path: Path, out_path: Path) -> dict:
    idx: dict[str, list[dict]] = defaultdict(list)
    total = 0
    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            total += 1
            entry = {
                "doi": rec.get("doi"),
                "title": rec.get("title"),
                "published_at": rec.get("published_at"),
                "analysis_generation": rec.get("analysis_generation"),
                "duplicate_flag": bool(rec.get("duplicate_flag", False)),
            }
            for g in (rec.get("genre_tags") or ["unclassified"]):
                idx[str(g)].append(entry)

    # stable ordering: newest published_at first when available
    for g in list(idx.keys()):
        idx[g].sort(key=lambda x: (x.get("published_at") is not None, x.get("published_at") or ""), reverse=True)

    out = {
        "schema": "inf-memory-genre-index-v1",
        "total_records": total,
        "genres": {g: {"count": len(v), "items": v} for g, v in sorted(idx.items())},
    }
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "total": total, "genre_count": len(idx), "out": str(out_path)}


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: inf_memory_genre_index.py <normalized_jsonl> <genre_index_json>")
        return 2
    res = build_index(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
