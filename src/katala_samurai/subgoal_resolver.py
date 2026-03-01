"""
Subgoal Dependency Resolver — Dynamic replanning for long-horizon task execution.

Target: Long-term Agent 82% → 92%+ (the biggest single gap: -13%, 41% of total)

What was missing:
  HTN decomposes tasks and checkpoint saves state, but there was NO:
  1. Dynamic replanning when subtask fails → find ALTERNATIVE path, not just skip
  2. Cross-session progress tracking with decay/freshness
  3. Dependency cycle detection + resolution
  4. Learning from failure patterns → strategy adaptation

Key insight (Youta): "Goal generation ≠ Goal planning" (KS41a vs KS41b).
This module bridges them: when plans break, it regenerates subgoals while
preserving the original goal structure.

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from checkpoint import CheckpointEngine
    _HAS_CHECKPOINT = True
except ImportError:
    _HAS_CHECKPOINT = False

try:
    from htn_planner import HTNPlanner, HTNPlan, Task, TaskStatus, TaskState
    _HAS_HTN = True
except ImportError:
    _HAS_HTN = False


# ── Constants ──
VERSION = "1.0.0"

# Dependency resolution
MAX_ALTERNATIVE_PATHS = 5           # Max alternative paths to explore per failure
MAX_REPLAN_ATTEMPTS = 3             # Max replanning attempts before giving up
CYCLE_DETECTION_LIMIT = 100         # Nodes to visit before declaring cycle

# Progress tracking
PROGRESS_DECAY_RATE = 0.95          # Per-session freshness decay
STALE_PROGRESS_THRESHOLD = 0.3     # Below this = progress considered stale
MIN_VIABLE_PROGRESS = 0.1          # Minimum progress to keep a goal alive

# Strategy adaptation
FAILURE_PATTERN_WINDOW = 10         # Look at last N failures
STRATEGY_ADAPTATION_THRESHOLD = 3   # N same-type failures → switch strategy

# File persistence
RESOLVER_STATE_FILE = "resolver_state.json"


class FailureType(Enum):
    """Classification of subtask failures for strategy adaptation."""
    PRECONDITION = "precondition"     # Required state not met
    TIMEOUT = "timeout"               # Took too long
    LOW_CONFIDENCE = "low_confidence" # Result below threshold
    DEPENDENCY = "dependency"         # Upstream task failed
    RESOURCE = "resource"             # External resource unavailable
    UNKNOWN = "unknown"


class ResolutionStrategy(Enum):
    """Strategies for resolving failed subtasks."""
    RETRY = "retry"                   # Same approach, maybe conditions changed
    DECOMPOSE = "decompose"           # Break into smaller subtasks
    BYPASS = "bypass"                 # Skip and find alternative path
    SUBSTITUTE = "substitute"         # Replace with equivalent subtask
    ESCALATE = "escalate"             # Promote to higher-level replanning
    DEFER = "defer"                   # Push to future session


@dataclass
class FailureRecord:
    """Record of a subtask failure for pattern learning."""
    task_name: str
    failure_type: str        # FailureType.value
    strategy_tried: str      # ResolutionStrategy.value
    resolved: bool
    timestamp: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyNode:
    """Node in the subgoal dependency graph."""
    goal_id: str
    goal_text: str
    status: str = "pending"          # pending | active | completed | failed | deferred
    progress: float = 0.0            # 0.0 - 1.0
    freshness: float = 1.0           # Decays across sessions
    dependencies: List[str] = field(default_factory=list)    # goal_ids this depends on
    dependents: List[str] = field(default_factory=list)      # goal_ids that depend on this
    alternatives: List[str] = field(default_factory=list)    # Alternative goal_ids if this fails
    failure_count: int = 0
    sessions_active: int = 0
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class ResolutionResult:
    """Result of attempting to resolve a failed subtask."""
    resolved: bool
    strategy_used: str
    new_plan: Optional[Dict[str, Any]] = None
    alternative_path: Optional[List[str]] = None
    message: str = ""


class SubgoalDependencyGraph:
    """
    Directed acyclic graph of subgoal dependencies with:
    - Cycle detection (Kahn's algorithm)
    - Topological ordering for execution
    - Alternative path discovery
    - Progress propagation (child→parent)
    """

    def __init__(self):
        self.nodes: Dict[str, DependencyNode] = {}
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)  # node → dependencies
        self._reverse: Dict[str, Set[str]] = defaultdict(set)     # node → dependents

    def add_node(self, goal_id: str, goal_text: str,
                 dependencies: Optional[List[str]] = None) -> DependencyNode:
        """Add a subgoal node with dependencies."""
        now = time.time()
        node = DependencyNode(
            goal_id=goal_id,
            goal_text=goal_text,
            dependencies=dependencies or [],
            created_at=now,
            updated_at=now,
        )
        self.nodes[goal_id] = node

        for dep_id in (dependencies or []):
            self._adjacency[goal_id].add(dep_id)
            self._reverse[dep_id].add(goal_id)
            if dep_id in self.nodes:
                self.nodes[dep_id].dependents.append(goal_id)

        # Check for cycles
        if self._has_cycle():
            # Remove the edge that caused the cycle
            for dep_id in (dependencies or []):
                self._adjacency[goal_id].discard(dep_id)
                self._reverse[dep_id].discard(goal_id)
            node.dependencies = []

        return node

    def add_alternative(self, goal_id: str, alternative_id: str) -> None:
        """Register an alternative path for a goal."""
        if goal_id in self.nodes:
            self.nodes[goal_id].alternatives.append(alternative_id)

    def _has_cycle(self) -> bool:
        """Kahn's algorithm for cycle detection."""
        in_degree: Dict[str, int] = defaultdict(int)
        for node_id in self.nodes:
            in_degree.setdefault(node_id, 0)
            for dep_id in self._adjacency.get(node_id, set()):
                in_degree[dep_id] = in_degree.get(dep_id, 0)

        queue = deque([n for n, d in in_degree.items() if d == 0])
        visited = 0

        while queue and visited < CYCLE_DETECTION_LIMIT:
            node_id = queue.popleft()
            visited += 1
            for dependent in self._reverse.get(node_id, set()):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        return visited < len(self.nodes)

    def topological_order(self) -> List[str]:
        """Return execution order respecting dependencies."""
        in_degree: Dict[str, int] = {n: 0 for n in self.nodes}
        for node_id in self.nodes:
            for dep_id in self._adjacency.get(node_id, set()):
                if dep_id in in_degree:
                    in_degree[node_id] += 1

        queue = deque(sorted(
            [n for n, d in in_degree.items() if d == 0],
            key=lambda x: self.nodes[x].progress,
            reverse=True  # Prioritize higher-progress goals
        ))
        order = []

        while queue:
            node_id = queue.popleft()
            order.append(node_id)
            for dependent in self._reverse.get(node_id, set()):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return order

    def get_actionable(self) -> List[str]:
        """Return goals whose dependencies are all completed."""
        actionable = []
        for node_id, node in self.nodes.items():
            if node.status not in ("pending", "active"):
                continue
            deps_met = all(
                self.nodes.get(d, DependencyNode(goal_id=d, goal_text="")).status == "completed"
                for d in node.dependencies
            )
            if deps_met:
                actionable.append(node_id)
        return actionable

    def propagate_progress(self) -> None:
        """Update parent progress based on children's completion."""
        for node_id in self.topological_order():
            node = self.nodes[node_id]
            deps = [d for d in node.dependencies if d in self.nodes]
            if deps:
                child_progress = sum(self.nodes[d].progress for d in deps) / len(deps)
                # Parent progress = max(own progress, children average * 0.9)
                node.progress = max(node.progress, child_progress * 0.9)

    def find_alternative_path(self, failed_id: str) -> Optional[List[str]]:
        """When a goal fails, find an alternative route to its dependents."""
        if failed_id not in self.nodes:
            return None

        node = self.nodes[failed_id]
        # Check direct alternatives
        for alt_id in node.alternatives:
            if alt_id in self.nodes and self.nodes[alt_id].status != "failed":
                return [alt_id]

        # Try to find a path through sibling nodes
        dependents = list(self._reverse.get(failed_id, set()))
        for dependent_id in dependents:
            dep_node = self.nodes.get(dependent_id)
            if not dep_node:
                continue
            # Can this dependent proceed without the failed node?
            other_deps = [d for d in dep_node.dependencies if d != failed_id]
            if other_deps and all(
                self.nodes.get(d, DependencyNode(goal_id=d, goal_text="")).status in ("completed", "active")
                for d in other_deps
            ):
                return other_deps  # Can bypass via other dependencies

        return None

    def decay_freshness(self) -> None:
        """Apply freshness decay (called at session start)."""
        for node in self.nodes.values():
            if node.status in ("pending", "active"):
                node.freshness *= PROGRESS_DECAY_RATE
                if node.freshness < STALE_PROGRESS_THRESHOLD:
                    node.status = "deferred"

    def overall_progress(self) -> float:
        """Calculate weighted overall progress."""
        if not self.nodes:
            return 0.0
        total = sum(n.progress for n in self.nodes.values())
        return total / len(self.nodes)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for persistence."""
        return {
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "adjacency": {k: list(v) for k, v in self._adjacency.items()},
            "reverse": {k: list(v) for k, v in self._reverse.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubgoalDependencyGraph":
        """Deserialize from persistence."""
        graph = cls()
        for k, v in data.get("nodes", {}).items():
            graph.nodes[k] = DependencyNode(**v)
        for k, v in data.get("adjacency", {}).items():
            graph._adjacency[k] = set(v)
        for k, v in data.get("reverse", {}).items():
            graph._reverse[k] = set(v)
        return graph


class FailurePatternLearner:
    """
    Learns from failure patterns to adapt resolution strategies.

    Key insight: if the same failure type keeps occurring with the same
    strategy, switch to a different strategy.
    """

    # Strategy priority by failure type (most effective first)
    STRATEGY_MAP: Dict[str, List[str]] = {
        FailureType.PRECONDITION.value: [
            ResolutionStrategy.DECOMPOSE.value,
            ResolutionStrategy.DEFER.value,
            ResolutionStrategy.BYPASS.value,
        ],
        FailureType.TIMEOUT.value: [
            ResolutionStrategy.DECOMPOSE.value,
            ResolutionStrategy.RETRY.value,
            ResolutionStrategy.SUBSTITUTE.value,
        ],
        FailureType.LOW_CONFIDENCE.value: [
            ResolutionStrategy.RETRY.value,
            ResolutionStrategy.SUBSTITUTE.value,
            ResolutionStrategy.ESCALATE.value,
        ],
        FailureType.DEPENDENCY.value: [
            ResolutionStrategy.BYPASS.value,
            ResolutionStrategy.SUBSTITUTE.value,
            ResolutionStrategy.DEFER.value,
        ],
        FailureType.RESOURCE.value: [
            ResolutionStrategy.DEFER.value,
            ResolutionStrategy.SUBSTITUTE.value,
            ResolutionStrategy.RETRY.value,
        ],
        FailureType.UNKNOWN.value: [
            ResolutionStrategy.RETRY.value,
            ResolutionStrategy.DECOMPOSE.value,
            ResolutionStrategy.ESCALATE.value,
        ],
    }

    def __init__(self):
        self.history: List[FailureRecord] = []

    def record_failure(self, task_name: str, failure_type: FailureType,
                       strategy: ResolutionStrategy, resolved: bool,
                       context: Optional[Dict] = None) -> None:
        """Record a failure and its resolution outcome."""
        self.history.append(FailureRecord(
            task_name=task_name,
            failure_type=failure_type.value,
            strategy_tried=strategy.value,
            resolved=resolved,
            timestamp=time.time(),
            context=context or {},
        ))

    def recommend_strategy(self, failure_type: FailureType,
                           task_name: str = "") -> ResolutionStrategy:
        """Recommend a resolution strategy based on failure history."""
        strategies = self.STRATEGY_MAP.get(
            failure_type.value,
            [ResolutionStrategy.RETRY.value],
        )

        # Check recent history for this failure type
        recent = [
            r for r in self.history[-FAILURE_PATTERN_WINDOW:]
            if r.failure_type == failure_type.value
        ]

        # Count failed strategies
        failed_strategies = set()
        for r in recent:
            if not r.resolved:
                failed_strategies.add(r.strategy_tried)

        # Pick first strategy that hasn't failed recently
        for s in strategies:
            if s not in failed_strategies:
                return ResolutionStrategy(s)

        # All have failed — escalate
        return ResolutionStrategy.ESCALATE

    def success_rate(self, strategy: ResolutionStrategy) -> float:
        """Success rate for a given strategy."""
        relevant = [r for r in self.history if r.strategy_tried == strategy.value]
        if not relevant:
            return 0.5  # No data → neutral
        return sum(1 for r in relevant if r.resolved) / len(relevant)

    def to_dict(self) -> List[Dict]:
        """Serialize failure history."""
        return [asdict(r) for r in self.history[-FAILURE_PATTERN_WINDOW * 5:]]

    @classmethod
    def from_dict(cls, data: List[Dict]) -> "FailurePatternLearner":
        """Deserialize."""
        learner = cls()
        for d in data:
            learner.history.append(FailureRecord(**d))
        return learner


class SubgoalResolver:
    """
    Main resolver: integrates dependency graph, failure learning,
    and dynamic replanning.

    Workflow:
    1. Build dependency graph from KS41b Roadmap or HTN plan
    2. Execute in topological order
    3. On failure → classify → recommend strategy → apply
    4. If strategy fails → try alternative path → replan if needed
    5. Track progress across sessions via checkpoint
    """

    def __init__(self, checkpoint_dir: Optional[str] = None):
        self.graph = SubgoalDependencyGraph()
        self.learner = FailurePatternLearner()
        self._checkpoint_dir = Path(checkpoint_dir or ".katala_checkpoints")
        self._replan_count = 0
        self._session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

        # Try to load previous state
        self._load_state()

    def build_from_roadmap(self, roadmap_goals: List[Dict[str, Any]]) -> SubgoalDependencyGraph:
        """Build dependency graph from KS41b Roadmap goals.

        Args:
            roadmap_goals: List of dicts with keys:
                goal_id, goal, depends_on, sub_goals, priority
        """
        self.graph = SubgoalDependencyGraph()

        for g in roadmap_goals:
            self.graph.add_node(
                goal_id=g.get("goal_id", ""),
                goal_text=g.get("goal", ""),
                dependencies=g.get("depends_on", []),
            )

            # Add sub_goals as children
            for i, sg in enumerate(g.get("sub_goals", [])):
                sg_id = f"{g['goal_id']}_sub{i}"
                self.graph.add_node(
                    goal_id=sg_id,
                    goal_text=sg,
                    dependencies=[g["goal_id"]],
                )

        return self.graph

    def resolve_failure(self, failed_goal_id: str,
                        failure_type: FailureType = FailureType.UNKNOWN,
                        context: Optional[Dict] = None) -> ResolutionResult:
        """Attempt to resolve a failed subgoal.

        Steps:
        1. Classify failure
        2. Recommend strategy from pattern learner
        3. Execute strategy
        4. If resolved → update graph
        5. If not → try alternative path
        6. If no alternative → escalate/defer
        """
        if failed_goal_id not in self.graph.nodes:
            return ResolutionResult(
                resolved=False,
                strategy_used="none",
                message=f"Goal {failed_goal_id} not in graph",
            )

        node = self.graph.nodes[failed_goal_id]
        node.failure_count += 1
        node.status = "failed"

        # Get strategy recommendation
        strategy = self.learner.recommend_strategy(failure_type, node.goal_text)

        # Execute strategy
        result = self._execute_strategy(failed_goal_id, strategy, context or {})

        # Record outcome
        self.learner.record_failure(
            task_name=node.goal_text,
            failure_type=failure_type,
            strategy=strategy,
            resolved=result.resolved,
            context=context,
        )

        # If not resolved, try alternative path
        if not result.resolved:
            alt_path = self.graph.find_alternative_path(failed_goal_id)
            if alt_path:
                result = ResolutionResult(
                    resolved=True,
                    strategy_used="alternative_path",
                    alternative_path=alt_path,
                    message=f"Found alternative via: {alt_path}",
                )
                # Reroute dependents to alternative
                for dependent_id in list(self.graph._reverse.get(failed_goal_id, set())):
                    dep_node = self.graph.nodes.get(dependent_id)
                    if dep_node:
                        dep_node.dependencies = [
                            d if d != failed_goal_id else alt_path[0]
                            for d in dep_node.dependencies
                        ]

        # If still not resolved, try replanning
        if not result.resolved and self._replan_count < MAX_REPLAN_ATTEMPTS:
            self._replan_count += 1
            result = self._replan_around_failure(failed_goal_id)

        # Save state
        self._save_state()

        return result

    def _execute_strategy(self, goal_id: str, strategy: ResolutionStrategy,
                          context: Dict) -> ResolutionResult:
        """Execute a specific resolution strategy."""
        node = self.graph.nodes[goal_id]

        if strategy == ResolutionStrategy.RETRY:
            # Reset status, let it be picked up again
            node.status = "pending"
            return ResolutionResult(
                resolved=True,
                strategy_used=strategy.value,
                message=f"Retrying: {node.goal_text}",
            )

        elif strategy == ResolutionStrategy.DECOMPOSE:
            # Break into smaller subtasks
            sub_ids = self._auto_decompose(goal_id)
            if sub_ids:
                node.status = "active"
                return ResolutionResult(
                    resolved=True,
                    strategy_used=strategy.value,
                    new_plan={"subtasks": sub_ids},
                    message=f"Decomposed into {len(sub_ids)} subtasks",
                )
            return ResolutionResult(
                resolved=False,
                strategy_used=strategy.value,
                message="Could not decompose further",
            )

        elif strategy == ResolutionStrategy.BYPASS:
            # Mark as skipped, unblock dependents
            node.status = "deferred"
            node.progress = 0.5  # Partial credit
            return ResolutionResult(
                resolved=True,
                strategy_used=strategy.value,
                message=f"Bypassed: {node.goal_text}",
            )

        elif strategy == ResolutionStrategy.SUBSTITUTE:
            # Look for alternative approaches
            alt_path = self.graph.find_alternative_path(goal_id)
            if alt_path:
                node.status = "deferred"
                return ResolutionResult(
                    resolved=True,
                    strategy_used=strategy.value,
                    alternative_path=alt_path,
                    message=f"Substituted with: {alt_path}",
                )
            return ResolutionResult(
                resolved=False,
                strategy_used=strategy.value,
                message="No substitute found",
            )

        elif strategy == ResolutionStrategy.DEFER:
            node.status = "deferred"
            node.freshness *= 0.5
            return ResolutionResult(
                resolved=True,
                strategy_used=strategy.value,
                message=f"Deferred to future session: {node.goal_text}",
            )

        elif strategy == ResolutionStrategy.ESCALATE:
            return ResolutionResult(
                resolved=False,
                strategy_used=strategy.value,
                message=f"ESCALATE: {node.goal_text} requires higher-level replanning",
            )

        return ResolutionResult(resolved=False, strategy_used="unknown")

    def _auto_decompose(self, goal_id: str) -> List[str]:
        """Automatically decompose a goal into smaller subtasks."""
        node = self.graph.nodes[goal_id]
        text = node.goal_text.lower()

        # Heuristic decomposition rules
        sub_goals = []

        if "implement" in text or "complete" in text or "build" in text:
            sub_goals = [
                f"Analyze requirements for: {node.goal_text}",
                f"Design solution for: {node.goal_text}",
                f"Implement core logic for: {node.goal_text}",
                f"Test and verify: {node.goal_text}",
            ]
        elif "improve" in text or "optimize" in text:
            sub_goals = [
                f"Measure current state of: {node.goal_text}",
                f"Identify bottleneck in: {node.goal_text}",
                f"Apply fix for: {node.goal_text}",
            ]
        elif "verify" in text or "test" in text:
            sub_goals = [
                f"Define criteria for: {node.goal_text}",
                f"Execute verification of: {node.goal_text}",
            ]
        elif "investigate" in text or "research" in text:
            sub_goals = [
                f"Gather evidence for: {node.goal_text}",
                f"Analyze evidence for: {node.goal_text}",
                f"Synthesize findings for: {node.goal_text}",
            ]
        else:
            # Generic 2-step decomposition
            sub_goals = [
                f"Prepare: {node.goal_text}",
                f"Execute: {node.goal_text}",
            ]

        sub_ids = []
        for i, sg in enumerate(sub_goals):
            sg_id = f"{goal_id}_d{i}"
            deps = [sub_ids[-1]] if sub_ids else []  # Sequential chain
            self.graph.add_node(sg_id, sg, dependencies=deps)
            sub_ids.append(sg_id)

        return sub_ids

    def _replan_around_failure(self, failed_id: str) -> ResolutionResult:
        """Dynamic replanning: remove failed branch and rebuild."""
        node = self.graph.nodes[failed_id]
        dependents = list(self.graph._reverse.get(failed_id, set()))

        # For each dependent, check if it can still proceed
        unblocked = 0
        for dep_id in dependents:
            dep_node = self.graph.nodes.get(dep_id)
            if not dep_node:
                continue
            # Remove failed dependency
            dep_node.dependencies = [d for d in dep_node.dependencies if d != failed_id]
            if not dep_node.dependencies or all(
                self.graph.nodes.get(d, DependencyNode(goal_id=d, goal_text="")).status == "completed"
                for d in dep_node.dependencies
            ):
                dep_node.status = "pending"
                unblocked += 1

        if unblocked > 0:
            return ResolutionResult(
                resolved=True,
                strategy_used="replan",
                message=f"Replanned around {failed_id}: unblocked {unblocked} goals",
            )

        return ResolutionResult(
            resolved=False,
            strategy_used="replan",
            message=f"Could not replan around {failed_id}",
        )

    def session_start(self) -> Dict[str, Any]:
        """Called at session start: decay freshness, report status."""
        self.graph.decay_freshness()
        self.graph.propagate_progress()

        actionable = self.graph.get_actionable()
        stale = [n for n in self.graph.nodes.values() if n.freshness < STALE_PROGRESS_THRESHOLD]

        return {
            "total_goals": len(self.graph.nodes),
            "actionable": len(actionable),
            "actionable_ids": actionable,
            "stale": len(stale),
            "overall_progress": self.graph.overall_progress(),
            "session_id": self._session_id,
            "replan_count": self._replan_count,
            "failure_learner_stats": {
                s.value: self.learner.success_rate(s)
                for s in ResolutionStrategy
            },
        }

    def complete_goal(self, goal_id: str, confidence: float = 1.0) -> None:
        """Mark a goal as completed with confidence."""
        if goal_id in self.graph.nodes:
            node = self.graph.nodes[goal_id]
            node.status = "completed"
            node.progress = confidence
            node.updated_at = time.time()
            node.sessions_active += 1
            self.graph.propagate_progress()
            self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Return full resolver status."""
        by_status = defaultdict(int)
        for n in self.graph.nodes.values():
            by_status[n.status] += 1

        return {
            "version": VERSION,
            "total_goals": len(self.graph.nodes),
            "by_status": dict(by_status),
            "overall_progress": self.graph.overall_progress(),
            "failure_history_size": len(self.learner.history),
            "replan_count": self._replan_count,
            "graph_has_cycles": self.graph._has_cycle(),
        }

    def _save_state(self) -> None:
        """Persist resolver state."""
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "graph": self.graph.to_dict(),
            "learner": self.learner.to_dict(),
            "replan_count": self._replan_count,
            "session_id": self._session_id,
            "saved_at": time.time(),
        }
        path = self._checkpoint_dir / RESOLVER_STATE_FILE
        path.write_text(json.dumps(state, indent=2, default=str))

    def _load_state(self) -> None:
        """Load previous state from checkpoint."""
        path = self._checkpoint_dir / RESOLVER_STATE_FILE
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self.graph = SubgoalDependencyGraph.from_dict(data.get("graph", {}))
            self.learner = FailurePatternLearner.from_dict(data.get("learner", []))
            self._replan_count = data.get("replan_count", 0)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Start fresh on corruption


