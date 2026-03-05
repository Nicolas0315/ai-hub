#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from katala_samurai.inf_bridge import run_inf_bridge


def to_markdown(rep: dict) -> str:
    lines = ["# FlowIR Audit Report (inf-Bridge)", ""]
    lines.append(f"- Nodes: **{len(rep.get('nodes', []))}**")
    lines.append(f"- Edges: **{len(rep.get('edges', []))}**")
    lines.append(f"- SCC cycles: **{len(rep.get('cycles_scc', []))}**")
    lines.append("")
    lines.append("## Layers")
    for k, v in (rep.get("layers") or {}).items():
        lines.append(f"- `{k}`: {', '.join(v)}")
    lines.append("")
    lines.append("## High-Risk Edges")
    rs = rep.get("risk_edges") or []
    if not rs:
        lines.append("- none")
    else:
        for e in rs:
            lines.append(f"- `{e['src']} -> {e['dst']}` mode={e.get('mode')} cond=`{e.get('condition','')}`")
    lines.append("")
    lines.append("## Cycles (SCC)")
    for c in (rep.get("cycles_scc") or []):
        lines.append(f"- {' -> '.join(c)}")
    return "\n".join(lines)


def main():
    payload = run_inf_bridge("generate flow audit report")
    rep = payload.get("flow_audit_report") or {}

    out_dir = Path("inf-Coding")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "kq-flow-audit-report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "kq-flow-audit-report.md").write_text(to_markdown(rep), encoding="utf-8")
    print("inf-Coding/kq-flow-audit-report.json")
    print("inf-Coding/kq-flow-audit-report.md")


if __name__ == "__main__":
    main()
