"""
Semantic Parse — LLM-based Proposition Extraction for KS Solvers.

Replaces boolean pattern-matching _parse() with genuine semantic extraction:
  Old: {"p_causal": True, "p_has_negation": False, ...}  (35 bools)
  New: {"propositions": ["P1: X causes Y", "P2: Y implies Z"],
        "relations": [{"from": "P1", "to": "P2", "type": "implies"}],
        "entities": ["X", "Y", "Z"],
        "domain": "physics",
        "confidence": 0.85}

3-tier extraction:
  1. Ollama (local, free, fast) — qwen3:8b
  2. Gemini (API, if GEMINI_API_KEY set)
  3. Heuristic fallback (parse_bridge 35-bool features)

The output format is backward-compatible: old boolean props are still
available via .propositions dict, but solvers can now access .semantic
for richer structured data.

Design: Youta Hilono (direction: "意味的な命題抽出に置き換えて")
Implementation: Shirokuma
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ── Constants ──
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
LLM_TIMEOUT = 15                # seconds
MAX_TEXT_LENGTH = 2000           # truncate long inputs
CACHE_SIZE = 256                 # LRU cache size

# ── Extraction Prompt ──
_EXTRACTION_PROMPT = """Extract logical propositions from this text. Return ONLY valid JSON.

Text: "{text}"

Return this exact JSON structure:
{{
  "propositions": [
    {{"id": "P1", "text": "atomic claim in natural language", "type": "factual|causal|definitional|evaluative|conditional|comparative"}},
    {{"id": "P2", "text": "another atomic claim", "type": "factual"}}
  ],
  "relations": [
    {{"from": "P1", "to": "P2", "type": "implies|causes|contradicts|supports|requires|refines"}}
  ],
  "entities": ["key entity 1", "key entity 2"],
  "domain": "physics|biology|mathematics|computer_science|philosophy|law|music|general",
  "negations": ["P1"],
  "quantifiers": {{"P2": "universal|existential|most|some"}},
  "confidence": 0.85
}}

