"""
KS33b #2: Content Bridge — bidirectional layer between content understanding and S01-S27.

Creates a new layer that:
  - Takes content_understanding results (negation, roles, implications)
  - Converts them into structured signals S01-S27 can consume
  - Returns S01-S27 formal results back with content annotations
  
Preserves S01-S27 as form-only audit (they don't change).
ContentBridge is the translator between form and meaning.
"""

import re


def content_to_formal_signals(content_result):
    """Convert content understanding into formal propositions for S01-S27.
    
    Content results become additional propositions that S01-S27 can verify formally.
    S01-S27 remain form-only — they verify the structure of the generated propositions.
    """
    signals = []
    
    # Negation → formal propositions
    neg = content_result.get("negation", {})
    if neg.get("counterfactual"):
        signals.append({
            "type": "negation_counterfactual",
            "proposition": neg["counterfactual"],
            "formal_check": "verify_consistency",
            "confidence_modifier": -0.1 if neg["meaning_change_risk"] == "high" else 0.0,
        })
    
    if neg.get("has_double_negation"):
        signals.append({
            "type": "double_negation",
            "proposition": "Double negation detected — resolve to affirmative",
            "formal_check": "verify_logical_equivalence",
            "confidence_modifier": -0.05,
        })
    
    # Semantic roles → formal propositions
    roles = content_result.get("semantic_roles", {})
    for role in roles.get("roles", []):
        if role.get("agent") and role.get("action") and role.get("patient"):
            signals.append({
                "type": "semantic_role",
                "proposition": f"{role['agent']} {role['action']} {role['patient']}",
                "formal_check": "verify_predicate_structure",
                "confidence_modifier": 0.0,
            })
            
            # Quantifier signals
            for mod in role.get("modifiers", []):
                if mod in ("all", "every", "always", "never", "none"):
                    signals.append({
                        "type": "universal_quantifier",
                        "proposition": f"Universal claim: {mod} in '{role['agent']} {role['action']}'",
                        "formal_check": "verify_universal",
                        "confidence_modifier": -0.05,
                    })
    
    # Implications → formal propositions
    impl = content_result.get("implications", {})
    for imp in impl.get("implications", []):
        if imp["type"] == "hedging":
            signals.append({
                "type": "hedging_detected",
                "proposition": f"Hedging language: '{imp['marker']}' — claim may not be definitive",
                "formal_check": "verify_certainty_level",
                "confidence_modifier": -0.08,
            })
        elif imp["type"] == "attribution_distancing":
            signals.append({
                "type": "distancing_detected",
                "proposition": f"Attribution distancing: '{imp['marker']}' — source reliability unknown",
                "formal_check": "verify_source",
                "confidence_modifier": -0.1,
            })
        elif imp["type"] == "concession":
            signals.append({
                "type": "concession_detected",
                "proposition": f"Concession: '{imp['marker']}' — counter-argument acknowledged",
                "formal_check": "verify_both_sides",
                "confidence_modifier": 0.03,  # Slight bonus for acknowledging counter
            })
    
    return signals


def annotate_formal_results(formal_results, content_signals):
    """Annotate S01-S27 formal results with content intelligence.
    
    Does NOT modify S01-S27 behavior. Adds metadata layer on top.
    """
    annotations = []
    total_modifier = 0.0
    
    for signal in content_signals:
        modifier = signal.get("confidence_modifier", 0.0)
        total_modifier += modifier
        annotations.append({
            "type": signal["type"],
            "proposition": signal["proposition"][:80],
            "check": signal["formal_check"],
            "modifier": modifier,
        })
    
    return {
        "annotations": annotations,
        "annotation_count": len(annotations),
        "total_confidence_modifier": round(total_modifier, 3),
        "content_flags": {
            "has_negation_risk": any(a["type"] == "negation_counterfactual" for a in annotations),
            "has_hedging": any(a["type"] == "hedging_detected" for a in annotations),
            "has_distancing": any(a["type"] == "distancing_detected" for a in annotations),
            "has_universal": any(a["type"] == "universal_quantifier" for a in annotations),
        },
    }


def bridge_content(content_result, store=None):
    """Full content bridge pipeline.
    
    content_understanding → formal signals → annotations
    """
    signals = content_to_formal_signals(content_result)
    annotations = annotate_formal_results(None, signals)
    
    result = {
        "signals_generated": len(signals),
        "signals": signals,
        "annotations": annotations,
    }
    
    if store:
        store.write("content_bridge", result)
    
    return result
