"""Scoring functions for HTLF Phase 2."""

from __future__ import annotations

import json
import math
import os
import re
import statistics
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal

from .matcher import MatchResult
from .parser import DAG

ProfilePair = Literal["struct_context", "struct_qualia", "context_qualia", "struct", "context", "qualia"]
ProfileMode = Literal["sum", "prod"]

EDGE_TYPE_WEIGHTS: dict[str, float] = {
    "CAUSAL": 1.3,
    "PREMISE": 1.25,
    "SUPPORTS": 1.0,
    "CONTRADICTS": 1.15,
    "DEFINES": 1.05,
    "QUANTIFIES": 0.95,
}

EDGE_TYPE_MISMATCH_DISCOUNT: dict[tuple[str, str], float] = {
    ("CAUSAL", "SUPPORTS"): 0.7,
    ("SUPPORTS", "CAUSAL"): 0.8,
    ("PREMISE", "SUPPORTS"): 0.75,
    ("SUPPORTS", "PREMISE"): 0.8,
    ("DEFINES", "SUPPORTS"): 0.8,
    ("SUPPORTS", "DEFINES"): 0.85,
    ("CONTRADICTS", "SUPPORTS"): 0.6,
    ("SUPPORTS", "CONTRADICTS"): 0.65,
}

TERM_SYNONYM_GROUPS: list[set[str]] = [
    {"gravitational waves", "gravity waves", "重力波", "ripples in spacetime", "時空のさざなみ"},
    {"higgs boson", "ヒッグス粒子", "god particle"},
    {"black hole", "ブラックホール", "event horizon", "事象の地平面"},
    {"protein folding", "タンパク質構造予測", "alphafold", "folding"},
    {"gene editing", "遺伝子編集", "crispr", "crispr-cas9"},
]


@dataclass(slots=True)
class ProfileScore:
    """A single profile score among 12 profile patterns."""

    name: str
    pair: ProfilePair
    mode: ProfileMode
    score: float | None


@dataclass(slots=True)
class ScoreResult:
    """All HTLF axis scores and selected profile."""

    r_struct: float
    r_context: float
    r_qualia: float | None
    profile_type: str
    profile_score: float
    total_loss: float
    all_profiles: list[ProfileScore]


@dataclass(slots=True)
class PremiseItem:
    term: str
    definition: str
    weight: float = 1.0


def _normalize_edge_type(edge: object) -> str:
    edge_type = getattr(edge, "edge_type", None)
    if isinstance(edge_type, str) and edge_type:
        return edge_type.upper()
    rel = getattr(edge, "relation", "supports")
    rel = str(rel).lower()
    if "cause" in rel:
        return "CAUSAL"
    if "depend" in rel or "premise" in rel:
        return "PREMISE"
    if "define" in rel:
        return "DEFINES"
    if "contr" in rel or "oppose" in rel:
        return "CONTRADICTS"
    if "quant" in rel or "measure" in rel:
        return "QUANTIFIES"
    return "SUPPORTS"


def compute_r_struct(source_dag: DAG, target_dag: DAG, match_result: MatchResult) -> float:
    """Compute edge-type-aware DAG preservation ratio for R_struct."""
    source_edges = source_dag.edges
    if not source_edges:
        return 1.0

    mapping = match_result.mapping
    if not mapping:
        return 0.0

    target_index: dict[tuple[str, str], list[str]] = {}
    for edge in target_dag.edges:
        key = (edge.source, edge.target)
        target_index.setdefault(key, []).append(_normalize_edge_type(edge))

    weighted_score = 0.0
    total_weight = 0.0

    for edge in source_edges:
        mapped_source = mapping.get(edge.source)
        mapped_target = mapping.get(edge.target)
        if not mapped_source or not mapped_target:
            continue

        src_type = _normalize_edge_type(edge)
        weight = EDGE_TYPE_WEIGHTS.get(src_type, 1.0)
        total_weight += weight

        best = 0.0
        for tgt_type in target_index.get((mapped_source, mapped_target), []):
            if tgt_type == src_type:
                best = max(best, 1.0)
            else:
                best = max(best, EDGE_TYPE_MISMATCH_DISCOUNT.get((src_type, tgt_type), 0.5))

        weighted_score += weight * best

    if total_weight == 0:
        return 0.0

    return max(0.0, min(1.0, weighted_score / total_weight))