Rules:
- Each proposition must be ONE atomic claim (no conjunctions)
- Split compound sentences into separate propositions
- Identify ALL logical relations between propositions
- Mark negated propositions in "negations"
- Note quantifier scope in "quantifiers"
- Domain should reflect the primary knowledge domain"""


@dataclass
class SemanticPropositions:
    """Rich semantic parse result."""
    propositions: List[Dict[str, str]]        # [{id, text, type}, ...]
    relations: List[Dict[str, str]]           # [{from, to, type}, ...]
    entities: List[str]
    domain: str
    negations: List[str]                      # IDs of negated props
    quantifiers: Dict[str, str]               # ID → scope
    confidence: float
    source: str                               # "ollama" | "gemini" | "heuristic"
    extraction_time_ms: float = 0.0

    @property
    def prop_count(self) -> int:
        return len(self.propositions)

    @property
    def relation_count(self) -> int:
        return len(self.relations)

    def to_solver_props(self) -> Dict[str, bool]:
        """Convert to legacy boolean format for backward compat.

        Solvers that expect the old format get meaningful bools derived
        from semantic content rather than surface pattern matching.
        """
        props: Dict[str, bool] = {}

        # From propositions
        props["p_has_content"] = len(self.propositions) > 0
        props["p_multi_proposition"] = len(self.propositions) > 1
        props["p_many_propositions"] = len(self.propositions) > 3

        # From types
        types = {p.get("type", "") for p in self.propositions}
        props["p_causal"] = "causal" in types
        props["p_definitional"] = "definitional" in types
        props["p_comparative"] = "comparative" in types
        props["p_conditional"] = "conditional" in types
        props["p_evaluative"] = "evaluative" in types
        props["p_factual"] = "factual" in types

        # From relations
        rel_types = {r.get("type", "") for r in self.relations}
        props["p_has_implication"] = "implies" in rel_types
        props["p_has_causation"] = "causes" in rel_types
        props["p_has_contradiction"] = "contradicts" in rel_types
        props["p_has_support"] = "supports" in rel_types
        props["p_has_refinement"] = "refines" in rel_types

        # From structure
        props["p_has_negation"] = len(self.negations) > 0
        props["p_has_quantifier"] = len(self.quantifiers) > 0
        props["p_universal"] = "universal" in self.quantifiers.values()
        props["p_existential"] = "existential" in self.quantifiers.values()

        # From entities
        props["p_has_entities"] = len(self.entities) > 0
        props["p_many_entities"] = len(self.entities) > 3

        # Domain detection
        props["p_scientific"] = self.domain in ("physics", "biology", "chemistry")
        props["p_mathematical"] = self.domain == "mathematics"
        props["p_technical"] = self.domain == "computer_science"
        props["p_philosophical"] = self.domain == "philosophy"
        props["p_legal"] = self.domain == "law"

        # Complexity
        props["p_complex"] = len(self.propositions) > 2 and len(self.relations) > 1
        props["p_chain"] = any(
            r["type"] in ("implies", "causes") for r in self.relations
        )

        # Confidence-based
        props["p_high_confidence"] = self.confidence >= 0.8
        props["p_low_confidence"] = self.confidence < 0.5

        return props

    def to_dict(self) -> Dict[str, Any]:
        """Full semantic data as dict."""
        return {
            "propositions": self.propositions,
            "relations": self.relations,
            "entities": self.entities,
            "domain": self.domain,
            "negations": self.negations,
            "quantifiers": self.quantifiers,
            "confidence": self.confidence,
            "source": self.source,
            "extraction_time_ms": self.extraction_time_ms,
        }


# ── LRU Cache ──
_cache: Dict[str, SemanticPropositions] = {}
_cache_order: List[str] = []


def _cache_get(key: str) -> Optional[SemanticPropositions]:
    return _cache.get(key)


def _cache_put(key: str, value: SemanticPropositions) -> None:
    if key in _cache:
        _cache_order.remove(key)
    _cache[key] = value
    _cache_order.append(key)
    while len(_cache_order) > CACHE_SIZE:
        old_key = _cache_order.pop(0)
        _cache.pop(old_key, None)


# ── LLM Extraction ──

def _call_ollama(prompt: str) -> Optional[Dict]:
    """Call Ollama for semantic extraction."""
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt + "\n/no_think",
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 2048},
        }).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            text = data.get("response", "")
            # Strip markdown code fences
            text = re.sub(r'^```(?:json)?\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text.strip())
            # Extract JSON
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
    except Exception:
        pass
    return None


def _call_gemini(prompt: str) -> Optional[Dict]:
    """Call Gemini API for semantic extraction."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }).encode()
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r'^```(?:json)?\s*', '', text.strip())
            text = re.sub(r'\s*```$', '', text.strip())
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
    except Exception:
        pass
    return None


