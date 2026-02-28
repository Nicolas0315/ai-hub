"""
Layer 7: Adversarial Verifier — Devil's Advocate attack on conclusions.

Generates counter-arguments, tests falsifiability (Popper criterion),
and attacks layer consensus to find fragile conclusions.

Non-LLM: structural pattern matching + logical negation + premise analysis.

Design: Youta Hilono, 2026-02-28
"""

import re
from typing import Dict, Any, List, Optional


# ── Falsifiability patterns ──
_UNFALSIFIABLE = [
    (re.compile(r'\b(?:by\s+definition|tautolog|necessarily\s+true|axiom)\b', re.I),
     "tautological — true by definition, not empirically testable"),
    (re.compile(r'\b(?:some|sometimes|may|might|could|possibly|perhaps)\b', re.I),
     "weak_hedged — too hedged to be falsifiable"),
    (re.compile(r'\b(?:in\s+some\s+sense|metaphorically|loosely\s+speaking)\b', re.I),
     "metaphorical — not a concrete testable claim"),
    (re.compile(r'\b(?:everything|nothing|always|never)\b.*\b(?:everything|nothing|always|never)\b', re.I),
     "double_absolute — contradictory absolutes"),
]

_FALSIFIABLE_SIGNALS = [
    (re.compile(r'\b(?:if\s+.+then|predicts?\s+that|would\s+result\s+in)\b', re.I), "conditional_prediction"),
    (re.compile(r'\b(?:measur|quantif|observe|detect|count)\b', re.I), "measurable"),
    (re.compile(r'\b\d+\.?\d*\s*(?:%|degrees?|kg|mg|ml|cm|km|mph|Hz)\b', re.I), "quantitative"),
]


def check_falsifiability(text: str) -> Dict[str, Any]:
    """Popper criterion: is the claim falsifiable?"""
    unfalsifiable_signals = []
    for pattern, desc in _UNFALSIFIABLE:
        if pattern.search(text):
            unfalsifiable_signals.append(desc)
    
    falsifiable_signals = []
    for pattern, desc in _FALSIFIABLE_SIGNALS:
        if pattern.search(text):
            falsifiable_signals.append(desc)
    
    if unfalsifiable_signals and not falsifiable_signals:
        verdict = "UNFALSIFIABLE"
        score = 0.2
    elif unfalsifiable_signals and falsifiable_signals:
        verdict = "PARTIALLY_FALSIFIABLE"
        score = 0.5
    elif falsifiable_signals:
        verdict = "FALSIFIABLE"
        score = 0.9
    else:
        verdict = "INDETERMINATE"
        score = 0.5
    
    return {
        "verdict": verdict,
        "falsifiability_score": score,
        "unfalsifiable_signals": unfalsifiable_signals,
        "falsifiable_signals": falsifiable_signals,
    }


# ── Premise attack ──
_PREMISE_MARKERS = [
    re.compile(r'\b(?:because|since|as|given\s+that|due\s+to)\s+(.{10,80})', re.I),
    re.compile(r'\b(?:assuming|if\s+we\s+assume|presuppos)\s+(.{10,80})', re.I),
    re.compile(r'(.{10,60})\s+(?:therefore|thus|hence|so)\b', re.I),
]

_HIDDEN_ASSUMPTIONS = [
    (re.compile(r'\b(?:obviously|clearly|of\s+course|everyone\s+knows|it\s+is\s+well\s+known)\b', re.I),
     "appeal_to_obviousness — hidden premise disguised as common knowledge"),
    (re.compile(r'\b(?:naturally|inherently|essentially|fundamentally)\b', re.I),
     "essentialist_assumption — assumes intrinsic nature without evidence"),
    (re.compile(r'\b(?:real|true|actual|genuine)\s+\w+\s+(?:is|are|would)\b', re.I),
     "no_true_scotsman — defining away counterexamples"),
    (re.compile(r'\b(?:common\s+sense|stands\s+to\s+reason|intuitively)\b', re.I),
     "appeal_to_intuition — substituting argument with gut feeling"),
]


def attack_premises(text: str) -> Dict[str, Any]:
    """Identify and attack explicit/hidden premises."""
    explicit_premises = []
    for pattern in _PREMISE_MARKERS:
        for m in pattern.finditer(text):
            premise = m.group(1) if m.lastindex else m.group(0)
            premise = premise.strip(".,;: ")
            if len(premise) > 10:
                explicit_premises.append(premise[:100])
    
    hidden_assumptions = []
    for pattern, desc in _HIDDEN_ASSUMPTIONS:
        if pattern.search(text):
            hidden_assumptions.append(desc)
    
    # Generate counter-premise attacks
    attacks = []
    for premise in explicit_premises[:3]:
        attacks.append({
            "premise": premise,
            "attack": f"What if '{premise[:50]}...' is false?",
            "type": "premise_negation",
        })
    
    for assumption in hidden_assumptions[:3]:
        attacks.append({
            "assumption": assumption.split(" — ")[0],
            "attack": f"Unexamined assumption: {assumption}",
            "type": "hidden_assumption",
        })
    
    return {
        "explicit_premises": len(explicit_premises),
        "hidden_assumptions": hidden_assumptions,
        "attacks_generated": len(attacks),
        "attacks": attacks,
    }


