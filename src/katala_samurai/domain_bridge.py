"""
Domain Bridge — extends L1 to handle unknown domains via external knowledge.

Bridges the gap between unknown-domain input and L1's formal solvers by
expanding concepts through ConceptNet, OpenAlex, and Firecrawl.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Principles:
  - Non-LLM: API + text matching
  - No accumulation: fresh expansion each run
  - Plugs into L1: outputs structured propositions for S01-S28
"""

import re
import urllib.request
import urllib.parse
import json as _json


# ─── ConceptNet Expansion ───────────────────────────────────────────────────

def _conceptnet_expand(term, max_edges=10):
    """Expand a term via ConceptNet relations."""
    try:
        url = f"http://api.conceptnet.io/c/en/{urllib.parse.quote(term.lower())}?limit={max_edges}"
        req = urllib.request.Request(url, headers={"User-Agent": "KS31e-DomainBridge/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        
        expansions = []
        for edge in data.get("edges", []):
            rel = edge.get("rel", {}).get("label", "")
            start = edge.get("start", {}).get("label", "")
            end = edge.get("end", {}).get("label", "")
            weight = edge.get("weight", 0)
            
            if weight < 1.0:
                continue
            
            # Determine which side is our term
            if start.lower() == term.lower():
                related = end
                direction = "outgoing"
            else:
                related = start
                direction = "incoming"
            
            expansions.append({
                "term": related,
                "relation": rel,
                "direction": direction,
                "weight": round(weight, 2),
            })
        
        return {
            "source": "conceptnet",
            "query": term,
            "expansions": sorted(expansions, key=lambda x: -x["weight"])[:max_edges],
            "count": len(expansions),
        }
    except Exception as e:
        return {"source": "conceptnet", "query": term, "expansions": [], "count": 0, "error": str(e)[:60]}


# ─── OpenAlex Concept Expansion ─────────────────────────────────────────────

def _openalex_concepts(term, max_results=5):
    """Find related academic concepts via OpenAlex."""
    try:
        params = {
            "search": term,
            "per_page": str(max_results),
            "select": "id,display_name,works_count,description",
            "mailto": "katala@openclaw.ai",
        }
        url = "https://api.openalex.org/concepts?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS31e-DomainBridge/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
        
        concepts = []
        for c in data.get("results", []):
            concepts.append({
                "name": c.get("display_name", ""),
                "works_count": c.get("works_count", 0),
                "description": (c.get("description") or "")[:150],
            })
        
        return {
            "source": "openalex_concepts",
            "query": term,
            "concepts": concepts,
            "count": len(concepts),
        }
    except Exception as e:
        return {"source": "openalex_concepts", "query": term, "concepts": [], "count": 0, "error": str(e)[:60]}


# ─── Term Extraction ────────────────────────────────────────────────────────

_STOPS = {
    "the","a","an","is","are","was","were","be","been","being",
    "have","has","had","do","does","did","will","would","shall",
    "should","may","might","can","could","and","or","but","in",
    "on","at","to","for","of","with","by","from","it","this","that",
    "all","every","some","any","no","not","than","as","so","if",
    "then","therefore","because","since","also","very","more","most",
    "each","both","these","those","such","into","through","about",
}

def _extract_domain_terms(text, max_terms=5):
    """Extract domain-specific terms from text."""
    words = re.findall(r'[A-Za-z]+', text)
    seen = set()
    terms = []
    for w in words:
        wl = w.lower()
        if wl not in _STOPS and len(w) > 3 and wl not in seen:
            seen.add(wl)
            terms.append(wl)
    return terms[:max_terms]


# ─── Domain Bridge: Concept → Propositions ──────────────────────────────────

def _concept_to_propositions(term, expansions, concepts):
    """Convert expanded concepts into structured propositions for L1.
    
    Each proposition is a verifiable statement derived from external knowledge.
    """
    propositions = []
    
    # From ConceptNet: relation-based propositions
    for exp in expansions:
        rel = exp["relation"]
        related = exp["term"]
        weight = exp["weight"]
        
        if rel == "IsA":
            propositions.append({
                "text": f"{term} is a type of {related}",
                "type": "taxonomy",
                "confidence": min(weight / 10, 1.0),
                "source": "conceptnet",
            })
        elif rel == "PartOf":
            propositions.append({
                "text": f"{term} is part of {related}",
                "type": "mereology",
                "confidence": min(weight / 10, 1.0),
                "source": "conceptnet",
            })
        elif rel == "HasProperty":
            propositions.append({
                "text": f"{term} has the property of being {related}",
                "type": "property",
                "confidence": min(weight / 10, 1.0),
                "source": "conceptnet",
            })
        elif rel == "UsedFor":
            propositions.append({
                "text": f"{term} is used for {related}",
                "type": "function",
                "confidence": min(weight / 10, 1.0),
                "source": "conceptnet",
            })
        elif rel == "Causes":
            propositions.append({
                "text": f"{term} causes {related}",
                "type": "causal",
                "confidence": min(weight / 10, 1.0),
                "source": "conceptnet",
            })
        elif rel in ("RelatedTo", "SimilarTo"):
            propositions.append({
                "text": f"{term} is related to {related}",
                "type": "association",
                "confidence": min(weight / 10, 0.8),
                "source": "conceptnet",
            })
    
    # From OpenAlex: academic grounding
    for concept in concepts:
        if concept.get("description"):
            propositions.append({
                "text": f"{concept['name']}: {concept['description']}",
                "type": "academic_definition",
                "confidence": min(concept.get("works_count", 0) / 100000, 1.0),
                "source": "openalex",
            })
    
    return propositions


# ─── Main Bridge Function ───────────────────────────────────────────────────

def bridge_domain(text, store=None):
    """Expand unknown-domain text into structured propositions for L1.
    
    Args:
        text: input claim or step text
        store: StageStore for externalization
    
    Returns:
        dict with expanded propositions, domain info, and enrichment metadata
    """
    terms = _extract_domain_terms(text)
    
    if not terms:
        return {
            "terms": [],
            "propositions": [],
            "domain_detected": False,
            "enrichment_count": 0,
        }
    
    all_propositions = []
    term_expansions = {}
    
    for term in terms[:3]:  # Limit to top 3 terms for speed
        # ConceptNet expansion
        cn = _conceptnet_expand(term)
        
        # OpenAlex concept expansion
        oa = _openalex_concepts(term)
        
        # Convert to propositions
        props = _concept_to_propositions(
            term,
            cn.get("expansions", []),
            oa.get("concepts", []),
        )
        
        term_expansions[term] = {
            "conceptnet_count": cn["count"],
            "openalex_count": oa["count"],
            "propositions_generated": len(props),
        }
        
        all_propositions.extend(props)
    
    # Deduplicate by text
    seen_texts = set()
    unique_props = []
    for p in all_propositions:
        if p["text"] not in seen_texts:
            seen_texts.add(p["text"])
            unique_props.append(p)
    
    # Sort by confidence
    unique_props.sort(key=lambda x: -x.get("confidence", 0))
    
    # Limit to top 15 propositions
    unique_props = unique_props[:15]
    
    result = {
        "terms": terms,
        "term_expansions": term_expansions,
        "propositions": unique_props,
        "domain_detected": len(unique_props) > 0,
        "enrichment_count": len(unique_props),
        "proposition_types": list(set(p["type"] for p in unique_props)),
    }
    
    if store:
        store.write("domain_bridge", result)
    
    return result
