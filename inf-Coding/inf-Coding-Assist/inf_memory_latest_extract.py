#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: inf_memory_latest_extract.py <normalized_jsonl> <top_n_per_genre> <out_json>")
        return 2

    src = Path(sys.argv[1])
    top_n = int(sys.argv[2])
    out = Path(sys.argv[3])

    buckets: dict[str, list[dict]] = defaultdict(list)
    with src.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            tags = rec.get("genre_tags") or ["unclassified"]
            for g in tags:
                buckets[str(g)].append(rec)

    result = {}
    for g, items in buckets.items():
        items.sort(key=lambda r: (r.get("published_at") is not None, r.get("published_at") or ""), reverse=True)
        result[g] = {
            "count": len(items),
            "latest": items[:top_n],
        }

    payload = {
        "schema": "inf-memory-latest-v1",
        "top_n_per_genre": top_n,
        "genres": result,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "genres": len(result)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