# ── Logical negation ──
def generate_negation(text: str) -> str:
    """Generate the logical negation of a claim."""
    # Simple structural negation
    negations = [
        (re.compile(r'\b(is)\b', re.I), r'is not'),
        (re.compile(r'\b(are)\b', re.I), r'are not'),
        (re.compile(r'\b(does)\b', re.I), r'does not'),
        (re.compile(r'\b(do)\b', re.I), r'do not'),
        (re.compile(r'\b(can)\b', re.I), r'cannot'),
        (re.compile(r'\b(will)\b', re.I), r'will not'),
        (re.compile(r'\b(causes?)\b', re.I), r'does not cause'),
        (re.compile(r'\b(prevents?)\b', re.I), r'does not prevent'),
        (re.compile(r'\b(increases?)\b', re.I), r'does not increase'),
        (re.compile(r'\b(decreases?)\b', re.I), r'does not decrease'),
        # Already negated → remove negation
        (re.compile(r'\b(is\s+not|are\s+not|does\s+not|do\s+not|cannot|will\s+not)\b', re.I), lambda m: m.group().replace(" not", "").replace("not ", "").replace("cannot", "can")),
    ]
    
    result = text
    for pattern, repl in negations:
        if pattern.search(result):
            result = pattern.sub(repl, result, count=1)
            break
    
    return result if result != text else f"It is not the case that: {text}"


# ── Consensus attack ──
def attack_consensus(layer_results: Dict[str, Any]) -> Dict[str, Any]:
    """Attack layer consensus — find fragile agreement."""
    verdicts = {}
    confidences = {}
    
    for key, val in layer_results.items():
        if isinstance(val, dict):
            if "verdict" in val:
                verdicts[key] = val["verdict"]
            if "confidence" in val:
                confidences[key] = val["confidence"]
    
    # Check for false unanimity
    unique_verdicts = set(verdicts.values())
    
    attacks = []
    if len(unique_verdicts) == 1 and len(verdicts) >= 3:
        attacks.append({
            "type": "false_unanimity",
            "detail": f"All {len(verdicts)} layers agree ({list(unique_verdicts)[0]}) — possible echo chamber",
            "severity": "info",
        })
    
    # Check for low-confidence agreement
    low_conf_agreers = [k for k, v in confidences.items() if v < 0.5]
    if len(low_conf_agreers) > len(confidences) / 2:
        attacks.append({
            "type": "weak_consensus",
            "detail": f"{len(low_conf_agreers)}/{len(confidences)} layers have confidence < 0.5",
            "severity": "warning",
        })
    
    # Confidence spread
    if confidences:
        conf_vals = list(confidences.values())
        spread = max(conf_vals) - min(conf_vals)
        if spread > 0.4:
            attacks.append({
                "type": "high_disagreement",
                "detail": f"Confidence spread = {spread:.2f} (max-min). Layers disagree significantly",
                "severity": "warning",
            })
    
    return {
        "consensus_attacks": attacks,
        "verdict_diversity": len(unique_verdicts),
        "confidence_spread": max(confidences.values()) - min(confidences.values()) if confidences else 0,
    }


def run_adversarial_verification(text: str, layer_results: Dict = None, store=None) -> Dict[str, Any]:
    """Full L7 adversarial verification."""
    
    # 1. Falsifiability
    falsifiability = check_falsifiability(text)
    
    # 2. Premise attack
    premises = attack_premises(text)
    
    # 3. Logical negation
    negation = generate_negation(text)
    
    # 4. Consensus attack
    consensus = attack_consensus(layer_results or {})
    
    # Scoring
    issues = []
    if falsifiability["verdict"] == "UNFALSIFIABLE":
        issues.append(("unfalsifiable", -0.15))
    if premises["hidden_assumptions"]:
        issues.append(("hidden_assumptions", -0.03 * min(len(premises["hidden_assumptions"]), 3)))
    if any(a["severity"] == "warning" for a in consensus.get("consensus_attacks", [])):
        issues.append(("weak_consensus", -0.05))
    
    bonuses = []
    if falsifiability["verdict"] == "FALSIFIABLE" and not premises["hidden_assumptions"]:
        bonuses.append(("clean_falsifiable", 0.05))
    
    total_mod = sum(v for _, v in issues) + sum(v for _, v in bonuses)
    total_mod = max(-0.25, min(0.1, total_mod))
    
    result = {
        "falsifiability": falsifiability,
        "premise_attacks": premises,
        "negation": negation[:200],
        "consensus": consensus,
        "issues": issues,
        "bonuses": bonuses,
        "confidence_modifier": round(total_mod, 4),
        "verdict": (
            "ADVERSARIAL_PASS" if not issues
            else "ADVERSARIAL_CONCERNS" if total_mod > -0.1
            else "ADVERSARIAL_FAIL"
        ),
    }
    
    if store:
        try:
            store.write("L7_adversarial_verification", result)
        except (ValueError, Exception):
            pass
    
    return result
