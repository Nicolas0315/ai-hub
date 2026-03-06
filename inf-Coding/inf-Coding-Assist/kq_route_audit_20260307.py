#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala')
ROUTER = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'ksi1-router.py'
KEXEC = ROOT / 'inf-Coding' / 'katala-exec.sh'
OUT = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'kq_route_audit_20260307.json'


def has_text(path: Path, text: str) -> bool:
    if not path.exists():
        return False
    return text in path.read_text(encoding='utf-8', errors='ignore')


def main() -> int:
    checks = {
        'router_has_kq_mandatory_gate': has_text(ROUTER, 'KQ_MANDATORY_GATE'),
        'router_blocks_on_violation': has_text(ROUTER, 'kq_mandatory_gate_input_violation'),
        'router_exports_packet_env': has_text(ROUTER, 'KQ_INPUT_PACKET_JSON'),
        'katala_exec_has_fail_close_gate': has_text(KEXEC, 'missing KQ_INPUT_PACKET_JSON under mandatory KQ gate'),
        'katala_exec_validates_packet_json': has_text(KEXEC, 'invalid KQ_INPUT_PACKET_JSON under mandatory KQ gate'),
    }

    # still pending: chat ingress direct hard-binding in gateway/runtime layer
    pending = {
        'chat_ingress_hard_binding': 'unknown_or_pending',
        'note': 'No direct gateway chat-ingress gate file was updated in this pass.',
    }

    payload = {
        'schema': 'kq-route-audit-v1',
        'checks': checks,
        'pending': pending,
        'summary': {
            'no3_router_external_fail_close': bool(checks['katala_exec_has_fail_close_gate'] and checks['katala_exec_validates_packet_json']),
            'no1_chat_ingress_forced': False,
        },
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT), 'summary': payload['summary']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
