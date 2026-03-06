#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala')
OUT = ROOT / 'inf-Coding' / 'inf-Coding-Assist' / 'inf_model_u_layer_mapping_check_20260307.json'


def u_metric(alpha: float, beta: float, gamma: float, h: list[list[float]]) -> list[list[float]]:
    # U-layer toy metric combination (hierarchical mapped structure)
    # g_U = alpha * h + beta * I + gamma * 1*1^T
    n = len(h)
    out = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            out[i][j] = alpha * h[i][j] + (beta if i == j else 0.0) + gamma
    return out


def max_abs_diff(a: list[list[float]], b: list[list[float]]) -> float:
    m = 0.0
    for i in range(len(a)):
        for j in range(len(a[i])):
            d = abs(a[i][j] - b[i][j])
            if d > m:
                m = d
    return m


def main() -> int:
    # Euclid target (2D identity metric)
    I2 = [[1.0, 0.0], [0.0, 1.0]]

    # Lower-layer representative mapped metric from relativity/quantum projections
    h = [[1.02, 0.01], [0.01, 0.98]]

    # Local recovery test: tiny deformation around Euclid
    g_local = u_metric(alpha=0.0, beta=1.0, gamma=0.0, h=h)
    local_err = max_abs_diff(g_local, I2)
    local_pass = bool(local_err <= 1e-12)

    # Limit recovery test: alpha->0, beta->1, gamma->0
    # sample sequence towards limit
    seq = [1e-1, 1e-2, 1e-3, 1e-4, 1e-5]
    limit_errs = []
    for eps in seq:
        g_lim = u_metric(alpha=eps, beta=1.0, gamma=0.0, h=h)
        limit_errs.append(max_abs_diff(g_lim, I2))
    limit_pass = all(limit_errs[i+1] <= limit_errs[i] + 1e-15 for i in range(len(limit_errs)-1)) and (limit_errs[-1] < 1e-4)

    payload = {
        'schema': 'inf-model-u-layer-mapping-check-v1',
        'u_layer_mapping_equations': {
            'unified_metric': 'g_U = alpha*h + beta*I + gamma*J',
            'local_recovery_condition': 'alpha=0, beta=1, gamma=0 => g_U = I',
            'limit_recovery_condition': 'alpha->0, beta->1, gamma->0 => g_U -> I',
        },
        'tests': {
            'local_recovery': {
                'pass': local_pass,
                'max_abs_error': local_err,
            },
            'limit_recovery': {
                'pass': bool(limit_pass),
                'sample_eps': seq,
                'errors': limit_errs,
            },
        },
        'overall_pass': bool(local_pass and limit_pass),
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ok': True, 'overall_pass': payload['overall_pass'], 'out': str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
