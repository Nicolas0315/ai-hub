"""
Generalization Engine — unified pipeline for unknown-domain handling.

Integrates Domain Bridge + Analogical Transfer + Cross-Domain Relations
into a single coherent generalization layer.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Three enhancements over KS31e base:
  1. Cross-Domain Relation Graph: concept→concept edges via ConceptNet
  2. Template Compositionality: compound sentence decomposition
  3. Verification Rule Strengthening: type-aware rule application
"""

import re
import urllib.request
import urllib.parse
import json as _json

try:
    from .domain_bridge import bridge_domain, _extract_domain_terms, _conceptnet_expand
    from .analogical_transfer import match_templates, run_analogical_transfer, _TEMPLATES
except ImportError:
    from domain_bridge import bridge_domain, _extract_domain_terms, _conceptnet_expand
    from analogical_transfer import match_templates, run_analogical_transfer, _TEMPLATES


# ─── Enhancement 1: Cross-Domain Relation Graph ────────────────────────────

def build_relation_graph(terms, max_edges_per_term=8):
    """Build a concept relation graph from domain terms.
    
    Unlike Domain Bridge (which expands individual concepts),
    this finds RELATIONS BETWEEN the input terms.
    """
    # Get ConceptNet edges for each term
    term_edges = {}
    all_concepts = set(t.lower() for t in terms)
    
    for term in terms[:2]:
        cn = _conceptnet_expand(term, max_edges=max_edges_per_term)
        edges = []
        for exp in cn.get("expansions", []):
            edges.append({
                "from": term,
                "to": exp["term"],
                "relation": exp["relation"],
                "weight": exp["weight"],
                "direction": exp["direction"],
            })
            all_concepts.add(exp["term"].lower())
        term_edges[term] = edges
    
    # Find cross-term connections: edges where 'to' matches another input term
    cross_links = []
    for term, edges in term_edges.items():
        for edge in edges:
            target = edge["to"].lower()
            for other_term in terms:
                if other_term.lower() != term.lower() and (
                    target == other_term.lower() or
                    other_term.lower() in target or
                    target in other_term.lower()
                ):
                    cross_links.append({
                        "from": term,
                        "to": other_term,
                        "via": edge["to"],
                        "relation": edge["relation"],
                        "weight": edge["weight"],
                    })
    
    return {
        "terms": terms,
        "total_edges": sum(len(e) for e in term_edges.values()),
        "cross_links": cross_links,
        "cross_link_count": len(cross_links),
        "concepts_discovered": len(all_concepts),
    }


# ─── Enhancement 2: Template Compositionality ──────────────────────────────

# Compound sentence splitters
_COMPOUND_SPLITTERS = [
    re.compile(r'(.+?)\s*,\s*which\s+(.+)', re.I),
    re.compile(r'(.+?)\s*,\s*(?:and|but)\s+(?:this|it|that)\s+(.+)', re.I),
    re.compile(r'(.+?)\s*;\s*(.+)', re.I),
    re.compile(r'(.+?)\s*,\s*(?:thereby|thus|hence)\s+(.+)', re.I),
    re.compile(r'(.+?)\s*,\s*(?:leading to|resulting in|causing)\s+(.+)', re.I),
]


def decompose_compound(text):
    """Split compound sentences into components for individual template matching."""
    components = []
    
    for splitter in _COMPOUND_SPLITTERS:
        m = splitter.match(text)
        if m:
            parts = [g.strip().rstrip(".,;:") for g in m.groups() if g.strip()]
            components.extend(parts)
            break
    
    if not components:
        # Try splitting on common conjunctions
        parts = re.split(r'\s*(?:,\s*and\s+|;\s*|\.\s+)', text)
        components = [p.strip().rstrip(".,;:") for p in parts if len(p.strip()) > 10]
    
    if not components or (len(components) == 1 and components[0] == text):
        return [text]
    
    return components


def match_compound(text):
    """Match compound sentences by decomposing and matching each part."""
    components = decompose_compound(text)
    
    if len(components) <= 1:
        return match_templates(text), components
    
    all_matches = []
    for component in components:
        matches = match_templates(component)
        for m in matches:
            all_matches.append({
                "component": component,
                "template": m.template,
                "slots": m.slots,
                "confidence": m.confidence,
            })
    
    return all_matches, components


# ─── Enhancement 3: Verification Rule Strengthening ────────────────────────

