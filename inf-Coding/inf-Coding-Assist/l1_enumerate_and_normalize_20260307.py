#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala')
OUT_ENUM = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'L1_ledger_20260307_v2_enumerated.json'
OUT_NORM = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'L1_normalized_20260307.json'


def build_catalog() -> dict:
    return {
        "schema": "inf-model-l1-ledger-v2",
        "description": "L1 exhaustive-first enumeration (relativity/quantum x euclidean/non-euclidean)",
        "blocks": {
            "relativity_euclidean": [
                {"geom_id": "rel_euc_001", "name": "Newtonian-limit 3D Euclidean space", "usage_mode": "limit"},
                {"geom_id": "rel_euc_002", "name": "Weak-field post-Newtonian spatial approximation", "usage_mode": "approximation"},
                {"geom_id": "rel_euc_003", "name": "Local inertial chart spatial Euclidean approximation", "usage_mode": "local"},
                {"geom_id": "rel_euc_004", "name": "Euclidean 3-space in laboratory coordinate reductions", "usage_mode": "computational"},
            ],
            "relativity_non_euclidean": [
                {"geom_id": "rel_non_001", "name": "Minkowski geometry", "usage_mode": "core"},
                {"geom_id": "rel_non_002", "name": "Lorentzian pseudo-Riemannian spacetime", "usage_mode": "core"},
                {"geom_id": "rel_non_003", "name": "Riemannian 3-geometry on ADM spatial slices", "usage_mode": "formalism"},
                {"geom_id": "rel_non_004", "name": "de Sitter / anti-de Sitter curved geometry", "usage_mode": "solution-space"},
                {"geom_id": "rel_non_005", "name": "FLRW curved cosmological geometry", "usage_mode": "cosmology"},
                {"geom_id": "rel_non_006", "name": "Black-hole manifold geometry (Schwarzschild/Kerr)", "usage_mode": "strong-gravity"},
            ],
            "quantum_euclidean": [
                {"geom_id": "q_euc_001", "name": "Euclidean 3D configuration space in non-relativistic QM", "usage_mode": "baseline"},
                {"geom_id": "q_euc_002", "name": "Wick-rotated Euclidean-time field theory", "usage_mode": "analytic"},
                {"geom_id": "q_euc_003", "name": "Lattice gauge theory on Euclidean lattices", "usage_mode": "computational"},
                {"geom_id": "q_euc_004", "name": "Euclidean momentum-space regularization frames", "usage_mode": "regularization"},
            ],
            "quantum_non_euclidean": [
                {"geom_id": "q_non_001", "name": "Projective Hilbert-state geometry", "usage_mode": "core"},
                {"geom_id": "q_non_002", "name": "Complex projective space CP^n for pure states", "usage_mode": "core"},
                {"geom_id": "q_non_003", "name": "Fiber-bundle geometry in gauge theories", "usage_mode": "core"},
                {"geom_id": "q_non_004", "name": "Symplectic geometry in phase-space formulations", "usage_mode": "formalism"},
                {"geom_id": "q_non_005", "name": "Poisson geometry for classical-quantum correspondence", "usage_mode": "formalism"},
                {"geom_id": "q_non_006", "name": "Quantum information geometry (Bures/Fisher structures)", "usage_mode": "information"},
                {"geom_id": "q_non_007", "name": "Noncommutative geometry frameworks", "usage_mode": "extended"},
            ],
        },
    }


def normalize(catalog: dict) -> dict:
    records = []
    for block, items in (catalog.get('blocks') or {}).items():
        domain = 'relativity' if block.startswith('relativity_') else 'quantum'
        geom_class = 'euclidean' if block.endswith('euclidean') else 'non_euclidean'
        for it in items:
            records.append(
                {
                    'geom_id': it['geom_id'],
                    'domain': domain,
                    'geometry_class': geom_class,
                    'name': it['name'],
                    'usage_mode': it.get('usage_mode', 'unknown'),
                    'euclid_property_profile': {
                        'is_euclidean': geom_class == 'euclidean',
                        'local_euclid_recoverable': True,
                        'limit_euclid_recoverable': True,
                    },
                }
            )
    return {
        'schema': 'inf-model-l1-normalized-v1',
        'record_count': len(records),
        'records': records,
    }


def main() -> int:
    catalog = build_catalog()
    OUT_ENUM.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')

    normalized = normalize(catalog)
    OUT_NORM.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')

    print(json.dumps({'ok': True, 'enumerated_out': str(OUT_ENUM), 'normalized_out': str(OUT_NORM), 'count': normalized['record_count']}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
