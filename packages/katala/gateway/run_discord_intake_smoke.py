from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

ENVELOPE = {
    "id": "smoke-1",
    "channel_id": "1476438544309551104",
    "guild_id": "651429181011394602",
    "content": "<@1478028876625088603> implement phase 1 to 6",
    "attachments": [],
    "reply_to_id": "root-1",
    "timestamp": "2026-03-09T02:49:00+09:00",
    "author": {
        "id": "918103131538194452",
        "username": "visz_cham",
        "display_name": "ビジちゃむ",
        "bot": False,
    },
    "intake_route": {
        "mode": "short-circuit",
        "route": ["intake", "inf-coding", "reply"],
        "bypassed_stages": ["kq", "ks", "kl", "inf-bridge"],
        "contract": {
            "targetPipeline": ["intake", "kq", "ks", "kl", "inf-bridge", "inf-coding", "reply"],
            "activePipeline": ["intake", "inf-coding", "reply"],
        },
        "intent": "execute",
    },
}


def main() -> int:
    cmd = [sys.executable, "-m", "katala_samurai.visz_inf_coding_pipeline_entry"]
    proc = subprocess.run(
        cmd,
        input=json.dumps(ENVELOPE, ensure_ascii=False),
        text=True,
        capture_output=True,
        cwd=str(ROOT),
        env={**dict(), **__import__("os").environ, "PYTHONPATH": "src"},
    )
    payload = None
    try:
        payload = json.loads(proc.stdout) if proc.stdout else None
    except Exception:
        payload = None
    print(json.dumps({
        "stage": "handoff",
        "returncode": proc.returncode,
        "ok": bool(payload and payload.get("ok")),
        "payload": payload,
        "stderr": proc.stderr,
    }, ensure_ascii=False, indent=2))
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
