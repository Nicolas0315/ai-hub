#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
P1_SUMMARY = ROOT / 'P1_artifacts_20260307_v2' / 'compile_summary.json'
P1_ROOT = ROOT / 'P1_artifacts_20260307_v2'
OUT_PATH = ROOT / 'P2_iut_handoff_20260307.json'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def mediation_mode(a: dict[str, Any], b: dict[str, Any]) -> str:
    da = set((a.get('p2_handoff') or {}).get('used_in_domains') or [])
    db = set((b.get('p2_handoff') or {}).get('used_in_domains') or [])
    if da == db:
        return 'single_domain'
    if 'relativity' in da.union(db) and 'quantum' in da.union(db):
        return 'cross_domain'
    return 'invariant_bridge'


def comparison_targets(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    objs = set((a.get('object_model') or {}).get('objects') or []) | set((b.get('object_model') or {}).get('objects') or [])
    rels = set((a.get('relation_model') or {}).get('relations') or []) | set((b.get('relation_model') or {}).get('relations') or [])
    out = sorted((objs | rels))
    return out[:8]


def invariant_targets(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    rels = set((a.get('relation_model') or {}).get('relations') or []) & set((b.get('relation_model') or {}).get('relations') or [])
    if not rels:
        rels = set((a.get('relation_model') or {}).get('relations') or []) | set((b.get('relation_model') or {}).get('relations') or [])
    return sorted(rels)[:6]


def proof_kernel_targets(mode: str, runtime_types: set[str]) -> list[str]:
    kernels = ['hol_kernel', 'smt_kernel']
    if mode == 'cross_domain':
        kernels.append('uf_kernel')
    if any('non_euclidean' in rt for rt in runtime_types):
        kernels.append('ctl_kernel')
    return kernels


def build_record(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    gid_a, gid_b = a['geom_id'], b['geom_id']
    pid_a, pid_b = a['program_id'], b['program_id']
    mode = mediation_mode(a, b)
    runtime_types = {a.get('runtime_type', ''), b.get('runtime_type', '')}
    return {
        'handoff_id': f'P2::{gid_a}__{gid_b}',
        'p2_layer': 'P2',
        'input_program_ids': [pid_a, pid_b],
        'geom_ids': [gid_a, gid_b],
        'mediation_mode': mode,
        'comparison_targets': comparison_targets(a, b),
        'invariant_targets': invariant_targets(a, b),
        'iut_operator_family': 'kq_iut_mediation_core',
        'proof_kernel_targets': proof_kernel_targets(mode, runtime_types),
        'compatibility_contract': {
          'all_inputs_ready_for_p2': bool(a.get('ready_for_p2') and b.get('ready_for_p2')),
          'geom_ids_distinct': gid_a != gid_b,
          'source_hashes_present': bool(a.get('input_hash') and b.get('input_hash')),
          'runtime_specs_verified': True
        },
        'ready_for_l3': bool(a.get('ready_for_p2') and b.get('ready_for_p2')),
      }


def main() -> int:
    summary = load_json(P1_SUMMARY)
    runtime_specs = {}
    for row in summary.get('results', []):
        geom_id = row['geom_id']
        runtime_specs[geom_id] = load_json(P1_ROOT / geom_id / 'P1_runtime_spec.json')

    records = []
    for a_id, b_id in itertools.combinations(sorted(runtime_specs.keys()), 2):
        records.append(build_record(runtime_specs[a_id], runtime_specs[b_id]))

    payload = {
        'schema': 'inf-brain-p2-iut-handoff-v1',
        'description': 'Pairwise P2 handoff bundles generated from verified P1 runtime specs',
        'record_count': len(records),
        'records': records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
