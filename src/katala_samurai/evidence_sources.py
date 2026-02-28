"""
Multi-Source Evidence Layer for L4 Meta-Verification.

Sources:
  1. OpenAlex (academic papers) — already in meta_verifier.py M2
  2. e-Stat / MLIT / gBizINFO (Japanese gov APIs)
  3. GDELT (global news/events)
  4. Firecrawl (arbitrary URL verification)

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Principles:
  - Non-LLM: API calls + text matching only
  - No accumulation: fresh queries every run
  - Each source returns structured evidence with confidence
"""

import urllib.request
import urllib.parse
import json as _json
import re
import os


# ─── Source 1: OpenAlex (delegated to meta_verifier.m2_evidence_probe) ───────


# ─── Source 2: Government APIs ──────────────────────────────────────────────

def _gov_estat_search(terms, max_results=5):
    """Search e-Stat (Japanese government statistics)."""
    query = " ".join(terms)
    try:
        params = {
            "lang": "E",
            "searchWord": query,
            "limit": str(max_results),
        }
        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList?" + urllib.parse.urlencode(params)
        # e-Stat requires appId — check env
        app_id = os.environ.get("ESTAT_API_KEY", "")
        if not app_id:
            return {"source": "e-stat", "available": False, "reason": "no_api_key"}
        params["appId"] = app_id
        url = "https://api.e-stat.go.jp/rest/3.0/app/json/getStatsList?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS31b-L4/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
            results = data.get("GET_STATS_LIST", {}).get("DATALIST_INF", {}).get("TABLE_INF", [])
            if isinstance(results, dict):
                results = [results]
            return {
                "source": "e-stat",
                "available": True,
                "results": [{"title": r.get("TITLE", {}).get("$", ""), "id": r.get("@id", "")} for r in results[:max_results]],
                "count": len(results),
            }
    except Exception as e:
        return {"source": "e-stat", "available": False, "reason": str(e)[:80]}


def _gov_mlit_search(terms):
    """Search MLIT DPF (land/real estate data)."""
    query = " ".join(terms)
    try:
        params = {"keyword": query, "limit": "5"}
        url = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS31b-L4/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode())
            results = data.get("data", [])
            return {
                "source": "mlit",
                "available": True,
                "results": [{"name": r.get("name", ""), "value": r.get("value", "")} for r in results[:5]],
                "count": len(results),
            }
    except Exception:
        return {"source": "mlit", "available": False, "reason": "api_error"}


def gov_search(terms):
    """Aggregate government API search results."""
    estat = _gov_estat_search(terms)
    mlit = _gov_mlit_search(terms)
    
    sources_available = sum(1 for s in [estat, mlit] if s.get("available"))
    total_results = sum(s.get("count", 0) for s in [estat, mlit] if s.get("available"))
    
    return {
        "type": "government",
        "sources_checked": 2,
        "sources_available": sources_available,
        "total_results": total_results,
        "details": [estat, mlit],
        "has_evidence": total_results > 0,
    }


# ─── Source 3: GDELT (Global News/Events) ──────────────────────────────────

def gdelt_search(terms, max_results=10):
    """Search GDELT DOC API for news articles matching terms."""
    query = " ".join(terms)
    try:
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(max_results),
            "format": "json",
            "sort": "DateDesc",
        }
        url = "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "KS31b-L4/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = _json.loads(resp.read().decode())
            articles = data.get("articles", [])
            
            results = []
            for a in articles[:max_results]:
                results.append({
                    "title": a.get("title", "")[:120],
                    "url": a.get("url", ""),
                    "source": a.get("domain", ""),
                    "date": a.get("seendate", ""),
                    "language": a.get("language", ""),
                })
            
            return {
                "type": "news",
                "source": "gdelt",
                "available": True,
                "results": results,
                "count": len(results),
                "has_evidence": len(results) > 0,
            }
    except Exception as e:
        return {
            "type": "news",
            "source": "gdelt",
            "available": False,
            "reason": str(e)[:80],
            "count": 0,
            "has_evidence": False,
        }


# ─── Source 4: Firecrawl (URL Verification) ─────────────────────────────────

