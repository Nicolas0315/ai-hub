#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont


@dataclass
class Edge:
    src: str
    dst: str
    weight: float = 1.0


@dataclass
class FlowIR:
    nodes: Dict[str, dict] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)

    def add_node(self, node_id: str, layer: str, label: str):
        self.nodes[node_id] = {"layer": layer, "label": label}

    def add_edge(self, src: str, dst: str, weight: float = 1.0):
        self.edges.append(Edge(src, dst, weight))


def tarjan_scc(nodes: List[str], edges: List[Tuple[str, str]]) -> List[List[str]]:
    graph = defaultdict(list)
    for a, b in edges:
        graph[a].append(b)

    index = 0
    stack = []
    onstack = set()
    idx = {}
    low = {}
    out = []

    def strongconnect(v: str):
        nonlocal index
        idx[v] = index
        low[v] = index
        index += 1
        stack.append(v)
        onstack.add(v)

        for w in graph[v]:
            if w not in idx:
                strongconnect(w)
                low[v] = min(low[v], low[w])
            elif w in onstack:
                low[v] = min(low[v], idx[w])

        if low[v] == idx[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack.remove(w)
                comp.append(w)
                if w == v:
                    break
            out.append(comp)

    for n in nodes:
        if n not in idx:
            strongconnect(n)
    return out


def build_kq_flowir() -> FlowIR:
    f = FlowIR()
    # layer names for auto fold
    f.add_node("inbound", "L0_inbound", "Inbound")
    f.add_node("bridge_collect", "L1_bridge", "inf-Bridge Collect")
    f.add_node("bridge_detect", "L1_bridge", "Pattern Detect")
    f.add_node("bridge_plan", "L1_bridge", "Route A/B Plan")
    f.add_node("verify_core", "L2_kq", "KQ Verify Core")
    f.add_node("spm_spml", "L2_kq", "SPM->SPML")
    f.add_node("formal", "L3_formal", "Formal Kernels")
    f.add_node("zfc_hol", "L3_formal", "ZFC/HOL")
    f.add_node("ctl_mu", "L3_formal", "CTL/mu-lite")
    f.add_node("gate", "L4_gate", "translation_loss_gate")
    f.add_node("claimir", "L4_gate", "ClaimIR v2")
    f.add_node("output", "L5_output", "Output + ks47 compat")
    f.add_node("cleanup", "L5_output", "Ephemeral Cleanup")

    # weighted edges (runtime-frequency-inspired heuristics)
    f.add_edge("inbound", "bridge_collect", 1.0)
    f.add_edge("bridge_collect", "bridge_detect", 0.95)
    f.add_edge("bridge_detect", "bridge_plan", 0.9)
    f.add_edge("bridge_plan", "verify_core", 1.0)
    f.add_edge("verify_core", "spm_spml", 0.98)
    f.add_edge("verify_core", "formal", 0.92)
    f.add_edge("formal", "zfc_hol", 0.45)
    f.add_edge("formal", "ctl_mu", 0.35)
    f.add_edge("zfc_hol", "gate", 0.55)
    f.add_edge("ctl_mu", "gate", 0.38)
    f.add_edge("spm_spml", "claimir", 0.95)
    f.add_edge("claimir", "gate", 0.9)
    f.add_edge("gate", "output", 1.0)
    f.add_edge("output", "cleanup", 1.0)

    # explicit cycles
    f.add_edge("output", "bridge_plan", 0.42)
    f.add_edge("gate", "formal", 0.3)
    f.add_edge("formal", "claimir", 0.5)
    f.add_edge("claimir", "formal", 0.33)

    return f


def fold_layers(flow: FlowIR):
    layers = defaultdict(list)
    for nid, meta in flow.nodes.items():
        layers[meta["layer"]].append(nid)
    return dict(layers)


def render_flow(flow: FlowIR, out_path: str):
    W, H = 2200, 1400
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    layers = fold_layers(flow)
    ordered_layers = sorted(layers.keys())
    layer_x = {ly: 80 + i * 380 for i, ly in enumerate(ordered_layers)}
    pos = {}

    # layer auto-fold view (grouped boxes)
    for ly in ordered_layers:
        nids = layers[ly]
        x = layer_x[ly]
        y = 110
        h = 70 + 22 * len(nids)
        d.rounded_rectangle([x, y, x + 320, y + h], radius=12, outline="black", width=2, fill="#f3f7ff")
        d.text((x + 10, y + 8), ly, fill="black", font=font)
        for i, nid in enumerate(nids):
            d.text((x + 14, y + 32 + i * 18), f"- {flow.nodes[nid]['label']}", fill="black", font=font)
            pos[nid] = (x + 160, y + h + 80 + i * 40)

    # draw nodes in detail band
    for nid, (cx, cy) in pos.items():
        w, h = 220, 32
        x1, y1 = cx - w // 2, cy - h // 2
        x2, y2 = cx + w // 2, cy + h // 2
        d.rounded_rectangle([x1, y1, x2, y2], radius=10, outline="black", width=2, fill="#fffde7")
        d.text((x1 + 8, y1 + 10), flow.nodes[nid]["label"][:28], fill="black", font=font)

    # edges weighted
    for e in flow.edges:
        if e.src not in pos or e.dst not in pos:
            continue
        x1, y1 = pos[e.src]
        x2, y2 = pos[e.dst]
        color = "#1e88e5" if e.weight >= 0.8 else ("#43a047" if e.weight >= 0.5 else "#e53935")
        width = 1 + int(e.weight * 5)
        d.line([x1, y1, x2, y2], fill=color, width=width)
        d.text(((x1 + x2) // 2, (y1 + y2) // 2), f"{e.weight:.2f}", fill=color, font=font)

    # SCC cycles annotation
    sccs = tarjan_scc(list(flow.nodes.keys()), [(e.src, e.dst) for e in flow.edges])
    cyc = [c for c in sccs if len(c) > 1]
    d.text((80, 20), "KQ FlowIR (r41) / SCC cycles / weighted edges / auto-folded layers", fill="black", font=font)
    d.text((80, 50), f"Detected SCC cycles: {len(cyc)} -> {cyc}", fill="#c62828", font=font)

    img.save(out_path)


def main():
    flow = build_kq_flowir()
    render_flow(flow, "kq-flowir-r41-cycles.png")
    print("kq-flowir-r41-cycles.png")


if __name__ == "__main__":
    main()
