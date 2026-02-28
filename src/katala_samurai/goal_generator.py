"""
KS32a — Autonomous Verification Goal Generator

Three goal sources derive verification targets from structure, not memory:
  G1: Gap Detector — finds unverified elements in input
  G2: Contradiction Hunter — spots conflicting signals
  G3: Scope Expander — generates related propositions to test

Design: Youta Hilono, 2026-02-28
Implementation: Shirokuma

Principle: Goals are derived from current structure, never accumulated.
Session-only. Fresh each run.
"""

import re
from collections import namedtuple

try:
    from .domain_bridge import bridge_domain, _extract_domain_terms
    from .analogical_transfer import match_templates
except ImportError:
    from domain_bridge import bridge_domain, _extract_domain_terms
    from analogical_transfer import match_templates

Goal = namedtuple("Goal", ["target_text", "source", "priority", "reason"])


# ─── G1: Gap Detector ───────────────────────────────────────────────────────

# Patterns that indicate implicit assumptions
_ASSUMPTION_MARKERS = [
    (re.compile(r'\b(obviously|clearly|of course|naturally|everyone knows)\b', re.I),
     "unstated_assumption", "Assumed to be obvious without evidence"),
    (re.compile(r'\b(always|never|all|none|every|no one)\b', re.I),
     "universal_claim", "Universal quantifier — exceptions not checked"),
    (re.compile(r'\b(therefore|thus|hence|consequently|so)\b', re.I),
     "implicit_inference", "Inferential leap — intermediate steps unverified"),
    (re.compile(r'\b(because|since|due to|as a result of)\b', re.I),
     "causal_assumption", "Causal claim — mechanism unverified"),
    (re.compile(r'\b(should|must|ought|need to)\b', re.I),
     "normative_claim", "Normative/prescriptive — basis unexamined"),
    (re.compile(r'\b(most|many|few|some|often|rarely|usually|typically)\b', re.I),
     "vague_quantifier", "Vague quantifier — exact scope unclear"),
]

# Patterns for undefined terms (technical jargon without definition)
_JARGON_PATTERN = re.compile(r'\b([A-Z][a-z]*(?:[A-Z][a-z]+)+)\b')  # CamelCase
_ACRONYM_PATTERN = re.compile(r'\b([A-Z]{2,6})\b')  # Acronyms


def detect_gaps(text, verification_result=None):
    """Find unverified elements: assumptions, undefined terms, logical gaps."""
    gaps = []
    
    # Check for assumption markers
    for pattern, gap_type, reason in _ASSUMPTION_MARKERS:
        matches = pattern.finditer(text)
        for m in matches:
            # Extract surrounding context
            start = max(0, m.start() - 30)
            end = min(len(text), m.end() + 50)
            context = text[start:end].strip()
            
            gaps.append({
                "type": gap_type,
                "marker": m.group(),
                "context": context,
                "reason": reason,
                "position": m.start(),
            })
    
    # Check for undefined technical terms
    jargon = set(_JARGON_PATTERN.findall(text))
    acronyms = set(_ACRONYM_PATTERN.findall(text))
    # Filter common acronyms
    common = {"DNA", "RNA", "ATP", "GDP", "GTP", "USA", "EU", "UK", "AI", "ML", "NLP", "API"}
    undefined = (jargon | acronyms) - common
    
    for term in undefined:
        # Check if term is defined in text (followed by "is", "means", "refers to")
        defined = re.search(rf'{re.escape(term)}\s+(?:is|means|refers\s+to|denotes)', text, re.I)
        if not defined:
            gaps.append({
                "type": "undefined_term",
                "marker": term,
                "context": term,
                "reason": f"Term '{term}' used without definition",
                "position": text.index(term) if term in text else 0,
            })
    
    # Check for multi-step claims without intermediate verification
    sentences = re.split(r'[.!?]+', text)
    if len(sentences) >= 3:
        gaps.append({
            "type": "multi_step_unverified",
            "marker": f"{len(sentences)} steps",
            "context": f"Multi-step argument ({len(sentences)} claims)",
            "reason": "Each step should be independently verifiable",
            "position": 0,
        })
    
    # Generate goals from gaps
    goals = []
    for i, gap in enumerate(gaps):
        priority = _gap_priority(gap["type"])
        goals.append(Goal(
            target_text=f"Verify: {gap['reason']} — '{gap['marker']}'",
            source="G1_gap_detector",
            priority=priority,
            reason=gap["reason"],
        ))
    
    return gaps, goals


