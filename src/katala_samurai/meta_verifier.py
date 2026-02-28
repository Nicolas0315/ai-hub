"""
Layer 4: Meta-Verification — verifies the verification itself.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Purpose:
  Detect when L1-L3 produce verdicts based on form rather than content.
  Two probes:
    M1: Counter-Factual Probe — negate claim, re-verify, compare
    M2: OpenAlex Evidence Probe — check if academic evidence exists

Design principles:
  - Non-LLM (API + text matching only)
  - No accumulation (each run is fresh)
  - Connects to L1 cyclically: L4 uses L1 to test, then feeds back
  - L3 consulted: L4 results go through L3 for chain-level meta-analysis

Architecture:
  After L1→L3→L2→L1 cycle:
    L4 receives verdict + claim
    M1: generates negation → sends to L1 lightweight → compares pass_rates
    M2: searches OpenAlex for supporting/contradicting evidence
    → If M1 detects content-blindness: downgrade verdict, flag "FORMAL_ONLY"
    → If M2 finds no evidence: flag "NO_ACADEMIC_SUPPORT"
    → Results feed back through L3 for integration
"""

import re
import urllib.request
import urllib.parse
import json as _json
import hashlib

try:
    from .evidence_sources import multi_source_evidence
except ImportError:
    from evidence_sources import multi_source_evidence


# ─── M1: Counter-Factual Probe ──────────────────────────────────────────────

_NEGATION_PATTERNS = [
    # (pattern, replacement) — applied in order
    (r'\bis\b', 'is not'),
    (r'\bare\b', 'are not'),
    (r'\bwas\b', 'was not'),
    (r'\bwere\b', 'were not'),
    (r'\bcan\b', 'cannot'),
    (r'\bwill\b', 'will not'),
    (r'\bhas\b', 'has not'),
    (r'\bhave\b', 'have not'),
    (r'\bdoes\b', 'does not'),
    (r'\bdo\b', 'do not'),
]

_STRONG_NEGATION_PATTERNS = [
    # For sentences that already contain negation, remove it
    (r'\bis not\b', 'is'),
    (r'\bare not\b', 'are'),
    (r'\bcannot\b', 'can'),
    (r'\bwill not\b', 'will'),
    (r'\bnot\b', ''),
    (r'\bnever\b', 'always'),
    (r'\bno\b', 'some'),
]


def _negate_text(text):
    """Generate negation of a claim text. Non-LLM: regex substitution."""
    lower = text.lower()
    
    # Check if already negated
    has_negation = any(re.search(p, lower) for p, _ in _STRONG_NEGATION_PATTERNS[:5])
    
    if has_negation:
        # Remove negation
        result = text
        for pattern, replacement in _STRONG_NEGATION_PATTERNS:
            result, count = re.subn(pattern, replacement, result, count=1, flags=re.IGNORECASE)
            if count > 0:
                break
        return result.strip()
    else:
        # Add negation
        result = text
        for pattern, replacement in _NEGATION_PATTERNS:
            result, count = re.subn(pattern, replacement, result, count=1, flags=re.IGNORECASE)
            if count > 0:
                break
        return result.strip()


def m1_counterfactual_probe(claim_text, l1_verify_fn, original_pass_rate):
    """Negate the claim and verify with L1. Compare pass rates.
    
    If |original_rate - negated_rate| < threshold:
      → L1 is content-blind for this claim (FORMAL_ONLY)
    
    Args:
        claim_text: original claim text
        l1_verify_fn: Layer1.verify_lightweight function
        original_pass_rate: pass_rate from original L1 verification
    
    Returns:
        dict with negation, negated_pass_rate, delta, and content_sensitivity flag
    """
    negated = _negate_text(claim_text)
    
    # Skip if negation didn't change anything meaningful
    if negated.lower().strip() == claim_text.lower().strip():
        return {
            "original": claim_text,
            "negated": negated,
            "negation_failed": True,
            "content_sensitive": None,
            "note": "could not generate meaningful negation",
        }
    
    # Verify negated claim with L1
    negated_result = l1_verify_fn(negated)
    negated_rate = negated_result["pass_rate"]
    
    delta = abs(original_pass_rate - negated_rate)
    
    # Threshold: if delta < 0.10, L1 can't distinguish claim from its negation
    content_sensitive = delta >= 0.10
    
    return {
        "original": claim_text,
        "negated": negated,
        "original_pass_rate": original_pass_rate,
        "negated_pass_rate": negated_rate,
        "delta": round(delta, 4),
        "content_sensitive": content_sensitive,
        "flag": None if content_sensitive else "FORMAL_ONLY",
        "negation_failed": False,
    }


