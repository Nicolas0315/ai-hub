"""
KS33b #4: Template Auto-Extractor — extract structural templates from OpenAlex papers.

Instead of hand-coded templates, discover claim patterns from peer-reviewed literature.
Uses OpenAlex works search to find structural patterns in paper titles/abstracts.

Non-LLM: regex extraction from academic text.
"""

import re
import urllib.request
import urllib.parse
import json as _json


# ─── Base Pattern Extractors ────────────────────────────────────────────────

_ACADEMIC_PATTERNS = [
    # "X causes Y" / "X leads to Y"
    (re.compile(r'(\w+(?:\s+\w+){0,2})\s+(causes?|leads?\s+to|results?\s+in|induces?|promotes?)\s+(\w+(?:\s+\w+){0,3})', re.I),
     "causal", ["agent", "action", "result"]),
    # "X inhibits/prevents Y"
    (re.compile(r'(\w+(?:\s+\w+){0,2})\s+(inhibits?|prevents?|blocks?|suppresses?|reduces?)\s+(\w+(?:\s+\w+){0,3})', re.I),
     "inhibition", ["inhibitor", "action", "target"]),
    # "X is associated with Y"
    (re.compile(r'(\w+(?:\s+\w+){0,2})\s+(?:is|are)\s+(associated|correlated|linked)\s+with\s+(\w+(?:\s+\w+){0,3})', re.I),
     "association", ["entity_a", "relation", "entity_b"]),
    # "X increases/decreases Y"
    (re.compile(r'(\w+(?:\s+\w+){0,2})\s+(increases?|decreases?|enhances?|diminishes?|elevates?|lowers?)\s+(\w+(?:\s+\w+){0,3})', re.I),
     "modulation", ["modulator", "direction", "target"]),
    # "X is a [type] of Y"
    (re.compile(r'(\w+(?:\s+\w+){0,2})\s+(?:is|are)\s+(?:a\s+)?(\w+)\s+(?:of|type\s+of)\s+(\w+(?:\s+\w+){0,2})', re.I),
     "taxonomy", ["instance", "relation", "category"]),
]


def extract_patterns_from_text(text):
    """Extract structural patterns from a text (title/abstract)."""
    patterns = []
    for regex, ptype, slot_names in _ACADEMIC_PATTERNS:
        for m in regex.finditer(text):
            groups = [g.strip() for g in m.groups()]
            slots = {}
            for i, name in enumerate(slot_names):
                if i < len(groups):
                    slots[name] = groups[i]
            patterns.append({
                "type": ptype,
                "slots": slots,
                "text": m.group()[:80],
                "source": "extracted",
            })
    return patterns


def discover_templates_from_openalex(domain_terms, max_works=10):
    """Search OpenAlex for domain-specific papers and extract patterns.
    
    Returns discovered templates that can augment the hand-coded ones.
    """
    discovered = []
    
    for term in domain_terms[:3]:
        try:
            query = urllib.parse.quote(term)
            url = f"https://api.openalex.org/works?filter=title.search:{query}&per_page={max_works}&select=title,abstract_inverted_index"
            req = urllib.request.Request(url, headers={"User-Agent": "KatalaSamurai/1.0"})
            
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = _json.loads(resp.read())
            
            for work in data.get("results", []):
                title = work.get("title", "")
                if title:
                    patterns = extract_patterns_from_text(title)
                    for p in patterns:
                        p["academic_source"] = title[:60]
                        p["domain_term"] = term
                    discovered.extend(patterns)
                
                # Reconstruct abstract from inverted index
                aii = work.get("abstract_inverted_index")
                if aii and isinstance(aii, dict):
                    max_pos = max(max(positions) for positions in aii.values()) + 1
                    abstract_words = [""] * max_pos
                    for word, positions in aii.items():
                        for pos in positions:
                            if pos < max_pos:
                                abstract_words[pos] = word
                    abstract = " ".join(w for w in abstract_words if w)
                    if abstract:
                        patterns = extract_patterns_from_text(abstract[:500])
                        for p in patterns:
                            p["academic_source"] = f"abstract:{title[:40]}"
                            p["domain_term"] = term
                        discovered.extend(patterns[:5])  # Limit per abstract
        except Exception:
            continue
    
    # Deduplicate by pattern text
    seen = set()
    unique = []
    for d in discovered:
        key = d["text"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(d)
    
    return {
        "templates_discovered": len(unique),
        "templates": unique,
        "terms_searched": domain_terms[:3],
    }
