"""
Adaptive Solver Router — Efficiency optimization via selective solver activation.

Problem: Running all 10+ solver types on every claim is expensive.
         ESS=10.5/15 means ~30% of computation is redundant.

Solution: Route claims to the minimum set of orthogonal solvers needed
for reliable consensus, adding more only when disagreement detected.

Efficiency target: 3× cost reduction while maintaining consensus quality.

Architecture:
  Stage 1: Domain classification (0.1ms) → select top-k orthogonal solvers
  Stage 2: Fast consensus check with top-k
  Stage 3: If disagreement → escalate with additional solvers
  Stage 4: Early termination when consensus reached

Cost model:
  Current:   15 solvers × 1.0 cost = 15.0 units
  Optimized: 3-5 fast + 0-3 escalation = 4.5-6.5 units (avg)
  Savings:   ~60-70%

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from katala_samurai.solver_quality import SolverProfile, SolverVote
from katala_samurai.solver_types import (
    AbstractSolver, SOLVER_TYPES, DEFAULT_EXPERTISE,
    create_full_solver_pool, FRAMEWORK_VECTORS,
)
from katala_samurai.solver_orthogonality import (
    OrthogonalityEngine, orthogonalize_solver_weights,
)

# ── Constants ──
INITIAL_POOL_SIZE = 3             # Start with top-3 orthogonal solvers
ESCALATION_POOL_SIZE = 2          # Add 2 solvers per escalation round
MAX_ESCALATION_ROUNDS = 3         # Max escalation before giving up
CONSENSUS_THRESHOLD = 0.7         # Agreement ratio needed for early termination
DISAGREEMENT_THRESHOLD = 0.4      # Below this, escalate
CONFIDENCE_FLOOR = 0.3            # Ignore votes below this confidence
COST_PER_SOLVER = 1.0             # Normalized cost unit per solver invocation
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "formal_logic": ["proof", "theorem", "axiom", "lemma", "corollary", "deduction",
                     "inference", "logic", "formal", "consistent"],
    "empirical": ["data", "experiment", "observation", "measurement", "evidence",
                  "sample", "trial", "result", "statistical"],
    "linguistic": ["language", "translation", "meaning", "semantics", "syntax",
                   "grammar", "discourse", "narrative", "text"],
    "cultural": ["culture", "convention", "tradition", "norm", "practice",
                 "society", "community", "ritual"],
    "temporal": ["history", "evolution", "change", "drift", "era", "period",
                 "timeline", "progress", "decay"],
    "causal": ["cause", "effect", "because", "therefore", "mechanism",
               "intervention", "counterfactual", "why"],
    "creative": ["novel", "abstract", "pattern", "analogy", "metaphor",
                 "compose", "generate", "design", "create"],
    "statistical": ["probability", "distribution", "correlation", "regression",
                    "variance", "confidence interval", "p-value", "bayesian"],
}


@dataclass(slots=True)
class RoutingDecision:
    """Record of which solvers were activated and why."""
    stage: int                    # 1=initial, 2=escalation1, 3=escalation2, ...
    solver_ids: list[str]
    reason: str


@dataclass(slots=True)
class RouterResult:
    """Result of adaptive routing."""
    # Final verdict
    verdict: str
    confidence: float
    votes: list[SolverVote]

    # Efficiency metrics
    solvers_activated: int
    solvers_available: int
    cost_units: float
    cost_savings: float           # vs running all solvers (0-1)

    # Routing trace
    routing_decisions: list[RoutingDecision]
    escalation_rounds: int
    early_terminated: bool

    # Quality
    consensus_ratio: float


# ════════════════════════════════════════════
# Domain Classification
# ════════════════════════════════════════════

def classify_domain(claim: str, evidence: list[str]) -> dict[str, float]:
    """Classify claim into expertise domains.

    Returns domain → relevance score (0-1).
    Fast: O(keywords × text_length), typically <1ms.
    """
    text = (claim + " " + " ".join(evidence)).lower()
    scores: dict[str, float] = {}

    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        scores[domain] = min(1.0, hits / max(len(keywords) * 0.3, 1))

    # Normalize to sum=1
    total = sum(scores.values()) or 1.0
    return {k: round(v / total, 4) for k, v in scores.items()}


# ════════════════════════════════════════════
# Solver Selection
# ════════════════════════════════════════════

def _select_solvers(
    domain_scores: dict[str, float],
    available_solvers: list[AbstractSolver],
    n: int,
    exclude: set[str] | None = None,
) -> list[AbstractSolver]:
    """Select top-n solvers by domain relevance × orthogonality.

    Balances:
    - Domain expertise match (right solvers for the claim)
    - Orthogonality (independent reasoning frameworks)
    """
    if exclude is None:
        exclude = set()

    # Score each solver
    solver_scores: list[tuple[AbstractSolver, float]] = []

    for solver in available_solvers:
        if solver.solver_id in exclude:
            continue

        # Domain match score
        expertise = solver._expertise
        domain_match = sum(
            domain_scores.get(domain, 0) * expertise.get(domain, 0)
            for domain in domain_scores
        )

        # Orthogonality bonus: prefer unique framework types
        framework = solver._framework
        orth_weights = orthogonalize_solver_weights(
            [s.solver_type for s in available_solvers],
        )
        orth_bonus = orth_weights.get(solver.solver_type, 0.1)

        combined = 0.6 * domain_match + 0.4 * orth_bonus
        solver_scores.append((solver, combined))

    solver_scores.sort(key=lambda x: -x[1])
    return [s for s, _ in solver_scores[:n]]


# ════════════════════════════════════════════
# Consensus Check
# ════════════════════════════════════════════

def _check_consensus(votes: list[SolverVote]) -> tuple[str, float, float]:
    """Check if current votes form consensus.

    Returns: (majority_verdict, consensus_ratio, avg_confidence)
    """
    # Filter low-confidence votes
    valid = [v for v in votes if v.confidence >= CONFIDENCE_FLOOR]
    if not valid:
        return "uncertain", 0.0, 0.0

    # Count verdicts (include uncertain as a valid verdict for consensus)
    verdict_counts: dict[str, float] = {}
    for v in valid:
        if v.verdict == "not_applicable":
            continue
        verdict_counts[v.verdict] = verdict_counts.get(v.verdict, 0) + v.confidence

    if not verdict_counts:
        return "uncertain", 0.0, sum(v.confidence for v in valid) / len(valid)

    total_weight = sum(verdict_counts.values())
    majority = max(verdict_counts, key=verdict_counts.get)
    ratio = verdict_counts[majority] / total_weight if total_weight > 0 else 0.0
    avg_conf = sum(v.confidence for v in valid) / len(valid)

    return majority, round(ratio, 4), round(avg_conf, 4)


# ════════════════════════════════════════════
# Adaptive Router
# ════════════════════════════════════════════

class AdaptiveSolverRouter:
    """Routes claims to minimum solver set for efficient consensus.

    Strategy:
    1. Classify domain (fast, <1ms)
    2. Select top-3 orthogonal solvers matched to domain
    3. Run fast consensus check
    4. If consensus ≥ 70%: early terminate (FAST PATH)
    5. If disagreement: escalate with 2 more solvers per round
    6. Max 3 escalation rounds, then return best-effort

    Typical cost: 3-5 solver activations vs 10-15 full pool.
    """

    def __init__(
        self,
        solver_pool: list[AbstractSolver] | None = None,
        initial_k: int = INITIAL_POOL_SIZE,
        escalation_k: int = ESCALATION_POOL_SIZE,
        max_rounds: int = MAX_ESCALATION_ROUNDS,
    ):
        self.pool = solver_pool or create_full_solver_pool()
        self.initial_k = initial_k
        self.escalation_k = escalation_k
        self.max_rounds = max_rounds

    def route(
        self,
        claim: str,
        evidence: list[str],
        context: dict[str, Any] | None = None,
    ) -> RouterResult:
        """Route a claim through adaptive solver selection.

        Parameters
        ----------
        claim : str
            The claim to verify.
        evidence : list[str]
            Supporting evidence.
        context : dict, optional
            Additional context for solvers.

        Returns
        -------
        RouterResult
            Verdict with efficiency metrics.
        """
        if context is None:
            context = {}

        decisions: list[RoutingDecision] = []
        all_votes: list[SolverVote] = []
        activated: set[str] = set()

        # Stage 1: Domain classification
        domain_scores = classify_domain(claim, evidence)
        top_domain = max(domain_scores, key=domain_scores.get)

        # Stage 2: Initial solver selection
        initial = _select_solvers(domain_scores, self.pool, self.initial_k)
        decisions.append(RoutingDecision(
            stage=1,
            solver_ids=[s.solver_id for s in initial],
            reason=f"Top-{self.initial_k} for domain '{top_domain}' ({domain_scores[top_domain]:.0%})",
        ))

        # Run initial solvers
        for solver in initial:
            vote = solver.evaluate(claim, evidence, context)
            all_votes.append(vote)
            activated.add(solver.solver_id)

        # Check consensus
        verdict, ratio, avg_conf = _check_consensus(all_votes)
        if ratio >= CONSENSUS_THRESHOLD:
            # FAST PATH: consensus reached with minimal solvers
            return self._build_result(
                verdict, avg_conf * ratio, all_votes, decisions,
                escalation_rounds=0, early_terminated=True,
                consensus_ratio=ratio,
            )

        # Stage 3+: Escalation
        for round_n in range(1, self.max_rounds + 1):
            escalation = _select_solvers(
                domain_scores, self.pool, self.escalation_k, exclude=activated,
            )
            if not escalation:
                break  # No more solvers available

            decisions.append(RoutingDecision(
                stage=round_n + 1,
                solver_ids=[s.solver_id for s in escalation],
                reason=f"Escalation round {round_n}: consensus={ratio:.0%} < {CONSENSUS_THRESHOLD:.0%}",
            ))

            for solver in escalation:
                vote = solver.evaluate(claim, evidence, context)
                all_votes.append(vote)
                activated.add(solver.solver_id)

            verdict, ratio, avg_conf = _check_consensus(all_votes)
            if ratio >= CONSENSUS_THRESHOLD:
                return self._build_result(
                    verdict, avg_conf * ratio, all_votes, decisions,
                    escalation_rounds=round_n, early_terminated=True,
                    consensus_ratio=ratio,
                )

        # Max escalation reached — return best effort
        return self._build_result(
            verdict, avg_conf * ratio, all_votes, decisions,
            escalation_rounds=self.max_rounds, early_terminated=False,
            consensus_ratio=ratio,
        )

    def _build_result(
        self,
        verdict: str,
        confidence: float,
        votes: list[SolverVote],
        decisions: list[RoutingDecision],
        escalation_rounds: int,
        early_terminated: bool,
        consensus_ratio: float,
    ) -> RouterResult:
        """Build RouterResult with efficiency metrics."""
        activated = len(votes)
        available = len(self.pool)
        cost = activated * COST_PER_SOLVER
        full_cost = available * COST_PER_SOLVER
        savings = 1.0 - (cost / full_cost) if full_cost > 0 else 0.0

        return RouterResult(
            verdict=verdict,
            confidence=round(confidence, 4),
            votes=votes,
            solvers_activated=activated,
            solvers_available=available,
            cost_units=round(cost, 2),
            cost_savings=round(savings, 4),
            routing_decisions=decisions,
            escalation_rounds=escalation_rounds,
            early_terminated=early_terminated,
            consensus_ratio=consensus_ratio,
        )

    @staticmethod
    def format_result(r: RouterResult) -> str:
        """Pretty-print router result."""
        path = "⚡ FAST" if r.early_terminated else "🔄 ESCALATED"
        lines = [
            f"╔══ Adaptive Router ({path}) ══╗",
            f"║ Verdict:    {r.verdict} ({r.confidence:.0%})",
            f"║ Consensus:  {r.consensus_ratio:.0%}",
            f"║ Activated:  {r.solvers_activated} / {r.solvers_available}",
            f"║ Cost:       {r.cost_units:.1f} / {r.solvers_available * COST_PER_SOLVER:.1f} units",
            f"║ Savings:    {r.cost_savings:.0%}",
            f"║ Escalation: {r.escalation_rounds} rounds",
            "║",
            "║ Routing:",
        ]
        for d in r.routing_decisions:
            lines.append(f"║  Stage {d.stage}: {d.solver_ids} — {d.reason}")
        lines.append("╚" + "═" * 35 + "╝")
        return "\n".join(lines)
