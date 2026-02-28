"""
Solver Quality Engine — HTLF-based Multi-Solver Consensus Analysis

Applies HTLF's translation loss model *between solvers* to measure:
1. Solver diversity (are they actually independent?)
2. Disagreement classification (data gap vs epistemic vs principled)
3. Expertise matching (domain-solver affinity)
4. Consensus depth (confident agreement vs herd following)

The key insight (Youta Hilono):
"Multi-solver consensus at 94% can't reach 100% by adding more solvers.
The gap is inter-solver translation loss — solvers interpret the same
evidence through different frameworks, and that translation is lossy."

This is HTLF applied to the verification process itself.

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any

# ── Constants ──
MIN_DIVERSITY_THRESHOLD = 0.3    # Below this, solvers are too similar
EXPERTISE_DOMAINS = [
    "formal_logic", "empirical", "statistical", "causal",
    "linguistic", "cultural", "temporal", "creative",
]
DISAGREEMENT_TYPES = [
    "data_gap",       # Insufficient evidence — solvable with more data
    "epistemic",      # Different knowledge bases — solvable with knowledge sharing
    "framework",      # Different paradigms (Kuhnian) — may be principled
    "principled",     # Fundamentally underdetermined (Quinean) — not solvable
]
CONFIDENCE_BINS = 5   # Discretize confidence for depth analysis
HERD_THRESHOLD = 0.15  # If std(confidence) < this, possible herding


# ════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════

@dataclass(slots=True)
class SolverProfile:
    """Profile of a single solver's characteristics."""
    solver_id: str
    solver_type: str           # "llm" | "formal" | "statistical" | "hybrid" | "human"
    expertise: dict[str, float] = field(default_factory=dict)  # domain → affinity (0-1)
    reasoning_framework: str = "general"  # "deductive" | "inductive" | "abductive" | "bayesian"
    base_model: str = ""       # For LLM solvers: which model family


@dataclass(slots=True)
class SolverVote:
    """A single solver's verdict on a claim."""
    solver_id: str
    verdict: str               # "true" | "false" | "uncertain" | "not_applicable"
    confidence: float          # 0-1
    reasoning_summary: str = ""
    evidence_cited: list[str] = field(default_factory=list)
    domain_relevance: float = 0.5  # How relevant is this solver to this claim


@dataclass(slots=True)
class DisagreementAnalysis:
    """Classification of why solvers disagree."""
    disagreement_type: str     # data_gap | epistemic | framework | principled
    confidence: float          # How confident we are in this classification
    root_cause: str
    resolution_path: str       # How to resolve (if resolvable)
    is_resolvable: bool


@dataclass(slots=True)
class ConsensusReport:
    """Full multi-solver consensus analysis with HTLF metrics."""
    # Basic consensus
    total_solvers: int
    agreeing: int
    disagreeing: int
    abstaining: int
    raw_consensus: float       # Simple majority ratio

    # HTLF-enhanced metrics
    diversity_score: float     # 0-1: how diverse are the solvers
    depth_score: float         # 0-1: confidence-weighted agreement
    expertise_match: float     # 0-1: are the right solvers voting
    inter_solver_loss: float   # HTLF translation loss between solver frameworks

    # Enhanced consensus (adjusted for quality)
    adjusted_consensus: float  # Raw consensus × quality multiplier

    # Disagreement analysis
    disagreements: list[DisagreementAnalysis]

    # Recommendations
    weak_points: list[str]
    improvement_actions: list[str]


# ════════════════════════════════════════════
# 1. Solver Diversity Measurement
# ════════════════════════════════════════════

