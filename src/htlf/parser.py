"""Parser for extracting JSON-DAG representations from free text.

Supports multilingual concept extraction:
- English: regex-based noun phrase mining
- Japanese: MeCab/fugashi morphological analysis for compound noun extraction
- Cross-lingual: automatic language detection + layer inference
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

# ── Morphological analysis (optional, graceful fallback) ──
try:
    import fugashi
    _TAGGER: fugashi.Tagger | None = fugashi.Tagger()
    _HAS_MORPHO = True
except (ImportError, RuntimeError):
    _TAGGER = None
    _HAS_MORPHO = False

NodeType = Literal["claim", "concept", "equation"]
EdgeType = Literal["CAUSAL", "PREMISE", "SUPPORTS", "CONTRADICTS", "DEFINES", "QUANTIFIES"]


@dataclass(slots=True)
class DAGNode:
    """Node in HTLF structured representation."""

    id: str
    node_type: NodeType
    text: str


@dataclass(slots=True)
class DAGEdge:
    """Directed edge in HTLF structured representation."""

    source: str
    target: str
    relation: str
    edge_type: EdgeType = "SUPPORTS"


@dataclass(slots=True)
class DAG:
    """JSON-serializable DAG container."""

    nodes: list[DAGNode]
    edges: list[DAGEdge]

    def to_dict(self) -> dict[str, Any]:
        """Convert DAG to JSON-compatible dictionary."""
        return {
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
        }


PROMPT_TEMPLATE = """You are a strict information extraction engine.

Task:
Extract a directed acyclic graph (DAG) from the given text.

Output JSON schema:
{
  "nodes": [{"id": "n1", "node_type": "claim|concept|equation", "text": "..."}],
  "edges": [{"source": "n1", "target": "n2", "relation": "supports|depends_on|causes|defines|contrasts|instantiates", "edge_type": "CAUSAL|PREMISE|SUPPORTS|CONTRADICTS|DEFINES|QUANTIFIES"}]
}

Rules:
1) Keep 5-30 important nodes only.
2) node_type=equation only for mathematical symbols/equations.
3) Ensure edges are acyclic and reference existing IDs.
4) edge_type must be one of: CAUSAL, PREMISE, SUPPORTS, CONTRADICTS, DEFINES, QUANTIFIES.
5) Output JSON only. No markdown.