def strengthen_verification(transfer_result, domain_result, relation_graph=None):
    """Strengthen verification by cross-referencing multiple sources.
    
    Uses proposition types from Domain Bridge to select verification strategy.
    """
    if not transfer_result.get("matched"):
        return {"strengthened": False, "reason": "no_template_match"}
    
    props = domain_result.get("propositions", [])
    
    # Group propositions by type
    props_by_type = {}
    for p in props:
        ptype = p.get("type", "unknown")
        if ptype not in props_by_type:
            props_by_type[ptype] = []
        props_by_type[ptype].append(p)
    
    strengthening_signals = []
    
    # Strategy 1: Taxonomy consistency (if classification template matched)
    best = transfer_result.get("best_template", "")
    if best == "classification" and "taxonomy" in props_by_type:
        tax_props = props_by_type["taxonomy"]
        slots = transfer_result["transfers"][0]["slots"] if transfer_result.get("transfers") else {}
        instance = slots.get("instance", "").lower()
        category = slots.get("category", "").lower()
        
        for tp in tax_props:
            if instance in tp["text"].lower() or category in tp["text"].lower():
                strengthening_signals.append({
                    "type": "taxonomy_confirmed",
                    "evidence": tp["text"][:80],
                    "boost": 0.15,
                })
    
    # Strategy 2: Causal support (if agent_action template matched)
    if best in ("agent_action_object_result", "prevention_inhibition") and "causal" in props_by_type:
        causal_props = props_by_type["causal"]
        if causal_props:
            strengthening_signals.append({
                "type": "causal_domain_support",
                "evidence": causal_props[0]["text"][:80],
                "boost": 0.12,
            })
    
    # Strategy 3: Cross-domain relation support
    if relation_graph and relation_graph.get("cross_links"):
        for link in relation_graph["cross_links"][:3]:
            strengthening_signals.append({
                "type": "cross_domain_link",
                "from": link["from"],
                "to": link["to"],
                "relation": link["relation"],
                "boost": 0.08,
            })
    
    # Strategy 4: Academic definition grounding
    if "academic_definition" in props_by_type:
        academic = props_by_type["academic_definition"]
        high_confidence = [p for p in academic if p.get("confidence", 0) > 0.5]
        if high_confidence:
            strengthening_signals.append({
                "type": "academic_grounding",
                "count": len(high_confidence),
                "boost": 0.10,
            })
    
    # Strategy 5: Property verification for comparisons
    if best == "comparison" and "property" in props_by_type:
        strengthening_signals.append({
            "type": "property_confirmed",
            "boost": 0.12,
        })
    
    # Calculate strengthened confidence
    base_confidence = transfer_result.get("transfer_confidence", 0.5)
    total_boost = sum(s["boost"] for s in strengthening_signals)
    strengthened_confidence = min(base_confidence + total_boost, 0.95)
    
    return {
        "strengthened": len(strengthening_signals) > 0,
        "signals": strengthening_signals,
        "signal_count": len(strengthening_signals),
        "base_confidence": base_confidence,
        "total_boost": round(total_boost, 3),
        "strengthened_confidence": round(strengthened_confidence, 3),
    }


# ─── Unified Generalization Pipeline ────────────────────────────────────────

def run_generalization(text, store=None):
    """Full generalization pipeline combining all three enhancements.
    
    Pipeline:
      1. Domain Bridge: concept expansion
      2. Relation Graph: cross-concept edges
      3. Compound Decomposition + Template Matching
      4. Analogical Transfer with domain knowledge
      5. Verification Strengthening
    
    Returns comprehensive generalization result.
    """
    # Step 1: Domain Bridge
    domain = bridge_domain(text, store=store)
    
    # Step 2: Relation Graph
    terms = _extract_domain_terms(text)
    rel_graph = build_relation_graph(terms)
    
    # Step 3: Compound decomposition
    compound_matches, components = match_compound(text)
    
    # Step 4: Analogical Transfer (with domain props)
    transfer = run_analogical_transfer(
        text,
        domain_propositions=domain.get("propositions", []),
        store=store,
    )
    
    # Step 5: Verification Strengthening
    strengthening = strengthen_verification(transfer, domain, rel_graph)
    
    # Combine into generalization score
    domain_score = 0.3 if domain.get("domain_detected") else 0.0
    transfer_score = transfer.get("transfer_confidence", 0.0)
    strength_score = strengthening.get("strengthened_confidence", transfer_score)
    compound_bonus = 0.05 * max(0, len(components) - 1)  # bonus for compound handling
    relation_bonus = 0.03 * min(rel_graph.get("cross_link_count", 0), 3)  # cap at 3
    
    generalization_score = min(
        0.3 * domain_score + 0.4 * strength_score + 0.2 * transfer_score + compound_bonus + relation_bonus,
        0.95
    )
    
    result = {
        "text": text[:100],
        "domain": {
            "detected": domain.get("domain_detected", False),
            "terms": domain.get("terms", []),
            "enrichment_count": domain.get("enrichment_count", 0),
        },
        "relation_graph": {
            "cross_links": rel_graph.get("cross_link_count", 0),
            "concepts": rel_graph.get("concepts_discovered", 0),
        },
        "compound": {
            "components": len(components),
            "is_compound": len(components) > 1,
        },
        "transfer": {
            "matched": transfer.get("matched", False),
            "template": transfer.get("best_template"),
            "analog": transfer.get("best_analog"),
            "confidence": transfer.get("transfer_confidence", 0.0),
        },
        "strengthening": {
            "signals": strengthening.get("signal_count", 0),
            "boost": strengthening.get("total_boost", 0),
            "confidence": strengthening.get("strengthened_confidence", 0),
        },
        "generalization_score": round(generalization_score, 3),
    }
    
    if store:
        store.write("generalization_engine", result)
    
    return result
