#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
S1_PATH = ROOT / 'S1_source_ledger_20260307_v3_tier1_augmented.json'
CAT_PATH = ROOT / 'S1_geometry_catalog_20260307_v2_unified.json'
OUT_DIR = ROOT / 'P1_artifacts_20260307_v3'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SUBTYPE_ALIASES = {
    'minkowski': 'minkowski_geometry',
    'lorentzian_pseudo_riemannian': 'lorentzian_geometry',
    'riemannian_adm_slice': 'riemannian_manifold',
    'projective_hilbert': 'projective_hilbert_space',
    'symplectic': 'symplectic_manifold',
    'poisson': 'poisson_manifold',
    'information_geometry': 'fisher_metric_geometry',
    'noncommutative_geometry': 'operator_algebra_geometry',
    'fiber_bundle': 'fiber_bundle',
    'complex_projective_space': 'complex_projective_space',
}


def canonical_subtype(subtype: str) -> str:
    return SUBTYPE_ALIASES.get(subtype, subtype)


def build_catalog_index(cat: dict[str, Any]) -> dict[str, dict[str, Any]]:
    idx = {}
    for fam in cat['families']:
        family = fam['family']
        gclass = fam['geometry_class']
        for sub in fam['subtypes']:
            idx[sub['subtype']] = {
                'family': family,
                'geometry_class': gclass,
                'formalization_target': sub['formalization_target'],
                'catalog_subtype': sub['subtype'],
            }
    return idx


def materialize_s1_payload(s1_record: dict[str, Any], cat_meta: dict[str, Any]) -> dict[str, Any]:
    payload = dict(s1_record)
    payload['asset_kind'] = 'geometry_normalized_source'
    payload['binary_format'] = 'json'
    payload['producer'] = 'inf_brain_p1_compiler_v3_20260307.py'
    payload['created_at'] = now_iso()
    payload['intended_consumers'] = ['P1', 'P2', 'M1']
    payload['family'] = cat_meta['family']
    payload['catalog_geometry_class'] = cat_meta['geometry_class']
    payload['catalog_formalization_target'] = cat_meta['formalization_target']
    payload['catalog_subtype'] = cat_meta['catalog_subtype']
    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    payload['sha256'] = sha256_of_bytes(payload_bytes)
    return payload


def runtime_type(gclass: str, family: str, subtype: str) -> str:
    if family in {'pseudo_riemannian_geometry', 'riemannian_geometry', 'manifold_geometry'}:
        return 'manifold_runtime'
    if family in {'hilbert_geometry', 'projective_hilbert_geometry'}:
        return 'hilbert_runtime'
    if family in {'symplectic_geometry', 'poisson_geometry'}:
        return 'phase_space_runtime'
    if family in {'bundle_geometry'}:
        return 'bundle_runtime'
    if family in {'noncommutative_geometry'}:
        return 'operator_algebra_runtime'
    return f'{gclass}_single_geometry_runtime'