Text:
---
{input_text}
---
"""


def _is_equation_like(text: str) -> bool:
    return bool(re.search(r"[=<>∀∃Σ∫]|\b(omega|lambda|sigma|delta|epsilon|SNR|GDT)\b", text, re.IGNORECASE))


def _normalize_edge_type(relation: str, edge_type: str | None = None) -> EdgeType:
    relation_low = relation.lower().strip()
    if edge_type:
        et = edge_type.strip().upper()
        if et in {"CAUSAL", "PREMISE", "SUPPORTS", "CONTRADICTS", "DEFINES", "QUANTIFIES"}:
            return et  # type: ignore[return-value]

    if relation_low in {"causes", "cause", "because", "therefore"}:
        return "CAUSAL"
    if relation_low in {"depends_on", "depends", "requires", "premise", "prerequisite"}:
        return "PREMISE"
    if relation_low in {"supports", "support", "instantiates", "evidence_for"}:
        return "SUPPORTS"
    if relation_low in {"contrasts", "contradicts", "refutes", "opposes"}:
        return "CONTRADICTS"
    if relation_low in {"defines", "definition_of", "means"}:
        return "DEFINES"
    if relation_low in {"quantifies", "measures", "estimates", "computes"}:
        return "QUANTIFIES"
    return "SUPPORTS"


def _extract_noun_phrases(text: str) -> list[str]:
    """Extract key noun phrases / concepts using regex patterns."""
    patterns = [
        # Technical compound terms (e.g., "gene editing", "gravitational waves")
        r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
        # Acronyms with optional expansion
        r'\b[A-Z]{2,6}(?:-[A-Za-z0-9]+)*\b',
        # Hyphenated compounds (e.g., "CRISPR-Cas9")
        r'\b[A-Za-z]+-[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*\b',
        # Japanese technical terms (katakana compounds)
        r'[ァ-ヴー]{3,}(?:・[ァ-ヴー]{2,})*',
        # Key noun phrases: adjective + noun patterns
        r'\b(?:the\s+)?(?:[a-z]+\s+){0,2}(?:system|theory|model|method|process|mechanism|structure|function|principle|framework|algorithm|protocol|technique|analysis|experiment|measurement|frequency|wavelength|amplitude|velocity|energy|field|force|particle|molecule|protein|genome|sequence|mutation|expression|receptor|pathway|network|architecture|layer|module|component|parameter|variable|distribution|probability|correlation|coefficient|matrix|vector|tensor|gradient|optimization|convergence|iteration|approximation|transformation|decomposition|representation|embedding|encoding|decoding|inference|prediction|classification|regression|clustering|segmentation|detection|recognition|generation|synthesis|composition|harmony|melody|rhythm|tempo|timbre|chord|scale|mode|tonality|modulation|cadence|counterpoint|fugue|sonata|symphony|concerto|texture|canvas|brushstroke|palette|perspective|proportion|symmetry|contrast|saturation|luminance|hue)\b',
    ]
    found: dict[str, int] = {}  # term -> first position
    text_lower = text.lower()
    for pat in patterns:
        for m in re.finditer(pat, text):
            term = m.group().strip()
            if len(term) < 3 or term.lower() in ('the', 'and', 'for', 'with', 'from', 'that', 'this', 'which'):
                continue
            key = term.lower()
            if key not in found:
                found[key] = m.start()
    # Also extract sentence-level key claims for edge diversity
    return sorted(found.keys(), key=lambda k: found[k])


def _detect_language(text: str) -> str:
    """Detect dominant language: 'ja', 'en', or 'mixed'."""
    # Count CJK vs Latin characters
    cjk = len(re.findall(r'[\u3000-\u9fff\uff00-\uffef]', text))
    latin = len(re.findall(r'[a-zA-Z]', text))
    total = cjk + latin
    if total == 0:
        return "en"
    ratio = cjk / total
    if ratio > 0.5:
        return "ja"
    if ratio > 0.15:
        return "mixed"
    return "en"


def _extract_ja_concepts(text: str) -> list[str]:
    """Extract Japanese compound nouns using morphological analysis.

    Uses fugashi (MeCab wrapper) to identify noun compounds:
    - Consecutive 名詞 (noun) tokens are joined into compound terms
    - Filters particles, auxiliaries, and single-character terms
    - Falls back to regex if fugashi unavailable
    """
    if not _HAS_MORPHO or _TAGGER is None:
        # Fallback: regex-based extraction
        kanji = re.findall(r'[一-龯]{2,}(?:[一-龯ぁ-ん]*[一-龯])?', text)
        kata = re.findall(r'[ァ-ヴー]{3,}(?:・[ァ-ヴー]{2,})*', text)
        return list(dict.fromkeys(kanji + kata))

    words = _TAGGER(text)
    concepts: list[str] = []
    current_compound: list[str] = []

    noun_pos = {'名詞', '接尾辞'}
    
    for word in words:
        pos = word.feature.pos1 if hasattr(word.feature, 'pos1') else ''
        if pos in noun_pos and len(word.surface) >= 1:
            current_compound.append(word.surface)
        else:
            if len(current_compound) >= 2 or (
                len(current_compound) == 1 and len(current_compound[0]) >= 2
            ):
                compound = ''.join(current_compound)
                if len(compound) >= 2:
                    concepts.append(compound)
            current_compound = []

    # Flush last compound
    if len(current_compound) >= 2 or (
        len(current_compound) == 1 and len(current_compound[0]) >= 2
    ):
        compound = ''.join(current_compound)
        if len(compound) >= 2:
            concepts.append(compound)

    return list(dict.fromkeys(concepts))


def _extract_multilingual_concepts(text: str) -> list[str]:
    """Extract concepts from mixed-language text.

    Combines English noun phrase extraction with Japanese morphological analysis.
    Handles cross-lingual pairs like "重力波 (gravitational waves)".
    """
    lang = _detect_language(text)

    if lang == "en":
        return _extract_noun_phrases(text)
    elif lang == "ja":
        ja_concepts = _extract_ja_concepts(text)
        # Also grab any English terms embedded in Japanese text
        en_terms = re.findall(r'[A-Z][a-z]{2,}(?:\s[A-Z][a-z]+)*', text)
        en_terms += re.findall(r'[A-Z]{2,6}', text)
        return list(dict.fromkeys(ja_concepts + [t.lower() for t in en_terms]))
    else:  # mixed
        en_concepts = _extract_noun_phrases(text)
        ja_concepts = _extract_ja_concepts(text)
        # Merge, preserving order
        combined = list(dict.fromkeys(en_concepts + ja_concepts))
        return combined


def detect_layer(text: str) -> str:
    """Auto-detect the symbolic layer of the input text.

    Returns: 'math', 'formal_language', 'natural_language',
             'music', 'creative_arts'

    Enhanced with multilingual support:
    - Japanese academic text → natural_language
    - Japanese with 数式/定理 → math
    - Code (any language) → formal_language
    """
    lang = _detect_language(text)

    # Code detection (language-independent)
    code_markers = [
        r'def\s+\w+\(', r'class\s+\w+[:\(]', r'import\s+\w+',
        r'function\s+\w+', r'\{.*\}', r'(?:int|void|string)\s+\w+',
        r'=>\s*\{', r'#include', r'fn\s+\w+',
    ]
    if sum(1 for p in code_markers if re.search(p, text)) >= 2:
        return "formal_language"

    # Math detection
    math_markers = [
        r'\\(?:frac|sum|int|partial|nabla|infty|alpha|beta|gamma)',
        r'∀|∃|∈|∉|⊂|⊃|∪|∩|→|⟹|≡|≅|≤|≥',
        r'(?:theorem|lemma|proof|corollary)\s',
        r'定理|補題|証明|公理',
    ]
    if sum(1 for p in math_markers if re.search(p, text, re.IGNORECASE)) >= 2:
        return "math"

    # Music detection
    music_markers = [
        r'(?:major|minor)\s+(?:key|scale|chord)',
        r'(?:allegro|andante|adagio|forte|piano|crescendo)',
        r'(?:C|D|E|F|G|A|B)(?:#|b)?(?:m|maj|min|dim|aug|7)',
        r'長調|短調|和音|旋律|拍子',
    ]
    if sum(1 for p in music_markers if re.search(p, text, re.IGNORECASE)) >= 2:
        return "music"

    # Creative arts detection
    art_markers = [
        r'(?:canvas|brushstroke|composition|palette|sculpture)',
        r'(?:perspective|chiaroscuro|sfumato|impasto)',
        r'絵画|彫刻|構図|画法|色彩',
    ]
    if sum(1 for p in art_markers if re.search(p, text, re.IGNORECASE)) >= 2:
        return "creative_arts"

    # Formal language (but not code)
    if re.search(r'∧|∨|¬|⊢|⊨|BNF|grammar|syntax|semantics', text):
        return "formal_language"

    return "natural_language"


def _deduplicate_concepts(concepts: list[str], max_nodes: int = 25) -> list[str]:
    """Remove near-duplicate concepts."""
    result: list[str] = []
    for c in concepts:
        is_dup = False
        for existing in result:
            if c in existing or existing in c:
                is_dup = True
                break
        if not is_dup:
            result.append(c)
        if len(result) >= max_nodes:
            break
    return result


def _infer_edge_type_between(src_text: str, tgt_text: str, full_text: str) -> tuple[str, EdgeType]:
    """Infer relationship between two concepts based on their co-occurrence context."""
    src_low = src_text.lower()
    tgt_low = tgt_text.lower()
    
    # Find sentences containing both concepts
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+', full_text) if s.strip()]
    co_sentences = [s for s in sentences if src_low in s.lower() and tgt_low in s.lower()]
    
    if co_sentences:
        ctx = co_sentences[0].lower()
        if any(k in ctx for k in ['cause', 'result', 'lead to', 'produce', 'enable', 'trigger', 'induce']):
            return ('causes', 'CAUSAL')
        if any(k in ctx for k in ['define', 'means', 'refers to', 'known as', 'called']):
            return ('defines', 'DEFINES')
        if any(k in ctx for k in ['measure', 'quantif', 'percent', 'ratio', 'rate', 'frequency']):
            return ('quantifies', 'QUANTIFIES')
        if any(k in ctx for k in ['however', 'but', 'contrast', 'unlike', 'whereas', 'despite']):
            return ('contrasts', 'CONTRADICTS')
        if any(k in ctx for k in ['require', 'depend', 'need', 'prerequisite', 'given']):
            return ('depends_on', 'PREMISE')
    
    return ('supports', 'SUPPORTS')


def _heuristic_extract(text: str, max_nodes: int = 20) -> DAG:
    """Concept-level DAG extraction using noun phrase mining + co-occurrence edges.

    Multilingual: auto-detects language and uses morphological analysis for Japanese.
    """
    # Phase 1: Extract concepts (multilingual)
    concepts = _extract_multilingual_concepts(text)
    
    # Also add key sentences as claim nodes for coverage
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+', text) if s.strip()]
    key_sentences = sentences[:5]  # First 5 sentences as anchor claims
    
    concepts = _deduplicate_concepts(concepts, max_nodes=max_nodes - len(key_sentences))
    
    # Build nodes: concepts first, then key sentences
    nodes: list[DAGNode] = []
    for idx, concept in enumerate(concepts, 1):
        node_type: NodeType = "equation" if _is_equation_like(concept) else "concept"
        nodes.append(DAGNode(id=f"c{idx}", node_type=node_type, text=concept))
    
    for idx, sentence in enumerate(key_sentences, 1):
        node_type = "equation" if _is_equation_like(sentence) else "claim"
        nodes.append(DAGNode(id=f"s{idx}", node_type=node_type, text=sentence[:400]))
    
    if not nodes:
        nodes.append(DAGNode(id="n1", node_type="claim", text=text[:200].strip() or "(empty)"))
    
    # Phase 2: Build edges from co-occurrence + semantic inference
    edges: list[DAGEdge] = []
    text_lower = text.lower()
    
    # Concept-to-concept edges (co-occurrence in same sentence)
    for i in range(len(concepts)):
        for j in range(i + 1, len(concepts)):
            # Check if they co-occur in a sentence
            ci_low = concepts[i].lower()
            cj_low = concepts[j].lower()
            co_occurs = any(ci_low in s.lower() and cj_low in s.lower() for s in sentences)
            if co_occurs:
                relation, edge_type = _infer_edge_type_between(concepts[i], concepts[j], text)
                edges.append(DAGEdge(
                    source=f"c{i+1}", target=f"c{j+1}",
                    relation=relation, edge_type=edge_type,
                ))
    
    # Concept-to-sentence edges (concept mentioned in sentence)
    for i, concept in enumerate(concepts):
        for j, sentence in enumerate(key_sentences):
            if concept.lower() in sentence.lower():
                edges.append(DAGEdge(
                    source=f"c{i+1}", target=f"s{j+1}",
                    relation="supports", edge_type="SUPPORTS",
                ))
    
    # Sentence chain edges (sequential)
    for i in range(len(key_sentences) - 1):
        cur_txt = key_sentences[i + 1].lower()
        relation = "supports"
        if any(k in cur_txt for k in ["because", "therefore", "thus", "hence"]):
            relation = "causes"
        elif any(k in cur_txt for k in ["define", "means"]):
            relation = "defines"
        elif any(k in cur_txt for k in ["however", "but", "contrary"]):
            relation = "contrasts"
        edges.append(DAGEdge(
            source=f"s{i+1}", target=f"s{i+2}",
            relation=relation, edge_type=_normalize_edge_type(relation),
        ))
    
    # If no edges were created, add fallback sequential edges
    if not edges and len(nodes) > 1:
        for i in range(len(nodes) - 1):
            edges.append(DAGEdge(
                source=nodes[i].id, target=nodes[i+1].id,
                relation="supports", edge_type="SUPPORTS",
            ))
    
    return DAG(nodes=nodes, edges=edges)


def _extract_json_object(text: str) -> dict[str, Any]:
    """Extract first JSON object from model output."""
    text = text.strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def _dag_from_dict(payload: dict[str, Any]) -> DAG:
    nodes = [
        DAGNode(
            id=str(node["id"]),
            node_type=node.get("node_type", "claim"),
            text=str(node.get("text", "")),
        )
        for node in payload.get("nodes", [])
    ]
    edges = [
        DAGEdge(
            source=str(edge["source"]),
            target=str(edge["target"]),
            relation=str(edge.get("relation", "supports")),
            edge_type=_normalize_edge_type(
                relation=str(edge.get("relation", "supports")),
                edge_type=edge.get("edge_type"),
            ),
        )
        for edge in payload.get("edges", [])
    ]
    return DAG(nodes=nodes, edges=edges)


def extract_dag(text: str, model: str = "gpt-4o-mini", use_mock: bool = False) -> DAG:
    """Extract DAG using OpenAI API when available, otherwise fallback heuristic mode."""
    api_key = os.getenv("OPENAI_API_KEY")
    if use_mock or not api_key:
        return _heuristic_extract(text)

    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        prompt = PROMPT_TEMPLATE.format(input_text=text[:18000])
        response = client.responses.create(
            model=model,
            temperature=0,
            input=prompt,
        )
        output_text = response.output_text
        payload = _extract_json_object(output_text)
        return _dag_from_dict(payload)
    except Exception:
        return _heuristic_extract(text)


def get_manual_prompt(text: str) -> str:
    """Return a manually runnable prompt template for offline extraction."""
    return PROMPT_TEMPLATE.format(input_text=text)
