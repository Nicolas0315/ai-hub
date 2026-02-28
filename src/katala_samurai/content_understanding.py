"""
Content Understanding Enhancer — fixes S01-S27 content-blindness.

Addresses weakness ①: Content Understanding 88% vs Claude 92% (-4%)

Three sub-modules:
  CU1: Negation Sensitivity — detect meaning changes from negation
  CU2: Semantic Role Extraction — who does what to whom
  CU3: Implication Detector — implicit meanings beyond literal text

Non-LLM: regex + structural analysis + WordNet-style patterns.
"""

import re
from collections import namedtuple

SemanticRole = namedtuple("SemanticRole", ["agent", "action", "patient", "modifiers"])


# ─── CU1: Negation Sensitivity ─────────────────────────────────────────────

_NEGATION_WORDS = {
    "not", "no", "never", "neither", "nor", "none", "nothing",
    "nowhere", "nobody", "doesn't", "don't", "didn't", "isn't",
    "aren't", "wasn't", "weren't", "won't", "wouldn't", "couldn't",
    "shouldn't", "can't", "cannot", "hardly", "barely", "scarcely",
    "rarely", "seldom", "few", "little",
}

_NEGATION_PREFIXES = re.compile(
    r'\b(un|in|im|il|ir|dis|non|anti|counter|de|mis)\w+', re.I
)

_DOUBLE_NEGATION = re.compile(
    r'\b(not\s+(?:un|in|im|dis)\w+|never\s+(?:un|in|im|dis)\w+|'
    r'no\s+(?:un|in|im|dis)\w+)\b', re.I
)


def analyze_negation(text):
    """Detect negation patterns and their impact on meaning."""
    words = text.lower().split()
    word_set = set(words)
    
    negations = []
    
    # Direct negation words
    for neg in _NEGATION_WORDS & word_set:
        idx = words.index(neg)
        context_start = max(0, idx - 2)
        context_end = min(len(words), idx + 4)
        context = " ".join(words[context_start:context_end])
        negations.append({
            "type": "direct",
            "word": neg,
            "context": context,
            "position": idx,
        })
    
    # Prefix negation
    for m in _NEGATION_PREFIXES.finditer(text):
        negations.append({
            "type": "prefix",
            "word": m.group(),
            "context": text[max(0, m.start()-15):m.end()+15],
            "position": m.start(),
        })
    
    # Double negation (= affirmative)
    for m in _DOUBLE_NEGATION.finditer(text):
        negations.append({
            "type": "double_negation",
            "word": m.group(),
            "context": text[max(0, m.start()-10):m.end()+10],
            "position": m.start(),
            "meaning_flip": True,
        })
    
    # Compute negation density
    neg_count = len([n for n in negations if n["type"] == "direct"])
    density = neg_count / max(len(words), 1)
    
    # Generate counter-factual: flip the negation
    counterfactual = text
    for neg in _NEGATION_WORDS:
        counterfactual = re.sub(rf'\b{neg}\b', '', counterfactual, flags=re.I)
    counterfactual = re.sub(r'\s+', ' ', counterfactual).strip()
    
    return {
        "negations": negations,
        "negation_count": len(negations),
        "density": round(density, 3),
        "has_double_negation": any(n.get("meaning_flip") for n in negations),
        "counterfactual": counterfactual[:200] if counterfactual != text else None,
        "meaning_change_risk": "high" if density > 0.15 else "medium" if density > 0.05 else "low",
    }


# ─── CU2: Semantic Role Extraction ─────────────────────────────────────────

_SVO_PATTERNS = [
    # Subject + verb + object
    re.compile(r'^(\b\w+(?:\s+\w+){0,3})\s+(is|are|was|were|has|have|had|does|do|did|can|could|will|would|shall|should|may|might|must)\s+(.+)', re.I),
    # Subject + active verb + object
    re.compile(r'^(\b\w+(?:\s+\w+){0,2})\s+(\w+(?:s|es|ed|ing)?)\s+(.+)', re.I),
]

_MODIFIER_PATTERNS = [
    re.compile(r'\b(very|extremely|highly|significantly|slightly|partially|completely|almost|nearly)\b', re.I),
    re.compile(r'\b(always|never|sometimes|often|rarely|usually|frequently)\b', re.I),
    re.compile(r'\b(all|most|some|few|many|several|no|every|each)\b', re.I),
]


