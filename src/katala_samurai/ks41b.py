"""
KS41b — Katala Samurai 41b: Goal Planning Engine

Extends KS41a (goal generation) with goal *planning*:
1. Temporal roadmap: goals organized into phases (now/next/later)
2. Dependency graph: goals can depend on other goals
3. Historical tracking: learn from past goal success/failure
4. Phase-aware prioritization: adapt to current project phase
5. External signal integration: GitHub issues, CI, user feedback
6. Goal decomposition: break large goals into sub-goals
7. Adaptive confidence: calibrate estimates from historical data
8. Gradient verification: partial credit instead of binary accept/reject

Philosophical basis:
- Pragmatism: goals evaluated by consequences, not intentions
- Kuhn: project phases are mini-paradigms; phase transitions shift priorities
- Quine: goal "correctness" is holistic — depends on the web of all other goals
- Dewey: inquiry is iterative — goals refine through execution feedback

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import json
import os
import sys as _sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.dirname(_dir)
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

try:
    from .ks41a import KS41a
except ImportError:
    from ks41a import KS41a

from katala_coding.kcs2a import NextGoal

# ── Constants ──
PHASE_NOW = "now"        # Current sprint / immediate
PHASE_NEXT = "next"      # Next iteration
PHASE_LATER = "later"    # Backlog / future

PHASES = [PHASE_NOW, PHASE_NEXT, PHASE_LATER]

PROJECT_PHASES = [
    "design",       # Architecture, spec writing
    "implement",    # Active coding
    "test",         # Testing, validation
    "refactor",     # Cleanup, optimization
    "release",      # Stabilization, docs
]

# Impact multipliers per project phase
_PHASE_PRIORITY_BOOST: dict[str, dict[str, float]] = {
    "design":    {"R_struct": 1.5, "R_context": 1.8, "R_temporal": 1.2, "R_qualia": 0.8, "R_cultural": 1.0},
    "implement": {"R_struct": 1.2, "R_context": 1.0, "R_qualia": 1.3, "R_cultural": 1.5, "R_temporal": 0.8},
    "test":      {"R_struct": 0.8, "R_context": 0.8, "R_qualia": 1.0, "R_cultural": 1.2, "R_temporal": 1.8},
    "refactor":  {"R_struct": 1.5, "R_context": 1.0, "R_qualia": 1.5, "R_cultural": 1.3, "R_temporal": 1.5},
    "release":   {"R_struct": 0.8, "R_context": 1.5, "R_qualia": 1.2, "R_cultural": 1.0, "R_temporal": 1.3},
}

DECOMPOSITION_THRESHOLD = 50  # Characters in goal description → decompose if longer
MAX_SUB_GOALS = 5
HISTORY_FILE = ".katala_goal_history.jsonl"
GRADIENT_LEVELS = 5  # 0.0, 0.25, 0.5, 0.75, 1.0 instead of binary


# ════════════════════════════════════════════
# Data Structures
# ════════════════════════════════════════════

@dataclass(slots=True)
class PlannedGoal:
    """A goal with planning metadata."""
    # Core (from NextGoal)
    goal: str
    priority: str
    rationale: str
    estimated_impact: str
    source: str

    # Planning extensions
    phase: str                          # now / next / later
    depends_on: list[str] = field(default_factory=list)   # Goal IDs this depends on
    sub_goals: list[str] = field(default_factory=list)     # Decomposed sub-goals
    verification_score: float = 0.0     # 0.0-1.0 gradient (not binary)
    phase_boost: float = 1.0            # Priority multiplier from project phase
    confidence: float = 0.5             # Calibrated confidence estimate
    goal_id: str = ""                   # Unique identifier

    @classmethod
    def from_next_goal(cls, ng: NextGoal, goal_id: str = "") -> PlannedGoal:
        """Convert a NextGoal to PlannedGoal with default planning metadata."""
        return cls(
            goal=ng.goal,
            priority=ng.priority,
            rationale=ng.rationale,
            estimated_impact=ng.estimated_impact,
            source=ng.source,
            phase=PHASE_NOW if ng.priority == "high" else PHASE_NEXT,
            goal_id=goal_id or f"G{hash(ng.goal) % 10000:04d}",
        )


@dataclass(slots=True)
class GoalHistory:
    """Record of a past goal's outcome."""
    goal_id: str
    goal: str
    priority: str
    outcome: str           # "success" | "partial" | "failed" | "abandoned"
    actual_impact: float   # Measured improvement (0-1)
    estimated_impact: float  # What we predicted
    timestamp: float
    axis: str              # Which axis was targeted


