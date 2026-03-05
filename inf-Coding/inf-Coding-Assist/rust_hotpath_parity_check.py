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

    ok = mismatch == 0 and specificity_mismatch == 0
    print(json.dumps({"ok": ok, "total": total, "mismatch": mismatch, "specificity_mismatch": specificity_mismatch}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
