#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def validate_manifest(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    datasets = raw.get("datasets") or []

    reasons: list[str] = []

    ids = [str(d.get("dataset_id", "")) for d in datasets if isinstance(d, dict)]
    dup_ids = [k for k, v in Counter(ids).items() if v > 1 and k]
    if dup_ids:
        reasons.append(f"duplicate_dataset_id:{','.join(sorted(dup_ids))}")

    # dedup key collision: observable+pipeline+experiment+release must be unique
    tuples = []
    for d in datasets:
        if not isinstance(d, dict):
            continue
        tuples.append((
            str(d.get("observable", "")).strip(),
            str(d.get("pipeline", "")).strip(),
            str(d.get("experiment", "")).strip(),
            str(d.get("release", "")).strip(),
        ))
    dup_keys = [k for k, v in Counter(tuples).items() if v > 1 and any(k)]
    if dup_keys:
        reasons.append("duplicate_dedup_key")

    # one dataset should have exactly one track owner
    for d in datasets:
        if not isinstance(d, dict):
            continue
        owner = d.get("used_by_track")
        if not isinstance(owner, str) or not owner.strip():
            reasons.append(f"missing_used_by_track:{d.get('dataset_id','unknown')}")

    ok = len(reasons) == 0
    return {"ok": ok, "reasons": reasons, "dataset_count": len(datasets)}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: observation_manifest_guard.py <manifest.json>")
        return 2
    p = Path(sys.argv[1]).resolve()
    result = validate_manifest(p)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