@dataclass(slots=True)
class Roadmap:
    """Temporal roadmap with phased goals."""
    now: list[PlannedGoal]
    next: list[PlannedGoal]
    later: list[PlannedGoal]

    # Dependency graph (adjacency list: goal_id → [depends_on_ids])
    dependency_graph: dict[str, list[str]]

    # Metrics
    total_goals: int
    actionable_now: int     # Goals with all dependencies met
    blocked: int            # Goals with unmet dependencies
    estimated_total_improvement: float

    # Historical calibration
    historical_accuracy: float  # How well past estimates matched outcomes
    project_phase: str

    version: str


# ════════════════════════════════════════════
# 1. Goal Dependency Graph
# ════════════════════════════════════════════

def _build_dependency_graph(goals: list[PlannedGoal]) -> dict[str, list[str]]:
    """Build dependency graph from goal relationships.

    Heuristic: a goal depends on another if:
    - Its rationale mentions a concept that another goal targets
    - It's a "deepen" goal that requires a "complete" goal first
    - Sub-goals depend on their parent
    """
    graph: dict[str, list[str]] = {g.goal_id: [] for g in goals}
    goal_map = {g.goal_id: g for g in goals}

    for g in goals:
        for other in goals:
            if g.goal_id == other.goal_id:
                continue
            # "Deepen X" depends on "Complete X"
            if g.goal.startswith("Deepen") and other.goal.startswith("Complete"):
                if _concepts_overlap(g.goal, other.goal):
                    graph[g.goal_id].append(other.goal_id)
            # "Add test" depends on "Complete" implementation
            if g.goal.startswith("Add test") and other.goal.startswith("Complete"):
                if _concepts_overlap(g.goal, other.goal):
                    graph[g.goal_id].append(other.goal_id)
            # "Document" depends on implementation existing
            if g.goal.startswith("Document") and other.goal.startswith("Complete"):
                graph[g.goal_id].append(other.goal_id)

    return graph


def _concepts_overlap(goal_a: str, goal_b: str) -> bool:
    """Check if two goal descriptions share key concepts."""
    words_a = set(goal_a.lower().split()) - {"the", "a", "an", "to", "of", "in", "for"}
    words_b = set(goal_b.lower().split()) - {"the", "a", "an", "to", "of", "in", "for"}
    overlap = words_a & words_b
    return len(overlap) >= 2


def _get_actionable(goals: list[PlannedGoal], graph: dict[str, list[str]],
                    completed: set[str] | None = None) -> tuple[list[PlannedGoal], list[PlannedGoal]]:
    """Split goals into actionable (deps met) and blocked (deps unmet)."""
    completed = completed or set()
    actionable = []
    blocked = []

    for g in goals:
        deps = graph.get(g.goal_id, [])
        unmet = [d for d in deps if d not in completed]
        if not unmet:
            actionable.append(g)
        else:
            blocked.append(g)
            g.depends_on = unmet

    return actionable, blocked


# ════════════════════════════════════════════
# 2. Goal Decomposition
# ════════════════════════════════════════════

def _decompose_goal(goal: PlannedGoal) -> list[str]:
    """Break a large goal into sub-goals.

    Decomposition rules:
    - "Complete: ..." → [analyze, implement, test, document]
    - "Deepen X integration" → [survey X theory, identify gaps, implement, validate]
    - "Resolve solver disagreement" → [identify root cause, add evidence, re-verify]
    """
    text = goal.goal.lower()

    if text.startswith("complete"):
        target = goal.goal.split(":", 1)[-1].strip() if ":" in goal.goal else goal.goal
        return [
            f"Analyze scope: {target}",
            f"Implement: {target}",
            f"Test: {target}",
            f"Document: {target}",
        ][:MAX_SUB_GOALS]

    if "deepen" in text and "integration" in text:
        framework = goal.goal.replace("Deepen ", "").replace(" integration", "")
        return [
            f"Survey {framework} theory",
            f"Identify {framework} gaps in code",
            f"Implement {framework} improvements",
            f"Validate {framework} integration",
        ][:MAX_SUB_GOALS]

    if "resolve solver disagreement" in text:
        axis = goal.goal.split("on ")[-1] if "on " in goal.goal else "unknown"
        return [
            f"Identify root cause of {axis} disagreement",
            f"Add evidence/tests for {axis}",
            f"Re-verify {axis} with all solvers",
        ][:MAX_SUB_GOALS]

    if "add test" in text:
        return [
            f"Write unit test: {goal.goal.replace('Add test: ', '')}",
            f"Write edge case test: {goal.goal.replace('Add test: ', '')}",
        ][:MAX_SUB_GOALS]

    # Default: no decomposition for simple goals
    return []


