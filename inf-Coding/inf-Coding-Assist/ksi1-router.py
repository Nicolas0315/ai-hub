#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')

from katala_samurai.katala_quantum_02a import Katala_Quantum_02a, KQ02a
from katala_samurai.inf_bridge import build_inf_bridge_payload
from katala_samurai.inf_coding_adapter import emit_router_event

RISK_PATTERNS = [
    r"\brm\b", r"--force", r"\bdel\b", r"\bdrop\b", r"\btruncate\b",
    r"\bpush\b", r"\brebase\b", r"\breset\b", r"\bcherry-pick\b",
    r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b",
]

SAFE_FAST_PATTERNS = [
    r"^git status(\s|$)",
    r"^git diff(\s|$)",
    r"^git log(\s|$)",
    r"^ls(\s|$)",
    r"^pwd$",
    r"^cat(\s|$)",
    r"^grep(\s|$)",
    r"^find(\s|$)",
    r"^python3 -m py_compile(\s|$)",
    r"^npm run -s (test|build)(\s|$)",
]

STRICT_ONLY_PATTERNS = [
    r"^git (push|rebase|reset|cherry-pick|tag|branch -D)(\s|$)",
    r"^docker(\s|$)",
    r"^kubectl(\s|$)",
]


def _matches(patterns: list[str], command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE) for p in patterns)


def _select_model(command: str):
    """KQ-only policy: always use Katala_Quantum_02a unless explicitly disabled."""
    kq_only = os.getenv("KQ_ONLY", "1").strip().lower()
    if kq_only in {"1", "true", "yes", "on"}:
        return KQ02a()

    # compatibility path (when KQ_ONLY=0): allow explicit KS47 only
    requested = os.getenv("KSI_MODEL", "").strip().lower()
    c = command.lower()
    if requested in {"ks47"} or "ks47" in c:
        return "KS47"
    return KQ02a()


def decide_route(command: str) -> tuple[str, dict]:
    bridge = build_inf_bridge_payload(command)
    normalized_command = (bridge.get("input") or {}).get("normalized") or command
    cbind = (bridge.get("context_binding") or {})

    # inf-Bridge pre-gate (before KQ)
    if cbind.get("verdict") in {"reject", "defer"}:
        route = "strict"
        detail = {
            "route": route,
            "reason": f"inf_bridge_{cbind.get('verdict')}",
            "confidence": 0.0,
            "risky_pattern": True,
            "strict_only_pattern": True,
            "safe_fast_pattern": False,
            "verdict": cbind.get("verdict", "UNKNOWN").upper(),
            "mode": "inf-bridge-pre-gate",
            "model": "inf-bridge",
            "alias": "inf-bridge",
            "series": "[inf-Bridge]",
            "inf_bridge": bridge,
        }
        emit_router_event(detail["model"], {
            "alias": detail["alias"],
            "command": normalized_command,
            **detail,
        })
        return route, detail

    model = _select_model(normalized_command)
    claim = (
        "Route this command for efficiency+safety in inf-Coding.\n"
        f"command: {normalized_command}\n"
        "Use fast-path for low-risk local read/build checks; strict-path for destructive/network/history-rewriting ops."
        f"\ninf_bridge_meta: temporal={cbind.get('temporal_tag')} purpose={cbind.get('purpose_score')}"
    )

    if model == "KS47":
        bridge = subprocess.run(
            [
                "python3",
                "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/ks-bridge.py",
                "--model", "KS47",
                "--query", claim,
                "--report", command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if bridge.returncode != 0:
            raise RuntimeError(f"KS47 bridge failed: {bridge.stderr.strip()}")
        result = json.loads((bridge.stdout or "{}").strip())
        model_status = {
            "model": "KS47",
            "alias": "KS47",
            "series": "[KS] explicit-only",
        }
    else:
        result = model.verify(claim, fast=True)
        model_status = model.bridge_status() if hasattr(model, 'bridge_status') else {}

    verdict = result.get('verdict') if isinstance(result, dict) else 'UNKNOWN'
    mode = result.get('mode') if isinstance(result, dict) else 'unknown'
    conf = float(result.get('confidence', 0.5)) if isinstance(result, dict) else 0.5

    risky = _matches(RISK_PATTERNS, normalized_command)
    strict_only = _matches(STRICT_ONLY_PATTERNS, normalized_command)
    safe_fast = _matches(SAFE_FAST_PATTERNS, normalized_command)

    # Model suggested route has priority when provided
    model_route = result.get('route') if isinstance(result, dict) else None

    if model_route in {'fast', 'strict'}:
        route = model_route
        reason = 'model_quantum_route' if 'quantum' in str(mode) else 'model_route'
    elif strict_only:
        route = 'strict'
        reason = 'strict_only_pattern'
    elif risky:
        if safe_fast and conf >= 0.85 and verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'risky_but_high_conf_safe_fast'
        else:
            route = 'strict'
            reason = 'risky_pattern'
    elif safe_fast:
        if conf >= 0.5 or verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'safe_fast_pattern'
        else:
            route = 'strict'
            reason = 'safe_fast_low_conf'
    else:
        if conf >= 0.72 and verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'generic_high_conf'
        else:
            route = 'strict'
            reason = 'generic_default_strict'

    detail = {
        'route': route,
        'reason': reason,
        'confidence': conf,
        'risky_pattern': risky,
        'strict_only_pattern': strict_only,
        'safe_fast_pattern': safe_fast,
        'verdict': verdict,
        'mode': mode,
        'model': model_status.get('model', type(model).__name__),
        'alias': model_status.get('alias', 'unknown'),
        'series': model_status.get('series'),
        'inf_bridge': bridge,
    }
    emit_router_event(detail['model'], {
        'alias': detail['alias'],
        'command': normalized_command,
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

    env = os.environ.copy()
    env['KSI1_ROUTE'] = route
    env['KSI_MODEL_ACTIVE'] = detail.get('model', '')
    rc = subprocess.call(sys.argv[1:], cwd='/mnt/c/Users/ogosh/Documents/NICOLAS/Katala', env=env)
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
