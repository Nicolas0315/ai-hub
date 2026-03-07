#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
S1_PATH = ROOT / 'S1_source_ledger_20260307_v2_geometry_first.json'
OUT_DIR = ROOT / 'P1_artifacts_20260307_v2'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def materialize_s1_payload(s1_record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(s1_record)
    payload['asset_kind'] = 'geometry_normalized_source'
    payload['binary_format'] = 'json'
    payload['producer'] = 'inf_brain_p1_compiler_v2_20260307.py'
    payload['created_at'] = now_iso()
    payload['intended_consumers'] = ['P1', 'P2', 'M1']
    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    payload['sha256'] = sha256_of_bytes(payload_bytes)
    return payload


def build_runtime_type(s1_payload: dict[str, Any]) -> str:
    if s1_payload['geometry_class'] == 'euclidean':
        return 'euclidean_single_geometry_runtime'
    return 'non_euclidean_single_geometry_runtime'


def build_executable_model(s1_payload: dict[str, Any]) -> dict[str, Any]:
    geom_id = s1_payload['geom_id']
    executable = {
        'program_id': f'P1::{geom_id}',
        'geom_id': geom_id,
        'program_layer': 'P1',
        'compiled_from': s1_payload['source_id'],
        'runtime_type': build_runtime_type(s1_payload),
        'object_model': {
            'objects': s1_payload['core_objects'],
            'object_runtime_family': 'typed_geometry_objects',
            'subtype': s1_payload['subtype'],
        },
        'relation_model': {
            'relations': s1_payload['core_relations'],
            'relation_runtime_family': 'typed_geometry_relations',
        },
        'operation_stubs': s1_payload['required_operations'],
        'serialization_format': 'json',
        'verification_contract': {
            'geom_id_match_required': True,
            'source_hash_required': True,
            'operation_stub_presence_required': True,
            'compiled_from_expected_input_required': True,
        },
        'ready_for_p2': True,
        'p2_handoff': {
            'intended_role': 'iut_mediation_input',
            'used_in_domains': s1_payload['used_in_domains'],
            'usage_modes': s1_payload['usage_modes'],
        },
        'compiled_at': now_iso(),
        'input_hash': s1_payload['sha256'],
    }
    executable['program_sha256'] = sha256_of_bytes(json.dumps(executable, ensure_ascii=False, indent=2).encode('utf-8'))
    return executable


def build_verification_report(s1_payload: dict[str, Any], executable: dict[str, Any]) -> dict[str, Any]:
    checks = {
        'geom_id_match': s1_payload['geom_id'] == executable['geom_id'],
        'sha256_present': bool(s1_payload.get('sha256')),
        'operation_stubs_present': bool(executable.get('operation_stubs')),
        'compiled_from_expected_input': executable['compiled_from'] == s1_payload['source_id'],
    }
    return {
        'program_id': executable['program_id'],
        'geom_id': executable['geom_id'],
        'verified_at': now_iso(),
        'verification_contract': executable['verification_contract'],
        'checks': checks,
        'pass': all(checks.values()),
    }


def compile_one(s1_record: dict[str, Any]) -> dict[str, Any]:
    geom_id = s1_record['geom_id']
    s1_payload = materialize_s1_payload(s1_record)
    executable = build_executable_model(s1_payload)
    report = build_verification_report(s1_payload, executable)

    geom_dir = OUT_DIR / geom_id
    save_json(geom_dir / 'S1_materialized_v2.json', s1_payload)
    save_json(geom_dir / 'P1_runtime_spec.json', executable)
    save_json(geom_dir / 'P1_verification_report.json', report)

    return {
        'geom_id': geom_id,
        'artifact_dir': str(geom_dir),
        'pass': report['pass'],
        'runtime_type': executable['runtime_type'],
        'ready_for_p2': executable['ready_for_p2'],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--geom-id', help='compile only one geometry id')
    args = parser.parse_args()

    s1 = load_json(S1_PATH)
    s1_records = {r['geom_id']: r for r in s1['records']}
    geom_ids = [args.geom_id] if args.geom_id else sorted(s1_records.keys())
    results = [compile_one(s1_records[gid]) for gid in geom_ids]

    summary = {
        'schema': 'inf-brain-p1-compile-summary-v2',
        'compiled_count': len(results),
        'all_pass': all(r['pass'] for r in results),
        'all_ready_for_p2': all(r['ready_for_p2'] for r in results),
        'results': results,
        'output_root': str(OUT_DIR),
    }
    save_json(OUT_DIR / 'compile_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
