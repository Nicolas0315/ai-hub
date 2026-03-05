#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from collections import defaultdict
from pathlib import Path
from typing import List


@dataclass
class Node:
    id: str
    layer: str
    label: str
    criticality: str = "normal"  # critical|normal|optional


@dataclass
class Edge:
    src: str
    dst: str
    mode: str = "required"  # required|conditional|optional
    condition: str = ""
    weight: float = 1.0
    risk: str = "low"  # low|medium|high


class FlowAuditReport:
    def __init__(self):
        self.nodes: List[Node] = []
        self.edges: List[Edge] = []

    def add_node(self, *args, **kwargs):
        self.nodes.append(Node(*args, **kwargs))

    def add_edge(self, *args, **kwargs):
        self.edges.append(Edge(*args, **kwargs))

    def scc(self):
        nodes = [n.id for n in self.nodes]
        graph = defaultdict(list)
        for e in self.edges:
            graph[e.src].append(e.dst)

        idx, low, st, on = {}, {}, [], set()
        out = []
        i = 0

        def dfs(v):
            nonlocal i
            idx[v] = i
            low[v] = i
            i += 1
            st.append(v)
            on.add(v)
            for w in graph[v]:
                if w not in idx:
                    dfs(w)
                    low[v] = min(low[v], low[w])
                elif w in on:
                    low[v] = min(low[v], idx[w])
            if low[v] == idx[v]:
                comp = []
                while True:
                    w = st.pop()
                    on.remove(w)
                    comp.append(w)
                    if w == v:
                        break
                out.append(comp)

        for n in nodes:
            if n not in idx:
                dfs(n)
        return [c for c in out if len(c) > 1]

    def layer_summary(self):
        layers = defaultdict(list)
        for n in self.nodes:
            layers[n.layer].append(n.id)
        return {k: v for k, v in sorted(layers.items(), key=lambda kv: kv[0])}

    def to_json(self):
        return {
            "meta": {
                "schema": "flowir-audit-v1",
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
            "layers": self.layer_summary(),
            "cycles_scc": self.scc(),
            "risk_edges": [asdict(e) for e in self.edges if e.risk == "high"],
        }

    def to_markdown(self):
        j = self.to_json()
        lines = []
        lines.append("# FlowIR Audit Report")
        lines.append("")
        lines.append(f"- Nodes: **{j['meta']['node_count']}**")
        lines.append(f"- Edges: **{j['meta']['edge_count']}**")
        lines.append(f"- SCC cycles: **{len(j['cycles_scc'])}**")
        lines.append("")
        lines.append("## Layers")
        for k, v in j["layers"].items():
            lines.append(f"- `{k}`: {', '.join(v)}")
        lines.append("")
        lines.append("## High-Risk Edges")
        if not j["risk_edges"]:
            lines.append("- none")
        else:
            for e in j["risk_edges"]:
                lines.append(f"- `{e['src']} -> {e['dst']}` mode={e['mode']} condition=`{e['condition']}`")
        lines.append("")
        lines.append("## Cycles (SCC)")
        if not j["cycles_scc"]:
            lines.append("- none")
        else:
            for c in j["cycles_scc"]:
                lines.append(f"- {' -> '.join(c)}")
        return "\n".join(lines)


def build_kq_baseline() -> FlowAuditReport:
    r = FlowAuditReport()
    r.add_node("inbound", "L0", "Inbound", "critical")
    r.add_node("bridge", "L1", "inf-Bridge", "critical")
    r.add_node("verify", "L2", "KQ Verify", "critical")
    r.add_node("formal", "L3", "Formal Kernels", "normal")
    r.add_node("gate", "L4", "Loss/Gate", "critical")
    r.add_node("output", "L5", "Output", "critical")
    r.add_node("cleanup", "L6", "Ephemeral Cleanup", "critical")

    r.add_edge("inbound", "bridge", "required", weight=1.0)
    r.add_edge("bridge", "verify", "required", weight=1.0)
    r.add_edge("verify", "formal", "conditional", "formal inputs present", 0.7)
    r.add_edge("formal", "gate", "required", weight=0.9)
    r.add_edge("verify", "gate", "required", weight=1.0)
    r.add_edge("gate", "output", "required", weight=1.0)
    r.add_edge("output", "cleanup", "required", weight=1.0)

    # loops
    r.add_edge("output", "bridge", "optional", "goal loop", 0.4, "medium")
    r.add_edge("gate", "formal", "conditional", "re-check on caution", 0.3, "high")
    return r


def main():
    out_dir = Path("inf-Coding")
    out_dir.mkdir(parents=True, exist_ok=True)

    report = build_kq_baseline()
    j = report.to_json()
    md = report.to_markdown()

    (out_dir / "kq-flow-audit-report.json").write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "kq-flow-audit-report.md").write_text(md, encoding="utf-8")
    print("inf-Coding/kq-flow-audit-report.json")
    print("inf-Coding/kq-flow-audit-report.md")


if __name__ == "__main__":
    main()
