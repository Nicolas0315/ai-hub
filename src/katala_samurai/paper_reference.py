"""
Paper Reference Engine for KS29B
Queries OpenAlex API to find peer-reviewed papers relevant to a claim's contexts.

Design principle (Youta Hilono):
  Human cognition depends on scientific knowledge.
  Scientific knowledge is stored in peer-reviewed papers.
  Papers contain descriptions of bodily experience (pain, emotion, sensation).
  Therefore: paper reference = grounding in human knowledge + embodied experience.
"""

import urllib.request
import urllib.parse
import json
import time
from dataclasses import dataclass, field


@dataclass
class PaperReference:
    """A peer-reviewed paper relevant to a claim."""
    title: str
    year: int
    authors: list[str]
    cited_by: int
    openalex_id: str
    doi: str | None = None
    abstract: str | None = None
    relevance_score: float = 0.0
    context_domain: str = ""  # which context this paper supports


def _query_openalex(search_query, per_page=5, timeout=10):
    """Query OpenAlex API for papers matching a search query.
    
    OpenAlex: free, no API key required, 200M+ works.
    Rate limit: 10 req/s (unauthenticated), 100 req/s (with email).
    """
    params = {
        "search": search_query,
        "per_page": str(per_page),
        "select": "id,title,publication_year,cited_by_count,authorships,doi,abstract_inverted_index",
        "sort": "relevance_score:desc",  # relevance first, not just citations
        "mailto": "katala@openclaw.ai",  # polite pool
    }
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KS29B/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            return data.get("results", [])
    except Exception:
        return []


def _reconstruct_abstract(inverted_index):
    """Reconstruct abstract text from OpenAlex inverted index format."""
    if not inverted_index:
        return None
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)[:500]  # cap at 500 chars


def _build_search_query(claim_text, context):
    """Build an effective search query from claim text and academic context.
    
    Strategy: extract key content words + add domain-specific terms.
    """
    # Extract content words (skip short/common words)
    stops = {"the", "a", "an", "is", "are", "not", "and", "or", "of", "in",
             "to", "for", "that", "this", "it", "by", "on", "with", "has",
             "was", "be", "explain", "why", "how", "what", "which", "does",
             "said", "between", "concisely", "please"}
    words = [w.strip(",.;:?!()\"'") for w in claim_text.lower().split()]
    content_words = [w for w in words if w not in stops and len(w) > 2
                     and all(ord(c) < 128 for c in w)][:6]
    
    # For formal expressions with math symbols, add concept keywords
    math_concepts = {
        "∈": "membership", "∉": "non-membership", "⟺": "biconditional",
        "∀": "universal quantifier", "∃": "existential",
        "→": "implication", "¬": "negation",
    }
    for sym, concept in math_concepts.items():
        if sym in claim_text and concept not in " ".join(content_words):
            content_words.append(concept)
    
    # Detect well-known mathematical structures
    if "∉ x" in claim_text and "∈" in claim_text:
        content_words.extend(["Russell", "paradox"])
    if content_words == [] or all(len(w) <= 2 for w in content_words):
        content_words = ["formal", "logic", "paradox"]
    
    # Add domain context
    domain_terms = {
        "formal_science/arithmetic": "mathematics arithmetic",
        "formal_science/abstract_algebra": "abstract algebra field theory",
        "formal_science/set_theory": "set theory foundations",
        "formal_science/logic": "mathematical logic",
        "natural_science/physics": "physics",
        "natural_science/chemistry": "chemistry",
        "natural_science/biology": "biology",
        "natural_science/earth_science": "earth science geophysics",
        "humanities/philosophy": "philosophy",
        "humanities/history": "history",
        "humanities/epistemology": "epistemology knowledge",
        "social_science/politics": "political science",
        "arts_culture/literature": "literary studies",
        "arts_culture/music": "musicology",
        "arts_culture/linguistics": "linguistics translation",
        "information_science/ai_ethics": "artificial intelligence ethics",
    }
    
    domain_key = f"{context.domain}/{context.subdomain}"
    extra = domain_terms.get(domain_key, "")
    
    query = " ".join(content_words)
    if extra:
        query = f"{query} {extra}"
    
    return query


def fetch_papers_for_claim(claim_text, contexts, max_papers_per_context=3, 
                            max_total=10, timeout=10):
    """Fetch relevant papers for a claim across its detected contexts.
    
    Args:
        claim_text: The claim text
        contexts: List of AcademicContext from ContextResolver
        max_papers_per_context: Max papers to fetch per context
        max_total: Max total papers to return
        timeout: HTTP timeout in seconds
    
    Returns:
        List of PaperReference sorted by relevance (cited_by * context_relevance)
    """
    all_papers = []
    seen_ids = set()
    
    for ctx in contexts[:4]:  # limit to top 4 contexts
        query = _build_search_query(claim_text, ctx)
        if not query.strip():
            continue
        
        results = _query_openalex(query, per_page=max_papers_per_context, timeout=timeout)
        
        for work in results:
            oa_id = work.get("id", "")
            if oa_id in seen_ids:
                continue
            seen_ids.add(oa_id)
            
            # Extract authors
            authors = []
            for auth in work.get("authorships", [])[:5]:
                name = auth.get("author", {}).get("display_name", "")
                if name:
                    authors.append(name)
            
            # Reconstruct abstract
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            
            cited_by = work.get("cited_by_count", 0)
            year = work.get("publication_year", 0) or 0
            
            # Relevance: citation impact × context relevance × recency bonus
            recency_bonus = max(0.5, 1.0 - (2026 - year) * 0.02) if year > 0 else 0.5
            relevance = (min(cited_by, 10000) / 10000) * ctx.relevance * recency_bonus
            
            paper = PaperReference(
                title=work.get("title", "Unknown"),
                year=year,
                authors=authors,
                cited_by=cited_by,
                openalex_id=oa_id,
                doi=work.get("doi"),
                abstract=abstract,
                relevance_score=round(relevance, 4),
                context_domain=f"{ctx.domain}/{ctx.subdomain}",
            )
            all_papers.append(paper)
        
        # Be polite: small delay between requests
        time.sleep(0.15)
    
    # Sort by relevance score
    all_papers.sort(key=lambda p: -p.relevance_score)
    return all_papers[:max_total]


