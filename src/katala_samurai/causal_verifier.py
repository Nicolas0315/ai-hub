"""
Layer 5: Causal Verifier — formal causal reasoning via DAG + do-calculus.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma
References:
  - Pearl (1995): do-calculus completeness
  - DoVerifier (arXiv:2601.21210, 2025): BFS derivation graph
  - Causal-CoT (OpenReview, 2024): CoT → causal graph

Architecture:
  Step 1: A06 chain decomposition → causal DAG construction
  Step 2: DAG structural checks (cycle, d-separation, backdoor)
  Step 3: do-calculus identifiability (3 rules, BFS)
  Step 4: Counterfactual check (remove cause, check if effect persists)

Principles:
  - Non-LLM: networkx + regex + symbolic (no LLM dependency)
  - No accumulation: DAG built fresh each run
  - Integrates with L3 (A06) and L4 (M1 counter-factual)
"""

import re
import networkx as nx
from collections import deque
from itertools import combinations


# ─── Step 1: Causal DAG Construction from A06 output ────────────────────────

# Connector type → causal edge semantics
_CONNECTOR_TO_EDGE = {
    "cause":       {"type": "direct",      "causal": True},
    "implication": {"type": "direct",      "causal": True},
    "condition":   {"type": "conditional", "causal": True},
    "conclusion":  {"type": "direct",      "causal": True},
    "temporal":    {"type": "temporal",    "causal": None},  # maybe causal
    "addition":    {"type": "none",        "causal": False},
    "contrast":    {"type": "none",        "causal": False},
    "concession":  {"type": "none",        "causal": False},
}

# Additional causal signal patterns (applied to step text)
_CAUSAL_SIGNALS = [
    (re.compile(r'\b(?:causes?|caused|causing)\b', re.I), "direct"),
    (re.compile(r'\b(?:leads?\s+to|led\s+to|leading\s+to)\b', re.I), "direct"),
    (re.compile(r'\b(?:results?\s+in|resulted\s+in)\b', re.I), "direct"),
    (re.compile(r'\b(?:produces?|produced|producing)\b', re.I), "direct"),
    (re.compile(r'\b(?:prevents?|prevented|preventing)\b', re.I), "inhibit"),
    (re.compile(r'\b(?:enables?|enabled|enabling)\b', re.I), "enabling"),
    (re.compile(r'\b(?:increases?|decreased?|reduces?)\b', re.I), "modulating"),
    (re.compile(r'\b(?:if|when|whenever)\b', re.I), "conditional"),
    (re.compile(r'\b(?:because|since|due\s+to|owing\s+to)\b', re.I), "direct"),
    (re.compile(r'\b(?:therefore|thus|hence|consequently)\b', re.I), "conclusion"),
]


def _extract_node_label(text, max_words=6):
    """Extract a short label from step text for DAG node."""
    # Remove connectors and get core content
    cleaned = re.sub(r'\b(therefore|because|since|thus|hence|if|then|so|consequently)\b', '', text, flags=re.I)
    words = cleaned.split()
    # Take first N meaningful words
    stops = {"the", "a", "an", "is", "are", "was", "were", "it", "this", "that"}
    content = [w for w in words if w.lower().strip(".,;:") not in stops and len(w) > 1]
    label = " ".join(content[:max_words]).strip(".,;: ")
    return label or text[:30]