def compute_diversity(profiles: list[SolverProfile]) -> tuple[float, list[str]]:
    """Measure how diverse the solver pool is.

    Diversity = 1 - avg_pairwise_similarity.
    Similar solvers (same type, same model, same framework) reduce diversity.
    """
    if len(profiles) <= 1:
        return 0.0, ["Only one solver — no diversity possible"]

    warnings = []
    similarities = []

    for i, a in enumerate(profiles):
        for b in profiles[i + 1:]:
            sim = _solver_similarity(a, b)
            similarities.append(sim)

    avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
    diversity = round(1.0 - avg_sim, 4)

    # Check for problematic patterns
    type_counts: dict[str, int] = {}
    model_counts: dict[str, int] = {}
    for p in profiles:
        type_counts[p.solver_type] = type_counts.get(p.solver_type, 0) + 1
        if p.base_model:
            model_counts[p.base_model] = model_counts.get(p.base_model, 0) + 1

    total = len(profiles)
    for stype, count in type_counts.items():
        if count / total > 0.7:
            warnings.append(f"Low type diversity: {count}/{total} solvers are '{stype}'")

    for model, count in model_counts.items():
        if count / total > 0.5:
            warnings.append(f"Model monoculture: {count}/{total} use '{model}'")

    if diversity < MIN_DIVERSITY_THRESHOLD:
        warnings.append(f"Diversity {diversity:.0%} below threshold {MIN_DIVERSITY_THRESHOLD:.0%}")

    return diversity, warnings


def _solver_similarity(a: SolverProfile, b: SolverProfile) -> float:
    """Pairwise similarity between two solvers. 0=totally different, 1=identical."""
    score = 0.0
    weights = 0.0

    # Same type
    weights += 0.3
    if a.solver_type == b.solver_type:
        score += 0.3

    # Same base model
    weights += 0.3
    if a.base_model and a.base_model == b.base_model:
        score += 0.3

    # Same reasoning framework
    weights += 0.2
    if a.reasoning_framework == b.reasoning_framework:
        score += 0.2

    # Expertise overlap (cosine-like)
    weights += 0.2
    if a.expertise and b.expertise:
        domains = set(a.expertise) | set(b.expertise)
        if domains:
            dot = sum(a.expertise.get(d, 0) * b.expertise.get(d, 0) for d in domains)
            mag_a = math.sqrt(sum(v ** 2 for v in a.expertise.values()))
            mag_b = math.sqrt(sum(v ** 2 for v in b.expertise.values()))
            if mag_a > 0 and mag_b > 0:
                score += 0.2 * (dot / (mag_a * mag_b))

    return round(score / weights if weights > 0 else 0.0, 4)


# ════════════════════════════════════════════
# 2. Disagreement Classification
# ════════════════════════════════════════════

def classify_disagreement(
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile] | None = None,
) -> list[DisagreementAnalysis]:
    """Classify why solvers disagree.

    Four types (in order of resolvability):
    1. data_gap: Insufficient evidence → add more evidence
    2. epistemic: Different knowledge → share knowledge between solvers
    3. framework: Different paradigms → Kuhnian incommensurability
    4. principled: Fundamentally underdetermined → Quinean indeterminacy
    """
    if not votes:
        return []

    # Group by verdict
    verdict_groups: dict[str, list[SolverVote]] = {}
    for v in votes:
        verdict_groups.setdefault(v.verdict, []).append(v)

    if len(verdict_groups) <= 1:
        return []  # No disagreement

    analyses = []

    # Analyze each pair of disagreeing groups
    verdicts = list(verdict_groups.keys())
    for i, v1 in enumerate(verdicts):
        for v2 in verdicts[i + 1:]:
            group1 = verdict_groups[v1]
            group2 = verdict_groups[v2]

            analysis = _classify_pair(group1, group2, profiles)
            analyses.append(analysis)

    return analyses


