from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .kq_symbolic_bridge import solve_math_logic_unified


@dataclass
class IUTLemmaNode:
    id: str
    layer: str  # L1..L5
    title: str
    formal_spec: str
    depends_on: list[str]


def default_iut_core_subset_v1() -> list[IUTLemmaNode]:
    """Scaffold only (not full IUT reproduction).

    L1: base objects/axioms
    L2: local morphisms
    L3: inter-universal correspondences
    L4: invariant transfer lemmas
    L5: global synthesis
    """
    return [
        IUTLemmaNode("L1-obj-001", "L1", "base-object-consistency", "forall x in [0,1]: x == x", []),
        IUTLemmaNode("L2-mor-001", "L2", "local-morphism-wellformed", "x in [0,5]: x+1>x", ["L1-obj-001"]),
        IUTLemmaNode("L3-cor-001", "L3", "inter-universal-correspondence-lite", "(p or q) and (not p or q)", ["L2-mor-001"]),
        IUTLemmaNode("L4-inv-001", "L4", "invariant-transfer-lite", "x in [0,5]: x*x >= 0", ["L3-cor-001"]),
        IUTLemmaNode("L5-syn-001", "L5", "global-synthesis-lite", "exists x in [1,2,3]: x % 2 == 0", ["L4-inv-001"]),
    ]


def evaluate_iut_core_subset_v1(nodes: list[IUTLemmaNode] | None = None) -> dict[str, Any]:
    nodes = nodes or default_iut_core_subset_v1()
    id_map = {n.id: n for n in nodes}

    out: list[dict[str, Any]] = []
    passed: set[str] = set()

    for n in nodes:
        deps_ok = all(d in passed for d in n.depends_on)
        if not deps_ok:
            out.append({
                "id": n.id,
                "layer": n.layer,
                "title": n.title,
                "ok": False,
                "status": "blocked",
                "missing_dependencies": [d for d in n.depends_on if d not in passed],
            })
            continue

        r = solve_math_logic_unified(n.formal_spec)
        ok = bool(r.get("ok")) and str(r.get("proof_status", "")).lower() != "failed"
        if ok:
            passed.add(n.id)
        out.append({
            "id": n.id,
            "layer": n.layer,
            "title": n.title,
            "ok": ok,
            "status": "checked" if ok else "failed",
            "coverage": r.get("coverage"),
            "kq3_mode": r.get("kq3_mode"),
            "invariants": r.get("inter_universal_invariants"),
        })

    total = len(nodes)
    ok_n = sum(1 for x in out if x.get("ok"))
    return {
        "ok": ok_n == total,
        "subset": "iut_core_subset_v1",
        "total": total,
        "passed": ok_n,
        "pass_ratio": round(ok_n / max(1, total), 4),
        "layers": sorted(list({n.layer for n in nodes})),
        "results": out,
    }
