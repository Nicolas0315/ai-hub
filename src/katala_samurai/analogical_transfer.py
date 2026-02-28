"""
Analogical Transfer Engine — maps unknown-domain structures to known patterns.

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Principle: "Solve unknown problems by structural mapping to known domains."
  Unknown claim → extract structure → match template → apply known verification rules

Non-LLM: regex patterns + structural templates. No accumulation.
"""

import re
from collections import namedtuple

# ─── Structural Templates ───────────────────────────────────────────────────

StructuralMatch = namedtuple("StructuralMatch", ["template", "slots", "confidence", "known_analogs"])

# Template patterns: each extracts structured slots from text
_TEMPLATES = [
    {
        "name": "agent_action_object_result",
        "description": "X does Y to Z, producing W",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+)?)\s+(causes?|produces?|creates?|generates?|induces?|triggers?)\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+)?)\s+(leads?\s+to|results?\s+in)\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(enables?|allows?|facilitates?|permits?)\s+(.+)', re.I),
        ],
        "slots": ["agent", "action", "result"],
        "known_analogs": [
            {"domain": "physics", "example": "Heat causes expansion", "rule": "causal_direct"},
            {"domain": "biology", "example": "Virus causes disease", "rule": "causal_direct"},
            {"domain": "chemistry", "example": "Catalyst produces reaction", "rule": "causal_enabling"},
        ],
        "verification_rules": ["causal_chain_valid", "agent_capable_of_action", "result_follows_from_action"],
    },
    {
        "name": "transformation",
        "description": "X converts/transforms Y into Z",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(converts?|transforms?|changes?|turns?)\s+(.+?)\s+into\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(metabolizes?|synthesizes?|breaks?\s+down)\s+(.+)', re.I),
        ],
        "slots": ["agent", "action", "input", "output"],
        "known_analogs": [
            {"domain": "chemistry", "example": "Enzyme converts substrate into product", "rule": "transformation"},
            {"domain": "physics", "example": "Generator converts motion into electricity", "rule": "transformation"},
            {"domain": "biology", "example": "Photosynthesis converts light into energy", "rule": "transformation"},
        ],
        "verification_rules": ["conservation_principle", "agent_has_mechanism", "input_output_compatible"],
    },
    {
        "name": "conditional",
        "description": "If X then Y / When X, Y occurs",
        "patterns": [
            re.compile(r'(?:if|when|whenever)\s+(.+?)(?:\s*,\s*(?:then\s+)?|\s+then\s+)(.+)', re.I),
            re.compile(r'(.+?)\s+(?:implies|entails|means\s+that)\s+(.+)', re.I),
        ],
        "slots": ["condition", "consequence"],
        "known_analogs": [
            {"domain": "logic", "example": "If P then Q (modus ponens)", "rule": "conditional_logic"},
            {"domain": "physics", "example": "If temperature rises, pressure increases", "rule": "conditional_physical"},
        ],
        "verification_rules": ["condition_possible", "consequence_follows", "no_hidden_conditions"],
    },
    {
        "name": "classification",
        "description": "X is a type/kind of Y",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is|are)\s+(?:a\s+)?(?:type|kind|form|class|category|member)\s+of\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is|are)\s+(?:a\s+)?(.+?)(?:\s+that|\s+which|\.)', re.I),
            re.compile(r'(?:all|every)\s+(\w+(?:\s+\w+)?)\s+(?:is|are)\s+(.+)', re.I),
        ],
        "slots": ["instance", "category"],
        "known_analogs": [
            {"domain": "biology", "example": "Whale is a mammal", "rule": "taxonomic"},
            {"domain": "mathematics", "example": "Square is a rectangle", "rule": "set_membership"},
        ],
        "verification_rules": ["category_exists", "instance_has_category_properties", "taxonomy_consistent"],
    },
    {
        "name": "composition",
        "description": "X is part of / contains Y",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is\s+)?(?:part|component|element|constituent)\s+of\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:contains?|comprises?|consists?\s+of|includes?)\s+(.+)', re.I),
        ],
        "slots": ["part", "whole"],
        "known_analogs": [
            {"domain": "biology", "example": "Cell is part of tissue", "rule": "mereological"},
            {"domain": "chemistry", "example": "Atom contains protons", "rule": "mereological"},
        ],
        "verification_rules": ["whole_exists", "part_fits_whole", "no_circular_composition"],
    },
    {
        "name": "prevention_inhibition",
        "description": "X prevents/inhibits/blocks Y",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(prevents?|inhibits?|blocks?|suppresses?|stops?)\s+(.+)', re.I),
        ],
        "slots": ["inhibitor", "action", "target"],
        "known_analogs": [
            {"domain": "medicine", "example": "Vaccine prevents infection", "rule": "inhibition"},
            {"domain": "chemistry", "example": "Inhibitor blocks enzyme", "rule": "inhibition"},
        ],
        "verification_rules": ["inhibitor_has_mechanism", "target_is_inhibitable", "mechanism_plausible"],
    },
    {
        "name": "comparison",
        "description": "X is more/less/similar/different than Y",
        "patterns": [
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is\s+)?(?:more|less|greater|smaller|faster|slower|higher|lower|\w+er)\s+than\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is\s+)?(?:similar|identical|equivalent|comparable)\s+to\s+(.+)', re.I),
            re.compile(r'(\b\w+(?:\s+\w+){0,2})\s+(?:is\s+)?(?:different|distinct|unlike)\s+(?:from\s+)?(.+)', re.I),
        ],
        "slots": ["entity_a", "entity_b"],
        "known_analogs": [
            {"domain": "physics", "example": "Iron is denser than aluminum", "rule": "ordinal_comparison"},
            {"domain": "mathematics", "example": "Pi is greater than 3", "rule": "numeric_comparison"},
        ],
        "verification_rules": ["both_entities_exist", "comparison_dimension_valid", "ordering_consistent"],
    },
    {
        "name": "process_sequence",
        "description": "First X, then Y, finally Z",
        "patterns": [
            re.compile(r'(?:first|initially)\s+(.+?)(?:\s*[,;]\s*|\s+)(?:then|next|subsequently)\s+(.+?)(?:\s*[,;]\s*|\s+)(?:finally|lastly|ultimately)\s+(.+)', re.I),
            re.compile(r'(.+?)\s+(?:followed\s+by|and\s+then)\s+(.+)', re.I),
        ],
        "slots": ["step_1", "step_2"],
        "known_analogs": [
            {"domain": "biology", "example": "DNA replication → transcription → translation", "rule": "sequential_process"},
            {"domain": "chemistry", "example": "Reactants → intermediate → products", "rule": "sequential_process"},
        ],
        "verification_rules": ["steps_ordered", "each_step_possible", "transitions_valid"],
    },
]