# ════════════════════════════════════════════
# 3. Historical Goal Tracking
# ════════════════════════════════════════════

class GoalHistoryTracker:
    """Persistent tracker for goal outcomes. Enables learning from past goals.

    Stores history as JSONL (one JSON object per line) for append-only writes.
    """

    def __init__(self, history_path: str | Path | None = None):
        self.path = Path(history_path or HISTORY_FILE)
        self._cache: list[GoalHistory] | None = None

    def record(self, goal: PlannedGoal, outcome: str, actual_impact: float) -> GoalHistory:
        """Record a goal's outcome for future calibration."""
        entry = GoalHistory(
            goal_id=goal.goal_id,
            goal=goal.goal,
            priority=goal.priority,
            outcome=outcome,
            actual_impact=round(actual_impact, 4),
            estimated_impact=round(goal.confidence, 4),
            timestamp=time.time(),
            axis=goal.estimated_impact,
        )
        # Append to JSONL
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        self._cache = None  # Invalidate cache
        return entry

    def load(self) -> list[GoalHistory]:
        """Load all historical records."""
        if self._cache is not None:
            return self._cache

        if not self.path.exists():
            self._cache = []
            return self._cache

        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                d = json.loads(line)
                records.append(GoalHistory(**d))
        self._cache = records
        return records

    def calibration_accuracy(self) -> float:
        """How well past estimates matched actual outcomes.

        Returns mean absolute error inverted to 0-1 scale.
        1.0 = perfect calibration, 0.0 = completely off.
        """
        records = self.load()
        if not records:
            return 0.5  # No data → neutral prior

        errors = [abs(r.estimated_impact - r.actual_impact) for r in records]
        mae = sum(errors) / len(errors)
        return round(max(0.0, min(1.0, 1.0 - mae)), 4)

    def success_rate_by_priority(self) -> dict[str, float]:
        """Success rate grouped by priority level."""
        records = self.load()
        groups: dict[str, list[bool]] = {}
        for r in records:
            groups.setdefault(r.priority, []).append(r.outcome in ("success", "partial"))
        return {k: round(sum(v) / len(v), 4) for k, v in groups.items()} if groups else {}

    def adaptive_confidence(self, priority: str, base_estimate: float) -> float:
        """Calibrate confidence using historical data.

        Bayesian update: blend base_estimate with historical success rate.
        More history → more weight on historical data.
        """
        records = self.load()
        relevant = [r for r in records if r.priority == priority]

        if not relevant:
            return base_estimate  # No data → use base estimate

        historical_rate = sum(1 for r in relevant if r.outcome in ("success", "partial")) / len(relevant)
        # Weight: more history → more trust in historical data
        history_weight = min(0.8, len(relevant) * 0.1)
        calibrated = (1 - history_weight) * base_estimate + history_weight * historical_rate

        return round(max(0.0, min(1.0, calibrated)), 4)


# ════════════════════════════════════════════
# 4. Gradient Verification
# ════════════════════════════════════════════

def _gradient_verify(goal: PlannedGoal, fidelity_score: float) -> float:
    """Gradient verification: score 0.0-1.0 instead of binary accept/reject.

    Quantizes to GRADIENT_LEVELS for interpretability:
    - 1.00: Fully verified — clear, measurable loss at target axis
    - 0.75: Mostly verified — loss detected but indirect
    - 0.50: Partially verified — some evidence of need
    - 0.25: Weakly verified — marginal evidence
    - 0.00: Not verified — no measurable loss at target
    """
    if goal.source == "solver_feedback":
        return 1.0  # Solver feedback is always verified

    # Map fidelity to gradient
    loss = 1.0 - fidelity_score
    if loss >= 0.30:
        return 1.0
    elif loss >= 0.20:
        return 0.75
    elif loss >= 0.10:
        return 0.50
    elif loss >= 0.05:
        return 0.25
    else:
        return 0.0


# ════════════════════════════════════════════
# 5. Phase-Aware Prioritization
# ════════════════════════════════════════════

