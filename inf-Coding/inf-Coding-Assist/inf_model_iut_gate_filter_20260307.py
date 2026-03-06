#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala')
OVR = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'inf_model_user_overrides.json'
OUT = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'inf_model_iut_gate_filter_result_20260307.json'


def main() -> int:
    data = json.loads(OVR.read_text(encoding='utf-8')) if OVR.exists() else {}
    exp = (data.get('expansion_plan') or {})
    prog = (exp.get('iut_candidate_survival_program') or {})

    candidates = list(prog.get('candidate_axioms_euclid_pure') or [])
    recovery_cfg = (((prog.get('hierarchy') or {}).get('upper_unified_dimension_layer') or {}).get('recovery') or {})
    require_local = bool(recovery_cfg.get('local_euclid_recovery', True))
    require_limit = bool(recovery_cfg.get('limit_euclid_recovery', True))

    # First executable pass (based on currently fixed derivability/hold-condition knowledge)
    # E1 is conditional on continuity/completeness assumptions and is held for now.
    gate_eval = {
        'E1_continuous_segment_division': {
            'commutativity': True,
            'invariant_preservation': True,
            'non_contradiction': True,
            'local_euclid_recovery': True,
            'limit_euclid_recovery': False,
            'status': 'hold_conditional_base_axioms',
            'note': 'Needs explicit continuity/completeness base decision before promotion.',
        },
        'E2_layered_dimension_parameter': {
            'commutativity': True,
            'invariant_preservation': True,
            'non_contradiction': True,
            'local_euclid_recovery': True,
            'limit_euclid_recovery': True,
            'status': 'pass',
        },
        'E3_canonical_comparison_map_uniqueness': {
            'commutativity': True,
            'invariant_preservation': True,
            'non_contradiction': True,
            'local_euclid_recovery': True,
            'limit_euclid_recovery': True,
            'status': 'pass',
        },
        'E4_path_independent_comparison': {
            'commutativity': True,
            'invariant_preservation': True,
            'non_contradiction': True,
            'local_euclid_recovery': True,
            'limit_euclid_recovery': True,
            'status': 'pass',
        },
        'E5_classical_euclid_recovery_limit': {
            'commutativity': True,
            'invariant_preservation': True,
            'non_contradiction': True,
            'local_euclid_recovery': True,
            'limit_euclid_recovery': True,
            'status': 'pass_connection_axiom',
        },
    }

    passed = []
    held = []
    for c in candidates:
        r = gate_eval.get(c, {})
        all_gates = bool(
            r.get('commutativity')
            and r.get('invariant_preservation')
            and r.get('non_contradiction')
            and (r.get('local_euclid_recovery') if require_local else True)
            and (r.get('limit_euclid_recovery') if require_limit else True)
        )
        if all_gates:
            passed.append(c)
        else:
            held.append(c)

    payload = {
        'schema': 'inf-model-iut-gate-filter-v1',
        'selection_rule': prog.get('selection_rule', 'adopt_candidate_only_if_all_gates_pass'),
        'candidates_input': candidates,
        'gate_evaluation': gate_eval,
        'adopt_candidates': passed,
        'hold_candidates': held,
        'summary': {
            'input_count': len(candidates),
            'adopt_count': len(passed),
            'hold_count': len(held),
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT), 'adopt_count': len(passed), 'hold_count': len(held)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
