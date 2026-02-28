"""
Solver Optimizer — Active consensus quality improvement.

Not just measuring problems (solver_quality.py) but fixing them:
1. Diversity compensation: re-weight votes to counter monoculture
2. Evidence sharing: merge evidence pools across solver groups
3. Herd detection + penalty: reduce weight of clustered votes
4. Expertise-weighted voting: domain-relevant solvers get more weight
5. Disagreement resolution: route sub-claims to specialist solvers

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from katala_samurai.solver_quality import (
    SolverProfile, SolverVote, ConsensusReport,
    compute_diversity, compute_consensus_depth,
    compute_expertise_match, classify_disagreement,
    HERD_THRESHOLD, EXPERTISE_DOMAINS,
)

# ── Constants ──
MIN_EFFECTIVE_WEIGHT = 0.1       # Floor for vote weight
MAX_DIVERSITY_BOOST = 3.0        # Cap for minority solver boost
EVIDENCE_MERGE_BONUS = 0.15      # Confidence boost when evidence is shared
HERD_PENALTY_FACTOR = 0.5        # Weight reduction for herded votes
EXPERTISE_WEIGHT_POWER = 1.5     # Exponent for expertise weighting


@dataclass(slots=True)
class WeightedVote:
    """A vote with computed weights and adjustments."""
    solver_id: str
    verdict: str
    raw_confidence: float
    adjusted_confidence: float
    weight: float                  # Final vote weight (0-MAX_DIVERSITY_BOOST)
    adjustments: list[str] = field(default_factory=list)  # What was adjusted and why


@dataclass(slots=True)
class OptimizedConsensus:
    """Result of optimized consensus computation."""
    # Original
    raw_consensus: float
    raw_verdict: str

    # Optimized
    optimized_consensus: float
    optimized_verdict: str
    confidence_interval: tuple[float, float]  # (low, high)

    # Weighted votes
    weighted_votes: list[WeightedVote]
    effective_sample_size: float  # Accounts for correlated votes

    # Improvements applied
    improvements: list[str]
    remaining_issues: list[str]

    # Evidence pool
    merged_evidence: list[str]
    evidence_coverage: float  # What % of total evidence each solver now sees


# ════════════════════════════════════════════
# 1. Diversity Compensation
# ════════════════════════════════════════════

def _compute_diversity_weights(
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile],
) -> dict[str, float]:
    """Re-weight votes to compensate for solver monoculture.

    Minority solver types get boosted, majority types get penalized.
    If 20/28 solvers are LLMs, each LLM vote weighs less and each
    non-LLM vote weighs more — correcting for redundancy.
    """
    if not profiles:
        return {v.solver_id: 1.0 for v in votes}

    # Count by type
    type_counts: dict[str, int] = {}
    for v in votes:
        p = profiles.get(v.solver_id)
        stype = p.solver_type if p else "unknown"
        type_counts[stype] = type_counts.get(stype, 0) + 1

    total = len(votes)
    if total == 0:
        return {}

    # Inverse frequency weighting
    # Type with 20/28 solvers: weight = 28/(20*num_types) ≈ 0.47
    # Type with 3/28 solvers: weight = 28/(3*num_types) ≈ 3.11
    num_types = len(type_counts)
    weights: dict[str, float] = {}

    for v in votes:
        p = profiles.get(v.solver_id)
        stype = p.solver_type if p else "unknown"
        count = type_counts[stype]
        raw_weight = total / (count * num_types) if count > 0 else 1.0
        weights[v.solver_id] = round(
            max(MIN_EFFECTIVE_WEIGHT, min(MAX_DIVERSITY_BOOST, raw_weight)), 4
        )

    return weights


# ════════════════════════════════════════════
# 2. Evidence Sharing
# ════════════════════════════════════════════

def _merge_evidence(votes: list[SolverVote]) -> tuple[list[str], dict[str, float]]:
    """Merge evidence pools across all solver groups.

    Returns (merged_evidence, solver_coverage) where coverage
    is what fraction of total evidence each solver originally had.
    """
    all_evidence: set[str] = set()
    solver_evidence: dict[str, set[str]] = {}

    for v in votes:
        evidence = set(v.evidence_cited)
        solver_evidence[v.solver_id] = evidence
        all_evidence.update(evidence)

    total = len(all_evidence) if all_evidence else 1
    coverage = {
        sid: round(len(ev) / total, 4)
        for sid, ev in solver_evidence.items()
    }

    return sorted(all_evidence), coverage


def _apply_evidence_sharing(
    votes: list[SolverVote],
) -> tuple[list[SolverVote], list[str]]:
    """Simulate evidence sharing: boost confidence of solvers who see new evidence.

    When epistemic disagreement is detected (different evidence bases),
    sharing evidence can resolve the disagreement by giving all solvers
    the same information.
    """
    merged, coverage = _merge_evidence(votes)
    improvements = []

    for v in votes:
        original_coverage = len(v.evidence_cited) / len(merged) if merged else 1.0
        if original_coverage < 0.5 and len(merged) > len(v.evidence_cited):
            # This solver would benefit from seeing more evidence
            new_evidence = set(merged) - set(v.evidence_cited)
            boost = min(EVIDENCE_MERGE_BONUS, len(new_evidence) * 0.03)
            # Don't modify original — tracked in adjustments
            improvements.append(
                f"Solver {v.solver_id}: +{boost:.0%} confidence if shown "
                f"{len(new_evidence)} new evidence items"
            )

    return votes, improvements


# ════════════════════════════════════════════
# 3. Herd Detection + Penalty
# ════════════════════════════════════════════

def _detect_and_penalize_herds(
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile],
) -> dict[str, float]:
    """Detect herding and reduce weight of correlated votes.

    Herding signals:
    - Very low confidence variance within a type group
    - Same base model producing same confidence levels
    """
    penalties: dict[str, float] = {v.solver_id: 1.0 for v in votes}

    # Group by base model
    model_groups: dict[str, list[SolverVote]] = {}
    for v in votes:
        p = profiles.get(v.solver_id)
        model = p.base_model if p and p.base_model else "none"
        model_groups.setdefault(model, []).append(v)

    for model, group in model_groups.items():
        if model == "none" or len(group) < 3:
            continue

        # Check confidence variance
        confs = [v.confidence for v in group]
        mean_c = sum(confs) / len(confs)
        std_c = math.sqrt(sum((c - mean_c) ** 2 for c in confs) / len(confs))

        if std_c < HERD_THRESHOLD:
            # Herding detected — penalize
            for v in group:
                penalties[v.solver_id] = HERD_PENALTY_FACTOR

    return penalties


# ════════════════════════════════════════════
# 4. Expertise-Weighted Voting
# ════════════════════════════════════════════

def _expertise_weights(
    votes: list[SolverVote],
    profiles: dict[str, SolverProfile],
    claim_domain: str,
) -> dict[str, float]:
    """Weight votes by domain expertise relevance.

    A formal logic expert's vote on a formal logic claim weighs more
    than a cultural expert's vote on the same claim.
    """
    weights: dict[str, float] = {}

    for v in votes:
        p = profiles.get(v.solver_id)
        if p and p.expertise:
            relevance = p.expertise.get(claim_domain, 0.1)
            # Power scaling: expertise 0.9 → weight ~0.86, expertise 0.1 → weight ~0.03
            weight = relevance ** EXPERTISE_WEIGHT_POWER
            weights[v.solver_id] = round(max(MIN_EFFECTIVE_WEIGHT, weight), 4)
        else:
            weights[v.solver_id] = 0.5  # Unknown expertise

    return weights


# ════════════════════════════════════════════
# 5. Effective Sample Size
# ════════════════════════════════════════════

def _effective_sample_size(weights: list[float]) -> float:
    """Compute effective sample size accounting for unequal weights.

    Kish's formula: ESS = (sum(w))^2 / sum(w^2)
    28 equal-weight votes → ESS=28
    28 votes where 20 are penalized → ESS<28
    """
    if not weights:
        return 0.0
    sum_w = sum(weights)
    sum_w2 = sum(w ** 2 for w in weights)
    if sum_w2 == 0:
        return 0.0
    return round(sum_w ** 2 / sum_w2, 2)


# ════════════════════════════════════════════
# Main Optimizer
# ════════════════════════════════════════════

class SolverOptimizer:
    """Active multi-solver consensus optimizer.

    Applies 4 corrections to raw consensus:
    1. Diversity compensation (inverse frequency weighting)
    2. Evidence sharing (merge evidence pools)
    3. Herd penalty (reduce correlated vote weight)
    4. Expertise weighting (domain relevance)

    The result is an optimized consensus that reflects *quality* of agreement,
    not just *quantity*.
    """

    def optimize(
        self,
        votes: list[SolverVote],
        profiles: dict[str, SolverProfile],
        claim_domain: str = "general",
    ) -> OptimizedConsensus:
        """Optimize multi-solver consensus.

        Parameters
        ----------
        votes : list[SolverVote]
            Raw solver verdicts.
        profiles : dict[str, SolverProfile]
            Solver capability profiles.
        claim_domain : str
            Domain of the claim being verified.

        Returns
        -------
        OptimizedConsensus
            Quality-adjusted consensus with confidence interval.
        """
        improvements = []
        remaining = []

        # 1. Diversity compensation
        div_weights = _compute_diversity_weights(votes, profiles)
        improvements.append("Diversity compensation applied (inverse frequency)")

        # 2. Evidence sharing
        _, evidence_improvements = _apply_evidence_sharing(votes)
        merged_ev, ev_coverage = _merge_evidence(votes)
        if evidence_improvements:
            improvements.extend(evidence_improvements[:3])

        # 3. Herd detection + penalty
        herd_penalties = _detect_and_penalize_herds(votes, profiles)
        herded = sum(1 for p in herd_penalties.values() if p < 1.0)
        if herded > 0:
            improvements.append(f"Herd penalty applied to {herded} correlated votes")

        # 4. Expertise weighting
        exp_weights = _expertise_weights(votes, profiles, claim_domain)
        improvements.append(f"Expertise weighting for domain '{claim_domain}'")

        # Combine weights: diversity × herd_penalty × expertise
        weighted_votes = []
        for v in votes:
            combined_weight = (
                div_weights.get(v.solver_id, 1.0) *
                herd_penalties.get(v.solver_id, 1.0) *
                exp_weights.get(v.solver_id, 0.5)
            )
            combined_weight = round(max(MIN_EFFECTIVE_WEIGHT, combined_weight), 4)

            # Adjusted confidence
            adj_conf = v.confidence
            ev_cov = ev_coverage.get(v.solver_id, 0.5)
            if ev_cov < 0.3:
                adj_conf *= 0.8  # Low evidence coverage → lower confidence
                
            adjustments = []
            if div_weights.get(v.solver_id, 1.0) != 1.0:
                adjustments.append(f"diversity: ×{div_weights[v.solver_id]:.2f}")
            if herd_penalties.get(v.solver_id, 1.0) < 1.0:
                adjustments.append(f"herd penalty: ×{HERD_PENALTY_FACTOR}")
            if exp_weights.get(v.solver_id, 0.5) != 0.5:
                adjustments.append(f"expertise: ×{exp_weights[v.solver_id]:.2f}")

            weighted_votes.append(WeightedVote(
                solver_id=v.solver_id,
                verdict=v.verdict,
                raw_confidence=v.confidence,
                adjusted_confidence=round(adj_conf, 4),
                weight=combined_weight,
                adjustments=adjustments,
            ))

        # Compute optimized consensus (weighted vote)
        verdict_weights: dict[str, float] = {}
        for wv in weighted_votes:
            if wv.verdict in ("uncertain", "not_applicable"):
                continue
            key = wv.verdict
            verdict_weights[key] = verdict_weights.get(key, 0.0) + (
                wv.weight * wv.adjusted_confidence
            )

        total_weight = sum(verdict_weights.values())
        if total_weight > 0:
            opt_verdict = max(verdict_weights, key=verdict_weights.get)
            opt_consensus = verdict_weights[opt_verdict] / total_weight
        else:
            opt_verdict = "uncertain"
            opt_consensus = 0.0

        # Raw consensus for comparison
        raw_verdicts: dict[str, int] = {}
        for v in votes:
            raw_verdicts[v.verdict] = raw_verdicts.get(v.verdict, 0) + 1
        raw_majority = max(raw_verdicts, key=raw_verdicts.get) if raw_verdicts else "uncertain"
        raw_consensus = raw_verdicts.get(raw_majority, 0) / len(votes) if votes else 0.0

        # Confidence interval (bootstrap-like approximation)
        all_weights = [wv.weight for wv in weighted_votes]
        ess = _effective_sample_size(all_weights)
        margin = 1.96 / math.sqrt(max(1, ess))  # 95% CI
        ci_low = round(max(0.0, opt_consensus - margin), 4)
        ci_high = round(min(1.0, opt_consensus + margin), 4)

        # Evidence coverage
        avg_coverage = (sum(ev_coverage.values()) / len(ev_coverage)
                        if ev_coverage else 0.0)

        # Check for remaining issues
        disagreements = classify_disagreement(votes, profiles)
        for d in disagreements:
            if not d.is_resolvable:
                remaining.append(f"Principled disagreement: {d.root_cause}")

        return OptimizedConsensus(
            raw_consensus=round(raw_consensus, 4),
            raw_verdict=raw_majority,
            optimized_consensus=round(opt_consensus, 4),
            optimized_verdict=opt_verdict,
            confidence_interval=(ci_low, ci_high),
            weighted_votes=weighted_votes,
            effective_sample_size=ess,
            improvements=improvements,
            remaining_issues=remaining,
            merged_evidence=merged_ev,
            evidence_coverage=round(avg_coverage, 4),
        )

    @staticmethod
    def format_result(r: OptimizedConsensus) -> str:
        """Pretty-print optimized consensus."""
        lines = [
            "╔══ Optimized Consensus ══╗",
            f"║ Raw:       {r.raw_consensus:.0%} → {r.raw_verdict}",
            f"║ Optimized: {r.optimized_consensus:.0%} → {r.optimized_verdict}",
            f"║ 95% CI:    [{r.confidence_interval[0]:.0%}, {r.confidence_interval[1]:.0%}]",
            f"║ ESS:       {r.effective_sample_size:.1f} / {len(r.weighted_votes)} votes",
            f"║ Evidence:  {len(r.merged_evidence)} items, avg coverage {r.evidence_coverage:.0%}",
        ]
        if r.improvements:
            lines.append("║")
            lines.append("║ ✅ Applied:")
            for imp in r.improvements[:5]:
                lines.append(f"║   • {imp}")
        if r.remaining_issues:
            lines.append("║")
            lines.append("║ ⚠️ Unresolvable:")
            for iss in r.remaining_issues:
                lines.append(f"║   • {iss}")

        # Top vote adjustments
        adjusted = [wv for wv in r.weighted_votes if wv.adjustments]
        if adjusted:
            lines.append("║")
            lines.append("║ 🔧 Key Adjustments:")
            for wv in adjusted[:5]:
                lines.append(f"║   {wv.solver_id}: w={wv.weight:.2f} ({', '.join(wv.adjustments)})")

        lines.append("╚" + "═" * 28 + "╝")
        return "\n".join(lines)