def build_causal_dag(chain_result):
    """Build a causal DAG from A06 chain decomposition output.
    
    Args:
        chain_result: output from a06_chain_decompose() with steps and dependency_edges
    
    Returns:
        nx.DiGraph with causal edges and metadata
    """
    G = nx.DiGraph()
    steps = chain_result.get("steps", [])
    dep_edges = chain_result.get("dependency_edges", [])
    
    if not steps:
        return G
    
    # Add nodes
    for i, step in enumerate(steps):
        text = step.get("text", step) if isinstance(step, dict) else str(step)
        label = _extract_node_label(text)
        # Also detect causal signals in the step text itself
        step_signals = []
        for pattern, signal_type in _CAUSAL_SIGNALS:
            if pattern.search(text):
                step_signals.append(signal_type)
        G.add_node(i, text=text, label=label, step_index=i, signals=step_signals)
    
    # Add edges from dependency_edges
    for edge in dep_edges:
        src = edge.get("from", 0)
        dst = edge.get("to", 0)
        relation = edge.get("relation", "unknown")
        
        edge_info = _CONNECTOR_TO_EDGE.get(relation, {"type": "unknown", "causal": None})
        
        # Check both source and target text for causal signals
        src_text = steps[src].get("text", "") if src < len(steps) and isinstance(steps[src], dict) else ""
        dst_text = steps[dst].get("text", "") if dst < len(steps) and isinstance(steps[dst], dict) else ""
        combined_text = src_text + " " + dst_text
        
        detected_signals = []
        for pattern, signal_type in _CAUSAL_SIGNALS:
            if pattern.search(combined_text):
                detected_signals.append(signal_type)
        
        is_causal = edge_info["causal"]
        if is_causal is None and detected_signals:
            is_causal = any(s in ("direct", "conclusion", "conditional") for s in detected_signals)
        # If still None but we have signals, lean toward causal
        if is_causal is None and detected_signals:
            is_causal = True
        
        G.add_edge(src, dst,
                    connector=relation,
                    edge_type=edge_info["type"],
                    causal=is_causal,
                    signals=detected_signals)
    
    # Fallback: if no dependency_edges, use sequential step order
    if not dep_edges and len(steps) > 1:
        for i in range(len(steps) - 1):
            text = steps[i + 1].get("text", "") if isinstance(steps[i + 1], dict) else str(steps[i + 1])
            conn_type = steps[i].get("connector_type", "unknown") if isinstance(steps[i], dict) else "unknown"
            edge_info = _CONNECTOR_TO_EDGE.get(conn_type, {"type": "unknown", "causal": None})
            
            detected_signals = []
            for pattern, signal_type in _CAUSAL_SIGNALS:
                if pattern.search(text):
                    detected_signals.append(signal_type)
            
            is_causal = edge_info["causal"]
            if is_causal is None and detected_signals:
                is_causal = any(s in ("direct", "conclusion") for s in detected_signals)
            
            G.add_edge(i, i + 1,
                        connector=conn_type,
                        edge_type=edge_info["type"],
                        causal=is_causal,
                        signals=detected_signals)
    
    return G


# ─── Step 2: DAG Structural Checks ──────────────────────────────────────────

def check_dag_structure(G):
    """Structural analysis of the causal DAG.
    
    Returns:
        dict with cycle detection, d-separation info, backdoor candidates
    """
    result = {
        "is_dag": nx.is_directed_acyclic_graph(G),
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "causal_edges": 0,
        "non_causal_edges": 0,
        "temporal_edges": 0,
        "cycles": [],
        "roots": [],
        "leaves": [],
        "confounders": [],
        "backdoor_paths": [],
    }
    
    if not G.nodes:
        return result
    
    # Count edge types
    for u, v, data in G.edges(data=True):
        if data.get("causal") is True:
            result["causal_edges"] += 1
        elif data.get("causal") is False:
            result["non_causal_edges"] += 1
        else:
            result["temporal_edges"] += 1
    
    # Cycle detection
    if not result["is_dag"]:
        try:
            cycle = nx.find_cycle(G)
            result["cycles"] = [(u, v) for u, v, _ in cycle]
        except nx.NetworkXNoCycle:
            pass
        return result  # Can't do d-separation on cyclic graph
    
    # Roots and leaves
    result["roots"] = [n for n in G.nodes if G.in_degree(n) == 0]
    result["leaves"] = [n for n in G.nodes if G.out_degree(n) == 0]
    
    # Confounder detection: nodes with out-degree ≥ 2 (common causes)
    for n in G.nodes:
        if G.out_degree(n) >= 2:
            children = list(G.successors(n))
            result["confounders"].append({
                "node": n,
                "label": G.nodes[n].get("label", ""),
                "affects": children,
            })
    
    # Backdoor path detection (simplified)
    # For each causal edge A→B, check if there's a non-causal path A←...→B
    undirected = G.to_undirected()
    for u, v, data in G.edges(data=True):
        if data.get("causal"):
            # Remove direct edge temporarily
            undirected_copy = undirected.copy()
            undirected_copy.remove_edge(u, v)
            # Check if alternative path exists
            try:
                alt_path = nx.shortest_path(undirected_copy, u, v)
                if len(alt_path) > 2:  # Non-trivial alternative path
                    result["backdoor_paths"].append({
                        "from": u,
                        "to": v,
                        "backdoor": alt_path,
                    })
            except nx.NetworkXNoPath:
                pass
    
    return result


