#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
L1_PATH = ROOT / 'L1_normalized_20260307.json'
S1_PATH = ROOT / 'S1_source_ledger_20260307.json'
OUT_MAPPING = ROOT / 'inf_brain_l1_s1_p1_mapping_20260307.json'
OUT_SPEC = ROOT / 'S1_asset_format_spec_20260307.json'


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def p1_target_for(record: dict) -> dict:
    domain = record['domain']
    geom_class = record['geometry_class']
    usage_mode = record['usage_mode']
    geom_id = record['geom_id']
    return {
        'program_id': f'P1::{geom_id}',
        'program_layer': 'P1',
        'program_family': f'{domain}_geometry_compiler',
        'compiler_profile': f'{domain}_{geom_class}_{usage_mode}',
        'expected_inputs': [f'S1::{geom_id}'],
        'expected_outputs': [
            f'P1::{geom_id}::executable_model',
            f'P1::{geom_id}::verification_report',
        ],
        'verification_contract': {
            'sha256_match_required': True,
            'geom_id_match_required': True,
            'schema_validation_required': True,
        },
    }


def build_spec() -> dict:
    return {
        'schema': 'inf-brain-s1-asset-format-spec-v1',
        'layer': 'S1',
        'purpose': 'Canonical materialization format for geometry assets inside inf-Brain',
        'required_fields': [
            'source_id',
            'geom_id',
            'source_layer',
            'domain',
            'geometry_class',
            'semantic_name',
            'asset_kind',
            'binary_format',
            'payload_path',
            'sha256',
            'producer',
            'created_at',
            'intended_consumers',
        ],
        'binary_formats_allowed': ['json', 'jsonl', 'npz', 'bin', 'onnx', 'csv'],
        'hash_policy': {
            'algorithm': 'sha256',
            'required_on_materialized_binary': True,
            'p1_must_verify_before_compile': True,
        },
        'identity_policy': {
            'shared_cross_layer_key': 'geom_id',
            'source_id_format': 'S1::<geom_id>',
            'program_id_format': 'P1::<geom_id>',
            'model_id_format': 'M1::<geom_id>',
        },
        'example_materialized_record': {
            'source_id': 'S1::rel_non_002',
            'geom_id': 'rel_non_002',
            'source_layer': 'S1',
            'domain': 'relativity',
            'geometry_class': 'non_euclidean',
            'semantic_name': 'Lorentzian pseudo-Riemannian spacetime',
            'asset_kind': 'geometry_binary',
            'binary_format': 'json',
            'payload_path': 'inf-Brain/S1/relativity/rel_non_002.json',
            'sha256': '<filled-on-materialization>',
            'producer': 'inf_brain_asset_builder',
            'created_at': '<iso8601>',
            'intended_consumers': ['P1', 'M1'],
        },
    }


def build_mapping(l1: dict, s1: dict) -> dict:
    s1_records = {r['geom_id']: r for r in s1['records']}
    mappings = []
    for rec in l1['records']:
        geom_id = rec['geom_id']
        s1_rec = s1_records[geom_id]
        mappings.append({
            'geom_id': geom_id,
            'l1': {
                'layer': 'L1',
                'name': rec['name'],
                'domain': rec['domain'],
                'geometry_class': rec['geometry_class'],
                'usage_mode': rec['usage_mode'],
            },
            's1': {
                'source_id': s1_rec['source_id'],
                'materialization_status': s1_rec['materialization_status'],
                'asset_kind': s1_rec['asset_kind'],
                'sha256_required': s1_rec['hash_required_when_materialized'],
            },
            'p1': p1_target_for(rec),
        })

    return {
        'schema': 'inf-brain-l1-s1-p1-mapping-v1',
        'description': 'Cross-layer mapping from L1 semantic geometry entries to S1 assets and P1 compiler targets',
        'shared_key': 'geom_id',
        'layer_scope': 'inf-Brain',
        'record_count': len(mappings),
        'mappings': mappings,
    }


def main() -> int:
    l1 = load_json(L1_PATH)
    s1 = load_json(S1_PATH)
    spec = build_spec()
    mapping = build_mapping(l1, s1)
    OUT_SPEC.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MAPPING.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({
        'ok': True,
        'mapping_out': str(OUT_MAPPING),
        'spec_out': str(OUT_SPEC),
        'count': mapping['record_count'],
    }, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
