#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
IN_PATH = ROOT / 'S1_source_ledger_20260307.json'
OUT_PATH = ROOT / 'S1_source_ledger_20260307_v2_geometry_first.json'


def subtype_for(name: str, geom_id: str) -> str:
    low = name.lower()
    if 'newtonian-limit' in low:
        return 'euclidean_3d_newtonian_limit'
    if 'post-newtonian' in low:
        return 'euclidean_weak_field_post_newtonian'
    if 'local inertial' in low:
        return 'euclidean_local_inertial_chart'
    if 'laboratory' in low:
        return 'euclidean_laboratory_reduction'
    if 'minkowski' in low:
        return 'minkowski'
    if 'lorentzian pseudo-riemannian' in low:
        return 'lorentzian_pseudo_riemannian'
    if 'riemannian 3-geometry' in low:
        return 'riemannian_adm_slice'
    if 'de sitter' in low or 'anti-de sitter' in low:
        return 'de_sitter_anti_de_sitter'
    if 'flrw' in low:
        return 'flrw_curved_cosmology'
    if 'black-hole manifold' in low:
        return 'black_hole_manifold'
    if 'configuration space' in low:
        return 'euclidean_configuration_space'
    if 'wick-rotated' in low:
        return 'euclidean_wick_rotated_field_theory'
    if 'lattice gauge' in low:
        return 'euclidean_lattice_gauge'
    if 'momentum-space' in low:
        return 'euclidean_momentum_regularization'
    if 'projective hilbert' in low:
        return 'projective_hilbert'
    if 'complex projective space' in low:
        return 'complex_projective_space'
    if 'fiber-bundle' in low:
        return 'fiber_bundle'
    if 'symplectic' in low:
        return 'symplectic'
    if 'poisson' in low:
        return 'poisson'
    if 'information geometry' in low:
        return 'information_geometry'
    if 'noncommutative' in low:
        return 'noncommutative_geometry'
    return f'normalized_{geom_id}'


def usage_modes(name: str) -> list[str]:
    low = name.lower()
    modes = []
    for key, mode in [
        ('limit', 'limit'),
        ('approximation', 'approximation'),
        ('local', 'local'),
        ('computational', 'computational'),
        ('core', 'core'),
        ('formalism', 'formalism'),
        ('solution-space', 'solution_space'),
        ('cosmological', 'cosmology'),
        ('strong-gravity', 'strong_gravity'),
        ('analytic', 'analytic'),
        ('regularization', 'regularization'),
        ('information', 'information'),
        ('extended', 'extended')
    ]:
        if key in low:
            modes.append(mode)
    return modes or ['general']


def core_objects(subtype: str) -> list[str]:
    mapping = {
        'minkowski': ['event', 'interval', 'frame'],
        'lorentzian_pseudo_riemannian': ['manifold', 'metric_tensor', 'connection', 'geodesic'],
        'riemannian_adm_slice': ['slice_manifold', 'spatial_metric', 'curvature_tensor'],
        'de_sitter_anti_de_sitter': ['manifold', 'metric_tensor', 'curvature_scale'],
        'flrw_curved_cosmology': ['scale_factor', 'metric_tensor', 'cosmic_slice'],
        'black_hole_manifold': ['manifold', 'horizon', 'metric_tensor', 'geodesic'],
        'projective_hilbert': ['hilbert_state', 'ray', 'inner_product'],
        'complex_projective_space': ['state_ray', 'complex_coordinate', 'projective_class'],
        'fiber_bundle': ['base_space', 'fiber', 'connection'],
        'symplectic': ['phase_space', 'symplectic_form'],
        'poisson': ['phase_space', 'poisson_bracket'],
        'information_geometry': ['statistical_state', 'metric', 'divergence'],
        'noncommutative_geometry': ['algebra', 'operator', 'spectrum'],
    }
    if subtype in mapping:
        return mapping[subtype]
    if subtype.startswith('euclidean_'):
        return ['point', 'line', 'distance', 'coordinate_chart']
    return ['geometry_object']


def core_relations(subtype: str, geometry_class: str) -> list[str]:
    rels = ['identity']
    if geometry_class == 'euclidean':
        rels += ['distance', 'angle', 'parallelism']
    else:
        rels += ['curvature', 'comparison_map']
    if subtype in ['lorentzian_pseudo_riemannian', 'minkowski', 'black_hole_manifold']:
        rels.append('causal_structure')
    if subtype in ['projective_hilbert', 'complex_projective_space']:
        rels.append('state_equivalence')
    if subtype in ['symplectic', 'poisson']:
        rels.append('phase_relation')
    rels.append('local_euclid_recovery_reference')
    return rels


def required_ops(subtype: str, geometry_class: str) -> list[str]:
    ops = ['identify_geometry', 'tag_for_program']
    if geometry_class == 'euclidean':
        ops += ['distance_evaluate', 'coordinate_compare']
    else:
        ops += ['map_compare', 'invariant_check']
    if subtype in ['lorentzian_pseudo_riemannian', 'minkowski', 'black_hole_manifold']:
        ops += ['causal_compare', 'local_limit_recover']
    elif subtype in ['projective_hilbert', 'complex_projective_space']:
        ops += ['state_project', 'ray_compare']
    elif subtype in ['symplectic', 'poisson']:
        ops += ['form_evaluate', 'bracket_compare']
    else:
        ops += ['local_limit_recover']
    return ops


def main() -> int:
    src = json.loads(IN_PATH.read_text(encoding='utf-8'))
    out_records = []
    for rec in src.get('records', []):
        name = rec['semantic_name']
        geom_id = rec['geom_id']
        geometry_class = rec['geometry_class']
        subtype = subtype_for(name, geom_id)
        domain = rec['domain']
        compiler_profile = f"{domain}_{geometry_class}_{usage_modes(name)[0]}"
        out_records.append({
            'source_id': rec['source_id'],
            'geom_id': geom_id,
            'source_layer': 'S1',
            'name': name,
            'geometry_class': geometry_class,
            'subtype': subtype,
            'used_in_domains': [domain],
            'usage_modes': usage_modes(name),
            'definition_level': 'normalized_source',
            'core_objects': core_objects(subtype),
            'core_relations': core_relations(subtype, geometry_class),
            'required_operations': required_ops(subtype, geometry_class),
            'p_layer_target': {
                'program_family': f'{domain}_geometry_compiler',
                'compiler_profile': compiler_profile
            },
            'formalization_status': 'normalized',
            'source_refs': [f'L1::{geom_id}'],
            'legacy_fields': {
                'asset_kind': rec.get('asset_kind'),
                'materialization_status': rec.get('materialization_status'),
                'sha256': rec.get('sha256'),
                'hash_required_when_materialized': rec.get('hash_required_when_materialized'),
                'intended_consumers': rec.get('intended_consumers'),
                'notes': rec.get('notes')
            }
        })
    payload = {
        'schema': 'inf-model-s1-source-ledger-v2-geometry-first',
        'description': 'Geometry-first S1 source ledger with theory usage attached as metadata',
        'primary_grouping': 'geometry_first',
        'shared_key': 'geom_id',
        'record_count': len(out_records),
        'records': out_records,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(OUT_PATH), 'count': len(out_records)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
