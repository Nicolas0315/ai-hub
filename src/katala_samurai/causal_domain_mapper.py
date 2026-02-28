"""
KS33b #6: Causal Domain Mapper — maps Domain Bridge concepts directly to L5 DAG nodes.

Converts domain_bridge propositions into causal graph nodes/edges
that L5 CausalVerifier can use directly.

Improves DAG construction accuracy for unknown domains.
"""

import re

# No external imports needed — standalone module


def map_propositions_to_dag(propositions):
    """Convert Domain Bridge propositions to causal DAG nodes and edges.
    
    Proposition types → DAG elements:
      taxonomy → node attributes (is-a relationships)
      causal → directed edges
      property → node properties
      association → undirected edges
      academic_definition → enriched node labels
    """
    nodes = set()
    edges = []
    node_attrs = {}
    
    for prop in propositions:
        ptype = prop.get("type", "unknown")
        text = prop.get("text", "")
        
        if ptype == "taxonomy":
            # "X is a Y" → X node with category=Y
            m = re.match(r'(\w+(?:\s+\w+)?)\s+(?:is\s+a|are)\s+(.+)', text, re.I)
            if m:
                child, parent = m.group(1).strip(), m.group(2).strip()[:30]
                nodes.add(child)
                nodes.add(parent)
                edges.append({"from": child, "to": parent, "type": "is_a"})
                node_attrs[child] = {"category": parent}
        
        elif ptype == "causal":
            # "X causes Y" → X→Y directed edge
            m = re.search(r'(\w+(?:\s+\w+){0,2})\s+(?:causes?|leads?\s+to|results?\s+in|produces?)\s+(.+)', text, re.I)
            if m:
                cause, effect = m.group(1).strip(), m.group(2).strip()[:30]
                nodes.add(cause)
                nodes.add(effect)
                edges.append({"from": cause, "to": effect, "type": "causes"})
        
        elif ptype == "association":
            m = re.search(r'(\w+(?:\s+\w+)?)\s+.*?(\w+(?:\s+\w+)?)', text, re.I)
            if m:
                a, b = m.group(1).strip(), m.group(2).strip()
                if a != b and len(a) > 2 and len(b) > 2:
                    nodes.add(a)
                    nodes.add(b)
                    edges.append({"from": a, "to": b, "type": "associated"})
        
        elif ptype == "academic_definition":
            # Extract key concept and add as enriched node
            parts = text.split(":", 1)
            if len(parts) == 2:
                concept = parts[0].strip()
                definition = parts[1].strip()[:80]
                nodes.add(concept)
                node_attrs[concept] = {
                    "definition": definition,
                    "source": prop.get("source", "openalex"),
                }
    
    return {
        "nodes": list(nodes),
        "node_count": len(nodes),
        "edges": edges,
        "edge_count": len(edges),
        "node_attrs": node_attrs,
        "dag_ready": len(nodes) >= 2 and len(edges) >= 1,
    }


def enrich_causal_dag(existing_dag_result, domain_mapping):
    """Merge domain-mapped nodes/edges into existing L5 causal DAG results."""
    merged_nodes = set(existing_dag_result.get("nodes", []))
    merged_edges = list(existing_dag_result.get("edges", []))
    
    for node in domain_mapping.get("nodes", []):
        merged_nodes.add(node)
    
    for edge in domain_mapping.get("edges", []):
        merged_edges.append(edge)
    
    return {
        "nodes": list(merged_nodes),
        "node_count": len(merged_nodes),
        "edges": merged_edges,
        "edge_count": len(merged_edges),
        "domain_enriched": True,
        "original_nodes": len(existing_dag_result.get("nodes", [])),
        "added_nodes": len(merged_nodes) - len(existing_dag_result.get("nodes", [])),
    }
