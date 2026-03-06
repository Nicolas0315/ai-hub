#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def _sigma(d: dict) -> float | None:
    if d.get("uncertainty") is not None:
        return float(d["uncertainty"])
    up = d.get("uncertainty_plus")
    dn = d.get("uncertainty_minus")
    if up is not None and dn is not None:
        return (float(up) + float(dn)) / 2.0
    st = d.get("uncertainty_stat")
    sy = d.get("uncertainty_sys")
    if st is not None and sy is not None:
        return (float(st) ** 2 + float(sy) ** 2) ** 0.5
    return None


def build_vector(manifest: dict) -> dict:
    out = []
    for d in manifest.get("datasets", []):
        if not isinstance(d, dict):
            continue
        out.append({
            "dataset_id": d.get("dataset_id"),
            "domain": d.get("domain"),
            "observable": d.get("observable"),
            "value": d.get("value"),
            "sigma": _sigma(d),
            "unit": d.get("unit"),
            "used_by_track": d.get("used_by_track"),
            "source": d.get("source", {}),
        })
    return {
        "schema": "katala-observation-vector-v1",
        "count": len(out),
        "items": out,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: observation_vector_from_manifest.py <manifest.json> <out.json>")
        return 2
    m = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    vec = build_vector(m)
    Path(sys.argv[2]).write_text(json.dumps(vec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "count": vec["count"], "out": str(Path(sys.argv[2]).resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