# ─── Step 3: d-Separation Check ─────────────────────────────────────────────

def d_separation(G, x, y, z=None):
    """Check if X and Y are d-separated given Z in DAG G.
    
    Uses the Bayes-Ball algorithm (Shachter 1998).
    
    Args:
        G: nx.DiGraph (must be DAG)
        x: source node
        y: target node  
        z: set of conditioning nodes (or None)
    
    Returns:
        bool: True if d-separated (conditionally independent)
    """
    if z is None:
        z = set()
    else:
        z = set(z)
    
    if not nx.is_directed_acyclic_graph(G):
        return None  # Can't determine
    
    # Use networkx d-separation if available
    try:
        return nx.d_separated(G, {x}, {y}, z)
    except (AttributeError, nx.NetworkXError):
        pass
    
    # Fallback: manual Bayes-Ball
    # Reachable via active trails
    visited = set()
    queue = deque([(x, "up")])  # (node, direction)
    
    while queue:
        node, direction = queue.popleft()
        if (node, direction) in visited:
            continue
        visited.add((node, direction))
        
        if node == y:
            return False  # Active trail found → not d-separated
        
        if direction == "up" and node not in z:
            # Visit parents (continue up)
            for parent in G.predecessors(node):
                queue.append((parent, "up"))
            # Visit children (go down)
            for child in G.successors(node):
                queue.append((child, "down"))
        
        elif direction == "down":
            if node not in z:
                # Visit children (continue down)
                for child in G.successors(node):
                    queue.append((child, "down"))
            # If conditioned: visit parents (explaining away)
            if node in z:
                for parent in G.predecessors(node):
                    queue.append((parent, "up"))
    
    return True  # No active trail → d-separated


# ─── Step 3b: do-Calculus Identifiability ────────────────────────────────────

def _mutilate_graph(G, intervention_nodes):
    """Remove all incoming edges to intervention nodes (graph surgery)."""
    G_mut = G.copy()
    for node in intervention_nodes:
        parents = list(G_mut.predecessors(node))
        for parent in parents:
            G_mut.remove_edge(parent, node)
    return G_mut