def _extract_key_terms(claim_text):
    """Extract the most salient noun phrases / named entities from claim text."""
    stops = {"the", "a", "an", "is", "are", "not", "and", "or", "of", "in",
             "to", "for", "that", "this", "it", "by", "on", "with", "has",
             "was", "be", "explain", "why", "how", "what", "which", "does",
             "said", "between", "concisely", "please", "other", "its",
             "their", "there", "about", "from", "data", "based", "using",
             "can", "may", "will", "also", "such", "into", "than", "more"}
    words = [w.strip(",.;:?!()\"'") for w in claim_text.split()]
    # Keep capitalized words (likely proper nouns) and long content words
    terms = []
    for w in words:
        clean = w.lower().strip(",.;:?!()")
        if clean in stops or len(clean) < 3:
            continue
        # Proper nouns get priority
        if w[0].isupper() and len(w) > 2:
            terms.insert(0, w)
        else:
            terms.append(clean)
    return terms[:8]


def auto_refine_search(claim_text, contexts, initial_papers,
                       min_relevant=3, max_rounds=2, timeout=10):
    """Self-refining paper search: if initial results are insufficient,
    automatically generate refined queries and search again.
    
    Strategy:
    1. Check if initial papers are domain-relevant (title contains key terms)
    2. If insufficient, extract core terms and build focused queries
    3. Search with progressively narrower/broader queries
    
    Returns: augmented paper list
    """
    key_terms = _extract_key_terms(claim_text)
    if not key_terms:
        return initial_papers
    
    # Count how many initial papers are actually relevant
    primary_term = key_terms[0].lower()
    relevant = [p for p in initial_papers
                if primary_term in (p.title or "").lower()]
    
    if len(relevant) >= min_relevant:
        return initial_papers  # sufficient, no refinement needed
    
    # ── Auto-refinement: generate focused queries
    all_papers = list(initial_papers)
    seen_ids = {p.openalex_id for p in all_papers}
    
    # Build refined queries from key terms
    refined_queries = []
    if len(key_terms) >= 2:
        # Combination of top terms
        refined_queries.append(f"{key_terms[0]} {key_terms[1]}")
        refined_queries.append(f"{key_terms[0]} {key_terms[1]} prediction")
        refined_queries.append(f"{key_terms[0]} {key_terms[1]} analysis")
    if len(key_terms) >= 1:
        refined_queries.append(f"{key_terms[0]} empirical study")
        refined_queries.append(f"{key_terms[0]} systematic review")
    
    # Add domain-specific refinements
    for ctx in contexts[:2]:
        domain_key = f"{ctx.domain}/{ctx.subdomain}"
        if "economics" in domain_key:
            refined_queries.append(f"{key_terms[0]} market volatility correlation")
            refined_queries.append(f"{key_terms[0]} macroeconomic indicators")
        elif "psychology" in domain_key or "philosophy" in domain_key:
            refined_queries.append(f"{key_terms[0]} cognitive behavioral")
        elif "physics" in domain_key:
            refined_queries.append(f"{key_terms[0]} experimental measurement")
    
    for round_i in range(min(max_rounds, len(refined_queries))):
        query = refined_queries[round_i]
        results = _query_openalex(query, per_page=5, timeout=timeout)
        
        for work in results:
            oa_id = work.get("id", "")
            if oa_id in seen_ids:
                continue
            seen_ids.add(oa_id)
            
            title = work.get("title", "")
            # Relevance filter: must contain at least one key term
            if not any(t.lower() in title.lower() for t in key_terms[:3]):
                continue
            
            authors = [a.get("author", {}).get("display_name", "")
                       for a in work.get("authorships", [])[:5] if a.get("author")]
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            cited_by = work.get("cited_by_count", 0)
            year = work.get("publication_year", 0) or 0
            
            ctx_rel = contexts[0].relevance if contexts else 0.5
            recency = max(0.5, 1.0 - (2026 - year) * 0.02) if year > 0 else 0.5
            relevance = (min(cited_by, 10000) / 10000) * ctx_rel * recency
            
            paper = PaperReference(
                title=title, year=year, authors=authors,
                cited_by=cited_by, openalex_id=oa_id,
                doi=work.get("doi"), abstract=abstract,
                relevance_score=round(relevance, 4),
                context_domain=f"auto_refined/{query[:30]}",
            )
            all_papers.append(paper)
        
        time.sleep(0.15)
        
        # Re-check: enough relevant papers now?
        relevant = [p for p in all_papers if primary_term in (p.title or "").lower()]
        if len(relevant) >= min_relevant:
            break
    
    all_papers.sort(key=lambda p: -p.relevance_score)
    return all_papers


def papers_to_dict(papers):
    """Convert PaperReference list to serializable dict list."""
    return [
        {
            "title": p.title,
            "year": p.year,
            "authors": p.authors[:3],
            "cited_by": p.cited_by,
            "doi": p.doi,
            "abstract_snippet": p.abstract[:200] if p.abstract else None,
            "relevance": p.relevance_score,
            "domain": p.context_domain,
            "openalex_id": p.openalex_id,
        }
        for p in papers
    ]