def _classify_pair(
    group_a: list[SolverVote],
    group_b: list[SolverVote],
    profiles: dict[str, SolverProfile] | None,
) -> DisagreementAnalysis:
    """Classify a specific disagreement between two groups."""
    # Heuristic 1: Low confidence on both sides → data_gap
    avg_conf_a = sum(v.confidence for v in group_a) / len(group_a)
    avg_conf_b = sum(v.confidence for v in group_b) / len(group_b)

    if avg_conf_a < 0.5 and avg_conf_b < 0.5:
        return DisagreementAnalysis(
            disagreement_type="data_gap",
            confidence=round(1.0 - max(avg_conf_a, avg_conf_b), 4),
            root_cause="Both sides have low confidence — insufficient evidence",
            resolution_path="Gather more evidence and re-evaluate",
            is_resolvable=True,
        )

    # Heuristic 2: Different evidence cited → epistemic
    evidence_a = set()
    evidence_b = set()
    for v in group_a:
        evidence_a.update(v.evidence_cited)
    for v in group_b:
        evidence_b.update(v.evidence_cited)

    if evidence_a and evidence_b:
        overlap = evidence_a & evidence_b
        total = evidence_a | evidence_b
        evidence_overlap = len(overlap) / len(total) if total else 0
        if evidence_overlap < 0.3:
            return DisagreementAnalysis(
                disagreement_type="epistemic",
                confidence=round(1.0 - evidence_overlap, 4),
                root_cause=f"Evidence overlap only {evidence_overlap:.0%} — solvers see different data",
                resolution_path="Share evidence between solver groups and re-evaluate",
                is_resolvable=True,
            )

    # Heuristic 3: Different solver types/frameworks → framework
    if profiles:
        types_a = {profiles[v.solver_id].solver_type for v in group_a if v.solver_id in profiles}
        types_b = {profiles[v.solver_id].solver_type for v in group_b if v.solver_id in profiles}
        frameworks_a = {profiles[v.solver_id].reasoning_framework for v in group_a if v.solver_id in profiles}
        frameworks_b = {profiles[v.solver_id].reasoning_framework for v in group_b if v.solver_id in profiles}

        if types_a and types_b and not (types_a & types_b):
            return DisagreementAnalysis(
                disagreement_type="framework",
                confidence=0.7,
                root_cause=f"Paradigm split: {types_a} vs {types_b}",
                resolution_path="Meta-analysis across paradigms (Kuhnian bridge)",
                is_resolvable=False,  # Partially — requires paradigm negotiation
            )

        if frameworks_a and frameworks_b and not (frameworks_a & frameworks_b):
            return DisagreementAnalysis(
                disagreement_type="framework",
                confidence=0.6,
                root_cause=f"Reasoning framework split: {frameworks_a} vs {frameworks_b}",
                resolution_path="Identify shared premises and reason from there",
                is_resolvable=False,
            )

    # Heuristic 4: High confidence on both sides, same evidence → principled
    if avg_conf_a > 0.7 and avg_conf_b > 0.7:
        return DisagreementAnalysis(
            disagreement_type="principled",
            confidence=round(min(avg_conf_a, avg_conf_b), 4),
            root_cause="High-confidence disagreement with shared evidence — Quinean indeterminacy",
            resolution_path="Accept indeterminacy; report as (value, uncertainty) pair",
            is_resolvable=False,
        )

    # Default: epistemic
    return DisagreementAnalysis(
        disagreement_type="epistemic",
        confidence=0.4,
        root_cause="Unclear disagreement source",
        resolution_path="Decompose claim into sub-claims and re-evaluate",
        is_resolvable=True,
    )


# ════════════════════════════════════════════
# 3. Expertise Matching
# ════════════════════════════════════════════

def compute_expertise_match(
    claim_domain: str,
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile],
) -> tuple[float, list[str]]:
    """Measure how well solver expertise matches the claim domain.

    Returns (match_score, warnings).
    """
    warnings = []
    if not votes or not profiles:
        return 0.5, ["No profiles available for expertise matching"]

    relevance_scores = []
    for v in votes:
        profile = profiles.get(v.solver_id)
        if profile and profile.expertise:
            domain_affinity = profile.expertise.get(claim_domain, 0.0)
            # Also check related domains
            related = max(
                (profile.expertise.get(d, 0.0) for d in EXPERTISE_DOMAINS
                 if d != claim_domain),
                default=0.0,
            )
            relevance = 0.7 * domain_affinity + 0.3 * related
            relevance_scores.append(relevance)
            v.domain_relevance = round(relevance, 4)
        else:
            relevance_scores.append(0.5)

    match = sum(relevance_scores) / len(relevance_scores) if relevance_scores else 0.5

    # Warn if low-expertise solvers are voting with high confidence
    for v in votes:
        if v.domain_relevance < 0.3 and v.confidence > 0.8:
            warnings.append(
                f"Solver {v.solver_id}: high confidence ({v.confidence:.0%}) "
                f"but low domain relevance ({v.domain_relevance:.0%})"
            )

    return round(match, 4), warnings


# ════════════════════════════════════════════
# 4. Consensus Depth
# ════════════════════════════════════════════

