"""Scoring functions for HTLF Phase 1."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Literal

from .matcher import MatchResult
from .parser import DAG

ProfilePair = Literal["struct_context", "struct_qualia", "context_qualia", "struct", "context", "qualia"]
ProfileMode = Literal["sum", "prod"]


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


def compute_r_struct(source_dag: DAG, target_dag: DAG, match_result: MatchResult) -> float:
    """Compute DAG edge preservation ratio for R_struct."""
    source_edges = source_dag.edges
    if not source_edges:
        return 1.0

    mapping = match_result.mapping
    target_edge_set = {(edge.source, edge.target, edge.relation) for edge in target_dag.edges}
    target_edge_weak = {(edge.source, edge.target) for edge in target_dag.edges}

    preserved = 0
    for edge in source_edges:
        mapped_source = mapping.get(edge.source)
        mapped_target = mapping.get(edge.target)
        if not mapped_source or not mapped_target:
            continue
        if (mapped_source, mapped_target, edge.relation) in target_edge_set or (mapped_source, mapped_target) in target_edge_weak:
            preserved += 1

    return max(0.0, min(1.0, preserved / len(source_edges)))


def _extract_premises(text: str) -> set[str]:
    lines = re.split(r"(?<=[.!?。！？])\s+", text)
    premise_markers = ("if", "when", "under", "assuming", "given", "provided", "条件", "前提", "ただし", "場合")
    extracted: set[str] = set()
    for line in lines:
        lower = line.lower()
        if any(marker in lower for marker in premise_markers):
            for token in re.findall(r"\w+", lower):
                if len(token) >= 4:
                    extracted.add(token)
    return extracted


def _llm_context_score(source_text: str, target_text: str, model: str = "gpt-4o-mini") -> float | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # type: ignore

        client = OpenAI(api_key=api_key)
        prompt = f"""You are evaluating context restoration fidelity.
Rate how much prerequisite context from SOURCE is preserved in TARGET.
Return strict JSON: {{"score": float(0..1), "rationale": "..."}}

SOURCE:\n{source_text[:12000]}\n\nTARGET:\n{target_text[:12000]}"""
        response = client.responses.create(model=model, temperature=0, input=prompt)
        payload = json.loads(response.output_text)
        score = float(payload["score"])
        return max(0.0, min(1.0, score))
    except Exception:
        return None


def compute_r_context(source_text: str, target_text: str, model: str = "gpt-4o-mini") -> float:
    """Compute context restoration score with LLM-as-reader fallback."""
    llm_score = _llm_context_score(source_text, target_text, model=model)
    if llm_score is not None:
        return llm_score

    src_premises = _extract_premises(source_text)
    tgt_premises = _extract_premises(target_text)
    if not src_premises:
        return 0.5
    overlap = len(src_premises & tgt_premises)
    return max(0.0, min(1.0, overlap / len(src_premises)))


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
    """Compute HTLF Phase 1 score bundle."""
    r_struct = compute_r_struct(source_dag, target_dag, match_result)
    r_context = compute_r_context(source_text, target_text)
    r_qualia = None

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