def _apply_phase_boost(goal: PlannedGoal, project_phase: str) -> PlannedGoal:
    """Adjust goal priority based on current project phase.

    During 'test' phase, R_temporal goals get boosted.
    During 'design' phase, R_context goals get boosted.
    """
    boosts = _PHASE_PRIORITY_BOOST.get(project_phase, {})

    # Find which axis this goal targets
    impact_lower = goal.estimated_impact.lower().replace(" ", "_")
    for axis, multiplier in boosts.items():
        if axis.lower().replace("_", "") in impact_lower.replace("_", ""):
            goal.phase_boost = round(multiplier, 4)
            # Upgrade priority if boost is significant
            if multiplier >= 1.5 and goal.priority == "medium":
                goal.priority = "high"
                goal.phase = PHASE_NOW
            elif multiplier <= 0.8 and goal.priority == "high":
                goal.phase = PHASE_NEXT
            break

    return goal


# ════════════════════════════════════════════
# 6. External Signal Integration
# ════════════════════════════════════════════

@dataclass(slots=True)
class ExternalSignal:
    """An external signal that generates goals."""
    source: str        # "github_issue" | "ci_failure" | "user_feedback"
    title: str
    severity: str      # "critical" | "high" | "medium" | "low"
    details: str = ""
    url: str = ""


def _signals_to_goals(signals: list[ExternalSignal]) -> list[PlannedGoal]:
    """Convert external signals into planned goals."""
    goals = []
    severity_to_priority = {
        "critical": "high",
        "high": "high",
        "medium": "medium",
        "low": "low",
    }

    for sig in signals:
        priority = severity_to_priority.get(sig.severity, "medium")
        goal = PlannedGoal(
            goal=f"[{sig.source}] {sig.title}",
            priority=priority,
            rationale=sig.details or f"External signal from {sig.source}",
            estimated_impact="Multi-axis (external)",
            source=f"external_{sig.source}",
            phase=PHASE_NOW if priority == "high" else PHASE_NEXT,
            goal_id=f"EXT{hash(sig.title) % 10000:04d}",
        )
        goals.append(goal)

    return goals


# ════════════════════════════════════════════
# KS41b: Main Engine
# ════════════════════════════════════════════