# ════════════════════════════════════════════════════════════════
# Convenience: integrate with HTN planner
# ════════════════════════════════════════════════════════════════

def integrate_htn_resolver(planner: Any, resolver: SubgoalResolver) -> Callable:
    """Wrap HTN planner's execute() with resolver's failure handling.

    Returns a wrapped execute function that:
    1. Runs HTN plan normally
    2. On any failed task → resolver.resolve_failure()
    3. If resolved → retry
    4. Returns enhanced plan with resolution notes
    """
    if not _HAS_HTN:
        return lambda plan: plan

    original_execute = planner.execute

    def enhanced_execute(plan: HTNPlan) -> HTNPlan:
        # First pass: normal execution
        plan = original_execute(plan)

        # Check for failures
        failed_tasks = [
            (tid, t) for tid, t in plan.tasks.items()
            if t.status == TaskStatus.FAILED
        ]

        for task_id, task in failed_tasks:
            # Classify failure
            ftype = FailureType.UNKNOWN
            if "precondition" in (task.error or "").lower():
                ftype = FailureType.PRECONDITION
            elif "timeout" in (task.error or "").lower():
                ftype = FailureType.TIMEOUT
            elif "confidence" in (task.error or "").lower():
                ftype = FailureType.LOW_CONFIDENCE

            # Try to resolve
            result = resolver.resolve_failure(
                task_id, ftype,
                context={"task_name": task.name, "error": task.error},
            )

            if result.resolved and result.strategy_used == "retry":
                # Reset and retry this task
                task.status = TaskStatus.PENDING
                task.error = None

        # Second pass if any tasks were reset
        retryable = [t for t in plan.tasks.values() if t.status == TaskStatus.PENDING]
        if retryable:
            plan = original_execute(plan)

        return plan

    return enhanced_execute


# ════════════════════════════════════════════════════════════════
# Module identity
# ════════════════════════════════════════════════════════════════

def get_status() -> Dict[str, Any]:
    """Module status for KCS diagnosis."""
    return {
        "module": "subgoal_resolver",
        "version": VERSION,
        "components": [
            "SubgoalDependencyGraph",
            "FailurePatternLearner",
            "SubgoalResolver",
            "integrate_htn_resolver",
        ],
        "targets": {
            "long_term_agent": "82% → 92%",
            "mechanism": "Dynamic replanning + failure learning + cross-session progress",
        },
    }