def _gap_priority(gap_type):
    """Assign priority based on gap severity."""
    priorities = {
        "causal_assumption": 0.9,
        "implicit_inference": 0.85,
        "universal_claim": 0.8,
        "unstated_assumption": 0.75,
        "normative_claim": 0.7,
        "undefined_term": 0.65,
        "vague_quantifier": 0.6,
        "multi_step_unverified": 0.55,
    }
    return priorities.get(gap_type, 0.5)


# ─── G2: Contradiction Hunter ───────────────────────────────────────────────

def detect_contradictions(text, domain_result=None, verification_result=None):
    """Spot conflicting signals between sources."""
    contradictions = []
    goals = []
    
    # Internal contradictions: opposing claims in the same text
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    
    negation_pairs = []
    for i, s1 in enumerate(sentences):
        for j, s2 in enumerate(sentences):
            if i >= j:
                continue
            # Check if one negates the other
            s1_neg = _has_negation(s1)
            s2_neg = _has_negation(s2)
            
            # Extract key concepts from each
            s1_concepts = set(re.findall(r'\b(\w{4,})\b', s1.lower()))
            s2_concepts = set(re.findall(r'\b(\w{4,})\b', s2.lower()))
            overlap = s1_concepts & s2_concepts
            
            if overlap and s1_neg != s2_neg:
                contradictions.append({
                    "type": "internal_negation",
                    "sentence_a": s1[:60],
                    "sentence_b": s2[:60],
                    "shared_concepts": list(overlap)[:5],
                })
    
    # Domain evidence contradiction
    if domain_result and domain_result.get("propositions"):
        props = domain_result["propositions"]
        text_lower = text.lower()
        
        for prop in props:
            prop_text = prop.get("text", "").lower()
            # Simple contradiction: text says "X is Y" but domain says "X is not Y"
            # or text says "X causes Y" but domain evidence doesn't support it
            if any(neg in text_lower for neg in ["not", "never", "doesn't", "isn't", "cannot"]):
                # Check if domain evidence contradicts the negation
                key_words = set(re.findall(r'\b(\w{4,})\b', prop_text))
                text_words = set(re.findall(r'\b(\w{4,})\b', text_lower))
                if len(key_words & text_words) >= 2:
                    contradictions.append({
                        "type": "domain_tension",
                        "claim": text[:60],
                        "evidence": prop_text[:60],
                        "overlap": list(key_words & text_words)[:5],
                    })
    
    # Verification result contradictions
    if verification_result:
        # Check if different layers gave conflicting verdicts
        trace = verification_result.get("trace", [])
        verdicts = [t.get("verdict") for t in trace if t.get("verdict")]
        if "VERIFIED" in verdicts and "UNVERIFIED" in verdicts:
            contradictions.append({
                "type": "layer_disagreement",
                "verdicts": verdicts,
            })
    
    # Generate goals from contradictions
    for c in contradictions:
        goals.append(Goal(
            target_text=f"Resolve contradiction: {c['type']}",
            source="G2_contradiction_hunter",
            priority=0.9,  # Contradictions are always high priority
            reason=f"Conflicting signals detected: {c['type']}",
        ))
    
    return contradictions, goals


def _has_negation(sentence):
    """Check if a sentence contains negation."""
    negation_words = {"not", "no", "never", "neither", "nor", "doesn't", 
                      "don't", "isn't", "aren't", "won't", "can't", "cannot",
                      "couldn't", "shouldn't", "wouldn't", "hardly", "barely"}
    words = set(sentence.lower().split())
    return bool(words & negation_words)


# ─── G3: Scope Expander ─────────────────────────────────────────────────────

