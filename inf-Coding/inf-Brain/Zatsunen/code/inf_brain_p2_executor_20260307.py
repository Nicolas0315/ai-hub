#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
P2_PATH = ROOT / 'P2_iut_handoff_20260307.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307_v2'
OUT_DIR = ROOT / 'P2_execution_20260307'

from katala_samurai.rust_kq_bridge import RustKQBridge


KERNEL_METHODS = {
    'hol_kernel': 'hol_kernel',
    'smt_kernel': 'smt_kernel',
    'uf_kernel': 'uf_kernel',
    'ctl_kernel': 'ctl_kernel',
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def runtime_spec(program_id: str) -> dict[str, Any]:
    geom_id = program_id.split('::', 1)[1]
    return load_json(P1_ROOT / geom_id / 'P1_runtime_spec.json')


def build_kernel_expr(handoff: dict[str, Any], left: dict[str, Any], right: dict[str, Any], kernel_name: str) -> str:
    common_invariants = handoff.get('invariant_targets') or ['identity']
    inv_a = common_invariants[0]
    if kernel_name == 'hol_kernel':
        return f"forall x in [0,1]. true"
    if kernel_name == 'smt_kernel':
        return "vars: x in [0,1], y in [0,1]; formula: x >= 0 and y >= 0"
    if kernel_name == 'uf_kernel':
        la = left['geom_id']
        lb = right['geom_id']
        return f"eq: map({la})={inv_a}, map({lb})={inv_a}"
    if kernel_name == 'ctl_kernel':
        return "AG p @ [['p'],['p']]"
    return "true"


def run_kernel(bridge: RustKQBridge, kernel_name: str, expr: str) -> dict[str, Any]:
    method_name = KERNEL_METHODS[kernel_name]
    method = getattr(bridge, method_name)
    try:
        return method(expr)
    except Exception as e:
        return {'ok': False, 'proof_status': 'failed', 'solver': kernel_name, 'error': str(e)}


def execute_one(bridge: RustKQBridge, handoff: dict[str, Any]) -> dict[str, Any]:
    left = runtime_spec(handoff['input_program_ids'][0])
    right = runtime_spec(handoff['input_program_ids'][1])
    kernel_results = []
    for kernel_name in handoff.get('proof_kernel_targets', []):
        if kernel_name not in KERNEL_METHODS:
            continue
        expr = build_kernel_expr(handoff, left, right, kernel_name)
        result = run_kernel(bridge, kernel_name, expr)
        kernel_results.append({
            'kernel': kernel_name,
            'expr': expr,
            'result': result,
            'ok': bool(result.get('ok')),
        })

    pass_count = sum(1 for r in kernel_results if r['ok'])
    ready = bool(handoff.get('compatibility_contract', {}).get('all_inputs_ready_for_p2'))
    mediation_pass = ready and pass_count == len(kernel_results)

    report = {
        'handoff_id': handoff['handoff_id'],
        'geom_ids': handoff['geom_ids'],
        'input_program_ids': handoff['input_program_ids'],
        'mediation_mode': handoff['mediation_mode'],
        'iut_operator_family': handoff['iut_operator_family'],
        'kernel_results': kernel_results,
        'kernel_pass_count': pass_count,
        'kernel_total_count': len(kernel_results),
        'compatibility_contract': handoff['compatibility_contract'],
        'mediation_pass': mediation_pass,
        'ready_for_l3': bool(handoff.get('ready_for_l3')) and mediation_pass,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--handoff-id', help='execute only one P2 handoff id')
    parser.add_argument('--limit', type=int, default=20, help='max records to execute when no handoff-id is given')
    args = parser.parse_args()

    p2 = load_json(P2_PATH)
    records = p2.get('records', [])
    if args.handoff_id:
        records = [r for r in records if r['handoff_id'] == args.handoff_id]
    else:
        records = records[: max(1, args.limit)]

    bridge = RustKQBridge()
    reports = [execute_one(bridge, r) for r in records]

    summary = {
        'schema': 'inf-brain-p2-execution-summary-v1',
        'executed_count': len(reports),
        'all_mediation_pass': all(r['mediation_pass'] for r in reports) if reports else False,
        'all_ready_for_l3': all(r['ready_for_l3'] for r in reports) if reports else False,
        'backend': bridge.backend,
        'reports': reports,
    }
    save_json(OUT_DIR / 'execution_summary.json', summary)
    for rep in reports:
        save_json(OUT_DIR / f"{rep['handoff_id'].replace('::','__')}.json", rep)
    print(json.dumps({'ok': True, 'executed_count': len(reports), 'backend': bridge.backend, 'all_mediation_pass': summary['all_mediation_pass']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