def compute_consensus_depth(votes: list[SolverVote]) -> tuple[float, list[str]]:
    """Measure depth of consensus: confident agreement vs herd following.

    High depth = solvers independently arrived at high-confidence agreement.
    Low depth = solvers agreed but with low/uniform confidence (herding).
    """
    if not votes:
        return 0.0, ["No votes"]

    warnings = []
    agreeing = [v for v in votes if v.verdict in ("true", "false")]
    if not agreeing:
        return 0.0, ["No definitive votes"]

    # Majority verdict
    true_count = sum(1 for v in agreeing if v.verdict == "true")
    false_count = len(agreeing) - true_count
    majority = "true" if true_count >= false_count else "false"
    majority_votes = [v for v in agreeing if v.verdict == majority]

    # Confidence distribution of majority
    confidences = [v.confidence for v in majority_votes]
    mean_conf = sum(confidences) / len(confidences)
    std_conf = math.sqrt(sum((c - mean_conf) ** 2 for c in confidences) / len(confidences)) if len(confidences) > 1 else 0.0

    # Herd detection: very low variance in confidence
    if std_conf < HERD_THRESHOLD and len(majority_votes) > 3:
        warnings.append(
            f"Possible herding: confidence std={std_conf:.3f} "
            f"(all around {mean_conf:.0%}) — may not be independent"
        )

    # Depth = mean_confidence × variance_penalty
    # High mean + high variance = independent confident agreement = best
    # High mean + low variance = possible herding = penalized
    # Low mean = weak agreement = low depth
    variance_bonus = min(1.0, std_conf / 0.2)  # Reward some variance
    depth = mean_conf * (0.7 + 0.3 * variance_bonus)

    return round(max(0.0, min(1.0, depth)), 4), warnings


# ════════════════════════════════════════════
# 5. Inter-Solver Translation Loss (HTLF Application)
# ════════════════════════════════════════════

def compute_inter_solver_loss(
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile],
) -> float:
    """Compute HTLF translation loss between solver frameworks.

    When solver A (deductive) and solver B (bayesian) disagree,
    the disagreement itself has translation loss — they're speaking
    different "languages" about the same evidence.

    This is the meta-application of HTLF: measuring the loss in
    the verification process itself.
    """
    if len(votes) < 2 or not profiles:
        return 0.0

    losses = []
    for i, va in enumerate(votes):
        pa = profiles.get(va.solver_id)
        if not pa:
            continue
        for vb in votes[i + 1:]:
            pb = profiles.get(vb.solver_id)
            if not pb:
                continue

            # Framework distance
            framework_loss = 0.0 if pa.reasoning_framework == pb.reasoning_framework else 0.3

            # Type distance
            type_loss = 0.0 if pa.solver_type == pb.solver_type else 0.2

            # Expertise vector distance
            domains = set(pa.expertise) | set(pb.expertise)
            if domains:
                diff = sum(
                    (pa.expertise.get(d, 0) - pb.expertise.get(d, 0)) ** 2
                    for d in domains
                )
                expertise_loss = min(0.3, math.sqrt(diff / len(domains)))
            else:
                expertise_loss = 0.15

            # Verdict agreement reduces perceived loss
            verdict_bonus = 0.0
            if va.verdict == vb.verdict:
                verdict_bonus = -0.1  # Agreement despite framework difference = less loss

            pair_loss = max(0.0, framework_loss + type_loss + expertise_loss + verdict_bonus)
            losses.append(pair_loss)

    return round(sum(losses) / len(losses) if losses else 0.0, 4)


# ════════════════════════════════════════════
# Main Engine
# ════════════════════════════════════════════