# ─── Template Matching ──────────────────────────────────────────────────────

def match_templates(text):
    """Match text against all structural templates.
    
    Returns list of StructuralMatch (may be multiple matches).
    """
    matches = []
    
    for template in _TEMPLATES:
        for pattern in template["patterns"]:
            m = pattern.search(text)
            if m:
                groups = [g.strip().rstrip(".,;:") for g in m.groups() if g]
                slots = {}
                for i, slot_name in enumerate(template["slots"]):
                    if i < len(groups):
                        slots[slot_name] = groups[i]
                
                matches.append(StructuralMatch(
                    template=template["name"],
                    slots=slots,
                    confidence=0.8 if len(slots) >= 2 else 0.5,
                    known_analogs=template["known_analogs"],
                ))
                break  # One match per template
    
    return matches


# ─── Verification Rule Application ─────────────────────────────────────────

def _check_rule(rule, slots, domain_propositions=None):
    """Apply a verification rule to extracted slots.
    
    Non-LLM: structural checks based on slot content and domain knowledge.
    """
    props = domain_propositions or []
    prop_texts = " ".join(p.get("text", "") for p in props).lower()
    
    if rule == "causal_chain_valid":
        agent = slots.get("agent", "").lower()
        result = slots.get("result", "").lower()
        # Check if domain knowledge links agent to result
        if agent in prop_texts and result in prop_texts:
            return {"rule": rule, "pass": True, "reason": "domain knowledge supports causal link"}
        return {"rule": rule, "pass": None, "reason": "insufficient domain knowledge"}
    
    elif rule == "agent_capable_of_action":
        agent = slots.get("agent", "").lower()
        action = slots.get("action", "").lower()
        if agent in prop_texts:
            return {"rule": rule, "pass": True, "reason": "agent found in domain knowledge"}
        return {"rule": rule, "pass": None, "reason": "agent not found in domain knowledge"}
    
    elif rule == "category_exists":
        category = slots.get("category", "").lower()
        if category in prop_texts:
            return {"rule": rule, "pass": True, "reason": "category confirmed by domain knowledge"}
        return {"rule": rule, "pass": None, "reason": "category not in domain knowledge"}
    
    elif rule == "conservation_principle":
        # Transformations should preserve something
        inp = slots.get("input", "").lower()
        out = slots.get("output", "").lower()
        if inp and out and inp != out:
            return {"rule": rule, "pass": True, "reason": "input differs from output (transformation plausible)"}
        return {"rule": rule, "pass": None, "reason": "cannot verify conservation"}
    
    elif rule == "condition_possible":
        condition = slots.get("condition", "").lower()
        if condition and len(condition.split()) >= 2:
            return {"rule": rule, "pass": True, "reason": "condition is non-trivial"}
        return {"rule": rule, "pass": None, "reason": "condition too vague"}
    
    elif rule == "both_entities_exist":
        a = slots.get("entity_a", "").lower()
        b = slots.get("entity_b", "").lower()
        a_found = a in prop_texts if a else False
        b_found = b in prop_texts if b else False
        if a_found or b_found:
            return {"rule": rule, "pass": True, "reason": "at least one entity confirmed"}
        return {"rule": rule, "pass": None, "reason": "entities not in domain knowledge"}
    
    # Default
    return {"rule": rule, "pass": None, "reason": "rule not implemented"}


