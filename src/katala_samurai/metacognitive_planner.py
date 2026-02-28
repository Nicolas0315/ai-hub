"""
Metacognitive Planner — Strategic verification planning before execution.

PhD researchers don't just "run all tests" — they:
  1) Classify the claim type (causal? statistical? definitional? empirical?)
  2) Predict which layers will be most informative
  3) Allocate effort proportionally
  4) Set success/failure criteria BEFORE running
  5) Plan fallback strategies if primary approach fails
  6) Estimate confidence bounds BEFORE seeing evidence

Target: Metacognitive Planning 55% → 90%+

Design: Youta Hilono, 2026-02-28
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# ── Claim Type Classifier (non-LLM, pattern-based) ──

_CLAIM_PATTERNS = {
    "causal": [
        r"\bcaus(es?|ed|ing|al)\b", r"\bleads?\s+to\b", r"\bresults?\s+in\b",
        r"\bbecause\b", r"\bdue\s+to\b", r"\beffect\s+of\b", r"\btrigger",
        r"\binduc(es?|ed)\b", r"\bproduc(es?|ed)\b.*\beffect\b",
    ],
    "statistical": [
        r"\bp[\-\s]?value\b", r"\bsignifican(t|ce)\b", r"\bcorrelat",
        r"\bsample\s+size\b", r"\bn\s*=\s*\d+", r"\beffect\s+size\b",
        r"\bconfidence\s+interval\b", r"\bregression\b", r"\bstandard\s+dev",
        r"\bp\s*[<>=]\s*0\.\d+", r"\bd\s*=\s*\d+\.\d+",
    ],
    "definitional": [
        r"\bis\s+(defined|the)\b", r"\bmeans?\s+that\b", r"\brefers?\s+to\b",
        r"\bby\s+definition\b", r"\bis\s+known\s+as\b",
    ],
    "empirical": [
        r"\bstudy\b", r"\bresearch\b", r"\bexperiment\b", r"\bobserv(e|ed|ation)\b",
        r"\bdata\s+show", r"\bevidence\b", r"\bmeasur(e|ed|ement)\b",
    ],
    "logical": [
        r"\btherefore\b", r"\bthus\b", r"\bhence\b", r"\bit\s+follows\b",
        r"\bif\s+.*\bthen\b", r"\bnecessarily\b", r"\bcontradiction\b",
    ],
    "normative": [
        r"\bshould\b", r"\bmust\b", r"\bought\b", r"\bbetter\s+to\b",
        r"\bethical\b", r"\bmoral\b", r"\bright\s+to\b",
    ],
    "historical": [
        r"\bin\s+\d{3,4}\b", r"\bcentury\b", r"\bhistor(y|ical)\b",
        r"\bfounded\b", r"\binvent(ed|ion)\b", r"\bdiscover(ed|y)\b",
    ],
}


def classify_claim(text: str) -> Dict[str, float]:
    """Classify claim type by pattern matching. Returns type→confidence map."""
    text_lower = text.lower()
    scores = {}
    
    for ctype, patterns in _CLAIM_PATTERNS.items():
        hits = sum(1 for p in patterns if re.search(p, text_lower))
        if hits > 0:
            scores[ctype] = min(1.0, hits / max(3, len(patterns) * 0.4))
    
    if not scores:
        scores["unknown"] = 1.0
    
    # Normalize
    total = sum(scores.values())
    return {k: round(v/total, 3) for k, v in sorted(scores.items(), key=lambda x: -x[1])}


# ── Layer Effectiveness Matrix ──
# Which layers are most informative for each claim type?

_LAYER_EFFECTIVENESS = {
    "causal":       {"L5_causal": 0.95, "L3_analogy": 0.7, "L4_meta": 0.6, "L6_stat": 0.5, "L7_adv": 0.8, "L2_domain": 0.5, "L1_formal": 0.3},
    "statistical":  {"L6_stat": 0.95, "L7_adv": 0.8, "L4_meta": 0.5, "L1_formal": 0.4, "L5_causal": 0.3, "L3_analogy": 0.2, "L2_domain": 0.3},
    "definitional": {"L1_formal": 0.9, "L2_domain": 0.8, "L3_analogy": 0.5, "L4_meta": 0.4, "L7_adv": 0.3, "L5_causal": 0.1, "L6_stat": 0.1},
    "empirical":    {"L4_meta": 0.8, "L6_stat": 0.7, "L7_adv": 0.7, "L5_causal": 0.6, "L2_domain": 0.6, "L1_formal": 0.4, "L3_analogy": 0.5},
    "logical":      {"L1_formal": 0.95, "L7_adv": 0.8, "L3_analogy": 0.6, "L4_meta": 0.5, "L5_causal": 0.4, "L2_domain": 0.3, "L6_stat": 0.2},
    "normative":    {"L7_adv": 0.9, "L4_meta": 0.7, "L2_domain": 0.5, "L3_analogy": 0.4, "L1_formal": 0.3, "L5_causal": 0.3, "L6_stat": 0.1},
    "historical":   {"L2_domain": 0.9, "L4_meta": 0.7, "L1_formal": 0.5, "L7_adv": 0.5, "L3_analogy": 0.4, "L5_causal": 0.3, "L6_stat": 0.2},
    "unknown":      {"L1_formal": 0.5, "L2_domain": 0.5, "L3_analogy": 0.5, "L4_meta": 0.5, "L5_causal": 0.5, "L6_stat": 0.5, "L7_adv": 0.5},
}


def _estimate_difficulty(text: str) -> Tuple[str, float]:
    """Estimate verification difficulty."""
    length = len(text.split())
    
    # Multiple claims?
    conjunctions = len(re.findall(r'\b(and|also|furthermore|moreover|additionally)\b', text.lower()))
    negations = len(re.findall(r'\b(not|never|no|neither|without)\b', text.lower()))
    qualifiers = len(re.findall(r'\b(some|most|often|usually|generally|sometimes|rarely)\b', text.lower()))
    
    score = 0.3  # baseline
    score += min(0.2, length / 100)       # longer = harder
    score += min(0.15, conjunctions * 0.05) # compound claims
    score += min(0.15, negations * 0.05)    # negation adds difficulty
    score += min(0.2, qualifiers * 0.07)    # vague qualifiers
    
    score = min(1.0, score)
    
    if score < 0.35:
        return "LOW", score
    elif score < 0.6:
        return "MEDIUM", score
    else:
        return "HIGH", score


def plan_verification(text: str) -> Dict[str, Any]:
    """Create a strategic verification plan BEFORE executing any layers.
    
    This is what PhD researchers do: think about HOW to verify before verifying.
    """
    # 1) Classify
    types = classify_claim(text)
    primary_type = list(types.keys())[0]
    
    # 2) Estimate difficulty
    difficulty_label, difficulty_score = _estimate_difficulty(text)
    
    # 3) Layer priority
    effectiveness = {}
    for ctype, weight in types.items():
        if ctype in _LAYER_EFFECTIVENESS:
            for layer, eff in _LAYER_EFFECTIVENESS[ctype].items():
                effectiveness[layer] = effectiveness.get(layer, 0) + eff * weight
    
    sorted_layers = sorted(effectiveness.items(), key=lambda x: -x[1])
    priority_layers = [l for l, s in sorted_layers if s > 0.3]
    skip_layers = [l for l, s in sorted_layers if s <= 0.3]
    
    # 4) Pre-set success/failure criteria
    if primary_type in ("causal", "statistical"):
        success_threshold = 0.7
        failure_threshold = 0.3
    elif primary_type in ("definitional", "logical"):
        success_threshold = 0.8
        failure_threshold = 0.2
    else:
        success_threshold = 0.65
        failure_threshold = 0.35
    
    # 5) Expected confidence range (prior estimate)
    if primary_type == "definitional":
        expected_range = [0.6, 0.95]
    elif primary_type in ("causal", "statistical"):
        expected_range = [0.3, 0.8]
    elif primary_type == "normative":
        expected_range = [0.2, 0.6]
    else:
        expected_range = [0.3, 0.7]
    
    # 6) Fallback strategy
    fallbacks = []
    if primary_type == "causal" and "L5_causal" in [l for l, _ in sorted_layers[:3]]:
        fallbacks.append("If L5 inconclusive → escalate to multi-step intervention (KS34a deep)")
    if "L6_stat" in [l for l, _ in sorted_layers[:3]]:
        fallbacks.append("If L6 finds issues → check if sample size is the root cause before rejecting")
    if difficulty_label == "HIGH":
        fallbacks.append("If all layers disagree → output EXPLORING with full uncertainty range")
    fallbacks.append("If confidence within dead zone (0.4-0.6) → force L7 adversarial regardless of skip rules")
    
    # 7) Effort allocation (for parallel pipeline optimization)
    effort = {}
    total_eff = sum(s for _, s in sorted_layers)
    for layer, score in sorted_layers:
        effort[layer] = round(score / total_eff, 3)
    
    return {
        "claim_types": types,
        "primary_type": primary_type,
        "difficulty": {"label": difficulty_label, "score": round(difficulty_score, 3)},
        "layer_priority": [l for l, _ in sorted_layers],
        "priority_layers": priority_layers,
        "skip_candidates": skip_layers,
        "effort_allocation": effort,
        "criteria": {
            "success_threshold": success_threshold,
            "failure_threshold": failure_threshold,
            "expected_range": expected_range,
        },
        "fallback_strategies": fallbacks,
        "plan_summary": (
            f"Type: {primary_type} ({types[primary_type]:.0%}) | "
            f"Difficulty: {difficulty_label} | "
            f"Focus: {', '.join(priority_layers[:3])} | "
            f"Expected: {expected_range[0]:.0%}-{expected_range[1]:.0%}"
        ),
    }
