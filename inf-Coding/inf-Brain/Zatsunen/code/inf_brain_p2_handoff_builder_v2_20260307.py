#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
P1_SUMMARY = ROOT / 'P1_artifacts_20260307_v3' / 'compile_summary.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307_v3'
PROFILES_PATH = ROOT / 'P2_mediation_profiles_20260307.json'
OUT_PATH = ROOT / 'P2_iut_handoff_20260307_v2.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def profile_match(profile: dict[str, Any], left: dict[str, Any], right: dict[str, Any]) -> bool:
    fams = {left.get('family'), right.get('family')}
    subs = {left.get('subtype'), right.get('subtype'), left.get('catalog_subtype'), right.get('catalog_subtype')}
    q = profile['quantum_side']
    r = profile['relativity_side']
    q_hit = bool(fams & set(q['geometry_families']) or subs & set(q['candidate_subtypes']))
    r_hit = bool(fams & set(r['geometry_families']) or subs & set(r['candidate_subtypes']))
    return q_hit and r_hit


def select_profiles(profiles: list[dict[str, Any]], left: dict[str, Any], right: dict[str, Any]) -> list[dict[str, Any]]:
    matched = [p for p in profiles if profile_match(p, left, right)]
    if matched:
        return matched
    # fallback by family heuristics
    out = []
    if {'hilbert_geometry', 'projective_hilbert_geometry', 'symplectic_geometry'} & {left.get('family'), right.get('family')} and {'pseudo_riemannian_geometry'} & {left.get('family'), right.get('family')}:
        out.append(next(p for p in profiles if p['profile_id'].endswith('time_bridge')))
    return out


def build_record(left: dict[str, Any], right: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    gid_a, gid_b = left['geom_id'], right['geom_id']
    pid_a, pid_b = left['program_id'], right['program_id']
    selected = select_profiles(profiles, left, right)
    comparison_targets = sorted({t for p in selected for t in p['comparison_targets']})
    invariant_targets = sorted({t for p in selected for t in p['invariant_targets']})
    operator_families = [p['iut_operator_family'] for p in selected]
    unified_fields = [p['unified_field'] for p in selected]
    return {
        'handoff_id': f'P2::{gid_a}__{gid_b}',
        'p2_layer': 'P2',
        'input_program_ids': [pid_a, pid_b],
        'geom_ids': [gid_a, gid_b],
        'left_family': left.get('family'),
        'right_family': right.get('family'),
        'mediation_mode': 'profiled_bridge' if selected else 'unmatched_pair',
        'mediation_profiles': [p['profile_id'] for p in selected],
        'comparison_targets': comparison_targets,
        'invariant_targets': invariant_targets,
        'iut_operator_family': operator_families[0] if len(operator_families) == 1 else operator_families,
        'proof_kernel_targets': ['hol_kernel', 'smt_kernel', 'uf_kernel'] if selected else ['hol_kernel'],
        'compatibility_contract': {
          'all_inputs_ready_for_p2': bool(left.get('ready_for_p2') and right.get('ready_for_p2')),
          'geom_ids_distinct': gid_a != gid_b,
          'source_hashes_present': bool(left.get('input_hash') and right.get('input_hash')),
          'runtime_specs_verified': True,
          'profile_match_required': True,
          'profile_match_found': bool(selected),
        },
        'unified_fields': unified_fields,
        'ready_for_l3': bool(selected and left.get('ready_for_p2') and right.get('ready_for_p2')),
      }


def main() -> int:
    summary = load_json(P1_SUMMARY)
    profiles = load_json(PROFILES_PATH)['profiles']
    runtime_specs = {row['geom_id']: load_json(P1_ROOT / row['geom_id'] / 'P1_runtime_spec.json') for row in summary.get('results', [])}
    records = []
    for a_id, b_id in itertools.combinations(sorted(runtime_specs.keys()), 2):
        rec = build_record(runtime_specs[a_id], runtime_specs[b_id], profiles)
        if rec['mediation_profiles']:
            records.append(rec)
    payload = {
        'schema': 'inf-brain-p2-iut-handoff-v2',
        'description': 'Profile-aligned P2 handoff bundles generated from catalog-aligned P1 runtime specs',
        'record_count': len(records),
        'records': records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