def _tokenize(text: str) -> list[str]:
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヴー]+", text)
        if len(t) > 1
    ]


def _build_synonym_map() -> dict[str, set[str]]:
    synonym_map: dict[str, set[str]] = {}
    for group in TERM_SYNONYM_GROUPS:
        lower_group = {g.lower() for g in group}
        for term in lower_group:
            synonym_map[term] = lower_group - {term}
    return synonym_map


@lru_cache(maxsize=1)
def _embedding_model() -> object | None:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


@lru_cache(maxsize=4096)
def _embed_text(text: str) -> tuple[float, ...] | None:
    model = _embedding_model()
    if model is None:
        return None
    try:
        vec = model.encode([text], normalize_embeddings=True)[0]
        return tuple(float(x) for x in vec)
    except Exception:
        return None


def _cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _extract_json_block(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _llm_json_openai(prompt: str, model: str, temperature: float = 0.0) -> dict[str, Any] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        response = client.responses.create(model=model, input=prompt, temperature=temperature)
        return _extract_json_block(response.output_text)
    except Exception:
        return None


def _llm_json_gemini(prompt: str, model: str = "gemini-1.5-flash", temperature: float = 0.0) -> dict[str, Any] | None:
    api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        import google.generativeai as genai  # type: ignore

        genai.configure(api_key=api_key)
        gm = genai.GenerativeModel(model)
        response = gm.generate_content(
            prompt,
            generation_config={"temperature": temperature, "response_mime_type": "application/json"},
        )
        text = getattr(response, "text", "") or ""
        return _extract_json_block(text)
    except Exception:
        return None


def _llm_json(prompt: str, openai_model: str = "gpt-4o-mini", gemini_model: str = "gemini-1.5-flash", temperature: float = 0.0) -> dict[str, Any] | None:
    return _llm_json_openai(prompt=prompt, model=openai_model, temperature=temperature) or _llm_json_gemini(
        prompt=prompt, model=gemini_model, temperature=temperature
    )


def _text_similarity(a: str, b: str) -> float:
    va = _embed_text(a)
    vb = _embed_text(b)
    if va is not None and vb is not None:
        return max(0.0, min(1.0, (_cosine(va, vb) + 1.0) / 2.0))

    ta = set(_tokenize(a))
    tb = set(_tokenize(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _extract_premises_with_llm(source_text: str) -> list[PremiseItem] | None:
    prompt = f"""SOURCE テキストを読んで、読者が必要とする前提知識を抽出してください。
返答はJSONのみ:
{{"items":[{{"term":"...","definition":"...","weight":1.0}}]}}
- term: 専門用語/概念
- definition: SOURCE内での意味（1-2文）
- weight: 重要度(0.5-2.0)
最大12件。

SOURCE:\n{source_text[:14000]}"""
    data = _llm_json(prompt)
    if not data or "items" not in data:
        return None
    items: list[PremiseItem] = []
    for row in data.get("items", []):
        try:
            term = str(row.get("term", "")).strip()
            definition = str(row.get("definition", "")).strip()
            if not term or not definition:
                continue
            w = float(row.get("weight", 1.0))
            items.append(PremiseItem(term=term, definition=definition, weight=max(0.3, min(2.5, w))))
        except Exception:
            continue
    return items or None


def _extract_premise_units(text: str) -> list[dict[str, object]]:
    units: list[dict[str, object]] = []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", text) if s.strip()]
    premise_markers = ("if", "when", "under", "assuming", "given", "provided", "条件", "前提", "ただし", "場合")

    for idx, s in enumerate(sentences):
        low = s.lower()
        if any(m in low for m in premise_markers) or idx < 6:
            tokens = _tokenize(s)
            ngrams = set()
            for n in (2, 3):
                for i in range(len(tokens) - n + 1):
                    ngrams.add(" ".join(tokens[i : i + n]))

            parents: list[int] = []
            if units:
                parents.append(len(units) - 1)

            units.append({"text": s, "tokens": tokens, "ngrams": ngrams, "parents": parents})

    return units


def _premises_from_heuristic(source_text: str) -> list[PremiseItem]:
    units = _extract_premise_units(source_text)
    items: list[PremiseItem] = []
    for unit in units[:12]:
        toks = list(unit.get("tokens", []))
        if not toks:
            continue
        term = " ".join(toks[: min(4, len(toks))])
        definition = str(unit.get("text", ""))[:280]
        items.append(PremiseItem(term=term, definition=definition, weight=1.0))
    return items


def _reader_definitions_from_target(target_text: str, items: list[PremiseItem]) -> dict[str, str] | None:
    term_list = "\n".join(f"- {it.term}" for it in items)
    prompt = f"""あなたはTARGETだけを読んだ読者です。SOURCEは見ていません。
以下の用語/概念をTARGETのみから定義してください。
不明なら "UNKNOWN" と書いてください。
JSONのみで返答:
{{"definitions":[{{"term":"...","definition":"..."}}]}}

TERMS:\n{term_list}

TARGET:\n{target_text[:14000]}"""
    data = _llm_json(prompt)
    if not data:
        return None
    defs: dict[str, str] = {}
    for row in data.get("definitions", []):
        term = str(row.get("term", "")).strip()
        definition = str(row.get("definition", "")).strip()
        if term:
            defs[term.lower()] = definition
    return defs or None


def _token_match(src: str, tgt_tokens: set[str], synonym_map: dict[str, set[str]]) -> bool:
    if src in tgt_tokens:
        return True
    if src in synonym_map and synonym_map[src] & tgt_tokens:
        return True

    src_vec = _embed_text(src)
    if src_vec is None:
        return False

    for t in tgt_tokens:
        tgt_vec = _embed_text(t)
        if tgt_vec is None:
            continue
        if _cosine(src_vec, tgt_vec) >= 0.80:
            return True
    return False


def _idf_weights(source_units: list[dict[str, object]], target_text: str) -> dict[str, float]:
    docs: list[set[str]] = []
    for u in source_units:
        docs.append(set(u.get("tokens", [])))
    docs.append(set(_tokenize(target_text)))

    n_docs = max(1, len(docs))
    df: dict[str, int] = {}
    for d in docs:
        for t in d:
            df[t] = df.get(t, 0) + 1

    return {t: math.log((1 + n_docs) / (1 + c)) + 1.0 for t, c in df.items()}


def _heuristic_context_score(source_text: str, target_text: str) -> float:
    source_units = _extract_premise_units(source_text)
    if not source_units:
        return 0.5

    synonym_map = _build_synonym_map()
    target_tokens = set(_tokenize(target_text))
    target_ngrams = set()
    tgt_seq = _tokenize(target_text)
    for n in (2, 3):
        for i in range(len(tgt_seq) - n + 1):
            target_ngrams.add(" ".join(tgt_seq[i : i + n]))

    target_sentences = [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", target_text) if s.strip()]
    idf = _idf_weights(source_units, target_text)

    weighted_sum = 0.0
    total_weight = 0.0

    for idx, unit in enumerate(source_units):
        tokens: list[str] = list(unit.get("tokens", []))
        ngrams: set[str] = set(unit.get("ngrams", set()))
        parents: list[int] = list(unit.get("parents", []))
        unit_text = str(unit.get("text", ""))

        token_weight = sum(idf.get(t, 1.0) for t in tokens) or 1.0
        token_hit = sum(idf.get(t, 1.0) for t in tokens if _token_match(t, target_tokens, synonym_map))
        token_score = token_hit / token_weight

        if ngrams:
            matched_ng = sum(1 for ng in ngrams if ng in target_ngrams)
            ngram_score = matched_ng / len(ngrams)
        else:
            ngram_score = token_score

        semantic_score = max((_text_similarity(unit_text, ts) for ts in target_sentences), default=0.0)

        parent_missing_factor = 1.0
        if parents:
            parent_scores = []
            for p in parents:
                if p < idx and p < len(source_units):
                    p_text = str(source_units[p].get("text", ""))
                    parent_scores.append(max((_text_similarity(p_text, ts) for ts in target_sentences), default=0.0))
            if parent_scores and max(parent_scores) < 0.30 and semantic_score < 0.30:
                parent_missing_factor = 0.75

        unit_score = (0.45 * token_score + 0.20 * ngram_score + 0.35 * semantic_score) * parent_missing_factor
        unit_weight = token_weight * (1.1 if parents else 1.0)

        total_weight += unit_weight
        weighted_sum += unit_weight * unit_score

    premise_score = (weighted_sum / total_weight) if total_weight > 0 else 0.0
    global_semantic = _text_similarity(source_text[:4000], target_text[:4000])
    return max(0.0, min(1.0, 0.75 * premise_score + 0.25 * global_semantic))


def compute_r_context(source_text: str, target_text: str, model: str = "gpt-4o-mini") -> float:
    """LLM-as-reader protocol with OpenAI -> Gemini -> heuristic fallback."""
    items = _extract_premises_with_llm(source_text)
    if not items:
        items = _premises_from_heuristic(source_text)

    reader_defs = _reader_definitions_from_target(target_text, items)
    if reader_defs:
        weighted_sum = 0.0
        total_weight = 0.0
        for item in items:
            pred = reader_defs.get(item.term.lower(), "UNKNOWN")
            if pred.strip().upper() == "UNKNOWN":
                sim = 0.0
            else:
                sim = _text_similarity(item.definition, pred)
            weighted_sum += item.weight * sim
            total_weight += item.weight
        if total_weight > 0:
            return max(0.0, min(1.0, weighted_sum / total_weight))

    return _heuristic_context_score(source_text, target_text)


def compute_r_context_batch(cases: list[tuple[str, str]]) -> list[float]:
    """Batch-compatible scorer for validation runs."""
    return [compute_r_context(src, tgt) for src, tgt in cases]


def _heuristic_qualia(source_text: str, target_text: str) -> float:
    semantic = _text_similarity(source_text[:5000], target_text[:5000])
    src_exclaim = source_text.count("!") / max(1, len(source_text))
    tgt_exclaim = target_text.count("!") / max(1, len(target_text))
    src_q = source_text.count("?") / max(1, len(source_text))
    tgt_q = target_text.count("?") / max(1, len(target_text))
    style_match = 1.0 - min(1.0, abs(src_exclaim - tgt_exclaim) * 2000 + abs(src_q - tgt_q) * 2000)
    score = 0.10 + 0.25 * semantic + 0.15 * style_match
    return max(0.0, min(1.0, score))


def _llm_qualia_one(source_text: str, target_text: str, temperature: float) -> float | None:
    prompt = f"""SOURCE と TARGET の体験的・感情的・感覚的な質(qualia)の保存度を1-5で採点。
採点基準:
1=ほぼ失われた, 3=部分保持, 5=高度に保持。
JSONのみ: {{"rating": 1-5, "rationale": "..."}}

SOURCE:\n{source_text[:10000]}

TARGET:\n{target_text[:10000]}"""
    data = _llm_json(prompt, temperature=temperature)
    if not data:
        return None
    try:
        rating = float(data.get("rating"))
        if rating < 1 or rating > 5:
            return None
        return rating
    except Exception:
        return None


def compute_r_qualia(source_text: str, target_text: str) -> float:
    """LLM ensemble proxy: median(3 ratings)/5.0, Gemini-backed via fallback chain."""
    ratings: list[float] = []
    for temp in (0.0, 0.4, 0.8):
        r = _llm_qualia_one(source_text, target_text, temperature=temp)
        if r is not None:
            ratings.append(r)
    if ratings:
        med = statistics.median(ratings)
        return max(0.0, min(1.0, med / 5.0))
    return _heuristic_qualia(source_text, target_text)


def classify_profiles(
    r_struct: float,
    r_context: float,
    r_qualia: float | None,
    alpha: float = 0.5,
    beta: float = 0.5,
) -> tuple[str, float, list[ProfileScore]]:
    """Compute 12 profile patterns and return best profile label."""
    assert abs(alpha + beta - 1.0) < 1e-9, "alpha + beta must be 1"

    axes: dict[str, float | None] = {
        "struct": r_struct,
        "context": r_context,
        "qualia": r_qualia,
    }

    pattern_defs: list[tuple[str, ProfilePair, ProfileMode, tuple[str, str] | tuple[str]]] = [
        ("P01_struct_context_sum", "struct_context", "sum", ("struct", "context")),
        ("P02_struct_context_prod", "struct_context", "prod", ("struct", "context")),
        ("P03_struct_qualia_sum", "struct_qualia", "sum", ("struct", "qualia")),
        ("P04_struct_qualia_prod", "struct_qualia", "prod", ("struct", "qualia")),
        ("P05_context_qualia_sum", "context_qualia", "sum", ("context", "qualia")),
        ("P06_context_qualia_prod", "context_qualia", "prod", ("context", "qualia")),
        ("P07_struct_sum", "struct", "sum", ("struct",)),
        ("P08_struct_prod", "struct", "prod", ("struct",)),
        ("P09_context_sum", "context", "sum", ("context",)),
        ("P10_context_prod", "context", "prod", ("context",)),
        ("P11_qualia_sum", "qualia", "sum", ("qualia",)),
        ("P12_qualia_prod", "qualia", "prod", ("qualia",)),
    ]

    profiles: list[ProfileScore] = []
    for name, pair, mode, parts in pattern_defs:
        values = [axes[p] for p in parts]
        if any(v is None for v in values):
            profiles.append(ProfileScore(name=name, pair=pair, mode=mode, score=None))
            continue

        nums = [float(v) for v in values if v is not None]
        if len(nums) == 1:
            score = nums[0]
        elif mode == "sum":
            score = alpha * nums[0] + beta * nums[1]
        else:
            score = (nums[0] ** alpha) * (nums[1] ** beta)
        profiles.append(ProfileScore(name=name, pair=pair, mode=mode, score=max(0.0, min(1.0, score))))

    valid_profiles = [p for p in profiles if p.score is not None]
    best = max(valid_profiles, key=lambda p: float(p.score)) if valid_profiles else None
    if best is None or best.score is None:
        return ("P00_unclassified", 0.0, profiles)
    return (best.name, float(best.score), profiles)


def compute_scores(
    source_dag: DAG,
    target_dag: DAG,
    match_result: MatchResult,
    source_text: str,
    target_text: str,
    alpha: float = 0.5,
    beta: float = 0.5,
) -> ScoreResult:
    """Compute HTLF Phase 2 score bundle."""
    r_struct = compute_r_struct(source_dag, target_dag, match_result)
    r_context = compute_r_context(source_text, target_text)
    r_qualia = compute_r_qualia(source_text, target_text)

    profile_type, profile_score, all_profiles = classify_profiles(
        r_struct=r_struct,
        r_context=r_context,
        r_qualia=r_qualia,
        alpha=alpha,
        beta=beta,
    )

    total_loss = 1.0 - profile_score
    return ScoreResult(
        r_struct=r_struct,
        r_context=r_context,
        r_qualia=r_qualia,
        profile_type=profile_type,
        profile_score=profile_score,
        total_loss=total_loss,
        all_profiles=all_profiles,
    )
