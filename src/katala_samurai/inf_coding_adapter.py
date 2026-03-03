"""inf-Coding output adapter for KSi bridge models."""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT = "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/ksi-bridge.ndjson"


def _out_path() -> Path:
    return Path(os.getenv("INF_CODING_BRIDGE_FILE", DEFAULT_OUT))


def _append_row(row: dict[str, Any]) -> None:
    out_path = _out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def emit_bridge_output(model: str, payload: dict[str, Any]) -> None:
    """Emit KS bridge output to inf-Coding adapter sink (NDJSON)."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "verify",
        "model": model,
        "source": "katala_samurai_inf",
        "payload": payload,
    }
    _append_row(row)


def emit_router_event(model: str, payload: dict[str, Any]) -> None:
    """Emit KSi router event for fast/strict routing telemetry."""
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": "router",
        "model": model,
        "source": "katala_samurai_inf",
        "payload": payload,
    }
    _append_row(row)


def summarize_bridge(limit: int = 500) -> dict[str, Any]:
    """Summarize recent adapter activity for optimization decisions."""
    out_path = _out_path()
    if not out_path.exists():
        return {
            "path": str(out_path),
            "exists": False,
            "events": 0,
            "router_modes": {},
            "verdicts": {},
        }

    rows: list[dict[str, Any]] = []
    with out_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

    rows = rows[-max(1, limit):]
    verdicts = Counter()
    modes = Counter()

    for r in rows:
        p = r.get("payload", {}) if isinstance(r, dict) else {}
        v = p.get("verdict")
        m = p.get("mode") or p.get("route")
        if v:
            verdicts[str(v)] += 1
        if m:
            modes[str(m)] += 1

    return {
        "path": str(out_path),
        "exists": True,
        "events": len(rows),
        "router_modes": dict(modes),
        "verdicts": dict(verdicts),
        "last_event": rows[-1] if rows else None,
    }
