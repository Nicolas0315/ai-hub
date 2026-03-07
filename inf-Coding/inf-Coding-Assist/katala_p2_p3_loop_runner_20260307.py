#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
OUT_PATH = ROOT / 'P2_P3_loop_run_20260307.json'

STEPS = [
    ['python3', 'inf-Coding-Assist/inf_brain_p2_handoff_builder_v2_20260307.py'],
    ['python3', 'inf-Coding-Assist/inf_brain_p2_executor_v2_20260307.py', '--limit', '20'],
    ['python3', 'inf-Coding-Assist/inf_brain_p3_evaluator_v2_20260307.py'],
]


def run_step(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, cwd='/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding', capture_output=True, text=True)
    return {
        'cmd': cmd,
        'returncode': proc.returncode,
        'stdout': proc.stdout[-4000:],
        'stderr': proc.stderr[-4000:],
    }


def main() -> int:
    results = [run_step(cmd) for cmd in STEPS]
    p3 = json.loads((ROOT / 'P3_evaluation_20260307_v2.json').read_text(encoding='utf-8'))
    summary = {
        'schema': 'katala-p2-p3-loop-run-v1',
        'steps': results,
        'p3_summary': {
            'record_count': p3['record_count'],
            'success_count': p3['success_count'],
            'conditional_success_count': p3['conditional_success_count'],
            'revise_p2_count': p3['revise_p2_count'],
        },
        'loop_verdict': 'revise_p2' if p3['revise_p2_count'] > 0 else 'stable_for_next_stage'
    }
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'loop_verdict': summary['loop_verdict']}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