def check_identifiability(G, cause, effect):
    """Check if P(effect | do(cause)) is identifiable from observational data.
    
    Uses backdoor criterion (sufficient for most practical cases).
    Pearl's do-calculus is complete but BFS over all derivations is expensive;
    backdoor + front-door criteria cover the common cases.
    
    Args:
        G: causal DAG
        cause: cause node
        effect: effect node
    
    Returns:
        dict with identifiability result and adjustment set
    """
    if not nx.is_directed_acyclic_graph(G) or cause not in G or effect not in G:
        return {"identifiable": None, "reason": "invalid_graph_or_nodes"}
    
    # Check if there's a directed path from cause to effect
    has_causal_path = nx.has_path(G, cause, effect)
    if not has_causal_path:
        return {
            "identifiable": False,
            "reason": "no_causal_path",
            "detail": f"No directed path from {cause} to {effect}",
        }
    
    # Direct edge with no backdoor: trivially identifiable
    if G.has_edge(cause, effect):
        # Check if any node has paths to both cause and effect (confounder)
        has_confounder = False
        for n in G.nodes:
            if n == cause or n == effect:
                continue
            undirected = G.to_undirected()
            # Simple check: is there a path from n to cause NOT through effect?
            G_no_direct = G.copy()
            if G_no_direct.has_edge(cause, effect):
                G_no_direct.remove_edge(cause, effect)
            undirected_no = G_no_direct.to_undirected()
            try:
                if nx.has_path(undirected_no, n, cause) and nx.has_path(undirected_no, n, effect):
                    has_confounder = True
                    break
            except nx.NodeNotFound:
                pass
        
        if not has_confounder:
            return {
                "identifiable": True,
                "method": "direct_cause_no_confounders",
                "adjustment_set": [],
                "adjustment_labels": [],
            }
    
    # Backdoor criterion: find a set Z that blocks all backdoor paths
    # Z must not contain descendants of cause
    descendants_of_cause = nx.descendants(G, cause)
    non_descendants = set(G.nodes) - descendants_of_cause - {cause, effect}
    
    # Try all subsets of non-descendants (exponential but graph is small)
    for size in range(len(non_descendants) + 1):
        for z_set in combinations(non_descendants, size):
            z_set = set(z_set)
            # Check: Z blocks all backdoor paths (cause ⊥ effect | Z in mutilated graph)
            G_mut = _mutilate_graph(G, {cause})
            if d_separation(G_mut, cause, effect, z_set):
                # Additional check: Z doesn't contain descendants of cause
                if not z_set & descendants_of_cause:
                    return {
                        "identifiable": True,
                        "method": "backdoor_criterion",
                        "adjustment_set": list(z_set),
                        "adjustment_labels": [G.nodes[n].get("label", str(n)) for n in z_set],
                    }
    
    # Front-door criterion check
    # Find mediator M: cause → M → effect, no backdoor cause → M
    for mediator in G.nodes:
        if mediator == cause or mediator == effect:
            continue
        if G.has_edge(cause, mediator) and nx.has_path(G, mediator, effect):
            # Check: no backdoor path cause → mediator
            G_mut = _mutilate_graph(G, {cause})
            if d_separation(G_mut, cause, mediator, set()):
                return {
                    "identifiable": True,
                    "method": "front_door_criterion",
                    "mediator": mediator,
                    "mediator_label": G.nodes[mediator].get("label", str(mediator)),
                }
    
    return {
        "identifiable": None,
        "reason": "no_criterion_found",
        "detail": "Neither backdoor nor front-door criterion applicable. Full do-calculus BFS needed.",
    }


# ─── Step 4: Counterfactual Check ───────────────────────────────────────────

def counterfactual_check(G, cause, effect):
    """Check if removing the cause eliminates paths to the effect.
    
    'If A had not occurred, would B still occur?'
    → Remove A and all its outgoing edges → check if B is still reachable from any root.
    
    Args:
        G: causal DAG
        cause: the alleged cause node
        effect: the alleged effect node
    
    Returns:
        dict with necessity assessment
    """
    if cause not in G or effect not in G:
        return {"necessary": None, "reason": "nodes_not_in_graph"}
    
    # Remove cause node entirely
    G_removed = G.copy()
    G_removed.remove_node(cause)
    
    # Check if effect is still reachable from any root
    roots = [n for n in G_removed.nodes if G_removed.in_degree(n) == 0]
    
    effect_still_reachable = False
    alternative_paths = []
    
    if effect in G_removed:
        for root in roots:
            if nx.has_path(G_removed, root, effect):
                effect_still_reachable = True
                path = nx.shortest_path(G_removed, root, effect)
                alternative_paths.append({
                    "from": root,
                    "from_label": G.nodes[root].get("label", str(root)),
                    "path": path,
                    "path_labels": [G.nodes[n].get("label", str(n)) for n in path if n in G.nodes],
                })
    
    if not effect_still_reachable:
        necessity = "NECESSARY"
        detail = "Removing cause eliminates all paths to effect"
    else:
        necessity = "NOT_NECESSARY"
        detail = f"Effect reachable via {len(alternative_paths)} alternative path(s)"
    
    return {
        "necessary": necessity == "NECESSARY",
        "necessity": necessity,
        "detail": detail,
        "alternative_paths": alternative_paths,
    }


