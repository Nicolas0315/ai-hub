"""Parser for extracting JSON-DAG representations from free text."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

NodeType = Literal["claim", "concept", "equation"]


@dataclass(slots=True)
class DAGNode:
    """Node in HTLF structured representation."""

    id: str
    node_type: NodeType
    text: str


@dataclass(slots=True)
class DAGEdge:
    """Directed edge in HTLF structured representation."""

    source: str
    target: str
    relation: str


@dataclass(slots=True)
class DAG:
    """JSON-serializable DAG container."""

    nodes: list[DAGNode]
    edges: list[DAGEdge]

    def to_dict(self) -> dict[str, Any]:
        """Convert DAG to JSON-compatible dictionary."""
        return {
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
        }


PROMPT_TEMPLATE = """You are a strict information extraction engine.

Task:
Extract a directed acyclic graph (DAG) from the given text.

Output JSON schema:
{
  "nodes": [{"id": "n1", "node_type": "claim|concept|equation", "text": "..."}],
  "edges": [{"source": "n1", "target": "n2", "relation": "supports|depends_on|causes|defines|contrasts|instantiates"}]
}

Rules:
1) Keep 5-30 important nodes only.
2) node_type=equation only for mathematical symbols/equations.
3) Ensure edges are acyclic and reference existing IDs.
4) Output JSON only. No markdown.

Text:
---
{input_text}
---
"""


def _is_equation_like(text: str) -> bool:
    return bool(re.search(r"[=<>∀∃Σ∫]|\b(omega|lambda|sigma|delta|epsilon|SNR|GDT)\b", text, re.IGNORECASE))


def _heuristic_extract(text: str, max_nodes: int = 20) -> DAG:
    """Fallback parser when API access is unavailable."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", text) if s.strip()]
    if not sentences:
        sentences = [text[:200].strip()] if text.strip() else ["(empty)"]

    selected = sentences[: max(5, min(max_nodes, len(sentences)))]
    nodes: list[DAGNode] = []
    for idx, sentence in enumerate(selected, 1):
        node_type: NodeType = "equation" if _is_equation_like(sentence) else "claim"
        nodes.append(DAGNode(id=f"n{idx}", node_type=node_type, text=sentence[:400]))

    edges: list[DAGEdge] = []
    for idx in range(1, len(nodes)):
        relation = "supports"
        prev_txt = nodes[idx - 1].text.lower()
        cur_txt = nodes[idx].text.lower()
        if any(k in cur_txt for k in ["because", "therefore", "thus", "hence", "なので", "したがって"]):
            relation = "causes"
        elif any(k in cur_txt for k in ["define", "means", "とは", "定義"]):
            relation = "defines"
        elif any(k in cur_txt for k in ["however", "but", "一方", "しかし"]):
            relation = "contrasts"
        elif "if" in prev_txt or "when" in prev_txt:
            relation = "depends_on"
        edges.append(DAGEdge(source=nodes[idx - 1].id, target=nodes[idx].id, relation=relation))

    return DAG(nodes=nodes, edges=edges)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract first JSON object from model output."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def _dag_from_dict(payload: dict[str, Any]) -> DAG:
    nodes = [
        DAGNode(
            id=str(node["id"]),
            node_type=node.get("node_type", "claim"),
            text=str(node.get("text", "")),
        )
        for node in payload.get("nodes", [])
    ]
    edges = [
        DAGEdge(
            source=str(edge["source"]),
            target=str(edge["target"]),
            relation=str(edge.get("relation", "supports")),
        )
        for edge in payload.get("edges", [])
    ]
    return DAG(nodes=nodes, edges=edges)


def extract_dag(text: str, model: str = "gpt-4o-mini", use_mock: bool = False) -> DAG:
    """Extract DAG using OpenAI API when available, otherwise fallback heuristic mode."""
    api_key = os.getenv("OPENAI_API_KEY")
    if use_mock or not api_key:
        return _heuristic_extract(text)

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        prompt = PROMPT_TEMPLATE.format(input_text=text[:18000])
        response = client.responses.create(
            model=model,
            temperature=0,
            input=prompt,
        )
        output_text = response.output_text
        payload = _extract_json_object(output_text)
        return _dag_from_dict(payload)
    except Exception:
        return _heuristic_extract(text)


def get_manual_prompt(text: str) -> str:
    """Return a manually runnable prompt template for offline extraction."""
    return PROMPT_TEMPLATE.format(input_text=text)
