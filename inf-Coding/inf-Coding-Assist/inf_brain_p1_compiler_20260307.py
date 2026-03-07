#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
L1_PATH = ROOT / 'L1_normalized_20260307.json'
S1_PATH = ROOT / 'S1_source_ledger_20260307.json'
MAP_PATH = ROOT / 'inf_brain_l1_s1_p1_mapping_20260307.json'
OUT_DIR = ROOT / 'P1_artifacts_20260307'


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def materialize_s1_payload(s1_record: dict[str, Any], l1_record: dict[str, Any]) -> dict[str, Any]:
    payload = {
        'source_id': s1_record['source_id'],
        'geom_id': s1_record['geom_id'],
        'source_layer': 'S1',
        'domain': s1_record['domain'],
        'geometry_class': s1_record['geometry_class'],
        'semantic_name': s1_record['semantic_name'],
        'usage_mode': l1_record['usage_mode'],
        'euclid_property_profile': l1_record['euclid_property_profile'],
        'asset_kind': 'geometry_binary',
        'binary_format': 'json',
        'producer': 'inf_brain_p1_compiler_20260307.py',
        'created_at': now_iso(),
        'intended_consumers': ['P1', 'M1'],
        'semantic_snapshot': {
            'layer_anchor': l1_record['layer_anchor'],
            'expected_source_layer': l1_record['expected_source_layer'],
            'name': l1_record['name'],
        },
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
    payload['sha256'] = sha256_of_bytes(payload_bytes)
    return payload


def build_executable_model(mapping: dict[str, Any], s1_payload: dict[str, Any]) -> dict[str, Any]:
    p1 = mapping['p1']
    l1 = mapping['l1']
    executable = {
        'program_id': p1['program_id'],
        'program_layer': 'P1',
        'geom_id': mapping['geom_id'],
        'compiler_profile': p1['compiler_profile'],
        'program_family': p1['program_family'],
        'compiled_from': s1_payload['source_id'],
        'compiled_at': now_iso(),
        'semantic_contract': {
            'domain': l1['domain'],
            'geometry_class': l1['geometry_class'],
            'usage_mode': l1['usage_mode'],
        },
        'runtime_stub': {
            'entrypoint': 'simulate_geometry_model',
            'status': 'stubbed',
            'next_requirement': 'Replace stub with geometry-specific solver/runtime implementation.',
        },
        'input_hash': s1_payload['sha256'],
    }
    executable['program_sha256'] = sha256_of_bytes(json.dumps(executable, ensure_ascii=False, indent=2).encode('utf-8'))
    return executable


def build_verification_report(mapping: dict[str, Any], s1_payload: dict[str, Any], executable: dict[str, Any]) -> dict[str, Any]:
    contract = mapping['p1']['verification_contract']
    checks = {
        'geom_id_match': mapping['geom_id'] == s1_payload['geom_id'] == executable['geom_id'],
        'sha256_present': bool(s1_payload.get('sha256')),
        'schema_fields_present': all(k in s1_payload for k in ['source_id', 'geom_id', 'domain', 'geometry_class', 'sha256']),
        'compiled_from_expected_input': executable['compiled_from'] in mapping['p1']['expected_inputs'],
    }
    return {
        'program_id': mapping['p1']['program_id'],
        'geom_id': mapping['geom_id'],
        'verified_at': now_iso(),
        'verification_contract': contract,
        'checks': checks,
        'pass': all(checks.values()),
    }


def compile_one(geom_id: str, l1_records: dict[str, Any], s1_records: dict[str, Any], mappings: dict[str, Any]) -> dict[str, Any]:
    l1_record = l1_records[geom_id]
    s1_record = s1_records[geom_id]
    mapping = mappings[geom_id]

    s1_payload = materialize_s1_payload(s1_record, l1_record)
    executable = build_executable_model(mapping, s1_payload)
    report = build_verification_report(mapping, s1_payload, executable)

    geom_dir = OUT_DIR / geom_id
    save_json(geom_dir / 'S1_materialized.json', s1_payload)
    save_json(geom_dir / 'P1_executable_model.json', executable)
    save_json(geom_dir / 'P1_verification_report.json', report)

    return {
        'geom_id': geom_id,
        'artifact_dir': str(geom_dir),
        'pass': report['pass'],
        'compiler_profile': mapping['p1']['compiler_profile'],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--geom-id', help='compile only one geometry id')
    args = parser.parse_args()

    l1 = load_json(L1_PATH)
    s1 = load_json(S1_PATH)
    mapping = load_json(MAP_PATH)

    l1_records = {r['geom_id']: r for r in l1['records']}
    s1_records = {r['geom_id']: r for r in s1['records']}
    mappings = {r['geom_id']: r for r in mapping['mappings']}

    geom_ids = [args.geom_id] if args.geom_id else sorted(mappings.keys())
    results = [compile_one(gid, l1_records, s1_records, mappings) for gid in geom_ids]

    summary = {
        'schema': 'inf-brain-p1-compile-summary-v1',
        'compiled_count': len(results),
        'all_pass': all(r['pass'] for r in results),
        'results': results,
        'output_root': str(OUT_DIR),
    }
    save_json(OUT_DIR / 'compile_summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
