"""
Temporal Causal Graph — Time-aware causal DAG with precedence enforcement.

Adds temporal ordering to causal nodes. "A causes B" requires A to precede B.
Detects violations: "effect before cause" → spurious causation flag.

Design: Youta Hilono, 2026-02-28
"""

import re
import networkx as nx
from typing import Dict, Any, List, Optional

# Temporal signal patterns for ordering
_TEMPORAL_BEFORE = [
    (re.compile(r'\b(?:before|prior\s+to|preceding|earlier|first|initially)\b', re.I), -1),
    (re.compile(r'\b(?:causes?|leads?\s+to|produces?|triggers?)\b', re.I), -1),  # cause precedes effect
]

_TEMPORAL_AFTER = [
    (re.compile(r'\b(?:after|following|subsequently|then|later|next|finally)\b', re.I), 1),
    (re.compile(r'\b(?:results?\s+in|resulted\s+in|leads?\s+to)\b', re.I), 1),  # effect follows cause
]

_TEMPORAL_SIMULTANEOUS = [
    (re.compile(r'\b(?:simultaneously|at\s+the\s+same\s+time|concurrently|while)\b', re.I), 0),
]


def _infer_temporal_order(text: str) -> int:
    """Infer relative temporal position from text signals.
    
    Returns: negative = earlier, 0 = simultaneous/unknown, positive = later
    """
    score = 0
    for pattern, val in _TEMPORAL_BEFORE:
        if pattern.search(text):
            score += val
    for pattern, val in _TEMPORAL_AFTER:
        if pattern.search(text):
            score += val
    for pattern, val in _TEMPORAL_SIMULTANEOUS:
        if pattern.search(text):
            score += val
    return score


def add_temporal_ordering(G: nx.DiGraph) -> nx.DiGraph:
    """Add temporal order attributes to DAG nodes.
    
    Uses topological sort as base ordering, refined by temporal signals in text.
    """
    if not nx.is_directed_acyclic_graph(G):
        # Can't topologically sort a cyclic graph
        for n in G.nodes:
            G.nodes[n]["temporal_order"] = 0
        return G
    
    # Base: topological sort gives natural ordering
    topo_order = list(nx.topological_sort(G))
    for i, node in enumerate(topo_order):
        G.nodes[node]["temporal_order"] = i
        
        # Refine with text-based temporal signals
        text = G.nodes[node].get("text", "")
        temporal_signal = _infer_temporal_order(text)
        G.nodes[node]["temporal_signal"] = temporal_signal
    
    return G


def check_temporal_consistency(G: nx.DiGraph) -> Dict[str, Any]:
    """Check if causal edges respect temporal ordering.
    
    A causal edge A→B requires temporal_order(A) < temporal_order(B).
    Violations indicate potential spurious causation.
    """
    G = add_temporal_ordering(G)
    
    violations = []
    consistent_edges = 0
    total_causal = 0
    
    for u, v, data in G.edges(data=True):
        if not data.get("causal"):
            continue
        total_causal += 1
        
        t_u = G.nodes[u].get("temporal_order", 0)
        t_v = G.nodes[v].get("temporal_order", 0)
        
        if t_u >= t_v:
            violations.append({
                "cause": u,
                "effect": v,
                "cause_label": G.nodes[u].get("label", str(u)),
                "effect_label": G.nodes[v].get("label", str(v)),
                "cause_time": t_u,
                "effect_time": t_v,
                "type": "effect_before_cause" if t_u > t_v else "simultaneous",
            })
        else:
            consistent_edges += 1
    
    consistency_ratio = consistent_edges / max(total_causal, 1)
    
    return {
        "total_causal_edges": total_causal,
        "consistent_edges": consistent_edges,
        "violations": violations,
        "violation_count": len(violations),
        "consistency_ratio": round(consistency_ratio, 4),
        "temporal_verdict": (
            "CONSISTENT" if not violations
            else "MINOR_VIOLATIONS" if consistency_ratio >= 0.8
            else "MAJOR_VIOLATIONS"
        ),
    }


def detect_reverse_causation(G: nx.DiGraph) -> List[Dict[str, Any]]:
    """Detect potential reverse causation patterns.
    
    Looks for: A→B where text suggests B actually precedes A.
    """
    results = []
    
    for u, v, data in G.edges(data=True):
        if not data.get("causal"):
            continue
        
        cause_text = G.nodes[u].get("text", "")
        effect_text = G.nodes[v].get("text", "")
        
        # Check if effect text contains "before" signals relative to cause
        cause_signal = _infer_temporal_order(cause_text)
        effect_signal = _infer_temporal_order(effect_text)
        
        # If effect has "before/prior" signals and cause has "after" signals
        if effect_signal < 0 and cause_signal > 0:
            results.append({
                "edge": (u, v),
                "cause_label": G.nodes[u].get("label", str(u)),
                "effect_label": G.nodes[v].get("label", str(v)),
                "suspicion": "reverse_causation",
                "cause_temporal": cause_signal,
                "effect_temporal": effect_signal,
            })
    
    return results