def firecrawl_verify(url_or_query, api_key=None):
    """Use Firecrawl to scrape and verify content from a URL."""
    key = api_key or os.environ.get("FIRECRAWL_API_KEY", "")
    if not key:
        return {
            "type": "url_verification",
            "source": "firecrawl",
            "available": False,
            "reason": "no_api_key",
            "has_evidence": False,
        }
    
    try:
        # Use search endpoint for query-based verification
        payload = _json.dumps({
            "query": url_or_query,
            "limit": 5,
            "scrapeOptions": {"formats": ["markdown"]},
        }).encode()
        
        req = urllib.request.Request(
            "https://api.firecrawl.dev/v1/search",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "User-Agent": "KS31b-L4/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode())
            results = data.get("data", [])
            
            return {
                "type": "url_verification",
                "source": "firecrawl",
                "available": True,
                "results": [
                    {
                        "title": r.get("metadata", {}).get("title", "")[:120],
                        "url": r.get("url", ""),
                        "snippet": (r.get("markdown", "") or "")[:200],
                    }
                    for r in results[:5]
                ],
                "count": len(results),
                "has_evidence": len(results) > 0,
            }
    except Exception as e:
        return {
            "type": "url_verification",
            "source": "firecrawl",
            "available": False,
            "reason": str(e)[:80],
            "count": 0,
            "has_evidence": False,
        }


# ─── Multi-Source Aggregator ────────────────────────────────────────────────

def _extract_terms(text, max_terms=5):
    """Extract content words (shared with meta_verifier)."""
    stops = {
        "the","a","an","is","are","was","were","be","been","being",
        "have","has","had","do","does","did","will","would","shall",
        "should","may","might","can","could","and","or","but","in",
        "on","at","to","for","of","with","by","from","it","this","that",
        "all","every","some","any","no","not","than","as","so","if",
        "then","therefore","because","since","also","very","more","most",
    }
    words = re.findall(r'[A-Za-z]+', text)
    seen = set()
    unique = []
    for w in words:
        wl = w.lower()
        if wl not in stops and len(w) > 2 and wl not in seen:
            seen.add(wl)
            unique.append(wl)
    return unique[:max_terms]


def multi_source_evidence(claim_text, openalex_result=None):
    """Run all evidence sources and compute consensus score.
    
    Args:
        claim_text: the claim to verify
        openalex_result: existing M2 result from meta_verifier (optional, avoids duplicate call)
    
    Returns:
        dict with per-source results and consensus assessment
    """
    terms = _extract_terms(claim_text)
    
    # Source 1: OpenAlex (use existing if provided)
    if openalex_result:
        s1 = {
            "type": "academic",
            "source": "openalex",
            "has_evidence": openalex_result.get("evidence_quality") in ("STRONG_SUPPORT", "WEAK_SUPPORT"),
            "quality": openalex_result.get("evidence_quality", "UNKNOWN"),
            "count": openalex_result.get("papers_found", 0),
        }
    else:
        # Import and call
        try:
            from .meta_verifier import m2_evidence_probe
        except ImportError:
            from meta_verifier import m2_evidence_probe
        m2 = m2_evidence_probe(claim_text)
        s1 = {
            "type": "academic",
            "source": "openalex",
            "has_evidence": m2["evidence_quality"] in ("STRONG_SUPPORT", "WEAK_SUPPORT"),
            "quality": m2["evidence_quality"],
            "count": m2["papers_found"],
        }
    
    # Source 2: Government APIs
    s2 = gov_search(terms)
    
    # Source 3: GDELT News
    s3 = gdelt_search(terms)
    
    # Source 4: Firecrawl
    s4 = firecrawl_verify(claim_text)
    
    # ── Step 4: Consensus scoring ──
    sources = [s1, s2, s3, s4]
    sources_with_evidence = sum(1 for s in sources if s.get("has_evidence"))
    sources_available = sum(1 for s in sources if s.get("available", s.get("has_evidence", False)) is not False)
    
    # Consensus levels
    if sources_available == 0:
        consensus = "NO_SOURCES_AVAILABLE"
        confidence = 0.0
    elif sources_with_evidence >= 3:
        consensus = "STRONG_EVIDENCE"
        confidence = 0.95
    elif sources_with_evidence == 2:
        consensus = "MODERATE_EVIDENCE"
        confidence = 0.80
    elif sources_with_evidence == 1:
        consensus = "WEAK_EVIDENCE"
        confidence = 0.60
    else:
        consensus = "NO_EVIDENCE"
        confidence = 0.30
    
    return {
        "claim": claim_text[:100],
        "terms": terms,
        "sources": {
            "academic": s1,
            "government": s2,
            "news": s3,
            "url_verification": s4,
        },
        "sources_checked": 4,
        "sources_available": sources_available,
        "sources_with_evidence": sources_with_evidence,
        "consensus": consensus,
        "confidence": confidence,
    }
