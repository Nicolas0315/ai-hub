"""Bipartite graph matcher for HTLF DAG nodes."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from .parser import DAG
from . import rust_bridge as rb


@dataclass(slots=True)
class NodeMatch:
    """Single source-target node match."""

    source_id: str
    target_id: str
    similarity: float
    matched: bool


@dataclass(slots=True)
class MatchResult:
    """Output of bipartite matching."""

    matches: list[NodeMatch]
    unmatched_source_ids: list[str]
    unmatched_target_ids: list[str]

    @property
    def mapping(self) -> dict[str, str]:
        """Get source->target map for matched nodes."""
        return {m.source_id: m.target_id for m in self.matches if m.matched}


def _tokenize(text: str) -> set[str]:
    # English words + Japanese chunks
    return {
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_]+|[一-龯ぁ-んァ-ヴー]+", text)
        if len(t) > 1
    }


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def get_similarity_backend_name() -> str:
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _ = SentenceTransformer("all-MiniLM-L6-v2")
        return "sentence_transformers"
    except Exception:
        return "lexical"


def _get_similarity_backend() -> Callable[[list[str], list[str]], list[list[float]]]:
    """Return embedding similarity backend with fallback."""

    backend = get_similarity_backend_name()
    if backend == "sentence_transformers":
        from sentence_transformers import SentenceTransformer  # type: ignore

        model = SentenceTransformer("all-MiniLM-L6-v2")

        def embed_similarity(source_texts: list[str], target_texts: list[str]) -> list[list[float]]:
            source_emb = model.encode(source_texts, normalize_embeddings=True)
            target_emb = model.encode(target_texts, normalize_embeddings=True)
            return rb.htlf_similarity_matrix(
                [[float(x) for x in row] for row in source_emb],
                [[float(x) for x in row] for row in target_emb],
            )

        return embed_similarity

    def lexical_similarity(source_texts: list[str], target_texts: list[str]) -> list[list[float]]:
        return [[_jaccard(a, b) for b in target_texts] for a in source_texts]

    return lexical_similarity


def _node_edge_signature(dag: DAG) -> dict[str, set[str]]:
    sig: dict[str, set[str]] = {n.id: set() for n in dag.nodes}
    for e in dag.edges:
        edge_type = getattr(e, "edge_type", "SUPPORTS")
        sig.setdefault(e.source, set()).add(f"out:{edge_type}")
        sig.setdefault(e.target, set()).add(f"in:{edge_type}")
    return sig


def _signature_alignment_bonus(source_sig: set[str], target_sig: set[str]) -> float:
    if not source_sig or not target_sig:
        return 0.0
    overlap = len(source_sig & target_sig) / max(1, len(source_sig | target_sig))
    # small bonus to prioritize edge-type compatible node matches
    return 0.15 * overlap


def match_dags(source_dag: DAG, target_dag: DAG, threshold: float = 0.7) -> MatchResult:
    """Run greedy bipartite matching based on semantic similarity + edge-type signature bonus."""
    source_nodes = source_dag.nodes
    target_nodes = target_dag.nodes
    if not source_nodes or not target_nodes:
        return MatchResult(matches=[], unmatched_source_ids=[n.id for n in source_nodes], unmatched_target_ids=[n.id for n in target_nodes])

    similarity_fn = _get_similarity_backend()
    matrix = similarity_fn([n.text for n in source_nodes], [n.text for n in target_nodes])

    src_sig = _node_edge_signature(source_dag)
    tgt_sig = _node_edge_signature(target_dag)

    candidate_pairs: list[tuple[float, int, int]] = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if math.isnan(value):
                continue
            bonus = _signature_alignment_bonus(src_sig.get(source_nodes[i].id, set()), tgt_sig.get(target_nodes[j].id, set()))
            candidate_pairs.append((max(0.0, min(1.0, value + bonus)), i, j))
    candidate_pairs.sort(reverse=True, key=lambda x: x[0])

    used_source: set[int] = set()
    used_target: set[int] = set()
    matches: list[NodeMatch] = []

    for similarity, i, j in candidate_pairs:
        if i in used_source or j in used_target:
            continue
        if similarity < threshold:
            continue
        used_source.add(i)
        used_target.add(j)
        matches.append(
            NodeMatch(
                source_id=source_nodes[i].id,
                target_id=target_nodes[j].id,
                similarity=similarity,
                matched=True,
            )
        )

    unmatched_source_ids = [node.id for idx, node in enumerate(source_nodes) if idx not in used_source]
    unmatched_target_ids = [node.id for idx, node in enumerate(target_nodes) if idx not in used_target]

    return MatchResult(matches=matches, unmatched_source_ids=unmatched_source_ids, unmatched_target_ids=unmatched_target_ids)
