#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
IN_LEDGER = ROOT / 'S1_source_ledger_20260307_v2_geometry_first.json'
IN_CATALOG = ROOT / 'S1_geometry_catalog_tier1_20260307.json'
OUT_LEDGER = ROOT / 'S1_source_ledger_20260307_v3_tier1_augmented.json'


def load(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def infer_domains(family_id: str) -> list[str]:
    if family_id in {'euclidean_geometry', 'affine_geometry', 'projective_geometry', 'manifold_geometry', 'riemannian_geometry', 'pseudo_riemannian_geometry'}:
        return ['relativity', 'cross_domain']
    if family_id in {'hilbert_geometry', 'projective_hilbert_geometry', 'complex_geometry', 'symplectic_geometry', 'poisson_geometry', 'noncommutative_geometry', 'information_geometry'}:
        return ['quantum', 'cross_domain']
    return ['cross_domain']


def infer_usage(family_id: str) -> list[str]:
    if family_id in {'euclidean_geometry', 'pseudo_riemannian_geometry', 'hilbert_geometry', 'projective_hilbert_geometry'}:
        return ['core']
    if family_id in {'bundle_geometry', 'noncommutative_geometry', 'information_geometry'}:
        return ['extended']
    return ['general']


def objects_for(subtype: str, geometry_class: str) -> list[str]:
    if subtype.startswith('euclidean'):
        return ['point', 'line', 'distance', 'coordinate_chart']
    if 'affine' in subtype:
        return ['point', 'affine_frame', 'translation_class']
    if 'projective' in subtype:
        return ['point_class', 'line_class', 'incidence_structure']
    if 'manifold' in subtype:
        return ['manifold', 'chart', 'atlas']
    if 'riemannian' in subtype:
        return ['manifold', 'metric_tensor', 'curvature_tensor']
    if 'lorentzian' in subtype or 'pseudo_riemannian' in subtype or 'minkowski' in subtype:
        return ['manifold', 'metric_tensor', 'connection', 'causal_frame']
    if 'hilbert' in subtype:
        return ['state', 'ray', 'inner_product']
    if 'complex' in subtype or 'hermitian' in subtype or 'kahler' in subtype or 'fubini' in subtype:
        return ['complex_coordinate', 'metric', 'compatible_structure']
    if 'symplectic' in subtype:
        return ['phase_space', 'symplectic_form']
    if 'poisson' in subtype or 'bracket' in subtype:
        return ['phase_space', 'poisson_bracket']
    if 'bundle' in subtype or 'connection' in subtype or 'curvature' in subtype:
        return ['base_space', 'fiber', 'connection']
    if 'noncommutative' in subtype or 'operator' in subtype or 'spectral' in subtype:
        return ['algebra', 'operator', 'spectrum']
    if 'information' in subtype or 'statistical' in subtype or 'divergence' in subtype or 'fisher' in subtype:
        return ['statistical_state', 'metric', 'divergence']
    return ['geometry_object']


def relations_for(subtype: str, geometry_class: str) -> list[str]:
    rels = ['identity']
    if geometry_class == 'euclidean':
        rels += ['distance', 'angle', 'parallelism']
    else:
        rels += ['curvature', 'comparison_map']
    if any(k in subtype for k in ['lorentzian', 'pseudo_riemannian', 'minkowski']):
        rels.append('causal_structure')
    if any(k in subtype for k in ['hilbert', 'projective']):
        rels.append('state_equivalence')
    if any(k in subtype for k in ['symplectic', 'poisson', 'hamiltonian']):
        rels.append('phase_relation')
    rels.append('local_euclid_recovery_reference')
    return rels


def ops_for(subtype: str, geometry_class: str) -> list[str]:
    ops = ['identify_geometry', 'tag_for_program']
    if geometry_class == 'euclidean':
        ops += ['distance_evaluate', 'coordinate_compare']
    else:
        ops += ['map_compare', 'invariant_check']
    if any(k in subtype for k in ['hilbert', 'projective']):
        ops += ['state_project', 'ray_compare']
    elif any(k in subtype for k in ['symplectic', 'poisson', 'hamiltonian']):
        ops += ['form_evaluate', 'bracket_compare']
    else:
        ops += ['local_limit_recover']
    return ops


def main() -> int:
    ledger = load(IN_LEDGER)
    catalog = load(IN_CATALOG)
    records = ledger['records']
    seen = {r['subtype'] for r in records}
    next_id = len(records) + 1

    for fam in catalog['families']:
        family_id = fam['family_id']
        gclass = fam['geometry_class']
        for sub in fam['subtypes']:
            subtype = sub['subtype'] if isinstance(sub, dict) else sub
            formalization_target = sub['formalization_target'] if isinstance(sub, dict) else 'normalized'
            if subtype in seen:
                continue
            prefix = 'geom'
            if 'relativity' in infer_domains(family_id):
                prefix = 'x'
            geom_id = f"{prefix}_{next_id:03d}"
            next_id += 1
            record = {
                'source_id': f'S1::{geom_id}',
                'geom_id': geom_id,
                'source_layer': 'S1',
                'name': subtype.replace('_', ' '),
                'geometry_class': gclass,
                'subtype': subtype,
                'used_in_domains': infer_domains(family_id),
                'usage_modes': infer_usage(family_id),
                'definition_level': 'normalized_source',
                'core_objects': objects_for(subtype, gclass),
                'core_relations': relations_for(subtype, gclass),
                'required_operations': ops_for(subtype, gclass),
                'p_layer_target': {
                    'program_family': f'{family_id}_compiler',
                    'compiler_profile': f'{family_id}_{formalization_target}'
                },
                'formalization_status': 'normalized' if formalization_target != 'enumerated' else 'enumerated',
                'source_refs': [f'L1::{family_id}::{subtype}'],
                'legacy_fields': {
                    'tier': 1,
                    'family_id': family_id,
                    'formalization_target': formalization_target,
                    'augmentation_note': 'Added from Tier1 catalog expansion'
                }
            }
            records.append(record)
            seen.add(subtype)

    out = {
        'schema': 'inf-model-s1-source-ledger-v3-tier1-augmented',
        'description': 'Geometry-first S1 ledger augmented to Tier1 family+subtype coverage target',
        'primary_grouping': 'geometry_first',
        'shared_key': 'geom_id',
        'record_count': len(records),
        'records': records,
    }
    OUT_LEDGER.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_LEDGER), 'count': len(records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