class SolverQualityEngine:
    """HTLF-based multi-solver consensus quality analyzer.

    Instead of just counting votes, measures the *quality* of consensus:
    - Are solvers diverse enough? (not 28 copies of the same LLM)
    - Why do they disagree? (data gap vs Quinean indeterminacy)
    - Are the right solvers voting? (expertise matching)
    - Is agreement deep? (confident vs herding)
    - What's the inter-solver translation loss?

    Usage:
        engine = SolverQualityEngine()
        report = engine.analyze(votes, profiles, claim_domain="formal_logic")
        print(engine.format_report(report))
    """

    def analyze(
        self,
        votes: list[SolverVote],
        profiles: dict[str, SolverProfile] | None = None,
        claim_domain: str = "general",
    ) -> ConsensusReport:
        """Full consensus quality analysis."""
        profiles = profiles or {}
        profile_map = {p.solver_id: p for p in profiles.values()} if isinstance(profiles, dict) else profiles

        # If profiles is dict[str, SolverProfile], use directly
        if profiles and isinstance(next(iter(profiles.values()), None), SolverProfile):
            profile_map = profiles
        else:
            profile_map = {}

        # Basic consensus
        agreeing_verdicts: dict[str, int] = {}
        for v in votes:
            agreeing_verdicts[v.verdict] = agreeing_verdicts.get(v.verdict, 0) + 1

        total = len(votes)
        majority_count = max(agreeing_verdicts.values()) if agreeing_verdicts else 0
        abstaining = sum(1 for v in votes if v.verdict in ("uncertain", "not_applicable"))
        active = total - abstaining

        raw_consensus = majority_count / total if total > 0 else 0.0

        # Profile list for diversity
        profile_list = list(profile_map.values()) if profile_map else []

        # 1. Diversity
        diversity, div_warnings = compute_diversity(profile_list)

        # 2. Disagreement classification
        disagreements = classify_disagreement(votes, profile_map)

        # 3. Expertise matching
        expertise_match, exp_warnings = compute_expertise_match(
            claim_domain, votes, profile_map,
        )

        # 4. Consensus depth
        depth, depth_warnings = compute_consensus_depth(votes)

        # 5. Inter-solver translation loss
        inter_loss = compute_inter_solver_loss(votes, profile_map)

        # Adjusted consensus: raw × quality multipliers
        quality_multiplier = (
            0.25 * diversity +
            0.25 * depth +
            0.25 * expertise_match +
            0.25 * (1.0 - inter_loss)
        )
        adjusted = round(raw_consensus * (0.5 + 0.5 * quality_multiplier), 4)

        # Collect warnings and recommendations
        weak_points = div_warnings + exp_warnings + depth_warnings
        actions = []

        for d in disagreements:
            if d.is_resolvable:
                actions.append(f"[{d.disagreement_type}] {d.resolution_path}")

        if diversity < MIN_DIVERSITY_THRESHOLD:
            actions.append("Add solvers with different types/models/frameworks")
        if inter_loss > 0.3:
            actions.append("Reduce inter-solver loss: standardize evidence format")

        disagreeing_count = active - majority_count if active > 0 else 0

        return ConsensusReport(
            total_solvers=total,
            agreeing=majority_count,
            disagreeing=disagreeing_count,
            abstaining=abstaining,
            raw_consensus=round(raw_consensus, 4),
            diversity_score=diversity,
            depth_score=depth,
            expertise_match=expertise_match,
            inter_solver_loss=inter_loss,
            adjusted_consensus=adjusted,
            disagreements=disagreements,
            weak_points=weak_points,
            improvement_actions=actions,
        )

    @staticmethod
    def format_report(r: ConsensusReport) -> str:
        """Pretty-print consensus report."""
        lines = [
            "╔══ Solver Quality Report ══╗",
            f"║ Solvers: {r.total_solvers} (agree:{r.agreeing} disagree:{r.disagreeing} abstain:{r.abstaining})",
            f"║",
            f"║ Raw consensus:      {r.raw_consensus:.0%}",
            f"║ Adjusted consensus: {r.adjusted_consensus:.0%}",
            f"║",
            f"║ Diversity:          {r.diversity_score:.0%}",
            f"║ Depth:              {r.depth_score:.0%}",
            f"║ Expertise match:    {r.expertise_match:.0%}",
            f"║ Inter-solver loss:  {r.inter_solver_loss:.0%}",
        ]
        if r.disagreements:
            lines.append("║")
            lines.append("║ ⚡ Disagreements:")
            for d in r.disagreements:
                resolvable = "✅" if d.is_resolvable else "❌"
                lines.append(f"║   {resolvable} [{d.disagreement_type}] {d.root_cause}")
        if r.weak_points:
            lines.append("║")
            lines.append("║ ⚠️ Weak Points:")
            for w in r.weak_points:
                lines.append(f"║   • {w}")
        if r.improvement_actions:
            lines.append("║")
            lines.append("║ 🎯 Actions:")
            for a in r.improvement_actions:
                lines.append(f"║   → {a}")
        lines.append("╚" + "═" * 30 + "╝")
        return "\n".join(lines)
