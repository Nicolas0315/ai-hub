"""
KS41a — Katala Samurai 41a: Autonomous Goal-Setting Engine

Extends KS40b (KS40c) with:
- Autonomous goal generation via KCS-2a reverse inference
- KCS-1a verification loop for goal quality measurement
- Multi-solver consensus → goal priority feedback
- Self-improving goal setting: goals are verified by the same
  framework that generates them (controlled self-reference)

Philosophical basis:
- Pragmatism: goals are evaluated by their practical consequences
- Quine: goal "correctness" is underdetermined — we measure quality instead
- Kuhn: paradigm shifts may invalidate current goals (temporal awareness)

Design: Youta Hilono, 2026-03-01
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import sys as _sys, os as _os
from dataclasses import dataclass
from typing import Any

_dir = _os.path.dirname(_os.path.abspath(__file__))
_src_dir = _os.path.dirname(_dir)
if _dir not in _sys.path:
    _sys.path.insert(0, _dir)
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)

try:
    from .ks40b import KS40b
except ImportError:
    from ks40b import KS40b

from katala_coding.kcs2a import KCS2a, NextGoal, ReverseAnalysis
from katala_coding.kcs1a import KCS1a, CodeVerdict

# ── Constants ──
GOAL_VERIFICATION_THRESHOLD = 0.65   # Min KCS-1a fidelity to accept a goal
SOLVER_CONFIDENCE_THRESHOLD = 0.70   # Below this, solver disagreement → new goal
MAX_GOALS_PER_ANALYSIS = 10
GOAL_QUALITY_WEIGHTS = {
    "completeness": 0.30,    # Are there incomplete implementations?
    "testability": 0.25,     # Can goals be verified?
    "impact": 0.25,          # How much does this improve overall score?
    "feasibility": 0.20,     # Is this achievable in one iteration?
}


@dataclass(slots=True)
class GoalReport:
    """KS41a goal generation + verification report."""
    # Generated goals
    goals: list[NextGoal]
    goal_count: int

    # KCS-2a reverse inference
    reverse_analysis: ReverseAnalysis

    # KCS-1a verification of goal quality
    goal_quality_score: float     # 0-1: overall quality of generated goals
    verified_goals: list[NextGoal]   # Goals that passed verification
    rejected_goals: list[NextGoal]   # Goals that failed verification

    # Multi-solver integration
    solver_aligned_goals: list[NextGoal]  # Goals derived from solver feedback

    # Meta
    version: str
    improvement_potential: float   # Estimated % improvement if all goals are executed


class KS41a(KS40b):
    """KS41a: Autonomous Goal-Setting with KCS verification loop.

    Adds goal generation capability on top of KS40c (KS40b):
    1. **Reverse inference**: KCS-2a analyzes code to infer design intent
    2. **Goal generation**: Gaps between intent and implementation → goals
    3. **Goal verification**: KCS-1a verifies goal quality (the meta-loop)
    4. **Solver feedback**: Multi-solver disagreements → high-priority goals

    The verification loop:
    ```
    Code → KCS-2a (infer intent) → Goals
      ↓                               ↓
    KCS-1a (verify goals)        Prioritize
      ↓                               ↓
    Accept/Reject              Execute top goals
    ```
    """

    VERSION = "KS41a"

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._kcs1 = KCS1a()
        self._kcs2 = KCS2a()

    # ── Public API ───────────────────────────────────────────────

    def generate_goals(
        self,
        code: str,
        design: str | None = None,
        solver_feedback: list[dict[str, Any]] | None = None,
    ) -> GoalReport:
        """Generate and verify autonomous goals from code analysis.

        Parameters
        ----------
        code : str
            Source code to analyze for goal generation.
        design : str, optional
            Original design intent (if available). Used by KCS-1a for
            forward verification.
        solver_feedback : list[dict], optional
            Multi-solver disagreement data. Each dict should have:
            ``disagreement_axis`` (str) and ``avg_confidence`` (float).

        Returns
        -------
        GoalReport
            Prioritized, verified goals with quality metrics.
        """
        # Step 1: KCS-2a reverse inference
        reverse = self._kcs2.analyze(code, solver_feedback=solver_feedback)

        # Step 2: Get all generated goals
        all_goals = reverse.goals[:MAX_GOALS_PER_ANALYSIS]

        # Step 3: KCS-1a verification loop (if design is available)
        verified = []
        rejected = []

        if design:
            verdict = self._kcs1.verify(design, code)
            fidelity = verdict.total_fidelity

            for goal in all_goals:
                # A goal is "verified" if the code area it targets
                # actually shows measurable loss in KCS-1a
                if self._goal_is_actionable(goal, verdict):
                    verified.append(goal)
                else:
                    rejected.append(goal)
        else:
            # Without design text, accept all goals from reverse inference
            verified = all_goals
            rejected = []

        # Step 4: Extract solver-aligned goals
        solver_goals = [g for g in verified if g.source == "solver_feedback"]

        # Step 5: Compute goal quality score
        quality = self._compute_goal_quality(reverse, verified, rejected)

        # Step 6: Estimate improvement potential
        potential = self._estimate_improvement(verified)

        return GoalReport(
            goals=all_goals,
            goal_count=len(all_goals),
            reverse_analysis=reverse,
            goal_quality_score=round(quality, 4),
            verified_goals=verified,
            rejected_goals=rejected,
            solver_aligned_goals=solver_goals,
            version=self.VERSION,
            improvement_potential=round(potential, 4),
        )

    def generate_goals_for_file(
        self,
        file_path: str,
        design: str | None = None,
        solver_feedback: list[dict[str, Any]] | None = None,
    ) -> GoalReport:
        """Generate goals for a source file."""
        with open(file_path, encoding="utf-8") as f:
            code = f.read()
        return self.generate_goals(code, design=design, solver_feedback=solver_feedback)

    def verify_with_goals(self, claim: Any, store: Any = None,
                          skip_s28: bool = True, **kwargs: Any) -> dict[str, Any]:
        """Run KS40c verification + autonomous goal generation.

        Extends ``verify()`` with a ``goal_report`` field in the output.
        """
        result = super().verify(claim, store=store, skip_s28=skip_s28, **kwargs)

        if not isinstance(result, dict) or "results" in result:
            return result

        # Generate goals from the claim text
        claim_text = claim.text if hasattr(claim, "text") else str(claim)
        source_text = kwargs.get("source_text")

        if source_text:
            goal_report = self.generate_goals(
                code=claim_text,  # Treat claim as "code" in the general sense
                design=str(source_text),
            )
            result["goal_report"] = {
                "goal_count": goal_report.goal_count,
                "verified_count": len(goal_report.verified_goals),
                "quality_score": goal_report.goal_quality_score,
                "improvement_potential": goal_report.improvement_potential,
                "top_goals": [
                    {"goal": g.goal, "priority": g.priority, "impact": g.estimated_impact}
                    for g in goal_report.verified_goals[:5]
                ],
            }

        result["version"] = self.VERSION
        return result

    # ── Private helpers ──────────────────────────────────────────

    def _goal_is_actionable(self, goal: NextGoal, verdict: CodeVerdict) -> bool:
        """Check if a goal targets an area with measurable KCS-1a loss.

        A goal is actionable if:
        1. It targets an axis where loss > threshold, OR
        2. It's from solver feedback (always actionable)
        """
        if goal.source == "solver_feedback":
            return True

        # Map goal impact to KCS-1a axes
        impact_lower = goal.estimated_impact.lower()
        axis_scores = {
            "r_struct": verdict.r_struct,
            "r_context": verdict.r_context,
            "r_qualia": verdict.r_qualia,
            "r_cultural": verdict.r_cultural,
            "r_temporal": verdict.r_temporal,
        }

        for axis, score in axis_scores.items():
            if axis.replace("_", "") in impact_lower.replace("_", "").replace(" ", ""):
                # Goal targets this axis — actionable if there's actual loss
                return score < (1.0 - GOAL_VERIFICATION_THRESHOLD + 0.5)

        # Default: accept if overall fidelity is below threshold
        return verdict.total_fidelity < GOAL_VERIFICATION_THRESHOLD

    def _compute_goal_quality(
        self,
        reverse: ReverseAnalysis,
        verified: list[NextGoal],
        rejected: list[NextGoal],
    ) -> float:
        """Compute overall goal quality score."""
        total = len(verified) + len(rejected)
        if total == 0:
            return 0.5  # No goals → neutral

        components = {
            "completeness": reverse.goal_confidence,
            "testability": len(verified) / max(1, total),
            "impact": min(1.0, len([g for g in verified if g.priority == "high"]) / max(1, len(verified))),
            "feasibility": reverse.coverage_score,
        }

        score = sum(
            GOAL_QUALITY_WEIGHTS[k] * v
            for k, v in components.items()
        )
        return max(0.0, min(1.0, score))

    def _estimate_improvement(self, verified_goals: list[NextGoal]) -> float:
        """Estimate percentage improvement if all verified goals are executed."""
        if not verified_goals:
            return 0.0

        # Each high-priority goal → ~2% improvement
        # Each medium → ~1%, each low → ~0.5%
        impact_map = {"high": 0.02, "medium": 0.01, "low": 0.005}
        total = sum(impact_map.get(g.priority, 0.005) for g in verified_goals)

        return min(0.15, total)  # Cap at 15% improvement estimate

    @staticmethod
    def format_goal_report(report: GoalReport) -> str:
        """Pretty-print a goal report."""
        lines = [
            f"╔══ KS41a Goal Report (v{report.version}) ══╗",
            f"║ Goals: {report.goal_count} generated | {len(report.verified_goals)} verified | {len(report.rejected_goals)} rejected",
            f"║ Quality: {report.goal_quality_score:.0%} | Improvement potential: {report.improvement_potential:.1%}",
            f"║ Solver-aligned: {len(report.solver_aligned_goals)}",
            "║",
        ]
        if report.verified_goals:
            lines.append("║ ✅ Verified Goals:")
            for g in report.verified_goals[:8]:
                icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g.priority, "⚪")
                lines.append(f"║   {icon} {g.goal}")
                lines.append(f"║     Impact: {g.estimated_impact}")
        if report.rejected_goals:
            lines.append("║")
            lines.append("║ ❌ Rejected (no measurable loss):")
            for g in report.rejected_goals[:3]:
                lines.append(f"║   • {g.goal}")
        lines.append("╚" + "═" * 42 + "╝")
        return "\n".join(lines)