class KS41b(KS41a):
    """KS41b: Goal Planning Engine — generation + planning + learning.

    Extends KS41a's goal generation with full planning capabilities:

    1. **Temporal roadmap**: Goals in now/next/later phases
    2. **Dependency graph**: Goal ordering with prerequisite tracking
    3. **Historical learning**: Calibrate estimates from past outcomes
    4. **Phase awareness**: Adapt priorities to design/implement/test/refactor/release
    5. **External signals**: GitHub issues, CI failures → goals
    6. **Decomposition**: Large goals → actionable sub-goals
    7. **Adaptive confidence**: Bayesian calibration from history
    8. **Gradient verification**: 5-level scoring instead of binary

    The planning loop (Dewey's iterative inquiry):
    ```
    Generate goals → Plan (phase/deps/decompose)
        → Execute → Record outcome
        → Calibrate → Generate better goals next time
    ```
    """

    VERSION = "KS41b"

    def __init__(self, history_path: str | None = None, **kwargs: Any):
        super().__init__(**kwargs)
        self._history = GoalHistoryTracker(history_path)

    # ── Public API ───────────────────────────────────────────────

    def plan(
        self,
        code: str,
        design: str | None = None,
        solver_feedback: list[dict[str, Any]] | None = None,
        project_phase: str = "implement",
        external_signals: list[ExternalSignal] | None = None,
        completed_goals: set[str] | None = None,
    ) -> Roadmap:
        """Generate, plan, and organize goals into an actionable roadmap.

        Parameters
        ----------
        code : str
            Source code to analyze.
        design : str, optional
            Original design intent for forward verification.
        solver_feedback : list[dict], optional
            Multi-solver disagreement data.
        project_phase : str
            Current phase: design/implement/test/refactor/release.
        external_signals : list[ExternalSignal], optional
            GitHub issues, CI failures, user feedback.
        completed_goals : set[str], optional
            IDs of already-completed goals (for dependency resolution).

        Returns
        -------
        Roadmap
            Phased, dependency-ordered, verified goal roadmap.
        """
        # Step 1: Generate base goals via KS41a
        report = self.generate_goals(code, design=design, solver_feedback=solver_feedback)

        # Step 2: Convert to PlannedGoals
        planned = [
            PlannedGoal.from_next_goal(g, f"G{i:04d}")
            for i, g in enumerate(report.goals)
        ]

        # Step 3: Add external signal goals
        if external_signals:
            planned.extend(_signals_to_goals(external_signals))

        # Step 4: Apply phase-aware prioritization
        planned = [_apply_phase_boost(g, project_phase) for g in planned]

        # Step 5: Gradient verification (not binary)
        if design:
            from katala_coding.kcs1a import KCS1a
            verdict = KCS1a().verify(design, code)
            for g in planned:
                g.verification_score = _gradient_verify(g, verdict.total_fidelity)

        # Step 6: Decompose large goals
        for g in planned:
            if len(g.goal) > DECOMPOSITION_THRESHOLD or g.priority == "high":
                g.sub_goals = _decompose_goal(g)

        # Step 7: Adaptive confidence calibration
        for g in planned:
            base = {"high": 0.7, "medium": 0.5, "low": 0.3}.get(g.priority, 0.5)
            g.confidence = self._history.adaptive_confidence(g.priority, base)

        # Step 8: Build dependency graph
        dep_graph = _build_dependency_graph(planned)
        for g in planned:
            g.depends_on = dep_graph.get(g.goal_id, [])

        # Step 9: Split into actionable/blocked
        actionable, blocked = _get_actionable(planned, dep_graph, completed_goals)

        # Step 10: Phase assignment (override based on deps)
        for g in blocked:
            if g.phase == PHASE_NOW:
                g.phase = PHASE_NEXT  # Can't do now if blocked

        # Organize by phase
        now = sorted([g for g in planned if g.phase == PHASE_NOW],
                      key=lambda g: -g.phase_boost)
        next_ = sorted([g for g in planned if g.phase == PHASE_NEXT],
                        key=lambda g: -g.phase_boost)
        later = [g for g in planned if g.phase == PHASE_LATER]

        # Estimated total improvement
        total_improvement = sum(g.confidence * g.phase_boost * 0.02 for g in planned)

        return Roadmap(
            now=now,
            next=next_,
            later=later,
            dependency_graph=dep_graph,
            total_goals=len(planned),
            actionable_now=len(actionable),
            blocked=len(blocked),
            estimated_total_improvement=round(min(0.20, total_improvement), 4),
            historical_accuracy=self._history.calibration_accuracy(),
            project_phase=project_phase,
            version=self.VERSION,
        )

    def record_outcome(self, goal: PlannedGoal, outcome: str,
                       actual_impact: float) -> GoalHistory:
        """Record a goal's outcome for future calibration.

        Parameters
        ----------
        goal : PlannedGoal
            The goal that was executed.
        outcome : str
            "success" | "partial" | "failed" | "abandoned"
        actual_impact : float
            Measured improvement (0.0-1.0).
        """
        return self._history.record(goal, outcome, actual_impact)

    def learning_report(self) -> dict[str, Any]:
        """Report on what the goal planner has learned from history."""
        return {
            "total_recorded": len(self._history.load()),
            "calibration_accuracy": self._history.calibration_accuracy(),
            "success_rate_by_priority": self._history.success_rate_by_priority(),
            "version": self.VERSION,
        }

    @staticmethod
    def format_roadmap(rm: Roadmap) -> str:
        """Pretty-print a roadmap."""
        lines = [
            f"╔══ KS41b Roadmap (v{rm.version}) ══╗",
            f"║ Phase: {rm.project_phase} | Goals: {rm.total_goals}",
            f"║ Actionable: {rm.actionable_now} | Blocked: {rm.blocked}",
            f"║ Est. improvement: {rm.estimated_total_improvement:.1%}",
            f"║ Historical accuracy: {rm.historical_accuracy:.0%}",
        ]

        for phase_name, phase_goals in [("🔴 NOW", rm.now), ("🟡 NEXT", rm.next), ("🟢 LATER", rm.later)]:
            if phase_goals:
                lines.append("║")
                lines.append(f"║ {phase_name} ({len(phase_goals)}):")
                for g in phase_goals[:6]:
                    icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g.priority, "⚪")
                    verify = f"[{g.verification_score:.0%}]" if g.verification_score > 0 else ""
                    boost = f" ×{g.phase_boost:.1f}" if g.phase_boost != 1.0 else ""
                    lines.append(f"║   {icon} {g.goal} {verify}{boost}")
                    if g.sub_goals:
                        for sg in g.sub_goals[:3]:
                            lines.append(f"║     ↳ {sg}")
                    if g.depends_on:
                        lines.append(f"║     ⛓️ depends on: {', '.join(g.depends_on)}")

        lines.append("╚" + "═" * 38 + "╝")
        return "\n".join(lines)
