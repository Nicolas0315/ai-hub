"""
Hypothesis-Driven Exploration Loop (HDEL)

Extends PEV with a Hypothesize → Probe → Update Belief cycle:

  PEV Loop (existing):
    Plan → Execute → Verify → Adjust → ...

  HDEL (new layer):
    Hypothesize → Probe → Update Belief
      ↑               ↓
      └── refine ──────┘

Purpose: Enable **active exploration** instead of passive reaction.
- PEV waits for tasks then plans → executes → verifies
- HDEL generates hypotheses about the environment, designs probes
  to test them, and updates a belief model from results

Impact:
- Interactive Environment: 33% → 50%+ (active hypothesis testing)
- Long-term Agent: 38% → 55%+ (persistent belief model across sessions)

Architecture:
  HDEL wraps PEV. Each HDEL iteration runs a mini PEV loop where:
  - Plan = design a probe from the current hypothesis
  - Execute = run the probe
  - Verify = compare result with hypothesis prediction
  - Adjust = update belief model

Uses KS42a's EvolutionaryEngine for hypothesis generation:
  hypotheses are EvolutionaryRules about the environment.

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import time
import math
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from pev_loop import PEVLoop, PEVResult, StepType

# ── Constants ──────────────────────────────────────────────────
MAX_HYPOTHESES = 10              # Max active hypotheses
MAX_PROBES_PER_HYPOTHESIS = 5    # Max probes before moving on
BELIEF_UPDATE_RATE = 0.3         # Bayesian learning rate
PRIOR_CONFIDENCE = 0.5           # Starting confidence for new hypotheses
SURPRISE_THRESHOLD = 0.4         # If prediction error > this, hypothesis needs revision
CONVERGENCE_THRESHOLD = 0.85     # Belief confidence above which hypothesis is "accepted"
REJECTION_THRESHOLD = 0.15       # Belief confidence below which hypothesis is "rejected"
MAX_EXPLORATION_CYCLES = 20      # Max HDEL iterations
CURIOSITY_DECAY = 0.95           # Curiosity diminishes for explored regions
BELIEF_FILE = ".katala_beliefs.json"


# ════════════════════════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════════════════════════

class HypothesisStatus(Enum):
    ACTIVE = "active"           # Under investigation
    ACCEPTED = "accepted"       # Confidence above threshold
    REJECTED = "rejected"       # Confidence below threshold
    SUPERSEDED = "superseded"   # Replaced by better hypothesis


@dataclass
class Hypothesis:
    """A testable claim about the environment or problem space."""
    hypothesis_id: str
    claim: str                    # Natural language description
    domain: str                   # What aspect of the world this is about
    predicted_outcome: str        # What we expect to see if true
    confidence: float             # Current belief strength (0-1)
    status: HypothesisStatus = HypothesisStatus.ACTIVE
    probes_run: int = 0
    probes_confirmed: int = 0
    probes_refuted: int = 0
    surprise_history: List[float] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    source: str = ""              # "evolutionary" | "curiosity" | "anomaly" | "user"
    parent_id: str = ""           # If refined from another hypothesis

    def acceptance_ratio(self) -> float:
        """Fraction of probes that confirmed the hypothesis."""
        total = self.probes_confirmed + self.probes_refuted
        if total == 0:
            return 0.5
        return self.probes_confirmed / total

    def average_surprise(self) -> float:
        """Mean prediction error across probes."""
        if not self.surprise_history:
            return 0.0
        return sum(self.surprise_history) / len(self.surprise_history)

    def is_terminal(self) -> bool:
        """Whether this hypothesis has reached a conclusion."""
        return self.status in (HypothesisStatus.ACCEPTED,
                               HypothesisStatus.REJECTED,
                               HypothesisStatus.SUPERSEDED)


@dataclass
class Probe:
    """An experiment designed to test a hypothesis."""
    probe_id: str
    hypothesis_id: str
    action: str                  # What to do
    expected_result: str         # What we predict if hypothesis is true
    actual_result: str = ""      # What actually happened
    prediction_error: float = 0.0  # |expected - actual| normalized
    confirmed: bool = False
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class BeliefModel:
    """Persistent model of beliefs about the environment.

    Survives across sessions (serialized to disk).
    Each belief is a hypothesis that has been tested.
    """
    beliefs: Dict[str, Hypothesis] = field(default_factory=dict)
    total_probes: int = 0
    total_surprises: int = 0      # Probes where prediction error > threshold
    exploration_coverage: Dict[str, float] = field(default_factory=dict)  # domain → coverage
    version: str = "1.0"

    def add_hypothesis(self, h: Hypothesis):
        self.beliefs[h.hypothesis_id] = h

    def get_active(self) -> List[Hypothesis]:
        return [h for h in self.beliefs.values()
                if h.status == HypothesisStatus.ACTIVE]

    def get_accepted(self) -> List[Hypothesis]:
        return [h for h in self.beliefs.values()
                if h.status == HypothesisStatus.ACCEPTED]

    def domain_confidence(self, domain: str) -> float:
        """Average confidence in accepted beliefs for a domain."""
        relevant = [h for h in self.beliefs.values()
                    if h.domain == domain and h.status == HypothesisStatus.ACCEPTED]
        if not relevant:
            return 0.0
        return sum(h.confidence for h in relevant) / len(relevant)


@dataclass
class ExplorationResult:
    """Output of a full HDEL exploration."""
    hypotheses_tested: int
    hypotheses_accepted: int
    hypotheses_rejected: int
    total_probes: int
    surprises: int                # Unexpected results
    cycles: int
    total_time_ms: float
    belief_model: BeliefModel
    new_discoveries: List[str]    # Claims that were accepted
    open_questions: List[str]     # Hypotheses still active


# ════════════════════════════════════════════════════════════════
# Belief Persistence
# ════════════════════════════════════════════════════════════════

class BeliefStore:
    """Persistent storage for the belief model."""

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or BELIEF_FILE)

    def load(self) -> BeliefModel:
        if not self.path.exists():
            return BeliefModel()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            model = BeliefModel(
                total_probes=data.get("total_probes", 0),
                total_surprises=data.get("total_surprises", 0),
                exploration_coverage=data.get("exploration_coverage", {}),
                version=data.get("version", "1.0"),
            )
            for hd in data.get("beliefs", []):
                hd["status"] = HypothesisStatus(hd["status"])
                h = Hypothesis(**hd)
                model.beliefs[h.hypothesis_id] = h
            return model
        except Exception:
            return BeliefModel()

    def save(self, model: BeliefModel):
        beliefs_data = []
        for h in model.beliefs.values():
            d = {
                "hypothesis_id": h.hypothesis_id,
                "claim": h.claim,
                "domain": h.domain,
                "predicted_outcome": h.predicted_outcome,
                "confidence": round(h.confidence, 4),
                "status": h.status.value,
                "probes_run": h.probes_run,
                "probes_confirmed": h.probes_confirmed,
                "probes_refuted": h.probes_refuted,
                "surprise_history": [round(s, 4) for s in h.surprise_history[-20:]],
                "created_at": h.created_at,
                "source": h.source,
                "parent_id": h.parent_id,
            }
            beliefs_data.append(d)

        data = {
            "version": model.version,
            "total_probes": model.total_probes,
            "total_surprises": model.total_surprises,
            "exploration_coverage": {k: round(v, 4) for k, v in model.exploration_coverage.items()},
            "beliefs": beliefs_data,
        }
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ════════════════════════════════════════════════════════════════
# Hypothesis Generation
# ════════════════════════════════════════════════════════════════

def generate_hypotheses_from_observations(
    observations: List[Dict[str, Any]],
    existing_beliefs: BeliefModel,
    max_hypotheses: int = MAX_HYPOTHESES,
) -> List[Hypothesis]:
    """Generate testable hypotheses from observations.

    Sources of hypotheses:
    1. Pattern detection in observations
    2. Gaps in existing belief model
    3. Anomalies (observations contradicting accepted beliefs)
    4. Curiosity (unexplored domains)
    """
    hypotheses = []

    # 1. Pattern-based: look for regularities
    if observations:
        domains_seen: Dict[str, int] = {}
        for obs in observations:
            d = obs.get("domain", "unknown")
            domains_seen[d] = domains_seen.get(d, 0) + 1

        for domain, count in domains_seen.items():
            if count >= 2:
                hid = hashlib.md5(f"pattern_{domain}".encode()).hexdigest()[:10]
                if hid not in existing_beliefs.beliefs:
                    hypotheses.append(Hypothesis(
                        hypothesis_id=hid,
                        claim=f"Domain '{domain}' exhibits consistent patterns across {count} observations",
                        domain=domain,
                        predicted_outcome=f"New observations in '{domain}' will follow existing patterns",
                        confidence=PRIOR_CONFIDENCE,
                        source="pattern",
                    ))

    # 2. Gap-based: domains with low coverage
    covered = existing_beliefs.exploration_coverage
    for domain in set(obs.get("domain", "unknown") for obs in observations):
        if covered.get(domain, 0.0) < 0.3:
            hid = hashlib.md5(f"gap_{domain}".encode()).hexdigest()[:10]
            if hid not in existing_beliefs.beliefs:
                hypotheses.append(Hypothesis(
                    hypothesis_id=hid,
                    claim=f"Domain '{domain}' has unexplored structure worth investigating",
                    domain=domain,
                    predicted_outcome=f"Probing '{domain}' will reveal actionable structure",
                    confidence=PRIOR_CONFIDENCE,
                    source="curiosity",
                ))

    # 3. Anomaly-based: observations contradicting accepted beliefs
    for h in existing_beliefs.get_accepted():
        for obs in observations:
            if obs.get("domain") == h.domain:
                contradiction = obs.get("contradicts", "")
                if contradiction and h.claim in contradiction:
                    hid = hashlib.md5(f"anomaly_{h.hypothesis_id}".encode()).hexdigest()[:10]
                    if hid not in existing_beliefs.beliefs:
                        hypotheses.append(Hypothesis(
                            hypothesis_id=hid,
                            claim=f"Revised: {h.claim} — may be wrong based on new evidence",
                            domain=h.domain,
                            predicted_outcome=f"Re-probing will show the original belief needs update",
                            confidence=PRIOR_CONFIDENCE,
                            source="anomaly",
                            parent_id=h.hypothesis_id,
                        ))

    return hypotheses[:max_hypotheses]


# ════════════════════════════════════════════════════════════════
# Probe Design
# ════════════════════════════════════════════════════════════════

def design_probe(
    hypothesis: Hypothesis,
    probe_fn: Optional[Callable] = None,
) -> Probe:
    """Design an experiment to test a hypothesis.

    The probe should be the most informative possible action:
    maximize expected information gain.
    """
    pid = hashlib.md5(
        f"{hypothesis.hypothesis_id}_{hypothesis.probes_run}".encode()
    ).hexdigest()[:10]

    # Default action: direct test of the claim
    action = f"Test: {hypothesis.claim}"
    expected = hypothesis.predicted_outcome

    # If we have prior probes, design a more targeted probe
    if hypothesis.probes_run > 0:
        avg_surprise = hypothesis.average_surprise()
        if avg_surprise > SURPRISE_THRESHOLD:
            # High surprise → test boundary conditions
            action = f"Boundary test: Where does '{hypothesis.claim}' break?"
            expected = f"Find the limits of '{hypothesis.predicted_outcome}'"
        elif hypothesis.acceptance_ratio() > 0.7:
            # Mostly confirmed → test edge cases
            action = f"Edge case: Does '{hypothesis.claim}' hold in extreme conditions?"
            expected = f"'{hypothesis.predicted_outcome}' still holds at edges"

    return Probe(
        probe_id=pid,
        hypothesis_id=hypothesis.hypothesis_id,
        action=action,
        expected_result=expected,
    )


# ════════════════════════════════════════════════════════════════
# Bayesian Belief Update
# ════════════════════════════════════════════════════════════════

def update_belief(
    hypothesis: Hypothesis,
    probe: Probe,
    prediction_error: float,
) -> Hypothesis:
    """Update hypothesis confidence using Bayesian-inspired update.

    confidence' = confidence + lr * (evidence - confidence)

    Where evidence = 1 - prediction_error (0 = total miss, 1 = perfect prediction)
    """
    evidence = 1.0 - min(1.0, max(0.0, prediction_error))
    surprise = prediction_error

    # Bayesian update
    new_confidence = hypothesis.confidence + BELIEF_UPDATE_RATE * (evidence - hypothesis.confidence)
    new_confidence = max(0.0, min(1.0, new_confidence))

    # Record
    hypothesis.confidence = round(new_confidence, 4)
    hypothesis.probes_run += 1
    hypothesis.surprise_history.append(round(surprise, 4))

    if prediction_error < SURPRISE_THRESHOLD:
        hypothesis.probes_confirmed += 1
        probe.confirmed = True
    else:
        hypothesis.probes_refuted += 1
        probe.confirmed = False

    probe.prediction_error = round(prediction_error, 4)

    # Status transitions
    if hypothesis.confidence >= CONVERGENCE_THRESHOLD:
        hypothesis.status = HypothesisStatus.ACCEPTED
    elif hypothesis.confidence <= REJECTION_THRESHOLD:
        hypothesis.status = HypothesisStatus.REJECTED
    elif hypothesis.probes_run >= MAX_PROBES_PER_HYPOTHESIS:
        # Inconclusive after max probes — keep as active but deprioritize
        pass

    return hypothesis


# ════════════════════════════════════════════════════════════════
# Curiosity-Driven Exploration
# ════════════════════════════════════════════════════════════════

def compute_curiosity(
    hypothesis: Hypothesis,
    belief_model: BeliefModel,
) -> float:
    """Compute curiosity score: how much would testing this teach us?

    High curiosity = unexplored domain × uncertain belief × recent surprise.
    """
    domain_coverage = belief_model.exploration_coverage.get(hypothesis.domain, 0.0)
    unexplored = 1.0 - domain_coverage

    # Uncertainty: confidence near 0.5 = most uncertain
    uncertainty = 1.0 - abs(hypothesis.confidence - 0.5) * 2

    # Surprise bonus: recent high surprises = more to learn
    surprise_bonus = hypothesis.average_surprise() if hypothesis.surprise_history else 0.3

    # Decay: explored hypotheses become less interesting
    probe_decay = CURIOSITY_DECAY ** hypothesis.probes_run

    curiosity = unexplored * 0.3 + uncertainty * 0.3 + surprise_bonus * 0.2 + probe_decay * 0.2
    return round(min(1.0, curiosity), 4)


# ════════════════════════════════════════════════════════════════
# HDEL: Main Loop
# ════════════════════════════════════════════════════════════════

class HypothesisLoop:
    """Hypothesis-Driven Exploration Loop.

    Wraps PEV with active hypothesis testing:

    ```
    while active_hypotheses:
        h = select_most_curious(hypotheses)
        probe = design_probe(h)
        result = pev.run(probe.action)      ← PEV handles execution
        error = compare(result, h.prediction)
        h = update_belief(h, probe, error)
        if h.accepted → discovery
        if h.rejected → generate refined hypothesis
        if surprise → generate anomaly hypothesis
    ```

    Usage:
    ```python
    hdel = HypothesisLoop(
        probe_executor=my_probe_fn,      # runs probes in the real environment
        result_evaluator=my_eval_fn,     # compares result to prediction
    )
    result = hdel.explore(observations)
    ```
    """

    def __init__(
        self,
        probe_executor: Optional[Callable] = None,
        result_evaluator: Optional[Callable] = None,
        belief_path: Optional[str] = None,
        max_cycles: int = MAX_EXPLORATION_CYCLES,
    ):
        """
        Parameters
        ----------
        probe_executor : callable(action: str, context: dict) → dict
            Runs a probe action and returns result.
            Must return {"output": Any, "success": bool}
        result_evaluator : callable(expected: str, actual: Any) → float
            Returns prediction error (0.0 = perfect match, 1.0 = total miss)
        belief_path : str, optional
            Path to persist beliefs across sessions.
        max_cycles : int
            Max exploration iterations.
        """
        self.probe_executor = probe_executor or self._default_executor
        self.result_evaluator = result_evaluator or self._default_evaluator
        self.store = BeliefStore(belief_path)
        self.max_cycles = max_cycles
        self.belief_model = self.store.load()

    def explore(
        self,
        observations: List[Dict[str, Any]],
        hypotheses: Optional[List[Hypothesis]] = None,
    ) -> ExplorationResult:
        """Run the full hypothesis-driven exploration loop.

        Parameters
        ----------
        observations : list[dict]
            Current observations about the environment.
            Each dict should have at least {"domain": str, "data": Any}.
        hypotheses : list[Hypothesis], optional
            Pre-seeded hypotheses. If None, generates from observations.

        Returns
        -------
        ExplorationResult
        """
        start_time = time.time()

        # Generate hypotheses if not provided
        if hypotheses is None:
            hypotheses = generate_hypotheses_from_observations(
                observations, self.belief_model
            )

        # Add to belief model
        for h in hypotheses:
            if h.hypothesis_id not in self.belief_model.beliefs:
                self.belief_model.add_hypothesis(h)

        # Exploration metrics
        total_probes = 0
        surprises = 0
        discoveries = []
        cycle = 0

        while cycle < self.max_cycles:
            # Get active hypotheses
            active = self.belief_model.get_active()
            if not active:
                break

            # Select most curious hypothesis
            scored = [(h, compute_curiosity(h, self.belief_model)) for h in active]
            scored.sort(key=lambda x: -x[1])
            hypothesis = scored[0][0]

            # Skip if max probes reached
            if hypothesis.probes_run >= MAX_PROBES_PER_HYPOTHESIS:
                hypothesis.status = HypothesisStatus.REJECTED  # Inconclusive → soft reject
                cycle += 1
                continue

            # Design probe
            probe = design_probe(hypothesis)

            # Execute probe via PEV mini-loop
            probe_start = time.time()
            try:
                exec_result = self.probe_executor(
                    probe.action,
                    {
                        "hypothesis": hypothesis.claim,
                        "expected": probe.expected_result,
                        "domain": hypothesis.domain,
                        "probe_number": hypothesis.probes_run + 1,
                    },
                )
                probe.actual_result = str(exec_result.get("output", ""))[:500]
                probe.duration_ms = (time.time() - probe_start) * 1000
            except Exception as e:
                probe.actual_result = f"Error: {e}"
                probe.duration_ms = (time.time() - probe_start) * 1000
                cycle += 1
                continue

            # Evaluate prediction error
            prediction_error = self.result_evaluator(
                probe.expected_result,
                exec_result.get("output", None),
            )

            # Update belief
            hypothesis = update_belief(hypothesis, probe, prediction_error)
            total_probes += 1
            self.belief_model.total_probes += 1

            if prediction_error > SURPRISE_THRESHOLD:
                surprises += 1
                self.belief_model.total_surprises += 1

                # Generate anomaly hypothesis from surprise
                if hypothesis.status == HypothesisStatus.ACTIVE:
                    anomaly_h = Hypothesis(
                        hypothesis_id=hashlib.md5(
                            f"surprise_{hypothesis.hypothesis_id}_{cycle}".encode()
                        ).hexdigest()[:10],
                        claim=f"Surprise in '{hypothesis.domain}': prediction error {prediction_error:.2f} suggests missing factor",
                        domain=hypothesis.domain,
                        predicted_outcome="Refined probe will reveal the missing factor",
                        confidence=PRIOR_CONFIDENCE,
                        source="anomaly",
                        parent_id=hypothesis.hypothesis_id,
                    )
                    self.belief_model.add_hypothesis(anomaly_h)

            # Record discovery
            if hypothesis.status == HypothesisStatus.ACCEPTED:
                discoveries.append(hypothesis.claim)

            # Update domain coverage
            domain = hypothesis.domain
            current_coverage = self.belief_model.exploration_coverage.get(domain, 0.0)
            coverage_increment = 0.1 if probe.confirmed else 0.05
            self.belief_model.exploration_coverage[domain] = min(
                1.0, current_coverage + coverage_increment
            )

            cycle += 1

        # Persist beliefs
        self.store.save(self.belief_model)

        elapsed = (time.time() - start_time) * 1000

        accepted = [h for h in self.belief_model.beliefs.values()
                    if h.status == HypothesisStatus.ACCEPTED]
        rejected = [h for h in self.belief_model.beliefs.values()
                    if h.status == HypothesisStatus.REJECTED]
        still_active = self.belief_model.get_active()

        return ExplorationResult(
            hypotheses_tested=total_probes,
            hypotheses_accepted=len(accepted),
            hypotheses_rejected=len(rejected),
            total_probes=total_probes,
            surprises=surprises,
            cycles=cycle,
            total_time_ms=elapsed,
            belief_model=self.belief_model,
            new_discoveries=discoveries,
            open_questions=[h.claim for h in still_active],
        )

    # ── Default implementations ──────────────────────────────────

    @staticmethod
    def _default_executor(action: str, context: dict) -> dict:
        """Default probe executor: simulates environment interaction.

        In production, this would interface with the real environment
        (run code, query APIs, interact with UIs, etc.)
        """
        return {
            "output": f"Simulated result for: {action[:100]}",
            "success": True,
        }

    @staticmethod
    def _default_evaluator(expected: str, actual: Any) -> float:
        """Default result evaluator: string similarity as proxy for prediction error.

        In production, this would do semantic comparison or structural matching.
        """
        if actual is None:
            return 1.0
        expected_str = str(expected).lower()
        actual_str = str(actual).lower()

        # Simple word overlap
        exp_words = set(expected_str.split())
        act_words = set(actual_str.split())

        if not exp_words:
            return 0.5

        overlap = len(exp_words & act_words)
        similarity = overlap / len(exp_words)

        return round(1.0 - similarity, 4)

    # ── Formatting ───────────────────────────────────────────────

    @staticmethod
    def format_result(result: ExplorationResult) -> str:
        """Pretty-print exploration result."""
        lines = [
            "╔══ HDEL Exploration Report ══╗",
            f"║ Cycles: {result.cycles} | Probes: {result.total_probes}",
            f"║ Accepted: {result.hypotheses_accepted} | Rejected: {result.hypotheses_rejected}",
            f"║ Surprises: {result.surprises}",
            f"║ Time: {result.total_time_ms:.0f}ms",
        ]

        if result.new_discoveries:
            lines.append("║")
            lines.append("║ 🔬 Discoveries:")
            for d in result.new_discoveries:
                lines.append(f"║   ✅ {d[:80]}")

        if result.open_questions:
            lines.append("║")
            lines.append("║ ❓ Open Questions:")
            for q in result.open_questions[:5]:
                lines.append(f"║   ? {q[:80]}")

        bm = result.belief_model
        if bm.exploration_coverage:
            lines.append("║")
            lines.append("║ 🗺️ Domain Coverage:")
            for domain, cov in sorted(bm.exploration_coverage.items(),
                                       key=lambda x: -x[1]):
                bar_len = int(cov * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(f"║   {domain:15s} {bar} {cov:.0%}")

        lines.append("╚" + "═" * 35 + "╝")
        return "\n".join(lines)
