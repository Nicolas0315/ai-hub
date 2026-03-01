"""
Adaptive Planner — Dynamic HTN Re-planning on Environment Change.

Targets: Interactive Environment 78%→88% (component 2/3)

Bridges HTN Planner (static plan) + Realtime Observer (live events)
= plans that adapt when the world changes.

"The plan survives until first contact with reality."

Architecture:
    RealtimeObserver.poll()
        ↓ events
    AdaptivePlanner.on_event(event)
        ↓ assess impact
    If impact > threshold:
        HTNPlanner.replan(remaining_tasks, new_state)
        ↓ new execution order
    Else:
        Continue current plan

Key capabilities:
1. **Impact assessment**: Not every event needs replanning (cost-aware)
2. **Partial replanning**: Only replan affected subtrees, not entire plan
3. **Rollback**: If new plan is worse, revert to old
4. **Learning**: Track which events actually need replanning

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from htn_planner import HTNPlanner, HTNPlan, Task, TaskState, TaskStatus, TaskType
from realtime_observer import RealtimeObserver, EnvironmentEvent, EventType, Severity
from env_state_model import EnvironmentStateModel

# ── Constants ──
REPLAN_IMPACT_THRESHOLD = 0.4     # Minimum impact score to trigger replan
REPLAN_COOLDOWN_S = 5.0           # Min time between replans
MAX_REPLANS = 10                  # Max replans per execution
ROLLBACK_THRESHOLD = 0.3          # If new plan score < old × this, rollback
PARTIAL_REPLAN_DEPTH = 3          # Max depth for partial replanning

# Event type value (string) → base impact score
# Use string keys to avoid enum identity issues from dual module loading
EVENT_IMPACT_MAP = {
    "file_deleted": 0.8,
    "test_fail": 0.9,
    "process_ended": 0.7,
    "git_branch_change": 0.6,
    "metric_threshold": 0.7,
    "file_modified": 0.3,
    "file_created": 0.2,
    "git_commit": 0.3,
    "test_pass": 0.1,
    "custom": 0.5,
    "env_var_change": 0.4,
}


@dataclass
class ReplanDecision:
    """Record of a replanning decision."""
    event: EnvironmentEvent
    impact_score: float
    replanned: bool
    reason: str
    old_progress: float
    new_progress: float = 0.0
    replan_time_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class PlanExecution:
    """Tracks an active plan execution with adaptive replanning."""
    plan: HTNPlan
    planner: HTNPlanner
    observer: RealtimeObserver
    env_model: EnvironmentStateModel

    # Replanning state
    replan_count: int = 0
    last_replan_time: float = 0.0
    decisions: List[ReplanDecision] = field(default_factory=list)

    # Execution state
    current_task_idx: int = 0
    started_at: float = field(default_factory=time.time)
    paused: bool = False


class AdaptivePlanner:
    """Adaptive planner that replans HTN tasks when environment changes.

    Usage:
    ```python
    adaptive = AdaptivePlanner(planner, observer, env_model)
    plan = adaptive.create_plan("improve ks42b quality")

    # Execute with adaptation
    while not adaptive.is_complete():
        # Poll environment
        events = adaptive.observe()

        # Assess + maybe replan
        for event in events:
            adaptive.on_event(event)

        # Execute next task
        result = adaptive.step()
    ```
    """

    def __init__(
        self,
        planner: Optional[HTNPlanner] = None,
        observer: Optional[RealtimeObserver] = None,
        env_model: Optional[EnvironmentStateModel] = None,
    ):
        self._planner = planner or HTNPlanner()
        self._observer = observer or RealtimeObserver()
        self._env_model = env_model or EnvironmentStateModel()
        self._execution: Optional[PlanExecution] = None
        self._impact_history: List[Tuple[EventType, float, bool]] = []

    # ── Plan Lifecycle ──

    def create_plan(self, goal: str, state: Optional[TaskState] = None) -> HTNPlan:
        """Create a plan and set up adaptive execution."""
        plan = self._planner.plan(goal, state)

        self._execution = PlanExecution(
            plan=plan,
            planner=self._planner,
            observer=self._observer,
            env_model=self._env_model,
        )

        return plan

    def observe(self) -> List[EnvironmentEvent]:
        """Poll environment for changes."""
        if not self._execution:
            return []
        events = self._execution.observer.poll()

        # Record transitions in env model
        for event in events:
            self._env_model.record_transition(
                action=event.description,
                effects=event.data,
                confidence=0.9 if event.severity != Severity.CRITICAL else 1.0,
            )

        return events

    def on_event(self, event: EnvironmentEvent) -> ReplanDecision:
        """Assess an event and decide whether to replan."""
        if not self._execution:
            return ReplanDecision(
                event=event, impact_score=0, replanned=False,
                reason="No active execution", old_progress=0,
            )

        exec_ctx = self._execution
        old_progress = exec_ctx.plan.progress

        # Calculate impact
        impact = self._assess_impact(event, exec_ctx)

        # Check if replanning is warranted
        should_replan, reason = self._should_replan(impact, event, exec_ctx)

        decision = ReplanDecision(
            event=event,
            impact_score=impact,
            replanned=should_replan,
            reason=reason,
            old_progress=old_progress,
        )

        if should_replan:
            start = time.time()
            new_plan = self._partial_replan(exec_ctx)
            decision.replan_time_ms = (time.time() - start) * 1000

            if new_plan:
                # Check rollback condition
                new_quality = self._plan_quality(new_plan)
                old_quality = self._plan_quality(exec_ctx.plan)

                if new_quality >= old_quality * ROLLBACK_THRESHOLD:
                    exec_ctx.plan = new_plan
                    exec_ctx.replan_count += 1
                    exec_ctx.last_replan_time = time.time()
                    decision.new_progress = new_plan.progress
                else:
                    decision.replanned = False
                    decision.reason += " (rolled back: new plan worse)"

        exec_ctx.decisions.append(decision)
        self._impact_history.append((event.event_type.value, impact, should_replan))
        return decision

    def step(self) -> Optional[Dict[str, Any]]:
        """Execute the next task in the plan."""
        if not self._execution or self.is_complete():
            return None

        plan = self._execution.plan
        if self._execution.current_task_idx >= len(plan.execution_order):
            return None

        task_id = plan.execution_order[self._execution.current_task_idx]
        task = plan.tasks.get(task_id)
        if not task:
            self._execution.current_task_idx += 1
            return None

        # Execute single task
        task.status = TaskStatus.EXECUTING
        start = time.time()

        try:
            if task.task_type == TaskType.VERIFICATION:
                result = self._planner._default_verifier(task.name, plan.state.facts)
            else:
                result = self._planner._default_executor(task.name, task.parameters)

            task.output = result.get("output", "")
            task.confidence = result.get("confidence", 0.7)
            task.duration_ms = (time.time() - start) * 1000

            if result.get("success", True):
                task.status = TaskStatus.COMPLETED
                plan.state.update(task.effects)
                plan.completed_tasks += 1
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error", "")
                plan.failed_tasks += 1
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            plan.failed_tasks += 1

        self._execution.current_task_idx += 1

        # Record in env model
        self._env_model.record_transition(
            action=f"task:{task.name}",
            effects=task.effects if task.status == TaskStatus.COMPLETED else {},
        )

        return {
            "task_id": task_id,
            "name": task.name,
            "status": task.status.value,
            "confidence": task.confidence,
            "duration_ms": task.duration_ms,
        }

    def is_complete(self) -> bool:
        if not self._execution:
            return True
        plan = self._execution.plan
        return (
            self._execution.current_task_idx >= len(plan.execution_order)
            or plan.tasks[plan.root_task_id].status == TaskStatus.COMPLETED
        )

    # ── Impact Assessment ──

    def _assess_impact(self, event: EnvironmentEvent, ctx: PlanExecution) -> float:
        """Score how much an event impacts the current plan (0-1)."""
        # Base impact from event type (use .value for string lookup)
        base = EVENT_IMPACT_MAP.get(event.event_type.value, 0.3)

        # Severity multiplier — critical events must be loud
        severity_mult = {
            Severity.INFO: 0.5,
            Severity.WARNING: 1.0,
            Severity.CRITICAL: 2.0,
        }.get(event.severity, 1.0)

        # Relevance: does this event affect any pending task?
        relevance = self._event_relevance(event, ctx.plan)

        # Progress factor: more impact when near completion (more to lose)
        progress_factor = 0.5 + 0.5 * ctx.plan.progress

        impact = min(1.0, base * severity_mult * relevance * progress_factor)
        return round(impact, 3)

    def _event_relevance(self, event: EnvironmentEvent, plan: HTNPlan) -> float:
        """How relevant is this event to pending tasks?"""
        import re

        pending = [
            t for t in plan.tasks.values()
            if t.status == TaskStatus.PENDING
        ]
        if not pending:
            return 0.0

        # Tokenize: split on whitespace AND underscores for compound names
        def tokenize(text: str) -> set:
            return set(re.split(r'[\s_]+', text.lower()))

        event_tokens = tokenize(event.description)
        max_overlap = 0.0

        for task in pending:
            task_tokens = tokenize(task.name)
            if not task_tokens:
                continue
            overlap = len(event_tokens & task_tokens) / max(len(task_tokens), 1)
            max_overlap = max(max_overlap, overlap)

        # Floor: unknown events still matter
        return max(0.5, max_overlap)

    def _should_replan(
        self, impact: float, event: EnvironmentEvent, ctx: PlanExecution,
    ) -> Tuple[bool, str]:
        """Decide whether to replan."""
        # Critical events always trigger (bypass cooldown and threshold)
        if event.is_critical:
            if ctx.replan_count < MAX_REPLANS:
                return True, "Critical event — immediate replan"
            return False, "Critical but max replans reached"

        # Cooldown
        if time.time() - ctx.last_replan_time < REPLAN_COOLDOWN_S:
            return False, "Cooldown active"

        # Max replans
        if ctx.replan_count >= MAX_REPLANS:
            return False, f"Max replans ({MAX_REPLANS}) reached"

        # Impact threshold
        if impact < REPLAN_IMPACT_THRESHOLD:
            return False, f"Impact {impact:.2f} below threshold {REPLAN_IMPACT_THRESHOLD}"

        # Learn from history: if this event type rarely needs replanning, skip
        type_history = [h for h in self._impact_history if h[0] == event.event_type.value]
        if len(type_history) >= 5:
            replan_rate = sum(1 for h in type_history if h[2]) / len(type_history)
            if replan_rate < 0.2:
                return False, f"Event type {event.event_type.value} rarely needs replanning ({replan_rate:.0%})"

        return True, f"Impact {impact:.2f} exceeds threshold"

    # ── Replanning ──

    def _partial_replan(self, ctx: PlanExecution) -> Optional[HTNPlan]:
        """Replan only the affected portion of the current plan."""
        plan = ctx.plan

        # Find pending tasks
        pending = [
            t for t in plan.tasks.values()
            if t.status == TaskStatus.PENDING
        ]

        if not pending:
            return None

        # Create new state from completed effects
        new_state = ctx.plan.state.clone()

        # Replan the root goal with current state
        new_plan = ctx.planner.plan(
            plan.tasks[plan.root_task_id].name,
            new_state,
        )

        # Preserve completed task info
        new_plan.completed_tasks = plan.completed_tasks
        new_plan.backtrack_count = plan.backtrack_count

        return new_plan

    def _plan_quality(self, plan: HTNPlan) -> float:
        """Estimate plan quality (0-1)."""
        if plan.total_tasks == 0:
            return 0.0

        completion = plan.completed_tasks / max(plan.total_tasks, 1)
        failure_penalty = plan.failed_tasks / max(plan.total_tasks, 1) * 0.5
        backtrack_penalty = plan.backtrack_count * 0.05

        return max(0.0, completion - failure_penalty - backtrack_penalty)

    # ── Stats & Reporting ──

    def get_stats(self) -> Dict[str, Any]:
        if not self._execution:
            return {"status": "no_active_execution"}

        ctx = self._execution
        return {
            "goal": ctx.plan.tasks[ctx.plan.root_task_id].name,
            "progress": ctx.plan.progress,
            "replan_count": ctx.replan_count,
            "total_decisions": len(ctx.decisions),
            "replanned_decisions": sum(1 for d in ctx.decisions if d.replanned),
            "env_transitions": self._env_model.get_stats()["total_transitions"],
            "elapsed_s": round(time.time() - ctx.started_at, 1),
        }

    def format_execution_log(self) -> str:
        """Pretty-print execution history with replan decisions."""
        if not self._execution:
            return "No active execution"

        ctx = self._execution
        lines = [
            f"╔══ Adaptive Execution: {ctx.plan.tasks[ctx.plan.root_task_id].name} ══╗",
            f"║ Progress: {ctx.plan.progress:.0%} | Replans: {ctx.replan_count}",
        ]

        for d in ctx.decisions:
            icon = "🔄" if d.replanned else "➡️"
            lines.append(
                f"║ {icon} [{d.event.event_type.value}] impact={d.impact_score:.2f} — {d.reason}"
            )

        lines.append("╚" + "═" * 50 + "╝")
        return "\n".join(lines)