# ─── M2: OpenAlex Evidence Probe ────────────────────────────────────────────

def _extract_key_terms(text, max_terms=5):
    """Extract content words for search. Non-LLM: stopword removal + length filter."""
    stops = {
        "the","a","an","is","are","was","were","be","been","being",
        "have","has","had","do","does","did","will","would","shall",
        "should","may","might","can","could","and","or","but","in",
        "on","at","to","for","of","with","by","from","it","this","that",
        "all","every","some","any","no","not","than","as","so","if",
        "then","therefore","because","since","also","very","more","most",
        "each","both","these","those","such","into","through","about",
    }
    words = re.findall(r'[A-Za-z]+', text)
    content = [w.lower() for w in words if w.lower() not in stops and len(w) > 2]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for w in content:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:max_terms]


def m2_evidence_probe(claim_text, evidence_list=None):
    """Search OpenAlex for academic evidence supporting or contradicting the claim.
    
    Non-LLM: API call + title/abstract text matching.
    No caching, no accumulation — fresh search every time.
    
    Returns:
        dict with papers found, support indicators, and evidence quality assessment
    """
    terms = _extract_key_terms(claim_text)
    if not terms:
        return {
            "query": claim_text[:80],
            "terms": [],
            "papers_found": 0,
            "supporting": [],
            "contradicting": [],
            "evidence_quality": "NO_TERMS",
        }
    
    query = " ".join(terms)
    
    papers = []
    try:
        params = {
            "search": query,
            "per_page": "10",
            "select": "id,title,publication_year,cited_by_count,abstract_inverted_index",
            "sort": "relevance_score:desc",
            "mailto": "katala@openclaw.ai",
        }
        url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS31a-L4/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
            for p in data.get("results", []):
                # Reconstruct abstract from inverted index
                abstract = ""
                aii = p.get("abstract_inverted_index")
                if aii:
                    word_positions = []
                    for word, positions in aii.items():
                        for pos in positions:
                            word_positions.append((pos, word))
                    word_positions.sort()
                    abstract = " ".join(w for _, w in word_positions)
                
                papers.append({
                    "title": p.get("title", "")[:120],
                    "year": p.get("publication_year"),
                    "cited_by": p.get("cited_by_count", 0),
                    "abstract": abstract[:300],
                })
    except Exception:
        return {
            "query": query,
            "terms": terms,
            "papers_found": 0,
            "supporting": [],
            "contradicting": [],
            "evidence_quality": "API_ERROR",
        }
    
    if not papers:
        return {
            "query": query,
            "terms": terms,
            "papers_found": 0,
            "supporting": [],
            "contradicting": [],
            "evidence_quality": "NO_ACADEMIC_SUPPORT",
        }
    
    # Simple relevance check: how many search terms appear in title+abstract
    claim_lower = claim_text.lower()
    supporting = []
    contradicting = []
    
    for paper in papers:
        title_abs = (paper["title"] + " " + paper["abstract"]).lower()
        term_hits = sum(1 for t in terms if t in title_abs)
        relevance = term_hits / max(len(terms), 1)
        
        # Check for negation words near key terms (crude contradiction detection)
        has_negation = any(neg in title_abs for neg in ["not ", "no ", "fail", "unable", "contrary", "against", "disprove"])
        
        entry = {
            "title": paper["title"],
            "year": paper["year"],
            "cited_by": paper["cited_by"],
            "relevance": round(relevance, 2),
        }
        
        if relevance >= 0.4:
            if has_negation:
                contradicting.append(entry)
            else:
                supporting.append(entry)
    
    # Evidence quality assessment
    total_citations = sum(p["cited_by"] for p in supporting + contradicting)
    high_cite = any(p["cited_by"] >= 100 for p in supporting + contradicting)
    
    if supporting and high_cite:
        quality = "STRONG_SUPPORT"
    elif supporting:
        quality = "WEAK_SUPPORT"
    elif contradicting:
        quality = "CONTRADICTED"
    else:
        quality = "NO_RELEVANT_PAPERS"
    
    return {
        "query": query,
        "terms": terms,
        "papers_found": len(papers),
        "supporting": supporting[:5],
        "contradicting": contradicting[:3],
        "total_citations": total_citations,
        "evidence_quality": quality,
    }


