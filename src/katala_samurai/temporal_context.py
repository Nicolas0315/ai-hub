"""
R_temporal Phase 1: Temporal Context Verification

Estimates when knowledge in a claim was current, and whether it's still valid.

Problem:
  LLMs have training data cutoffs. A claim verified against 2024 data
  may be wrong in 2026. "GPT-4 is the best model" was true in 2023,
  not in 2026.

Solution:
  Phase 1 (this module): Heuristic + optional LLM estimation
    - Extract temporal signals from claim text
    - Detect knowledge that's likely time-sensitive
    - Estimate freshness score with decay function
    - Flag claims needing temporal verification

  Phase 2 (future): External data sources for ground truth
    - Live API checks, news feeds, version registries

Architecture:
  claim → temporal_signal_extraction → freshness_estimation → decay_score
    ↕                                    ↕
  LLM (optional)                    knowledge_domains
    "When was this knowledge current?"   (domain → half-life mapping)

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import re
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


# ════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════

# Current reference date (updated per release)
REFERENCE_YEAR = 2026
REFERENCE_MONTH = 3

# Knowledge domain half-lives (years) — how fast knowledge decays
DOMAIN_HALF_LIFE = {
    # Fast-moving domains
    "ai_ml": 0.5,           # AI/ML: changes every 6 months
    "software": 1.0,        # Software versions: ~1 year
    "technology": 1.0,      # Tech products: ~1 year
    "politics": 0.5,        # Political landscape: ~6 months
    "sports": 0.25,         # Sports results: ~3 months
    "stock_market": 0.08,   # Stock prices: ~1 month
    "social_media": 0.5,    # Social media trends: ~6 months
    "cybersecurity": 0.5,   # Security: ~6 months

    # Medium-moving domains
    "medicine": 2.0,        # Medical knowledge: ~2 years
    "law": 2.0,             # Legal frameworks: ~2 years
    "economics": 1.5,       # Economic conditions: ~1.5 years
    "demographics": 3.0,    # Population data: ~3 years
    "geography": 5.0,       # Geographic facts: ~5 years (borders change)

    # Slow-moving domains
    "physics": 20.0,        # Physics: ~20 years
    "mathematics": 100.0,   # Math: essentially eternal
    "chemistry": 15.0,      # Chemistry: ~15 years
    "biology": 5.0,         # Biology: ~5 years (genomics era)
    "history": 50.0,        # Historical facts: very stable
    "philosophy": 100.0,    # Philosophy: eternal

    # Default
    "unknown": 3.0,         # Unknown domain: ~3 years
}

# Temporal signal patterns
YEAR_PATTERN = re.compile(r'\b(19\d{2}|20[0-3]\d)\b')
MONTH_YEAR_PATTERN = re.compile(
    r'\b(January|February|March|April|May|June|July|August|'
    r'September|October|November|December)\s+(19\d{2}|20[0-3]\d)\b', re.I
)
RELATIVE_TIME_PATTERN = re.compile(
    r'\b(currently|now|today|recently|latest|newest|modern|'
    r'as of|this year|this month|at present)\b', re.I
)
SUPERLATIVE_PATTERN = re.compile(
    r'\b(best|fastest|largest|most popular|leading|dominant|'
    r'top|state-of-the-art|SOTA|cutting-edge)\b', re.I
)
VERSION_PATTERN = re.compile(
    r'\b(?:v(?:ersion)?\s*)?(\d+\.\d+(?:\.\d+)?)\b'
)

# Domain detection keywords
DOMAIN_KEYWORDS = {
    "ai_ml": ["gpt", "llm", "transformer", "neural", "model", "training",
              "inference", "benchmark", "fine-tune", "embedding", "token",
              "diffusion", "bert", "claude", "gemini", "openai", "anthropic",
              "mistral", "llama", "qwen", "deepseek"],
    "software": ["version", "release", "update", "deprecated", "api",
                 "framework", "library", "package", "npm", "pip", "cargo",
                 "python", "rust", "javascript", "node", "react", "vue"],
    "technology": ["smartphone", "processor", "gpu", "chip", "device",
                   "hardware", "apple", "google", "microsoft", "samsung",
                   "nvidia", "amd", "intel"],
    "politics": ["president", "election", "government", "policy",
                 "legislation", "congress", "parliament", "minister",
                 "political", "vote", "democrat", "republican"],
    "sports": ["championship", "tournament", "season", "score",
               "record", "medal", "olympic", "world cup", "league"],
    "stock_market": ["stock", "market", "price", "trading", "nasdaq",
                     "nyse", "index", "portfolio", "dividend", "ipo"],
    "medicine": ["treatment", "drug", "therapy", "clinical", "disease",
                 "vaccine", "diagnosis", "symptom", "patient", "medical"],
    "economics": ["gdp", "inflation", "unemployment", "economy",
                  "growth", "recession", "interest rate", "trade"],
    "physics": ["gravity", "quantum", "relativity", "particle",
                "thermodynamic", "electromagnetic", "entropy", "photon"],
    "mathematics": ["theorem", "proof", "conjecture", "equation",
                    "polynomial", "integral", "topology", "algebra"],
    "chemistry": ["molecule", "reaction", "element", "compound",
                  "catalyst", "bond", "electron", "atom"],
    "biology": ["gene", "protein", "cell", "organism", "evolution",
                "species", "dna", "rna", "genome", "mutation"],
    "history": ["century", "ancient", "medieval", "colonial",
                "war", "revolution", "civilization", "dynasty"],
}


# ════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════

class TemporalRisk(Enum):
    NONE = "none"           # Timeless claim
    LOW = "low"             # Slow-moving domain
    MEDIUM = "medium"       # Medium-moving domain
    HIGH = "high"           # Fast-moving domain, likely outdated
    CRITICAL = "critical"   # Specific date reference that's old


@dataclass
class TemporalSignal:
    """A temporal indicator found in the text."""
    signal_type: str        # "year", "relative", "superlative", "version"
    text: str               # The matched text
    position: int           # Character position in claim
    year: Optional[int] = None  # Extracted year if applicable


@dataclass
class TemporalVerdict:
    """Result of temporal context verification."""
    freshness_score: float      # 0.0 = definitely outdated, 1.0 = definitely current
    risk_level: TemporalRisk
    domain: str                 # Detected knowledge domain
    domain_half_life: float     # Years
    signals: List[TemporalSignal]
    estimated_knowledge_year: Optional[int]  # When this knowledge was likely current
    age_years: float            # Estimated age of knowledge
    decay_factor: float         # Exponential decay factor applied
    warnings: List[str]
    recommendation: str         # "accept", "verify_externally", "likely_outdated"


# ════════════════════════════════════════════
# Domain Detection
# ════════════════════════════════════════════

def detect_domain(text: str) -> str:
    """Detect the knowledge domain of a claim."""
    text_lower = text.lower()
    scores: Dict[str, int] = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[domain] = score

    if not scores:
        return "unknown"

    return max(scores, key=scores.get)


# ════════════════════════════════════════════
# Temporal Signal Extraction
# ════════════════════════════════════════════

def extract_temporal_signals(text: str) -> List[TemporalSignal]:
    """Extract all temporal indicators from claim text."""
    signals = []

    # Explicit years
    for m in YEAR_PATTERN.finditer(text):
        year = int(m.group(1))
        signals.append(TemporalSignal(
            signal_type="year", text=m.group(), position=m.start(), year=year
        ))

    # Month + Year
    for m in MONTH_YEAR_PATTERN.finditer(text):
        year = int(m.group(2))
        signals.append(TemporalSignal(
            signal_type="month_year", text=m.group(), position=m.start(), year=year
        ))

    # Relative time ("currently", "now", etc.)
    for m in RELATIVE_TIME_PATTERN.finditer(text):
        signals.append(TemporalSignal(
            signal_type="relative", text=m.group(), position=m.start()
        ))

    # Superlatives ("best", "fastest", etc.) — time-sensitive
    for m in SUPERLATIVE_PATTERN.finditer(text):
        signals.append(TemporalSignal(
            signal_type="superlative", text=m.group(), position=m.start()
        ))

    # Version numbers — imply specific software state
    for m in VERSION_PATTERN.finditer(text):
        signals.append(TemporalSignal(
            signal_type="version", text=m.group(), position=m.start()
        ))

    return signals


# ════════════════════════════════════════════
# Freshness Estimation
# ════════════════════════════════════════════

def estimate_knowledge_year(signals: List[TemporalSignal], domain: str) -> Optional[int]:
    """Estimate when the knowledge in the claim was current.

    Priority:
    1. Explicit year mentions (most recent one)
    2. Relative time markers → assume current
    3. Version numbers → map to release dates (simplified)
    4. No signals → assume training data cutoff (2024)
    """
    # Explicit years
    years = [s.year for s in signals if s.year is not None]
    if years:
        return max(years)  # Most recent year mentioned

    # Relative time → assume current
    relative = [s for s in signals if s.signal_type == "relative"]
    if relative:
        return REFERENCE_YEAR

    # Version numbers → heuristic (assume recent if version > 3)
    versions = [s for s in signals if s.signal_type == "version"]
    if versions:
        return REFERENCE_YEAR - 1  # Assume ~1 year old

    # No temporal signals → depends on domain
    if domain in ("mathematics", "physics", "history", "philosophy"):
        return None  # Timeless

    # Default: assume LLM training cutoff
    return 2024


def compute_decay(age_years: float, half_life: float) -> float:
    """Exponential decay: freshness = 2^(-age/half_life).

    At half_life years old, freshness = 0.5.
    At 2× half_life, freshness = 0.25.
    Rust-accelerated when available (0.11μs/call).
    """
    if age_years <= 0:
        return 1.0
    if half_life <= 0:
        return 0.0
    try:
        import ks_accel
        return ks_accel.temporal_decay(age_years, half_life)
    except (ImportError, AttributeError):
        pass
    return math.pow(2.0, -age_years / half_life)


# ════════════════════════════════════════════
# Main Verifier
# ════════════════════════════════════════════

def verify_temporal_context(
    claim_text: str,
    source_llm: Optional[str] = None,
    evidence: Optional[List[str]] = None,
) -> TemporalVerdict:
    """Verify the temporal context of a claim.

    Parameters
    ----------
    claim_text : str
        The claim to verify temporally.
    source_llm : str, optional
        LLM that generated the claim (for cutoff estimation).
    evidence : list[str], optional
        Evidence sources (may contain temporal info).

    Returns
    -------
    TemporalVerdict
    """
    # 1. Detect domain
    full_text = claim_text
    if evidence:
        full_text += " " + " ".join(evidence[:5])
    domain = detect_domain(full_text)
    half_life = DOMAIN_HALF_LIFE.get(domain, DOMAIN_HALF_LIFE["unknown"])

    # 2. Extract temporal signals
    signals = extract_temporal_signals(claim_text)

    # Also check evidence for year references
    if evidence:
        for ev in evidence[:5]:
            ev_signals = extract_temporal_signals(ev)
            signals.extend(ev_signals)

    # 3. Estimate knowledge year
    knowledge_year = estimate_knowledge_year(signals, domain)

    # 4. Compute age and decay
    if knowledge_year is None:
        # Timeless knowledge
        age_years = 0.0
        decay = 1.0
    else:
        age_years = REFERENCE_YEAR + (REFERENCE_MONTH - 1) / 12 - knowledge_year
        decay = compute_decay(age_years, half_life)

    # 5. Risk assessment
    warnings = []
    has_superlative = any(s.signal_type == "superlative" for s in signals)
    has_relative = any(s.signal_type == "relative" for s in signals)

    if has_superlative:
        # Superlatives are always risky — "best" changes rapidly
        decay *= 0.8
        warnings.append(f"Superlative claim in {domain} domain — prone to change")

    if has_relative and knowledge_year and knowledge_year < REFERENCE_YEAR:
        warnings.append("Uses 'currently/now' but knowledge may be outdated")

    # Source LLM cutoff estimation
    llm_cutoffs = {
        "gpt-4": 2023, "gpt-4o": 2024, "gpt-5": 2025,
        "claude-opus-4-6": 2025, "claude-sonnet-4-6": 2025,
        "gemini-2.0": 2024, "gemini-3-pro": 2025,
        "llama-4": 2025, "qwen-3": 2025,
    }
    if source_llm:
        cutoff = llm_cutoffs.get(source_llm)
        if cutoff and knowledge_year and knowledge_year > cutoff:
            warnings.append(
                f"Claim references {knowledge_year} but {source_llm} "
                f"cutoff is ~{cutoff}"
            )

    # 6. Freshness score
    freshness = round(max(0.0, min(1.0, decay)), 4)

    # 7. Risk level
    if freshness >= 0.8:
        risk = TemporalRisk.NONE
    elif freshness >= 0.5:
        risk = TemporalRisk.LOW
    elif freshness >= 0.25:
        risk = TemporalRisk.MEDIUM
    elif freshness >= 0.1:
        risk = TemporalRisk.HIGH
    else:
        risk = TemporalRisk.CRITICAL

    # 8. Recommendation
    if risk in (TemporalRisk.NONE, TemporalRisk.LOW):
        recommendation = "accept"
    elif risk == TemporalRisk.MEDIUM:
        recommendation = "verify_externally"
    else:
        recommendation = "likely_outdated"

    return TemporalVerdict(
        freshness_score=freshness,
        risk_level=risk,
        domain=domain,
        domain_half_life=half_life,
        signals=signals,
        estimated_knowledge_year=knowledge_year,
        age_years=round(age_years, 2),
        decay_factor=round(decay, 4),
        warnings=warnings,
        recommendation=recommendation,
    )


# ════════════════════════════════════════════
# Integration with KS31e
# ════════════════════════════════════════════

def temporal_score_for_ks31(
    claim_text: str,
    source_llm: Optional[str] = None,
    evidence: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return temporal context score in KS31 format.

    Returns dict compatible with KS31e L5 semantic output.
    """
    verdict = verify_temporal_context(claim_text, source_llm, evidence)

    return {
        "temporal_freshness": verdict.freshness_score,
        "temporal_risk": verdict.risk_level.value,
        "temporal_domain": verdict.domain,
        "temporal_half_life_years": verdict.domain_half_life,
        "knowledge_year": verdict.estimated_knowledge_year,
        "age_years": verdict.age_years,
        "warnings": verdict.warnings,
        "recommendation": verdict.recommendation,
        "signals_found": len(verdict.signals),
    }


# ════════════════════════════════════════════
# Format
# ════════════════════════════════════════════

def format_temporal_verdict(verdict: TemporalVerdict) -> str:
    """Pretty-print temporal verdict."""
    risk_emoji = {
        TemporalRisk.NONE: "🟢",
        TemporalRisk.LOW: "🟡",
        TemporalRisk.MEDIUM: "🟠",
        TemporalRisk.HIGH: "🔴",
        TemporalRisk.CRITICAL: "⛔",
    }
    lines = [
        f"╔══ Temporal Context ══╗",
        f"║ Freshness: {verdict.freshness_score:.2f} {risk_emoji.get(verdict.risk_level, '?')} {verdict.risk_level.value}",
        f"║ Domain: {verdict.domain} (t½ = {verdict.domain_half_life}y)",
    ]
    if verdict.estimated_knowledge_year:
        lines.append(f"║ Knowledge year: ~{verdict.estimated_knowledge_year} (age: {verdict.age_years}y)")
    lines.append(f"║ Recommendation: {verdict.recommendation}")
    if verdict.warnings:
        for w in verdict.warnings:
            lines.append(f"║ ⚠ {w}")
    lines.append("╚" + "═" * 25 + "╝")
    return "\n".join(lines)
