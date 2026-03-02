"""
Parse Bridge — Rust-accelerated _parse() with Python fallback.

Provides parse_propositions() that:
1. Tries Rust (ks_accel.parse_propositions) — 10-50x faster
2. Falls back to Python implementation if Rust unavailable

Upgraded from 22 to 35 features:
- Lexical (6): content, vocab richness, text length, complex words, very long
- Structural (6): sentences, conjunctions, negation, quantifiers, parentheticals
- Semantic (10): causal, comparative, temporal, definitional, numbers, modal,
                  evidence, hedging, conditional, evaluative
- Complexity (7): nesting, chains, lists, density, questions, imperative, exclamatory
- Hash diversity (2): for solver diversity
- Cross-domain (4): mathematical, scientific, technical, philosophical
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, List

# ── Try Rust import ──
_HAS_RUST = False
try:
    import ks_accel
    # Verify the function actually exists (old builds may lack it)
    if hasattr(ks_accel, 'parse_propositions'):
        _HAS_RUST = True
except ImportError:
    pass


# ── Python fallback (35 features) ──

_STOPS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "it", "its", "this", "that", "these", "those",
    "and", "or", "but", "not", "no", "nor",
})

_NEGATION = frozenset({"not", "no", "never", "neither", "nor", "none", "cannot",
                        "nothing", "nowhere", "nobody", "hardly", "scarcely", "barely"})

_QUANTIFIERS = frozenset({"all", "every", "each", "some", "many", "most", "few",
                           "several", "any", "none", "always", "never", "often", "sometimes"})

_CAUSAL = ("because", "therefore", "hence", "thus", "consequently", "causes",
           "leads", "results", "due", "since", "implies", "entails",
           "as a result", "in consequence", "owing to")

_COMPARATIVE = frozenset({"more", "less", "better", "worse", "greater", "smaller",
                           "higher", "lower", "faster", "slower", "than", "compared",
                           "superior", "inferior", "exceeds", "outperforms"})

_TEMPORAL = frozenset({"before", "after", "during", "when", "then", "now",
                        "previously", "currently", "recently", "future", "past",
                        "present", "eventually", "meanwhile", "simultaneously",
                        "subsequently"})

_DEFINITIONAL = ("is a", "is an", "defined as", "refers to", "means",
                 "constitutes", "consists of", "known as", "classified as",
                 "characterized by")

_MODAL = frozenset({"can", "could", "may", "might", "should", "would", "must",
                     "shall", "ought", "need"})

_EVIDENCE = frozenset({"study", "research", "evidence", "data", "experiment",
                        "analysis", "survey", "trial", "observation", "measurement",
                        "finding", "result", "showed", "demonstrated", "proved", "confirmed"})

_HEDGING = frozenset({"perhaps", "possibly", "likely", "unlikely", "probably",
                       "apparently", "seemingly", "arguably", "roughly",
                       "approximately", "about", "suggest", "indicates", "implies"})


def _parse_python(text: str) -> Dict[str, bool]:
    """Pure Python _parse with 35 features."""
    lower = text.lower()
    words = lower.split()
    word_count = len(words)

    content_words = [
        w.strip(",.;:?!()\"'[]") for w in words
        if w.strip(",.;:?!()\"'[]") not in _STOPS
        and len(w.strip(",.;:?!()\"'[]")) > 1
    ]
    unique_content = set(content_words)

    props: Dict[str, bool] = {}

    # Lexical (6)
    props["p_has_content"] = len(content_words) > 0
    props["p_rich_vocab"] = (
        len(unique_content) > max(len(content_words) * 0.5, 3)
        if content_words else False
    )
    props["p_long_text"] = word_count > 15
    props["p_short_text"] = word_count <= 5
    props["p_complex_words"] = any(len(w) > 10 for w in content_words)
    props["p_very_long"] = word_count > 50

    # Structural (6)
    sentence_count = max(1, sum(1 for c in text if c in ".!?"))
    props["p_multi_sentence"] = sentence_count > 1
    props["p_many_sentences"] = sentence_count > 4
    props["p_has_conjunction"] = any(
        w in lower for w in [" and ", " or ", " but ", " yet ", " however ",
                             " moreover ", " furthermore "]
    )
    props["p_has_negation"] = any(w in _NEGATION for w in words)
    props["p_has_quantifier"] = any(w in _QUANTIFIERS for w in words)
    props["p_has_parenthetical"] = "(" in text or "[" in text

    # Semantic (10)
    props["p_causal"] = any(w in lower for w in _CAUSAL)
    props["p_comparative"] = any(w in _COMPARATIVE for w in words)
    props["p_temporal"] = any(w in _TEMPORAL for w in words)
    props["p_definitional"] = any(w in lower for w in _DEFINITIONAL)
    props["p_has_numbers"] = bool(re.search(r"\d+", text))
    props["p_has_modal"] = any(w in _MODAL for w in words)
    props["p_has_evidence"] = any(w in _EVIDENCE for w in words)
    props["p_has_hedging"] = any(w in _HEDGING for w in words)
    props["p_conditional"] = any(
        w in lower for w in ["if ", "unless ", "provided ", "assuming "]
    )
    props["p_evaluative"] = any(
        w in lower for w in ["good", "bad", "important", "significant",
                              "critical", "essential", "excellent", "poor",
                              "valuable", "harmful"]
    )

    # Complexity (7)
    props["p_nested"] = text.count(",") > 2 or "(" in text
    props["p_chain"] = any(
        w in lower for w in ["therefore", "thus", "hence", "consequently",
                              "so that", "it follows"]
    )
    props["p_list_structure"] = "first" in lower and ("second" in lower or "then" in lower)
    props["p_high_density"] = (
        (len(content_words) / word_count > 0.65) if word_count > 0 else False
    )
    props["p_question"] = "?" in text
    props["p_imperative"] = any(
        w in lower for w in ["must", "should", "need to", "have to", "required"]
    )
    props["p_exclamatory"] = "!" in text

    # Hash diversity (2)
    h = hashlib.md5(text.encode()).hexdigest()
    props["p_hash_even"] = int(h[0], 16) % 2 == 0
    props["p_hash_quarter"] = int(h[1], 16) % 4 == 0

    # Cross-domain (4)
    props["p_mathematical"] = (
        "=" in text or "∀" in text or "∃" in text or
        any(w in lower for w in ["equation", "theorem", "proof", "formula", "axiom"])
    )
    props["p_scientific"] = any(
        w in lower for w in ["hypothesis", "experiment", "variable", "control",
                              "sample", "coefficient", "p-value", "null hypothesis"]
    )
    props["p_technical"] = any(
        w in lower for w in ["algorithm", "implementation", "architecture",
                              "protocol", "interface", "module", "framework", "pipeline"]
    )
    props["p_philosophical"] = any(
        w in lower for w in ["ontolog", "epistemo", "phenomeno", "metaphysic",
                              "axiolog", "hermeneutic", "dialectic", "apriori"]
    )

    return props


def parse_propositions(text: str, semantic: bool = True) -> Dict[str, bool]:
    """Parse text into proposition features.

    Priority:
    1. Semantic (LLM-based: Ollama → Gemini → heuristic) if semantic=True
    2. Rust (ks_accel.parse_propositions) — fast pattern matching
    3. Python fallback — same 35 features, slower

    Semantic mode returns richer bools derived from actual meaning,
    not surface patterns. Falls back to pattern matching if LLM unavailable.
    """
    if semantic:
        try:
            from katala_samurai.semantic_parse import semantic_parse
            sem = semantic_parse(text)
            if sem.source != "heuristic" or sem.prop_count > 0:
                return sem.to_solver_props()
        except ImportError:
            pass
        except Exception:
            pass  # LLM failure → fall through to pattern matching

    if _HAS_RUST:
        return ks_accel.parse_propositions(text)
    return _parse_python(text)


def batch_parse_propositions(texts: List[str]) -> List[Dict[str, bool]]:
    """Batch parse (Rayon-parallel in Rust, sequential in Python)."""
    if _HAS_RUST:
        return ks_accel.batch_parse_propositions(texts)
    return [_parse_python(t) for t in texts]


def parse_semantic(text: str, fast: bool = False) -> "SemanticPropositions":
    """Get full semantic parse result (not just bools).

    Returns SemanticPropositions with .propositions, .relations,
    .entities, .domain, etc. for solvers that want rich data.

    fast=True: Skip LLM tiers, use heuristic only (~0.06ms vs ~1500ms).
    """
    from katala_samurai.semantic_parse import semantic_parse
    return semantic_parse(text, fast=fast)


# ── Info ──
def backend() -> str:
    if _HAS_RUST:
        return "rust+semantic"
    return "python+semantic"
