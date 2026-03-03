"""inf-Coding output adapter for KSi bridge models."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT = "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/ksi-bridge.ndjson"


def emit_bridge_output(model: str, payload: dict[str, Any]) -> None:
    """Emit KS bridge output to inf-Coding adapter sink (NDJSON)."""
    out_path = Path(os.getenv("INF_CODING_BRIDGE_FILE", DEFAULT_OUT))
    out_path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "source": "katala_samurai_inf",
        "payload": payload,
    }
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