# ─── L5 Orchestrator ────────────────────────────────────────────────────────

def run_causal_verification(chain_result, store=None):
    """Full causal verification pipeline.
    
    Args:
        chain_result: output from a06_chain_decompose()
        store: StageStore for externalization
    
    Returns:
        dict with DAG, structural analysis, identifiability, counterfactual results
    """
    # Step 1: Build DAG
    G = build_causal_dag(chain_result)
    
    if G.number_of_nodes() < 2:
        result = {
            "dag_nodes": G.number_of_nodes(),
            "dag_edges": G.number_of_edges(),
            "causal_verdict": "INSUFFICIENT_STRUCTURE",
            "detail": "Need at least 2 nodes for causal analysis",
        }
        if store:
            store.write("L5_causal_verification", result)
        return result
    
    # Step 2: Structural checks
    structure = check_dag_structure(G)
    
    if not structure["is_dag"]:
        result = {
            "dag_nodes": structure["nodes"],
            "dag_edges": structure["edges"],
            "structure": structure,
            "causal_verdict": "CYCLIC_GRAPH",
            "detail": "Cyclic causal claims detected — logical inconsistency",
            "cycles": structure["cycles"],
        }
        if store:
            store.write("L5_causal_verification", result)
        return result
    
    # Step 3: Identifiability for each causal edge
    identifiability_results = []
    for u, v, data in G.edges(data=True):
        if data.get("causal"):
            ident = check_identifiability(G, u, v)
            ident["cause"] = u
            ident["effect"] = v
            ident["cause_label"] = G.nodes[u].get("label", str(u))
            ident["effect_label"] = G.nodes[v].get("label", str(v))
            identifiability_results.append(ident)
    
    # Step 4: Counterfactual for root→leaf pairs
    counterfactual_results = []
    roots = structure["roots"]
    leaves = structure["leaves"]
    for root in roots:
        for leaf in leaves:
            if root != leaf and nx.has_path(G, root, leaf):
                cf = counterfactual_check(G, root, leaf)
                cf["cause"] = root
                cf["effect"] = leaf
                cf["cause_label"] = G.nodes[root].get("label", str(root))
                cf["effect_label"] = G.nodes[leaf].get("label", str(leaf))
                counterfactual_results.append(cf)
    
    # Causal verdict
    all_identifiable = all(r.get("identifiable") for r in identifiability_results) if identifiability_results else False
    all_necessary = all(r.get("necessary") for r in counterfactual_results) if counterfactual_results else None
    has_confounders = len(structure["confounders"]) > 0
    has_backdoors = len(structure["backdoor_paths"]) > 0
    
    if not identifiability_results:
        causal_verdict = "NO_CAUSAL_CLAIMS"
        causal_confidence = 0.5
    elif all_identifiable and all_necessary and not has_backdoors:
        causal_verdict = "CAUSALLY_VERIFIED"
        causal_confidence = 0.95
    elif all_identifiable and not has_backdoors:
        causal_verdict = "CAUSALLY_SUPPORTED"
        causal_confidence = 0.80
    elif all_identifiable and has_backdoors:
        causal_verdict = "CONFOUNDED"
        causal_confidence = 0.60
    elif any(r.get("identifiable") for r in identifiability_results):
        causal_verdict = "PARTIALLY_CAUSAL"
        causal_confidence = 0.50
    else:
        causal_verdict = "CAUSALLY_UNVERIFIED"
        causal_confidence = 0.30
    
    result = {
        "dag_nodes": structure["nodes"],
        "dag_edges": structure["edges"],
        "causal_edges": structure["causal_edges"],
        "structure": {
            "is_dag": structure["is_dag"],
            "confounders": structure["confounders"],
            "backdoor_paths": structure["backdoor_paths"],
        },
        "identifiability": identifiability_results,
        "counterfactual": counterfactual_results,
        "causal_verdict": causal_verdict,
        "causal_confidence": causal_confidence,
    }
    
    if store:
        store.write("L5_causal_verification", result)
    
    return result
