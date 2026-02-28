"""
Multi-Step Intervention — Chain do-calculus for deep causal reasoning.

Current L5 only does single do(X) → observe(Y).
This adds multi-step: do(X) → do(Y) → observe(Z) chains.

Design: Youta Hilono, 2026-02-28
"""

import networkx as nx
from itertools import permutations
from typing import List, Dict, Any, Optional, Set


def _mutilate_graph(G: nx.DiGraph, intervention_nodes: Set[int]) -> nx.DiGraph:
    """Remove all incoming edges to intervention nodes."""
    G_mut = G.copy()
    for node in intervention_nodes:
        for parent in list(G_mut.predecessors(node)):
            G_mut.remove_edge(parent, node)
    return G_mut


def multi_step_intervene(
    G: nx.DiGraph,
    interventions: List[int],
    target: int,
) -> Dict[str, Any]:
    """Perform sequential do-calculus interventions.
    
    do(X1) → do(X2) → ... → observe(target)
    Each intervention removes incoming edges to that node (graph surgery).
    
    Args:
        G: Causal DAG
        interventions: Ordered list of intervention nodes
        target: Node to observe after interventions
    
    Returns:
        Dict with reachability, path analysis, and effect assessment
    """
    if not nx.is_directed_acyclic_graph(G):
        return {"error": "not_a_dag", "effect": None}
    
    # Apply sequential graph surgery
    G_mut = G.copy()
    surgery_log = []
    
    for node in interventions:
        if node not in G_mut:
            continue
        removed = list(G_mut.predecessors(node))
        for parent in removed:
            G_mut.remove_edge(parent, node)
        surgery_log.append({
            "do": node,
            "label": G.nodes[node].get("label", str(node)),
            "edges_removed": len(removed),
            "removed_from": [G.nodes[p].get("label", str(p)) for p in removed if p in G.nodes],
        })
    
    # Check if target is still reachable from last intervention
    reachable = False
    paths = []
    last_intervention = interventions[-1] if interventions else None
    
    if last_intervention is not None and target in G_mut and last_intervention in G_mut:
        reachable = nx.has_path(G_mut, last_intervention, target)
        if reachable:
            for path in nx.all_simple_paths(G_mut, last_intervention, target):
                paths.append({
                    "nodes": path,
                    "labels": [G.nodes[n].get("label", str(n)) for n in path if n in G.nodes],
                    "length": len(path),
                })
                if len(paths) >= 5:
                    break
    
    # Check from all roots too
    roots = [n for n in G_mut.nodes if G_mut.in_degree(n) == 0]
    root_paths = []
    for root in roots:
        if target in G_mut and nx.has_path(G_mut, root, target):
            root_paths.append(root)
    
    return {
        "interventions": surgery_log,
        "target": target,
        "target_label": G.nodes[target].get("label", str(target)) if target in G.nodes else str(target),
        "effect_persists": reachable,
        "causal_paths_after_surgery": paths,
        "roots_still_reaching_target": len(root_paths),
        "total_nodes_after": G_mut.number_of_nodes(),
        "total_edges_after": G_mut.number_of_edges(),
    }


def enumerate_intervention_chains(
    G: nx.DiGraph,
    cause: int,
    effect: int,
    max_chain_length: int = 3,
) -> List[Dict[str, Any]]:
    """Generate and evaluate all intervention chains from cause to effect.
    
    Finds intermediate nodes on causal paths, then tests all orderings
    of do() interventions up to max_chain_length.
    """
    if cause not in G or effect not in G:
        return []
    
    # Find all nodes on causal paths
    intermediates = set()
    try:
        for path in nx.all_simple_paths(G, cause, effect):
            for node in path[1:-1]:  # exclude cause and effect
                intermediates.add(node)
    except nx.NetworkXNoPath:
        return []
    
    results = []
    
    # Single intervention: do(cause)
    r = multi_step_intervene(G, [cause], effect)
    r["chain"] = [cause]
    r["chain_labels"] = [G.nodes[cause].get("label", str(cause))]
    results.append(r)
    
    # Multi-step: do(cause) → do(intermediate) → observe(effect)
    for length in range(1, min(max_chain_length, len(intermediates) + 1)):
        for combo in permutations(intermediates, length):
            chain = [cause] + list(combo)
            r = multi_step_intervene(G, chain, effect)
            r["chain"] = chain
            r["chain_labels"] = [G.nodes[n].get("label", str(n)) for n in chain if n in G.nodes]
            results.append(r)
            if len(results) >= 20:  # cap
                return results
    
    return results