def expand_scope(text, domain_result=None):
    """Generate related propositions: 'If X is true, then Y should also hold.'"""
    expansions = []
    goals = []
    
    # Extract key claims
    terms = _extract_domain_terms(text)
    
    # Template-based expansion: structural implications
    template_matches = match_templates(text)
    
    for match in template_matches:
        slots = match.slots
        
        if match.template == "agent_action_object_result":
            agent = slots.get("agent", "")
            result = slots.get("result", "")
            if agent and result:
                # Implication: if agent causes result, then removing agent should remove result
                expansions.append({
                    "type": "counterfactual",
                    "derived": f"Without {agent}, {result} should not occur",
                    "basis": "causal counterfactual",
                })
                # Implication: similar agents should cause similar results
                expansions.append({
                    "type": "analogical_extension",
                    "derived": f"Similar mechanisms to {agent} should also produce {result}",
                    "basis": "structural analogy",
                })
        
        elif match.template == "classification":
            instance = slots.get("instance", "")
            category = slots.get("category", "")
            if instance and category:
                # Implication: instance should have category properties
                expansions.append({
                    "type": "property_inheritance",
                    "derived": f"{instance} should have typical properties of {category}",
                    "basis": "taxonomic inheritance",
                })
        
        elif match.template == "conditional":
            condition = slots.get("condition", "")
            consequence = slots.get("consequence", "")
            if condition and consequence:
                # Contrapositive
                expansions.append({
                    "type": "contrapositive",
                    "derived": f"If NOT {consequence}, then NOT {condition}",
                    "basis": "logical contrapositive",
                })
        
        elif match.template == "transformation":
            agent = slots.get("agent", "")
            inp = slots.get("input", "")
            out = slots.get("output", "")
            if inp and out:
                # Conservation
                expansions.append({
                    "type": "conservation",
                    "derived": f"The transformation from {inp} to {out} should conserve fundamental properties",
                    "basis": "conservation principle",
                })
        
        elif match.template == "prevention_inhibition":
            inhibitor = slots.get("inhibitor", "")
            target = slots.get("target", "")
            if inhibitor and target:
                # Dose-response
                expansions.append({
                    "type": "dose_response",
                    "derived": f"More {inhibitor} should increase inhibition of {target}",
                    "basis": "dose-response relationship",
                })
    
    # Domain-knowledge based expansion
    if domain_result and domain_result.get("propositions"):
        props = domain_result["propositions"]
        # Find propositions not mentioned in original text
        text_lower = text.lower()
        for prop in props[:3]:
            prop_text = prop.get("text", "")
            # Check if this proposition adds new information
            prop_words = set(re.findall(r'\b(\w{4,})\b', prop_text.lower()))
            text_words = set(re.findall(r'\b(\w{4,})\b', text_lower))
            novel_words = prop_words - text_words
            if len(novel_words) >= 2:
                expansions.append({
                    "type": "domain_extension",
                    "derived": f"Related: {prop_text[:80]}",
                    "basis": f"domain knowledge ({prop.get('source', 'unknown')})",
                })
    
    # Generate goals from expansions
    for exp in expansions:
        priority = _expansion_priority(exp["type"])
        goals.append(Goal(
            target_text=exp["derived"],
            source="G3_scope_expander",
            priority=priority,
            reason=exp["basis"],
        ))
    
    return expansions, goals


def _expansion_priority(expansion_type):
    """Assign priority based on expansion type."""
    priorities = {
        "contrapositive": 0.85,
        "counterfactual": 0.8,
        "conservation": 0.75,
        "property_inheritance": 0.7,
        "analogical_extension": 0.65,
        "dose_response": 0.6,
        "domain_extension": 0.55,
    }
    return priorities.get(expansion_type, 0.5)


# ─── Unified Goal Generator ─────────────────────────────────────────────────

def generate_goals(text, domain_result=None, verification_result=None, store=None, max_goals=10):
    """Full autonomous goal generation pipeline.
    
    Combines G1 (gaps) + G2 (contradictions) + G3 (scope expansion)
    into a priority-sorted goal queue.
    
    All goals are derived from current structure — no accumulation.
    """
    # Run all three detectors
    gaps, g1_goals = detect_gaps(text, verification_result)
    
    # Get domain info if not provided
    if domain_result is None:
        domain_result = bridge_domain(text)
    
    contradictions, g2_goals = detect_contradictions(text, domain_result, verification_result)
    expansions, g3_goals = expand_scope(text, domain_result)
    
    # Merge and sort by priority
    all_goals = g1_goals + g2_goals + g3_goals
    all_goals.sort(key=lambda g: g.priority, reverse=True)
    
    # Deduplicate (by target_text similarity)
    seen = set()
    unique_goals = []
    for goal in all_goals:
        key = goal.target_text[:50].lower()
        if key not in seen:
            seen.add(key)
            unique_goals.append(goal)
    
    # Cap at max_goals
    final_goals = unique_goals[:max_goals]
    
    result = {
        "text": text[:100],
        "goal_count": len(final_goals),
        "goals": [
            {
                "target": g.target_text,
                "source": g.source,
                "priority": g.priority,
                "reason": g.reason,
            }
            for g in final_goals
        ],
        "sources": {
            "G1_gaps": len(g1_goals),
            "G2_contradictions": len(g2_goals),
            "G3_expansions": len(g3_goals),
        },
        "detail": {
            "gaps_found": len(gaps),
            "contradictions_found": len(contradictions),
            "expansions_generated": len(expansions),
        },
    }
    
    if store:
        store.write("goal_generator", result)
    
    return result