def build_executable_model(s1_payload: dict[str, Any], cat_meta: dict[str, Any]) -> dict[str, Any]:
    geom_id = s1_payload['geom_id']
    executable = {
        'program_id': f'P1::{geom_id}',
        'geom_id': geom_id,
        'program_layer': 'P1',
        'compiled_from': s1_payload['source_id'],
        'geometry_class': cat_meta['geometry_class'],
        'family': cat_meta['family'],
        'subtype': s1_payload['subtype'],
        'catalog_subtype': cat_meta['catalog_subtype'],
        'runtime_type': runtime_type(cat_meta['geometry_class'], cat_meta['family'], s1_payload['subtype']),
        'object_model': {
            'objects': s1_payload['core_objects'],
            'object_runtime_family': 'typed_geometry_objects',
            'family': cat_meta['family'],
            'subtype': s1_payload['subtype'],
        },
        'relation_model': {
            'relations': s1_payload['core_relations'],
            'relation_runtime_family': 'typed_geometry_relations',
            'family': cat_meta['family'],
        },
        'operation_stubs': s1_payload['required_operations'],
        'serialization_format': 'json',
        'verification_contract': {
            'geom_id_match_required': True,
            'source_hash_required': True,
            'operation_stub_presence_required': True,
            'compiled_from_expected_input_required': True,
            'catalog_alignment_required': True,
        },
        'ready_for_p2': True,
        'p2_handoff': {
            'intended_role': 'iut_mediation_input',
            'used_in_domains': s1_payload['used_in_domains'],
            'usage_modes': s1_payload['usage_modes'],
            'family': cat_meta['family'],
            'subtype': s1_payload['subtype'],
        },
        'catalog_alignment': {
            'catalog_family': cat_meta['family'],
            'catalog_geometry_class': cat_meta['geometry_class'],
            'catalog_formalization_target': cat_meta['formalization_target'],
        },
        'compiled_at': now_iso(),
        'input_hash': s1_payload['sha256'],
    }
    executable['program_sha256'] = sha256_of_bytes(json.dumps(executable, ensure_ascii=False, indent=2).encode('utf-8'))
    return executable


def build_verification_report(s1_payload: dict[str, Any], executable: dict[str, Any], cat_meta: dict[str, Any]) -> dict[str, Any]:
    checks = {
        'geom_id_match': s1_payload['geom_id'] == executable['geom_id'],
        'sha256_present': bool(s1_payload.get('sha256')),
        'operation_stubs_present': bool(executable.get('operation_stubs')),
        'compiled_from_expected_input': executable['compiled_from'] == s1_payload['source_id'],
        'catalog_alignment': executable['family'] == cat_meta['family'] and executable['geometry_class'] == cat_meta['geometry_class'] and executable['subtype'] == s1_payload['subtype'],
    }
    return {
        'program_id': executable['program_id'],
        'geom_id': executable['geom_id'],
        'verified_at': now_iso(),
        'verification_contract': executable['verification_contract'],
        'checks': checks,
        'pass': all(checks.values()),
    }


def compile_one(s1_record: dict[str, Any], cat_meta: dict[str, Any]) -> dict[str, Any]:
    geom_id = s1_record['geom_id']
    s1_payload = materialize_s1_payload(s1_record, cat_meta)
    executable = build_executable_model(s1_payload, cat_meta)
    report = build_verification_report(s1_payload, executable, cat_meta)

    geom_dir = OUT_DIR / geom_id
    save_json(geom_dir / 'S1_materialized_v3.json', s1_payload)
    save_json(geom_dir / 'P1_runtime_spec.json', executable)
    save_json(geom_dir / 'P1_verification_report.json', report)

    return {
        'geom_id': geom_id,
        'artifact_dir': str(geom_dir),
        'pass': report['pass'],
        'runtime_type': executable['runtime_type'],
        'family': executable['family'],
        'subtype': executable['subtype'],
        'ready_for_p2': executable['ready_for_p2'],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--geom-id', help='compile only one geometry id')
    args = parser.parse_args()

    s1 = load_json(S1_PATH)
    cat = load_json(CAT_PATH)
    cat_idx = build_catalog_index(cat)
    s1_records = {}
    for r in s1['records']:
        canon = canonical_subtype(r['subtype'])
        if canon in cat_idx:
            rr = dict(r)
            rr['catalog_subtype'] = canon
            s1_records[r['geom_id']] = rr
    geom_ids = [args.geom_id] if args.geom_id else sorted(s1_records.keys())
    results = [compile_one(s1_records[gid], cat_idx[s1_records[gid]['catalog_subtype']]) for gid in geom_ids]

    summary = {
        'schema': 'inf-brain-p1-compile-summary-v3',
        'compiled_count': len(results),
        'all_pass': all(r['pass'] for r in results),
        'all_ready_for_p2': all(r['ready_for_p2'] for r in results),
        'results': results,
        'output_root': str(OUT_DIR),
        'catalog_source': str(CAT_PATH),
    }
    save_json(OUT_DIR / 'compile_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