# ─── Analogical Transfer ────────────────────────────────────────────────────

def run_analogical_transfer(text, domain_propositions=None, store=None):
    """Full analogical transfer pipeline.
    
    Args:
        text: claim text to analyze
        domain_propositions: from domain_bridge.bridge_domain()
        store: StageStore
    
    Returns:
        dict with template matches, applied rules, and transfer confidence
    """
    matches = match_templates(text)
    
    if not matches:
        result = {
            "matched": False,
            "templates": [],
            "transfer_confidence": 0.0,
            "detail": "No structural template matched",
        }
        if store:
            store.write("analogical_transfer", result)
        return result
    
    # Apply verification rules for each match
    transfer_results = []
    for match in matches:
        template_def = next((t for t in _TEMPLATES if t["name"] == match.template), None)
        if not template_def:
            continue
        
        rule_results = []
        for rule in template_def["verification_rules"]:
            r = _check_rule(rule, match.slots, domain_propositions)
            rule_results.append(r)
        
        # Transfer confidence: based on matches + rule passes
        rules_passed = sum(1 for r in rule_results if r["pass"] is True)
        rules_total = len(rule_results)
        rule_score = rules_passed / max(rules_total, 1)
        
        # Find best analog
        best_analog = match.known_analogs[0] if match.known_analogs else None
        
        transfer_results.append({
            "template": match.template,
            "slots": match.slots,
            "match_confidence": match.confidence,
            "analog_domain": best_analog["domain"] if best_analog else None,
            "analog_example": best_analog["example"] if best_analog else None,
            "rules_applied": rule_results,
            "rules_passed": rules_passed,
            "rules_total": rules_total,
            "transfer_score": round(match.confidence * (0.5 + 0.5 * rule_score), 3),
        })
    
    # Overall transfer confidence
    best_transfer = max(transfer_results, key=lambda x: x["transfer_score"])
    
    result = {
        "matched": True,
        "templates_matched": len(transfer_results),
        "transfers": transfer_results,
        "best_template": best_transfer["template"],
        "best_analog": best_transfer.get("analog_example"),
        "transfer_confidence": best_transfer["transfer_score"],
        "structural_type": best_transfer["template"],
    }
    
    if store:
        store.write("analogical_transfer", result)
    
    return result
