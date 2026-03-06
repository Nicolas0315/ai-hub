#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai.inf_memory_layer_policy import sanitize_inf_memory_output, validate_inf_memory_output  # noqa: E402


def main() -> int:
    payload = {
        "enabled": True,
        "schema_version": "inf-memory-v1",
        "layer": "inf-memory",
        "goal": "peer_review_memory_only",
        "input": {"apply_to_kq": True},
        "peer_review_memory": {
            "papers": [
                {"source": "openalex", "title": "ok"},
                {"source": "blog", "title": "bad"},
            ]
        },
        "status": {"write_back": True},
    }
    s = sanitize_inf_memory_output(payload)
    v = validate_inf_memory_output(s)

    leaked = False
    for banned in ["apply_to_kq", "write_back"]:
        if banned in (s.get("input") or {}) or banned in (s.get("status") or {}):
            leaked = True

    sources = [str((p or {}).get("source", "")).lower() for p in (s.get("peer_review_memory") or {}).get("papers", [])]
    only_peer = set(sources).issubset({"openalex", "crossref", "pubmed"})

    ok = bool(v.get("ok")) and (not leaked) and only_peer
    print(json.dumps({"ok": ok, "leaked": leaked, "only_peer": only_peer, "sources": sources}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