def extract_semantic_roles(text):
    """Extract who-does-what-to-whom from text."""
    sentences = re.split(r'[.!?]+', text)
    roles = []
    
    for sent in sentences:
        sent = sent.strip()
        if not sent or len(sent.split()) < 3:
            continue
        
        # Extract modifiers
        modifiers = []
        for pattern in _MODIFIER_PATTERNS:
            for m in pattern.finditer(sent):
                modifiers.append(m.group().lower())
        
        # Try SVO extraction
        for pattern in _SVO_PATTERNS:
            m = pattern.match(sent)
            if m:
                groups = m.groups()
                role = SemanticRole(
                    agent=groups[0].strip() if len(groups) > 0 else "",
                    action=groups[1].strip() if len(groups) > 1 else "",
                    patient=groups[2].strip().rstrip(".,;:") if len(groups) > 2 else "",
                    modifiers=modifiers,
                )
                roles.append(role)
                break
    
    return {
        "roles": [{"agent": r.agent, "action": r.action, "patient": r.patient, 
                   "modifiers": r.modifiers} for r in roles],
        "role_count": len(roles),
        "has_quantifiers": any("quantifier" in str(r.modifiers) or 
                              any(m in {"all", "most", "some", "few", "many", "no", "every"} 
                                  for m in r.modifiers) for r in roles),
    }


# ─── CU3: Implication Detector ─────────────────────────────────────────────

_IMPLICATION_PATTERNS = [
    (re.compile(r'\b(suggests?|implies?|indicates?|means)\s+that\b', re.I),
     "explicit_implication"),
    (re.compile(r'\b(despite|although|however|nevertheless|yet|but)\b', re.I),
     "concession"),
    (re.compile(r'\b(if|unless|provided|assuming|given)\b', re.I),
     "conditional"),
    (re.compile(r'\b(only|merely|just|simply)\b', re.I),
     "restriction"),
    (re.compile(r'\b(actually|in fact|indeed|really)\b', re.I),
     "emphasis_correction"),
    (re.compile(r'\b(seems?|appears?|looks? like|apparently)\b', re.I),
     "hedging"),
    (re.compile(r'\b(claimed?|alleged|supposed|reportedly)\b', re.I),
     "attribution_distancing"),
]


def detect_implications(text):
    """Find implicit meanings and pragmatic signals."""
    implications = []
    
    for pattern, impl_type in _IMPLICATION_PATTERNS:
        for m in pattern.finditer(text):
            context_start = max(0, m.start() - 20)
            context_end = min(len(text), m.end() + 40)
            implications.append({
                "type": impl_type,
                "marker": m.group(),
                "context": text[context_start:context_end].strip(),
            })
    
    # Detect rhetorical questions
    if re.search(r'\?', text):
        questions = re.findall(r'[^.!?]*\?', text)
        for q in questions:
            if re.search(r'\b(isn\'t it|don\'t you|wouldn\'t|couldn\'t|shouldn\'t)\b', q, re.I):
                implications.append({
                    "type": "rhetorical_question",
                    "marker": "rhetorical",
                    "context": q.strip()[:60],
                })
    
    return {
        "implications": implications,
        "count": len(implications),
        "types": list(set(i["type"] for i in implications)),
        "has_hedging": any(i["type"] == "hedging" for i in implications),
        "has_distancing": any(i["type"] == "attribution_distancing" for i in implications),
        "reliability_signal": "uncertain" if any(i["type"] in ("hedging", "attribution_distancing") for i in implications) else "direct",
    }


# ─── Unified Content Understanding Pipeline ────────────────────────────────

def analyze_content(text, store=None):
    """Full content understanding analysis."""
    negation = analyze_negation(text)
    roles = extract_semantic_roles(text)
    implications = detect_implications(text)
    
    # Compute content understanding score
    signals = 0
    total = 3
    
    if negation["negation_count"] > 0:
        signals += 1  # Negation awareness
    if roles["role_count"] > 0:
        signals += 1  # Semantic structure extracted
    if implications["count"] > 0:
        signals += 1  # Implicit meaning detected
    
    result = {
        "negation": negation,
        "semantic_roles": roles,
        "implications": implications,
        "content_signals": signals,
        "content_depth": round(signals / total, 2),
        "reliability": implications["reliability_signal"],
    }
    
    if store:
        store.write("content_understanding", result)
    
    return result