def _heuristic_extract(text: str) -> Dict:
    """Heuristic fallback: split into sentences, detect basic relations.

    Rust-accelerated when available (ks_accel.heuristic_extract).
    """
    try:
        import ks_accel
        raw = ks_accel.heuristic_extract(text)
        # Parse JSON strings back to Python objects
        import json
        return {
            "propositions": json.loads(raw.get("propositions", "[]")),
            "relations": json.loads(raw.get("relations", "[]")),
            "entities": json.loads(raw.get("entities", "[]")),
            "domain": raw.get("domain", "general"),
            "negations": json.loads(raw.get("negations", "[]")),
            "quantifiers": json.loads(raw.get("quantifiers", "{}")),
            "confidence": float(raw.get("confidence", "0.5")),
        }
    except (ImportError, AttributeError):
        pass
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    propositions = []
    for i, sent in enumerate(sentences[:10]):  # Cap at 10
        # Detect type
        lower = sent.lower()
        if any(w in lower for w in ["because", "causes", "leads to", "results in", "due to"]):
            ptype = "causal"
        elif any(w in lower for w in ["is a", "defined as", "refers to", "means"]):
            ptype = "definitional"
        elif any(w in lower for w in ["more", "less", "better", "worse", "than"]):
            ptype = "comparative"
        elif any(w in lower for w in ["if", "unless", "provided", "assuming"]):
            ptype = "conditional"
        elif any(w in lower for w in ["good", "bad", "important", "should"]):
            ptype = "evaluative"
        else:
            ptype = "factual"

        propositions.append({
            "id": f"P{i+1}",
            "text": sent[:200],
            "type": ptype,
        })

    # Simple sequential relations
    relations = []
    for i in range(len(propositions) - 1):
        p1 = propositions[i]
        p2 = propositions[i + 1]
        if p1["type"] == "causal":
            rel_type = "causes"
        elif "therefore" in text.lower() or "thus" in text.lower():
            rel_type = "implies"
        else:
            rel_type = "supports"
        relations.append({
            "from": p1["id"],
            "to": p2["id"],
            "type": rel_type,
        })

    # Entity extraction (capitalized words that aren't sentence starters)
    words = text.split()
    entities = list(set(
        w.strip(",.;:?!()\"'[]") for w in words[1:]  # Skip first word
        if w[0].isupper() and len(w) > 2 and w.lower() not in {
            "the", "this", "that", "these", "those", "however", "therefore",
            "because", "although", "moreover", "furthermore",
        }
    ))[:10]

    # Domain detection
    lower = text.lower()
    if any(w in lower for w in ["equation", "theorem", "proof", "axiom"]):
        domain = "mathematics"
    elif any(w in lower for w in ["gene", "protein", "cell", "evolution", "organism"]):
        domain = "biology"
    elif any(w in lower for w in ["force", "energy", "quantum", "relativity", "particle"]):
        domain = "physics"
    elif any(w in lower for w in ["algorithm", "code", "function", "module", "API"]):
        domain = "computer_science"
    elif any(w in lower for w in ["ontolog", "epistemo", "phenomeno", "metaphysic"]):
        domain = "philosophy"
    elif any(w in lower for w in ["statute", "precedent", "jurisdiction", "liability"]):
        domain = "law"
    else:
        domain = "general"

    # Negations
    negations = [
        p["id"] for p in propositions
        if any(w in p["text"].lower() for w in ["not", "no", "never", "neither", "cannot"])
    ]

    # Quantifiers
    quantifiers = {}
    for p in propositions:
        lower_p = p["text"].lower()
        if any(w in lower_p for w in ["all", "every", "each", "always"]):
            quantifiers[p["id"]] = "universal"
        elif any(w in lower_p for w in ["some", "sometimes", "a few", "several"]):
            quantifiers[p["id"]] = "existential"
        elif any(w in lower_p for w in ["most", "many", "often"]):
            quantifiers[p["id"]] = "most"

    return {
        "propositions": propositions,
        "relations": relations,
        "entities": entities,
        "domain": domain,
        "negations": negations,
        "quantifiers": quantifiers,
        "confidence": 0.5,
    }


# ════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════

def semantic_parse(text: str, use_cache: bool = True) -> SemanticPropositions:
    """Extract semantic propositions from text.

    3-tier: Ollama → Gemini → Heuristic fallback.

    Returns SemanticPropositions with:
    - .propositions: structured atomic claims
    - .relations: logical relations between claims
    - .to_solver_props(): legacy boolean format
    """
    # Truncate
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "..."

    # Cache check
    cache_key = text[:100]
    if use_cache:
        cached = _cache_get(cache_key)
        if cached:
            return cached

    start = time.time()
    prompt = _EXTRACTION_PROMPT.format(text=text.replace('"', '\\"'))

    # Tier 1: Ollama
    result = _call_ollama(prompt)
    source = "ollama"

    # Tier 2: Gemini
    if result is None:
        result = _call_gemini(prompt)
        source = "gemini"

    # Tier 3: Heuristic
    if result is None:
        result = _heuristic_extract(text)
        source = "heuristic"

    elapsed_ms = (time.time() - start) * 1000

    # Build SemanticPropositions
    sem = SemanticPropositions(
        propositions=result.get("propositions", []),
        relations=result.get("relations", []),
        entities=result.get("entities", []),
        domain=result.get("domain", "general"),
        negations=result.get("negations", []),
        quantifiers=result.get("quantifiers", {}),
        confidence=result.get("confidence", 0.5),
        source=source,
        extraction_time_ms=round(elapsed_ms, 1),
    )

    # Cache
    if use_cache:
        _cache_put(cache_key, sem)

    return sem


def semantic_parse_to_props(text: str) -> Dict[str, bool]:
    """Quick API: returns legacy boolean props from semantic parse."""
    return semantic_parse(text).to_solver_props()
