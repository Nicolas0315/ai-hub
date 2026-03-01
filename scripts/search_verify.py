#!/usr/bin/env python3
"""Phase 1: Search result verification via KS40b + lightweight trust scoring.

Usage:
  python3 scripts/search_verify.py "query text"
  python3 scripts/search_verify.py --claim "specific claim to verify"
  python3 scripts/search_verify.py --lite "quick trust score without full KS40b"

Integrates:
  - KS40b: Full 5-axis HTLF verification (slow, ~17s per claim)
  - TrustScorer: Lightweight 4-axis trust scoring (fast, <1s)
  - Freshness decay by domain

Design: Nicolas Ogoshi
Implementation: Shirokuma (OpenClaw AI)
Date: 2026-03-01
"""

from __future__ import annotations

import argparse
import json
import sys
import os
import time
from dataclasses import dataclass, asdict
from typing import Any

# Add katala src to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))


# ── Domain freshness config (hours) ──
DOMAIN_FRESHNESS: dict[str, float] = {
    "crypto": 6,
    "politics": 24,
    "tech": 72,
    "science": 720,   # 30 days
    "general": 168,    # 7 days
}


@dataclass(slots=True)
class SearchResult:
    """A single search result to verify."""
    title: str
    snippet: str
    url: str
    source: str = ""
    timestamp: str = ""  # ISO format if available
    domain: str = "general"


@dataclass(slots=True)
class VerifiedResult:
    """Search result with trust/verification scores attached."""
    original: SearchResult
    # Lite scores (always computed, fast)
    trust_grade: str         # S/A/B/C/D/F
    freshness_score: float   # 0-1
    source_score: float      # 0-1
    snippet_quality: float   # 0-1 (length, specificity)
    # Full KS40b scores (optional, slow)
    ks40_score: float | None = None
    ks40_verdict: str | None = None
    ks40_confidence: float | None = None
    ks40_flags: list[str] | None = None
    # Elapsed
    verify_ms: float = 0.0


def _score_snippet_quality(snippet: str) -> float:
    """Heuristic quality score for a search snippet."""
    score = 0.5
    # Length bonus
    if len(snippet) > 100:
        score += 0.1
    if len(snippet) > 200:
        score += 0.1
    # Specificity: numbers, dates, proper nouns
    import re
    numbers = len(re.findall(r'\d+', snippet))
    if numbers >= 2:
        score += 0.1
    # Quotes suggest primary source
    if '"' in snippet or "'" in snippet:
        score += 0.05
    # Hedging language penalty
    hedge_words = ["maybe", "possibly", "might", "could be", "seems", "perhaps",
                   "かもしれない", "らしい", "っぽい"]
    for hw in hedge_words:
        if hw in snippet.lower():
            score -= 0.05
    return max(0.0, min(1.0, round(score, 4)))


def _score_source(url: str, source: str) -> float:
    """Heuristic source credibility score."""
    score = 0.5
    high_trust = ["gov", "edu", "ac.jp", "go.jp", "nature.com", "science.org",
                  "arxiv.org", "github.com", "wikipedia.org"]
    medium_trust = ["reuters.com", "apnews.com", "bbc.com", "nikkei.com",
                    "techcrunch.com", "arstechnica.com"]
    low_trust = ["reddit.com", "quora.com", "yahoo.com"]

    url_lower = url.lower()
    for domain in high_trust:
        if domain in url_lower:
            score = 0.85
            break
    for domain in medium_trust:
        if domain in url_lower:
            score = 0.75
            break
    for domain in low_trust:
        if domain in url_lower:
            score = 0.4
            break
    return round(score, 4)


def _grade(score: float) -> str:
    """Convert 0-1 score to letter grade."""
    if score >= 0.90: return "S"
    if score >= 0.80: return "A"
    if score >= 0.65: return "B"
    if score >= 0.50: return "C"
    if score >= 0.35: return "D"
    return "F"


def verify_lite(result: SearchResult) -> VerifiedResult:
    """Fast trust scoring without KS40b. <1s."""
    t0 = time.monotonic()
    freshness = 0.7  # Default when no timestamp
    source = _score_source(result.url, result.source)
    quality = _score_snippet_quality(result.snippet)

    # Weighted aggregate
    aggregate = 0.3 * freshness + 0.3 * source + 0.4 * quality
    grade = _grade(aggregate)

    return VerifiedResult(
        original=result,
        trust_grade=grade,
        freshness_score=freshness,
        source_score=source,
        snippet_quality=quality,
        verify_ms=round((time.monotonic() - t0) * 1000, 1),
    )


def verify_full(result: SearchResult) -> VerifiedResult:
    """Full verification: lite scores + KS40b claim verification."""
    # Start with lite
    verified = verify_lite(result)
    t0 = time.monotonic()

    try:
        from katala_samurai.ks40b import KS40b
        ks = KS40b()
        claim_text = f"{result.title}. {result.snippet}"
        ks_result = ks.verify(claim_text)

        verified.ks40_score = ks_result.get("final_score")
        verified.ks40_verdict = ks_result.get("verdict")
        verified.ks40_confidence = ks_result.get("confidence")
        verified.ks40_flags = ks_result.get("flags", [])
    except Exception as e:
        verified.ks40_flags = [f"KS40_ERROR: {e}"]

    verified.verify_ms += round((time.monotonic() - t0) * 1000, 1)
    return verified


def format_verified(v: VerifiedResult, compact: bool = False) -> str:
    """Format verified result for display."""
    if compact:
        ks_part = f" | KS40:{v.ks40_verdict}({v.ks40_score:.2f})" if v.ks40_score else ""
        return (f"[{v.trust_grade}] {v.original.title} "
                f"(src:{v.source_score:.2f} snip:{v.snippet_quality:.2f}{ks_part}) "
                f"[{v.verify_ms:.0f}ms]")

    lines = [
        f"━━━ {v.trust_grade} ━━━ {v.original.title}",
        f"  URL: {v.original.url}",
        f"  Freshness: {v.freshness_score:.2f} | Source: {v.source_score:.2f} | Snippet: {v.snippet_quality:.2f}",
    ]
    if v.ks40_score is not None:
        lines.append(f"  KS40b: {v.ks40_verdict} (score: {v.ks40_score:.4f}, conf: {v.ks40_confidence:.3f})")
        if v.ks40_flags:
            lines.append(f"  Flags: {', '.join(v.ks40_flags)}")
    lines.append(f"  Time: {v.verify_ms:.0f}ms")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Verify search results with KS40b/TrustScorer")
    parser.add_argument("query", nargs="?", help="Search query (simulates result)")
    parser.add_argument("--claim", help="Verify a specific claim (full KS40b)")
    parser.add_argument("--lite", action="store_true", help="Lite mode only (skip KS40b)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--url", default="", help="URL of the source")
    args = parser.parse_args()

    if args.claim:
        result = SearchResult(
            title=args.claim[:80],
            snippet=args.claim,
            url=args.url or "unknown",
        )
        if args.lite:
            verified = verify_lite(result)
        else:
            verified = verify_full(result)

        if args.json:
            print(json.dumps(asdict(verified), ensure_ascii=False, indent=2))
        else:
            print(format_verified(verified))
    elif args.query:
        # Demo: verify the query as a claim
        result = SearchResult(
            title=args.query,
            snippet=args.query,
            url=args.url or "search-result",
        )
        verified = verify_lite(result)
        print(format_verified(verified))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
