#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
P2_EXEC_PATH = ROOT / 'P2_execution_20260307_v2' / 'execution_summary.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307_v3'
OUT_PATH = ROOT / 'P3_evaluation_20260307_v2.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def runtime_spec(program_id: str) -> dict[str, Any]:
    geom_id = program_id.split('::', 1)[1]
    return load_json(P1_ROOT / geom_id / 'P1_runtime_spec.json')


def direct_euclid(report: dict[str, Any], specs: list[dict[str, Any]]) -> bool:
    if not report.get('mediation_pass'):
        return False
    return 'unified_space' in (report.get('unified_fields') or []) and any(s.get('geometry_class') == 'euclidean' for s in specs)


def local_recovery(report: dict[str, Any], specs: list[dict[str, Any]]) -> bool:
    if not report.get('mediation_pass'):
        return False
    return any('local_euclid_recovery_reference' in ((s.get('relation_model') or {}).get('relations') or []) for s in specs)


def limit_recovery(report: dict[str, Any], specs: list[dict[str, Any]]) -> bool:
    if not report.get('mediation_pass'):
        return False
    modes = []
    for s in specs:
        modes.extend(((s.get('p2_handoff') or {}).get('usage_modes') or []))
    return any(m in {'limit', 'approximation', 'local'} for m in modes)


def failure_reason(report: dict[str, Any], direct_ok: bool, local_ok: bool, limit_ok: bool) -> list[str]:
    if direct_ok or local_ok or limit_ok:
        return []
    reasons = []
    if not report.get('mediation_pass'):
        reasons.append('p2_mediation_failure')
    profiles = set(report.get('mediation_profiles') or [])
    unified = set(report.get('unified_fields') or [])
    if 'P2_PROFILE::time_bridge' in profiles and 'unified_time' not in unified:
        reasons.append('time_bridge_mismatch')
    if 'P2_PROFILE::space_bridge' in profiles and 'unified_space' not in unified:
        reasons.append('space_bridge_mismatch')
    if 'P2_PROFILE::dimension_bridge' in profiles and 'unified_dimension' not in unified:
        reasons.append('dimension_bridge_mismatch')
    if any(not kr.get('ok') for kr in report.get('kernel_results', [])):
        reasons.append('invariant_preservation_failure')
    if report.get('unified_fields') == ['unified_time']:
        reasons.append('causality_evolution_incompatibility')
    if 'unified_dimension' in unified:
        reasons.append('dimensional_inconsistency')
    if not reasons:
        reasons.append('nonrecoverable_geometry_pairing')
    return sorted(set(reasons))


def feedback_to_p2(reasons: list[str], report: dict[str, Any]) -> dict[str, Any]:
    suggestions = []
    if 'time_bridge_mismatch' in reasons:
        suggestions.append('revise_time_bridge_profile')
    if 'space_bridge_mismatch' in reasons:
        suggestions.append('revise_space_bridge_profile')
    if 'dimension_bridge_mismatch' in reasons or 'dimensional_inconsistency' in reasons:
        suggestions.append('revise_dimension_bridge_profile')
    if 'invariant_preservation_failure' in reasons:
        suggestions.append('tighten_invariant_targets')
    if 'causality_evolution_incompatibility' in reasons:
        suggestions.append('align_causality_with_quantum_evolution')
    if 'nonrecoverable_geometry_pairing' in reasons:
        suggestions.append('change_geometry_pairing_or_profile')
    return {
        'handoff_id': report['handoff_id'],
        'reasons': reasons,
        'suggestions': sorted(set(suggestions))
    }


def main() -> int:
    p2 = load_json(P2_EXEC_PATH)
    records = []
    for rep in p2.get('reports', []):
        specs = [runtime_spec(pid) for pid in rep.get('input_program_ids', [])]
        direct_ok = direct_euclid(rep, specs)
        local_ok = local_recovery(rep, specs)
        limit_ok = limit_recovery(rep, specs)
        reasons = failure_reason(rep, direct_ok, local_ok, limit_ok)
        feedback = feedback_to_p2(reasons, rep) if reasons else None
        records.append({
            'p3_id': f"P3::{rep['handoff_id']}",
            'computation_input': rep['handoff_id'],
            'geom_ids': rep['geom_ids'],
            'direct_euclid_reduction': direct_ok,
            'local_euclid_recovery': local_ok,
            'limit_euclid_recovery': limit_ok,
            'failure_reason': reasons,
            'feedback_to_p2': feedback,
            'final_status': 'success' if direct_ok else ('conditional_success' if (local_ok or limit_ok) else 'revise_p2')
        })
    payload = {
        'schema': 'katala-p3-evaluation-v2',
        'record_count': len(records),
        'success_count': sum(1 for r in records if r['final_status'] == 'success'),
        'conditional_success_count': sum(1 for r in records if r['final_status'] == 'conditional_success'),
        'revise_p2_count': sum(1 for r in records if r['final_status'] == 'revise_p2'),
        'records': records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(records), 'revise_p2_count': payload['revise_p2_count']}, ensure_ascii=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
