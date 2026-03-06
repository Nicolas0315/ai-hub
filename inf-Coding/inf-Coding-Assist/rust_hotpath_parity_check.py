#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from katala_samurai import rust_hotpath_bridge as rhb  # noqa: E402


def _rand_case(rng: random.Random):
    n = rng.randint(3, 9)
    node_ids = [f"N{i}" for i in range(n)]
    node_layers = [f"L{rng.randint(1,5)}" for _ in range(n)]
    morphisms = [rng.choice(["local_morphism", "inter_universal_correspondence", "", "global_synthesis"]) for _ in range(n)]
    invariants = [rng.choice(["truth+provability+counterexample-consistency", "", "invariant_transfer"]) for _ in range(n)]
    edges = []
    for i in range(n):
        for j in range(n):
            if i != j and rng.random() < 0.08:
                edges.append((node_ids[i], node_ids[j]))
    return node_ids, node_layers, morphisms, invariants, edges


def main() -> int:
    m = rhb._mod()  # type: ignore[attr-defined]
    if m is None:
        print(json.dumps({"ok": False, "reason": "rust module unavailable"}, ensure_ascii=False))
        return 2

    rng = random.Random(20260306)
    total = 1000
    mismatch = 0
    specificity_mismatch = 0
    trigger_mismatch = 0
    precision_mismatch = 0
    strict_hook_mismatch = 0
    verification_gate_mismatch = 0

    for _ in range(total):
        node_ids, node_layers, morphisms, invariants, edges = _rand_case(rng)
        py = rhb._py_dense_dependency_edges(node_ids, node_layers, morphisms, invariants, edges)  # type: ignore[attr-defined]
        rs = list(m.dense_dependency_edges(node_ids, node_layers, morphisms, invariants, edges))
        if sorted(py) != sorted(rs):
            mismatch += 1

        spec = rng.choice([
            "vars: x in [0,3]; formula: and(x>=0, x<=3)",
            "forall x in [1,2,3]: x > 0",
            "x+1>x",
            "exists x in [1,2,3]: x%2==1",
            "(p or q)",
        ])
        py_s = rhb._py_strict_specificity_score(spec)  # type: ignore[attr-defined]
        rs_s = float(m.strict_specificity_score(spec))
        if abs(py_s - rs_s) > 1e-9:
            specificity_mismatch += 1

        kq3 = rng.choice([True, False])
        invs = rng.choice([0.5, 0.71, 0.72, 0.9])
        cex = rng.choice([True, False])
        py_t = rhb._py_strict_triggered(kq3, invs, cex)  # type: ignore[attr-defined]
        rs_t = bool(m.strict_triggered(kq3, float(invs), cex))
        if py_t != rs_t:
            trigger_mismatch += 1

        d = rng.choice(["", "domain"])
        m1 = rng.choice(["", "morphism"])
        inv = rng.choice(["", "invariant"])
        sp = rng.choice(["", "forall x in [1]: x==x"])
        py_p = rhb._py_precision_score(d, m1, inv, sp)  # type: ignore[attr-defined]
        rs_p = float(m.precision_score(d, m1, inv, sp))
        if abs(py_p - rs_p) > 1e-9:
            precision_mismatch += 1

        py_h = rhb._py_strict_spec_hook(sp, py_s)  # type: ignore[attr-defined]
        rs_h = bool(m.strict_spec_hook(sp, float(rs_s)))
        if py_h != rs_h:
            strict_hook_mismatch += 1

        args = [rng.choice([True, False]) for _ in range(6)]
        py_v = rhb._py_verification_gate(*args)  # type: ignore[attr-defined]
        rs_v = bool(m.verification_gate(*args))
        if py_v != rs_v:
            verification_gate_mismatch += 1

    ok = mismatch == 0 and specificity_mismatch == 0 and trigger_mismatch == 0 and precision_mismatch == 0 and strict_hook_mismatch == 0 and verification_gate_mismatch == 0
    print(json.dumps({"ok": ok, "total": total, "mismatch": mismatch, "specificity_mismatch": specificity_mismatch, "trigger_mismatch": trigger_mismatch, "precision_mismatch": precision_mismatch, "strict_hook_mismatch": strict_hook_mismatch, "verification_gate_mismatch": verification_gate_mismatch}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
