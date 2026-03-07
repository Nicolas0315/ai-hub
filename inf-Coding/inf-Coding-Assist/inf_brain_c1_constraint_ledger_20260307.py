#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
OVERRIDES_PATH = ROOT / 'inf_model_user_overrides.json'
M1_PATH = ROOT / 'M1_model_ledger_20260307.json'
OUT_PATH = ROOT / 'C1_constraint_ledger_20260307.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def main() -> int:
    overrides = load_json(OVERRIDES_PATH)
    m1 = load_json(M1_PATH)

    exp = overrides.get('expansion_plan') or {}
    survival = exp.get('iut_candidate_survival_program') or {}
    arch = survival.get('three_layer_architecture') or {}
    l2 = arch.get('L2_iut_mediation_layer') or {}
    l3 = arch.get('L3_top_recovery_layer') or {}
    final_authority = exp.get('final_authority') or {}
    sep = exp.get('layer_separation_policy') or {}

    payload = {
        'schema': 'inf-brain-c1-constraint-ledger-v1',
        'description': 'C1 ledger unifying gate, policy, verification, activation, and rejection rules',
        'constraint_families': {
            'iut_gate': {
                'enabled': bool(l2.get('enabled', True)),
                'gates': l2.get('gates', {}),
            },
            'euclid_recovery_gate': {
                'final_acceptance_gate': bool(l3.get('final_acceptance_gate', True)),
                'recovery': l3.get('recovery', {}),
                'final_authority': final_authority,
            },
            'reverse_flow_guard': {
                'kq_to_inf_brain': 'full-access',
                'inf_brain_to_kq': 'no-access',
                'inf_brain_to_inf_bridge': 'no-access',
                'inf_brain_to_inf_coding': 'no-access',
                'writeback_forbidden': True,
                'upstream_mutation_forbidden': True,
            },
            'hash_and_schema_verification': {
                'sha256_required_on_materialized_binary': True,
                'p1_verification_required': True,
                'geom_id_match_required': True,
                'schema_validation_required': True,
            },
            'layer_separation_policy': sep,
            'activation_rule': {
                'ready_status': 'ready_for_c1_gate',
                'requires_m1_gate_status': 'pass',
                'requires_final_authority': ['local_euclid_recovery', 'limit_euclid_recovery'],
            },
            'rejection_rule': {
                'reject_if': [
                    'm1.gate_status != pass',
                    'local_euclid_recovery == false',
                    'limit_euclid_recovery == false',
                    'reverse_flow_guard violated',
                    'sha256 verification missing'
                ],
                'hold_if': [
                    'p1 passes but top recovery gate not yet evaluated'
                ]
            }
        },
        'm1_binding': {
            'record_count': m1.get('record_count', 0),
            'model_layer_ref': 'M1_model_ledger_20260307.json'
        }
    }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