# ─── Layer 4 Orchestrator ───────────────────────────────────────────────────

def run_meta_verification(claim_text, l1_verify_fn, original_pass_rate,
                          evidence_list=None, store=None):
    """Run both M1 and M2 probes. Returns meta-verification result.
    
    Args:
        claim_text: the claim being verified
        l1_verify_fn: Layer1.verify_lightweight (for M1 counterfactual)
        original_pass_rate: L1's pass_rate for the original claim
        evidence_list: original evidence provided with claim
        store: StageStore for externalization
    
    Returns:
        dict with M1/M2 results and overall meta-assessment
    """
    # M1: Counter-factual probe
    m1 = m1_counterfactual_probe(claim_text, l1_verify_fn, original_pass_rate)
    
    # M2: Multi-source evidence probe (OpenAlex + Gov + GDELT + Firecrawl)
    m2_openalex = m2_evidence_probe(claim_text, evidence_list)
    m2_multi = multi_source_evidence(claim_text, openalex_result={
        "evidence_quality": m2_openalex["evidence_quality"],
        "papers_found": m2_openalex["papers_found"],
    })
    m2 = m2_openalex  # backward compat for flags below
    
    # Meta-assessment: combine M1 and M2
    flags = []
    
    if m1.get("flag") == "FORMAL_ONLY":
        flags.append("FORMAL_ONLY")
    
    if m2["evidence_quality"] == "NO_ACADEMIC_SUPPORT":
        flags.append("NO_ACADEMIC_SUPPORT")
    elif m2["evidence_quality"] == "NO_RELEVANT_PAPERS":
        flags.append("NO_RELEVANT_PAPERS")
    elif m2["evidence_quality"] == "CONTRADICTED":
        flags.append("CONTRADICTED")
    elif m2["evidence_quality"] == "API_ERROR":
        flags.append("EVIDENCE_CHECK_UNAVAILABLE")
    
    # Verdict modifier — combines M1 + multi-source consensus
    multi_conf = m2_multi["confidence"]
    
    if "FORMAL_ONLY" in flags and m2_multi["consensus"] == "NO_EVIDENCE":
        meta_verdict = "HOLLOW"
        confidence_modifier = 0.4
    elif "FORMAL_ONLY" in flags and m2_multi["consensus"] in ("NO_EVIDENCE", "WEAK_EVIDENCE"):
        meta_verdict = "FORM_ONLY"
        confidence_modifier = 0.5
    elif "FORMAL_ONLY" in flags and m2_multi["consensus"] in ("MODERATE_EVIDENCE", "STRONG_EVIDENCE"):
        meta_verdict = "FORM_BUT_EVIDENCED"
        confidence_modifier = 0.75
    elif "CONTRADICTED" in flags:
        meta_verdict = "CONTESTED"
        confidence_modifier = 0.6
    elif m2_multi["consensus"] == "STRONG_EVIDENCE":
        meta_verdict = "SUBSTANTIVE"
        confidence_modifier = 1.0
    elif m2_multi["consensus"] == "MODERATE_EVIDENCE":
        meta_verdict = "SUBSTANTIVE"
        confidence_modifier = 0.9
    elif m2_multi["consensus"] in ("NO_EVIDENCE", "WEAK_EVIDENCE"):
        meta_verdict = "UNSUPPORTED"
        confidence_modifier = 0.7
    else:
        meta_verdict = "SUBSTANTIVE"
        confidence_modifier = 1.0
    
    result = {
        "m1_counterfactual": m1,
        "m2_evidence": {
            "quality": m2["evidence_quality"],
            "supporting_count": len(m2["supporting"]),
            "contradicting_count": len(m2["contradicting"]),
            "top_paper": m2["supporting"][0]["title"] if m2["supporting"] else None,
            "total_citations": m2.get("total_citations", 0),
        },
        "m2_multi_source": {
            "consensus": m2_multi["consensus"],
            "confidence": m2_multi["confidence"],
            "sources_with_evidence": m2_multi["sources_with_evidence"],
            "sources_available": m2_multi["sources_available"],
        },
        "flags": flags,
        "meta_verdict": meta_verdict,
        "confidence_modifier": confidence_modifier,
    }
    
    if store is not None:
        store.write("L4_meta_verification", result)
    
    return result
