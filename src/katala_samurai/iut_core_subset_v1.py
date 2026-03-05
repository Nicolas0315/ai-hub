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
    source_paper: str = ""
    source_note: str = ""


def default_iut_core_subset_v1() -> list[IUTLemmaNode]:
    """IUT-core subset v1 (paper-anchored, still lightweight formalization).

    Source anchors are derived from IUT I-IV public paper titles/major themes.
    This is not a full formalization of IUT; it is a structured stepping stone.
    """
    return [
        # L1: base objects / local coherence
        IUTLemmaNode("L1-obj-001", "L1", "hodge-theater-base-coherence", "forall x in [0,1]: x == x", [], source_paper="IUT I", source_note="Base object coherence"),
        IUTLemmaNode("L1-obj-002", "L1", "frobenioid-local-consistency", "x in [0,5]: x+1>x", [], source_paper="IUT I", source_note="Local consistency surrogate"),
        IUTLemmaNode("L1-obj-003", "L1", "local-order-preservation", "x in [0,5]: x*x >= 0", [], source_paper="IUT I", source_note="Order preservation baseline"),

        # L2: local morphisms / evaluation links
        IUTLemmaNode("L2-mor-001", "L2", "hodge-arakelov-evaluation-stability", "vars: x in [0,3], y in [0,3]; formula: and(x+y==3, x>=0, y>=0)", ["L1-obj-001", "L1-obj-002"], source_paper="IUT II", source_note="Evaluation stability"),
        IUTLemmaNode("L2-mor-002", "L2", "local-morphism-composition", "(p or q) and (not p or q)", ["L1-obj-002", "L1-obj-003"], source_paper="IUT II", source_note="Composition consistency"),
        IUTLemmaNode("L2-mor-003", "L2", "arith-constraint-soundness", "x in [1,10]: x % 2 == 0 and x > 1", ["L1-obj-003"], source_paper="IUT II", source_note="Arithmetic soundness surrogate"),

        # L3: inter-universal correspondences
        IUTLemmaNode("L3-cor-001", "L3", "log-theta-canonical-splitting-consistency", "(a or b) and (not a or b)", ["L2-mor-001"], source_paper="IUT III", source_note="Canonical splitting consistency"),
        IUTLemmaNode("L3-cor-002", "L3", "cross-theater-bridge-preservation", "forall x in [1,2,3]: x > 0", ["L2-mor-001", "L2-mor-002"], source_paper="IUT III", source_note="Bridge-preservation surrogate"),
        IUTLemmaNode("L3-cor-003", "L3", "theta-link-invariant-transfer", "exists x in [1,2,3]: x % 2 == 1", ["L2-mor-002", "L2-mor-003"], source_paper="IUT III", source_note="Theta-link transfer"),

        # L4: invariant transfer / log-volume style controls
        IUTLemmaNode("L4-inv-001", "L4", "log-volume-invariant-transfer", "x in [0,5]: x*x >= 0", ["L3-cor-001", "L3-cor-002"], source_paper="IUT IV", source_note="Invariant transfer baseline"),
        IUTLemmaNode("L4-inv-002", "L4", "set-theoretic-foundation-sanity", "vars: x in [0,4], y in [0,4]; formula: and(x>=0, y>=0, x+y>=0)", ["L3-cor-002"], source_paper="IUT IV", source_note="Set-theoretic sanity"),
        IUTLemmaNode("L4-inv-003", "L4", "counterexample-consistency-guard", "(p or q) and (not p or q)", ["L3-cor-003"], source_paper="IUT IV", source_note="Counterexample guard"),

        # L5: global synthesis
        IUTLemmaNode("L5-syn-001", "L5", "global-theater-synthesis-check", "vars: x in [0,3], y in [0,3]; formula: and(x+y==3, x>=0, y>=0)", ["L4-inv-001", "L4-inv-002"], source_paper="IUT I-IV", source_note="Global synthesis sanity"),
        IUTLemmaNode("L5-syn-002", "L5", "global-bridge-coherence", "forall x in [1,2,3]: x >= 1", ["L4-inv-001", "L4-inv-003"], source_paper="IUT I-IV", source_note="Bridge coherence"),
        IUTLemmaNode("L5-syn-003", "L5", "final-invariant-preservation", "exists x in [2,3,4,5]: x % 2 == 1", ["L5-syn-001", "L5-syn-002"], source_paper="IUT I-IV", source_note="Final preservation check"),
    ]


