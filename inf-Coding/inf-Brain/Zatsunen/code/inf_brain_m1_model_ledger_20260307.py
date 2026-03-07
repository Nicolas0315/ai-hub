#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
MAP_PATH = ROOT / 'inf_brain_l1_s1_p1_mapping_20260307.json'
P1_SUMMARY_PATH = ROOT / 'P1_artifacts_20260307' / 'compile_summary.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307'
OVERRIDES_PATH = ROOT / 'inf_model_user_overrides.json'
OUT_PATH = ROOT / 'M1_model_ledger_20260307.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    mapping = load_json(MAP_PATH)
    p1_summary = load_json(P1_SUMMARY_PATH)
    overrides = load_json(OVERRIDES_PATH)

    p1_results = {r['geom_id']: r for r in p1_summary.get('results', [])}
    final_authority = ((overrides.get('expansion_plan') or {}).get('final_authority') or {})

    records = []
    for item in mapping.get('mappings', []):
        geom_id = item['geom_id']
        p1_result = p1_results.get(geom_id, {})
        p1_dir = Path(p1_result.get('artifact_dir', ''))
        verification = {}
        if p1_dir and (p1_dir / 'P1_verification_report.json').exists():
            verification = load_json(p1_dir / 'P1_verification_report.json')

        gate_pass = bool(verification.get('pass', False))
        activation_status = 'ready_for_c1_gate' if gate_pass else 'blocked'
        adoption_status = 'hold' if gate_pass else 'reject'

        records.append({
            'model_id': f'M1::{geom_id}',
            'geom_id': geom_id,
            'model_layer': 'M1',
            'compiled_from': item['p1']['program_id'],
            'source_ref': item['s1']['source_id'],
            'gate_status': 'pass' if gate_pass else 'fail',
            'activation_status': activation_status,
            'decision_status': adoption_status,
            'evidence_refs': [
                str(p1_dir / 'P1_executable_model.json') if p1_dir else None,
                str(p1_dir / 'P1_verification_report.json') if p1_dir else None,
            ],
            'reproducibility_tag': 'p1_verified_v1' if gate_pass else 'p1_incomplete',
            'final_authority_ref': final_authority,
            'updated_at': now_iso(),
        })

    payload = {
        'schema': 'inf-brain-m1-model-ledger-v1',
        'description': 'M1 ledger for compiled model state and downstream adoption handling',
        'record_count': len(records),
        'records': records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
