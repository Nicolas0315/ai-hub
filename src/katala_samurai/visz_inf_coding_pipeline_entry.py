from __future__ import annotations

import json
import sys

from katala_samurai.visz_inf_coding_pipeline import process_discord_event


def main() -> int:
    raw = sys.stdin.read()
    try:
        event = json.loads(raw or "{}")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": {"code": "INVALID_PACKET", "message": str(exc)}} , ensure_ascii=False))
        return 1

    result = process_discord_event(event)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