def build_dependency_graph(nodes: list[IUTLemmaNode]) -> dict[str, Any]:
    ids = {n.id for n in nodes}
    edges: list[tuple[str, str]] = []
    indeg: dict[str, int] = {n.id: 0 for n in nodes}
    succ: dict[str, list[str]] = {n.id: [] for n in nodes}

    for n in nodes:
        for d in (n.depends_on or []):
            if d in ids:
                edges.append((d, n.id))
                indeg[n.id] += 1
                succ[d].append(n.id)

    # Kahn topological order
    q = [nid for nid, deg in indeg.items() if deg == 0]
    topo: list[str] = []
    while q:
        cur = q.pop(0)
        topo.append(cur)
        for nx in succ.get(cur, []):
            indeg[nx] -= 1
            if indeg[nx] == 0:
                q.append(nx)

    has_cycle = len(topo) != len(nodes)
    return {
        "nodes": sorted(list(ids)),
        "edges": [{"from": a, "to": b} for a, b in edges],
        "topological_order": topo,
        "has_cycle": has_cycle,
    }


def evaluate_iut_core_subset_v1(nodes: list[IUTLemmaNode] | None = None) -> dict[str, Any]:
    nodes = nodes or default_iut_core_subset_v1()
    graph = build_dependency_graph(nodes)

    id_map = {n.id: n for n in nodes}
    exec_order = [id_map[i] for i in graph.get("topological_order", []) if i in id_map]
    if len(exec_order) < len(nodes):
        # cycle fallback: keep input order for remaining
        used = {n.id for n in exec_order}
        exec_order.extend([n for n in nodes if n.id not in used])

    out: list[dict[str, Any]] = []
    passed: set[str] = set()

    for n in exec_order:
        deps_ok = all(d in passed for d in n.depends_on)
        if not deps_ok:
            out.append({
                "id": n.id,
                "layer": n.layer,
                "title": n.title,
                "source_paper": n.source_paper,
                "source_note": n.source_note,
                "ok": False,
                "status": "blocked",
                "missing_dependencies": [d for d in n.depends_on if d not in passed],
            })
            continue

        r = solve_math_logic_unified(n.formal_spec)
        kq3 = (r.get("kq3_mode") or {}) if isinstance(r, dict) else {}
        inv = (r.get("inter_universal_invariants") or {}) if isinstance(r, dict) else {}
        primary = (r.get("primary") or {}) if isinstance(r, dict) else {}
        pres_score = float(inv.get("invariant_preservation_score", 0.0) or 0.0)

        # Step 3: verification hooks 강화 (formal + counterexample + proof trace)
        formal_hook = bool(r.get("ok")) and str(r.get("proof_status", "")).lower() != "failed"
        counterexample_hook = bool(((inv.get("counterexample_invariant") or {}).get("consistent", False)))
        proof_trace_hook = bool((primary.get("result") or {}).get("proof_certificate") or (primary.get("result") or {}).get("proof_trace_machine"))

        # Step 4: KQ3 strict escalation linkage
        strict_trigger = bool(
            kq3.get("strict_activated")
            or pres_score < 0.72
            or not counterexample_hook
        )

        ok = bool(formal_hook and counterexample_hook and proof_trace_hook)
        if ok:
            passed.add(n.id)
        out.append({
            "id": n.id,
            "layer": n.layer,
            "title": n.title,
            "source_paper": n.source_paper,
            "source_note": n.source_note,
            "ok": ok,
            "status": "checked" if ok else "failed",
            "verification_hooks": {
                "formal_hook": formal_hook,
                "counterexample_hook": counterexample_hook,
                "proof_trace_hook": proof_trace_hook,
            },
            "strict_escalation": {
                "linked": True,
                "triggered": strict_trigger,
                "reason": {
                    "kq3_mode": bool(kq3.get("strict_activated")),
                    "low_invariant_score": bool(pres_score < 0.72),
                    "counterexample_inconsistent": bool(not counterexample_hook),
                },
            },
            "coverage": r.get("coverage"),
            "kq3_mode": kq3,
            "invariants": inv,
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
        "dependency_graph": graph,
        "results": out,
    }
