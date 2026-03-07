#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist')
CAT_PATH = ROOT / 'S1_geometry_catalog_20260307_v2_unified.json'
L1_PATH = ROOT / 'L1_geometry_catalog_20260307_v2_unified.json'

ADDITIONS = {
    'euclidean_geometry': [
        ('euclidean_3d_newtonian_limit', 'ready_for_program'),
        ('euclidean_weak_field_post_newtonian', 'normalized'),
        ('euclidean_local_inertial_chart', 'ready_for_program'),
        ('euclidean_laboratory_reduction', 'normalized'),
        ('euclidean_configuration_space', 'ready_for_program'),
        ('euclidean_wick_rotated_field_theory', 'normalized'),
        ('euclidean_lattice_gauge', 'normalized'),
        ('euclidean_momentum_regularization', 'normalized'),
    ],
    'pseudo_riemannian_geometry': [
        ('lorentzian_pseudo_riemannian', 'ready_for_program'),
        ('minkowski', 'ready_for_program'),
        ('riemannian_adm_slice', 'normalized'),
        ('de_sitter_anti_de_sitter', 'normalized'),
        ('flrw_curved_cosmology', 'normalized'),
        ('black_hole_manifold', 'ready_for_program'),
    ],
    'projective_hilbert_geometry': [
        ('projective_hilbert', 'ready_for_program'),
    ],
    'symplectic_geometry': [
        ('symplectic', 'ready_for_program'),
    ],
    'poisson_geometry': [
        ('poisson', 'ready_for_program'),
    ],
    'information_geometry': [
        ('information_geometry', 'normalized'),
    ],
    'noncommutative_geometry': [
        ('noncommutative_geometry', 'normalized'),
    ],
}


def update_s1(cat: dict) -> dict:
    for fam in cat['families']:
        family = fam['family']
        existing = {s['subtype'] for s in fam['subtypes']}
        for subtype, target in ADDITIONS.get(family, []):
            if subtype not in existing:
                fam['subtypes'].append({'subtype': subtype, 'formalization_target': target})
    return cat


def update_l1(cat: dict) -> dict:
    for fam in cat['families']:
        family = fam['family']
        existing = set(fam['subtypes'])
        for subtype, _ in ADDITIONS.get(family, []):
            if subtype not in existing:
                fam['subtypes'].append(subtype)
    return cat


def main() -> int:
    s1 = json.loads(CAT_PATH.read_text(encoding='utf-8'))
    l1 = json.loads(L1_PATH.read_text(encoding='utf-8'))
    s1 = update_s1(s1)
    l1 = update_l1(l1)
    CAT_PATH.write_text(json.dumps(s1, ensure_ascii=False, indent=2), encoding='utf-8')
    L1_PATH.write_text(json.dumps(l1, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 's1_updated': str(CAT_PATH), 'l1_updated': str(L1_PATH)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
