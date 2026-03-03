#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')

from katala_samurai.katala_samurai_inf_000001 import KSi1
from katala_samurai.inf_coding_adapter import emit_router_event

RISK_PATTERNS = [
    r"\brm\b", r"--force", r"\bdel\b", r"\bdrop\b", r"\btruncate\b",
    r"\bpush\b", r"\brebase\b", r"\breset\b", r"\bcherry-pick\b",
    r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b",
]


def decide_route(command: str) -> tuple[str, dict]:
    ks = KSi1()
    claim = (
        "Route this command for efficiency+safety in inf-Coding.\n"
        f"command: {command}\n"
        "Use fast-path for low-risk local read/build checks; strict-path for destructive/network/history-rewriting ops."
    )
    result = ks.verify(claim, fast=True)

    risky = any(re.search(p, command, re.IGNORECASE) for p in RISK_PATTERNS)
    conf = float(result.get('confidence', 0.5)) if isinstance(result, dict) else 0.5

    if risky or conf < 0.65:
        route = 'strict'
    else:
        route = 'fast'

    detail = {
        'route': route,
        'confidence': conf,
        'risky_pattern': risky,
        'verdict': result.get('verdict') if isinstance(result, dict) else 'UNKNOWN',
        'mode': result.get('mode') if isinstance(result, dict) else 'unknown',
    }
    emit_router_event('Katala_Samurai_inf_000001', {
        'alias': 'KSi1',
        'command': command,
        **detail,
    })
    return route, detail


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: ksi1-router.py <command...>', file=sys.stderr)
        return 64

    command = ' '.join(sys.argv[1:])
    route, detail = decide_route(command)

    print(json.dumps({'command': command, **detail}, ensure_ascii=False))

    # fast/strict currently both execute via inf-Coding gateway; strict is reserved for extra checks in future
    env = os.environ.copy()
    env['KSI1_ROUTE'] = route
    rc = subprocess.call(sys.argv[1:], cwd='/mnt/c/Users/ogosh/Documents/NICOLAS/Katala', env=env)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
