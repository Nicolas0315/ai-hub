#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
P2_EXEC_PATH = ROOT / 'P2_execution_20260307' / 'execution_summary.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307_v2'
C1_PATH = ROOT / 'C1_constraint_ledger_20260307.json'
OUT_PATH = ROOT / 'L3_recovery_ledger_20260307.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def runtime_spec(program_id: str) -> dict[str, Any]:
    geom_id = program_id.split('::', 1)[1]
    return load_json(P1_ROOT / geom_id / 'P1_runtime_spec.json')


def evaluate_local(report: dict[str, Any], specs: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    basis = []
    if report.get('mediation_pass'):
        basis.append('p2_mediation_pass')
    has_local_ref = any('local_euclid_recovery_reference' in ((s.get('relation_model') or {}).get('relations') or []) for s in specs)
    if has_local_ref:
        basis.append('local_euclid_recovery_reference_present')
    has_euclidean = any('euclidean' in str(s.get('runtime_type', '')) for s in specs)
    if has_euclidean:
        basis.append('euclidean_runtime_present')
    return bool(report.get('mediation_pass') and has_local_ref and (has_euclidean or len(specs) >= 2)), basis


def evaluate_limit(report: dict[str, Any], specs: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    basis = []
    if report.get('mediation_pass'):
        basis.append('p2_mediation_pass')
    usage_modes = []
    for s in specs:
        usage_modes.extend(((s.get('p2_handoff') or {}).get('usage_modes') or []))
    if any(m in {'limit', 'approximation', 'local'} for m in usage_modes):
        basis.append('euclidean_limit_tag_present')
    has_local_ref = any('local_euclid_recovery_reference' in ((s.get('relation_model') or {}).get('relations') or []) for s in specs)
    if has_local_ref:
        basis.append('local_euclid_recovery_reference_present')
    has_euclidean = any('euclidean' in str(s.get('runtime_type', '')) for s in specs)
    if has_euclidean:
        basis.append('euclidean_runtime_present')
    ok = bool(report.get('mediation_pass') and has_local_ref and (has_euclidean or 'euclidean_limit_tag_present' in basis))
    return ok, basis


def main() -> int:
    p2_exec = load_json(P2_EXEC_PATH)
    c1 = load_json(C1_PATH)
    authority = (((c1.get('constraint_families') or {}).get('euclid_recovery_gate') or {}).get('final_authority') or {})
    records = []
    for rep in p2_exec.get('reports', []):
        specs = [runtime_spec(pid) for pid in rep.get('input_program_ids', [])]
        local_ok, local_basis = evaluate_local(rep, specs)
        limit_ok, limit_basis = evaluate_limit(rep, specs)
        final = 'accept' if (local_ok and limit_ok) else 'hold'
        records.append({
            'l3_id': f"L3::{rep['handoff_id']}",
            'input_handoff_id': rep['handoff_id'],
            'geom_ids': rep['geom_ids'],
            'local_euclid_recovery': local_ok,
            'limit_euclid_recovery': limit_ok,
            'recovery_basis': sorted(set(local_basis + limit_basis)),
            'final_decision': final,
            'decision_authority': authority.get('decision_gate', 'L3_top_recovery_layer'),
            'evidence_refs': [str(ROOT / 'P2_execution_20260307' / f"{rep['handoff_id'].replace('::','__')}.json")],
        })
    payload = {
        'schema': 'inf-brain-l3-recovery-ledger-v1',
        'record_count': len(records),
        'accepted_count': sum(1 for r in records if r['final_decision'] == 'accept'),
        'records': records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(records), 'accepted': payload['accepted_count']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
