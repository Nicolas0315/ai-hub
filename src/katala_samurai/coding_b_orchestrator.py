"""
Coding B Orchestrator Artifacts — Step 1 foundation.

This module defines the first-class artifacts owned by the Coding B parent.
Step 1 intentionally stops at the artifact layer:
- GlobalSpec
- WorkShard
- WorkResult
- MergeBoard

No parallel execution is implemented here yet.
The goal is to make shard planning and collection explicit, inspectable,
and serializable before orchestration logic is added.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal
import uuid

Phase = Literal["implement", "fix", "test"]
ShardStatus = Literal["pending", "running", "done", "failed", "blocked"]
BoardStatus = Literal["open", "ready", "blocked"]


@dataclass(slots=True)
class GlobalSpec:
    """Canonical parent-owned spec for a Coding B run."""

    goal: str
    invariants: list[str] = field(default_factory=list)
    forbidden_zones: list[str] = field(default_factory=list)
    integration_points: list[str] = field(default_factory=list)
    done_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.goal.strip():
            issues.append("goal_missing")
        return issues

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkShard:
    """A parent-issued independent work packet."""

    shard_id: str
    phase: Phase
    goal: str
    owned_paths: list[str] = field(default_factory=list)
    allowed_symbols: list[str] = field(default_factory=list)
    forbidden_paths: list[str] = field(default_factory=list)
    input_contracts: list[str] = field(default_factory=list)
    output_contracts: list[str] = field(default_factory=list)
    local_done_criteria: list[str] = field(default_factory=list)
    depends_on_shard_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.shard_id.strip():
            issues.append("shard_id_missing")
        if not self.goal.strip():
            issues.append("goal_missing")
        overlap = sorted(set(self.owned_paths) & set(self.forbidden_paths))
        if overlap:
            issues.append(f"path_overlap:{','.join(overlap)}")
        return issues

    def owns_path(self, path: str) -> bool:
        return path in self.owned_paths

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WorkResult:
    """Child-returned result packet for one shard."""

    shard_id: str
    phase: Phase
    status: ShardStatus
    changed_files: list[str] = field(default_factory=list)
    summary: str = ""
    test_results: list[str] = field(default_factory=list)
    detected_issues: list[str] = field(default_factory=list)
    patch_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate_against(self, shard: WorkShard) -> list[str]:
        issues: list[str] = []
        if self.shard_id != shard.shard_id:
            issues.append("shard_id_mismatch")
        if self.phase != shard.phase:
            issues.append("phase_mismatch")
        for path in self.changed_files:
            if path not in shard.owned_paths:
                issues.append(f"boundary_violation:{path}")
        return issues

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MergeBoard:
    """Parent-owned merge state for one phase."""

    phase: Phase
    shard_results: list[WorkResult] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    status: BoardStatus = "open"
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: WorkResult, shard: WorkShard | None = None) -> list[str]:
        violations = result.validate_against(shard) if shard is not None else []
        self.shard_results.append(result)
        self.conflicts.extend(violations)
        self._refresh_status()
        return violations

    def add_gap(self, gap: str) -> None:
        self.gaps.append(gap)
        self._refresh_status()

    def add_conflict(self, conflict: str) -> None:
        self.conflicts.append(conflict)
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self.conflicts:
            self.status = "blocked"
        elif self.gaps:
            self.status = "open"
        else:
            self.status = "ready"

    @property
    def ready_for_next_phase(self) -> bool:
        return self.status == "ready"

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "shard_results": [r.to_dict() for r in self.shard_results],
            "conflicts": list(self.conflicts),
            "gaps": list(self.gaps),
            "status": self.status,
            "ready_for_next_phase": self.ready_for_next_phase,
            "metadata": dict(self.metadata),
        }


def build_empty_merge_board(phase: Phase, *, metadata: dict[str, Any] | None = None) -> MergeBoard:
    return MergeBoard(phase=phase, metadata=metadata or {})


@dataclass(slots=True)
class ChildSessionRecord:
    """Ephemeral child coding session owned by the parent run."""

    shard_id: str
    session_label: str
    session_key: str | None = None
    status: Literal["planned", "spawned", "completed", "deleted"] = "planned"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SessionActionPlan:
    """Serializable OpenClaw-facing session action plan."""

    action: Literal["spawn", "send", "delete"]
    shard_id: str
    label: str | None = None
    session_key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecManager:
    """Normalize and validate parent-owned specs before sharding."""

    @staticmethod
    def normalize(spec: GlobalSpec) -> GlobalSpec:
        return GlobalSpec(
            goal=" ".join(spec.goal.split()),
            invariants=_dedupe_preserve(spec.invariants),
            forbidden_zones=_normalize_paths(spec.forbidden_zones),
            integration_points=_dedupe_preserve(spec.integration_points),
            done_criteria=_dedupe_preserve(spec.done_criteria),
            metadata=dict(spec.metadata),
        )

    @staticmethod
    def validate_or_raise(spec: GlobalSpec) -> GlobalSpec:
        normalized = SpecManager.normalize(spec)
        issues = normalized.validate()
        if issues:
            raise ValueError(f"invalid_global_spec:{','.join(issues)}")
        return normalized


class ShardPlanner:
    """Produce independent work shards from path groups or candidate paths."""

    def __init__(self, max_children: int = 8):
        self.max_children = max_children

    def plan_from_path_groups(
        self,
        spec: GlobalSpec,
        phase: Phase,
        path_groups: list[list[str]],
        *,
        shard_prefix: str | None = None,
    ) -> list[WorkShard]:
        spec = SpecManager.validate_or_raise(spec)
        groups = [_normalize_paths(group) for group in path_groups if group]
        groups = [g for g in groups if g]
        groups = self._enforce_non_overlap(groups)
        if len(groups) > self.max_children:
            raise ValueError(f"too_many_shards:{len(groups)}>{self.max_children}")

        prefix = shard_prefix or phase
        shards: list[WorkShard] = []
        all_owned = [path for group in groups for path in group]
        all_owned_set = set(all_owned)

        for idx, owned_paths in enumerate(groups, start=1):
            shard_id = f"{prefix}-{idx:02d}"
            forbidden = sorted(all_owned_set - set(owned_paths))
            shard = WorkShard(
                shard_id=shard_id,
                phase=phase,
                goal=spec.goal,
                owned_paths=owned_paths,
                forbidden_paths=forbidden,
                input_contracts=_dedupe_preserve(spec.invariants),
                output_contracts=_dedupe_preserve(spec.integration_points),
                local_done_criteria=_dedupe_preserve(spec.done_criteria),
                metadata={"source": "ShardPlanner", "child_index": idx},
            )
            issues = shard.validate()
            if issues:
                raise ValueError(f"invalid_shard:{shard_id}:{','.join(issues)}")
            shards.append(shard)
        return shards

    def plan_from_candidate_paths(
        self,
        spec: GlobalSpec,
        phase: Phase,
        candidate_paths: list[str],
        *,
        shard_prefix: str | None = None,
    ) -> list[WorkShard]:
        normalized = _normalize_paths(candidate_paths)
        grouped = self._cluster_by_parent_dir(normalized)
        return self.plan_from_path_groups(spec, phase, grouped, shard_prefix=shard_prefix)

    def _enforce_non_overlap(self, groups: list[list[str]]) -> list[list[str]]:
        seen: set[str] = set()
        output: list[list[str]] = []
        for group in groups:
            overlap = sorted(set(group) & seen)
            if overlap:
                raise ValueError(f"overlapping_owned_paths:{','.join(overlap)}")
            seen.update(group)
            output.append(group)
        return output

    def _cluster_by_parent_dir(self, paths: list[str]) -> list[list[str]]:
        buckets: dict[str, list[str]] = {}
        for path in paths:
            parent = str(PurePosixPath(path).parent)
            buckets.setdefault(parent, []).append(path)
        groups = sorted(buckets.values(), key=lambda g: (-len(g), g[0]))
        return groups[: self.max_children]


class SessionLifecycleManager:
    """Manage ephemeral child-session records for shard execution.

    This layer intentionally stays tool-agnostic in Step 2.
    Real session spawning/deletion can bind to OpenClaw sessions tools later.
    """

    def __init__(self, parent_label: str = "coding-b-parent"):
        self.parent_label = parent_label
        self._records: dict[str, ChildSessionRecord] = {}

    def plan_sessions(self, shards: list[WorkShard]) -> list[ChildSessionRecord]:
        records: list[ChildSessionRecord] = []
        for shard in shards:
            label = f"{self.parent_label}:{shard.shard_id}:{uuid.uuid4().hex[:8]}"
            rec = ChildSessionRecord(shard_id=shard.shard_id, session_label=label)
            self._records[shard.shard_id] = rec
            records.append(rec)
        return records

    def mark_spawned(self, shard_id: str, session_key: str) -> ChildSessionRecord:
        rec = self._records[shard_id]
        rec.session_key = session_key
        rec.status = "spawned"
        return rec

    def mark_completed(self, shard_id: str) -> ChildSessionRecord:
        rec = self._records[shard_id]
        rec.status = "completed"
        return rec

    def mark_deleted(self, shard_id: str) -> ChildSessionRecord:
        rec = self._records[shard_id]
        rec.status = "deleted"
        return rec

    def get(self, shard_id: str) -> ChildSessionRecord | None:
        return self._records.get(shard_id)

    def snapshot(self) -> list[dict[str, Any]]:
        return [rec.to_dict() for rec in self._records.values()]


class ResultCollector:
    """Collect child results into a phase merge board."""

    def __init__(self, phase: Phase, shards: list[WorkShard]):
        self.phase = phase
        self.shards = {s.shard_id: s for s in shards}
        self.board = build_empty_merge_board(phase, metadata={"collector": "ResultCollector"})
        self.expected_shard_ids = set(self.shards)
        self.received_shard_ids: set[str] = set()

    def collect(self, result: WorkResult) -> list[str]:
        shard = self.shards.get(result.shard_id)
        if shard is None:
            violation = f"unknown_shard:{result.shard_id}"
            self.board.add_conflict(violation)
            return [violation]
        violations = self.board.add_result(result, shard)
        self.received_shard_ids.add(result.shard_id)
        self._refresh_gaps()
        return violations

    def finalize(self) -> MergeBoard:
        self._refresh_gaps()
        return self.board

    def _refresh_gaps(self) -> None:
        missing = sorted(self.expected_shard_ids - self.received_shard_ids)
        self.board.gaps = [f"missing_result:{shard_id}" for shard_id in missing]
        self.board._refresh_status()


def execute_coding_hand_16_session_runtime(
    spec: GlobalSpec,
    a_path_groups: list[list[str]],
    b_path_groups: list[list[str]],
    *,
    binder: OpenClawSessionBinder,
    parent_label: str = "coding-hand-parent",
    a_results: list[WorkResult] | None = None,
    b_results: list[WorkResult] | None = None,
) -> dict[str, Any]:
    """Execute Step 1+2 runtime wiring for Coding Hand 16-session topology.

    This runs real spawn/delete through the injected binder for both
    A-small-parent (8) and B-small-parent (8) branches.
    """
    orchestrator = CodingHand16SessionOrchestrator(parent_label=parent_label)
    spec = SpecManager.validate_or_raise(spec)
    a_state = orchestrator._build_branch("A", "analysis", orchestrator.a_lifecycle, spec, a_path_groups, a_results or [])
    b_state = orchestrator._build_branch("B", "implementation", orchestrator.b_lifecycle, spec, b_path_groups, b_results or [])

    a_spawned = binder.execute_spawn_plans(a_state.spawn_plans, orchestrator.a_lifecycle)
    b_spawned = binder.execute_spawn_plans(b_state.spawn_plans, orchestrator.b_lifecycle)

    a_cleanup = binder.execute_delete_plans(
        Dispatcher(orchestrator.a_lifecycle).build_openclaw_delete_plans([s.shard_id for s in a_state.shards]),
        orchestrator.a_lifecycle,
    ) if binder.delete_fn is not None else []
    b_cleanup = binder.execute_delete_plans(
        Dispatcher(orchestrator.b_lifecycle).build_openclaw_delete_plans([s.shard_id for s in b_state.shards]),
        orchestrator.b_lifecycle,
    ) if binder.delete_fn is not None else []

    return {
        "coding_hand": {
            "parent_label": parent_label,
            "spec": spec.to_dict(),
            "A_small_parent": a_state.to_dict(),
            "B_small_parent": b_state.to_dict(),
            "comparison": orchestrator._compare_branches(a_state, b_state),
            "runtime": {
                "A_spawned": a_spawned,
                "B_spawned": b_spawned,
                "A_cleanup": a_cleanup,
                "B_cleanup": b_cleanup,
                "A_sessions": orchestrator.a_lifecycle.snapshot(),
                "B_sessions": orchestrator.b_lifecycle.snapshot(),
            },
        }
    }


def build_step2_parent_state(
    spec: GlobalSpec,
    phase: Phase,
    path_groups: list[list[str]],
    *,
    parent_label: str = "coding-b-parent",
) -> dict[str, Any]:
    """Convenience helper for the Step 2 parent flow.

    Returns a fully inspectable state bundle:
    - normalized spec
    - planned shards (up to 8)
    - planned ephemeral child sessions
    - empty collector/merge-board snapshot
    """
    planner = ShardPlanner(max_children=8)
    shards = planner.plan_from_path_groups(spec, phase, path_groups)
    lifecycle = SessionLifecycleManager(parent_label=parent_label)
    sessions = lifecycle.plan_sessions(shards)
    collector = ResultCollector(phase, shards)
    return {
        "spec": SpecManager.validate_or_raise(spec).to_dict(),
        "shards": [s.to_dict() for s in shards],
        "sessions": [s.to_dict() for s in sessions],
        "merge_board": collector.finalize().to_dict(),
    }


def build_coding_hand_16_session_state(
    spec: GlobalSpec,
    a_path_groups: list[list[str]],
    b_path_groups: list[list[str]],
    *,
    parent_label: str = "coding-hand-parent",
    a_results: list[WorkResult] | None = None,
    b_results: list[WorkResult] | None = None,
) -> dict[str, Any]:
    orchestrator = CodingHand16SessionOrchestrator(parent_label=parent_label)
    return orchestrator.build(
        spec,
        a_path_groups,
        b_path_groups,
        a_results=a_results,
        b_results=b_results,
    )


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        norm = " ".join(str(item).split()).strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def _normalize_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        raw = str(path).strip().replace("\\", "/")
        if not raw:
            continue
        norm = str(PurePosixPath(raw))
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


class FixPlanner:
    """Build fix-phase shards from a merge board and prior shards/results."""

    def __init__(self, max_children: int = 8):
        self.max_children = max_children

    def plan(
        self,
        spec: GlobalSpec,
        prior_shards: list[WorkShard],
        prior_board: MergeBoard,
        *,
        shard_prefix: str = "fix",
    ) -> list[WorkShard]:
        if not prior_board.conflicts and not prior_board.gaps:
            return []

        shard_map = {s.shard_id: s for s in prior_shards}
        path_to_issues: dict[str, list[str]] = {}

        for conflict in prior_board.conflicts:
            if conflict.startswith("boundary_violation:"):
                path = conflict.split(":", 1)[1]
                path_to_issues.setdefault(path, []).append(conflict)

        for gap in prior_board.gaps:
            if gap.startswith("missing_result:"):
                shard_id = gap.split(":", 1)[1]
                shard = shard_map.get(shard_id)
                if shard:
                    for path in shard.owned_paths:
                        path_to_issues.setdefault(path, []).append(gap)

        if not path_to_issues:
            return []

        grouped_paths = self._group_paths(path_to_issues)
        planner = ShardPlanner(max_children=self.max_children)
        fix_shards = planner.plan_from_path_groups(spec, "fix", grouped_paths, shard_prefix=shard_prefix)
        for shard in fix_shards:
            shard.metadata["source"] = "FixPlanner"
            shard.metadata["issues"] = [
                issue
                for path in shard.owned_paths
                for issue in path_to_issues.get(path, [])
            ]
        return fix_shards

    def _group_paths(self, path_to_issues: dict[str, list[str]]) -> list[list[str]]:
        paths = sorted(path_to_issues)
        buckets: dict[str, list[str]] = {}
        for path in paths:
            parent = str(PurePosixPath(path).parent)
            buckets.setdefault(parent, []).append(path)
        groups = sorted(buckets.values(), key=lambda g: (-len(g), g[0]))
        return groups[: self.max_children]


class IntegrationJudge:
    """Judge whether a phase can advance, requires fixes, or is blocked."""

    def judge(self, board: MergeBoard) -> dict[str, Any]:
        if board.conflicts:
            return {
                "decision": "needs_fix",
                "reason": "conflicts_present",
                "conflicts": list(board.conflicts),
                "gaps": list(board.gaps),
            }
        if board.gaps:
            return {
                "decision": "await_results",
                "reason": "gaps_present",
                "conflicts": list(board.conflicts),
                "gaps": list(board.gaps),
            }
        return {
            "decision": "advance",
            "reason": "board_ready",
            "conflicts": [],
            "gaps": [],
        }


class Dispatcher:
    """Tool-agnostic dispatcher plan for parent-managed child sessions.

    Step 3 keeps dispatch planning local and inspectable; OpenClaw session
    actions are emitted as artifacts and can be executed by a runtime binder.
    """

    def __init__(self, lifecycle: SessionLifecycleManager):
        self.lifecycle = lifecycle

    def build_dispatch_packets(self, shards: list[WorkShard]) -> list[dict[str, Any]]:
        packets: list[dict[str, Any]] = []
        for shard in shards:
            rec = self.lifecycle.get(shard.shard_id)
            packets.append({
                "shard_id": shard.shard_id,
                "session_label": rec.session_label if rec else None,
                "phase": shard.phase,
                "packet": shard.to_dict(),
            })
        return packets

    def build_openclaw_spawn_plans(self, shards: list[WorkShard]) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for shard in shards:
            rec = self.lifecycle.get(shard.shard_id)
            plans.append(SessionActionPlan(
                action="spawn",
                shard_id=shard.shard_id,
                label=rec.session_label if rec else None,
                payload={
                    "task": self._make_child_task(shard),
                    "label": rec.session_label if rec else None,
                    "runtime": "subagent",
                    "mode": "run",
                    "cleanup": "delete",
                    "sandbox": "inherit",
                },
            ).to_dict())
        return plans

    def build_openclaw_send_plans(self, results: list[WorkResult]) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for result in results:
            rec = self.lifecycle.get(result.shard_id)
            if not rec or not rec.session_key:
                continue
            plans.append(SessionActionPlan(
                action="send",
                shard_id=result.shard_id,
                session_key=rec.session_key,
                payload={
                    "message": result.summary or f"phase={result.phase} status={result.status}",
                },
            ).to_dict())
        return plans

    def build_openclaw_delete_plans(self, shard_ids: list[str]) -> list[dict[str, Any]]:
        plans: list[dict[str, Any]] = []
        for shard_id in shard_ids:
            rec = self.lifecycle.get(shard_id)
            plans.append(SessionActionPlan(
                action="delete",
                shard_id=shard_id,
                session_key=rec.session_key if rec else None,
                label=rec.session_label if rec else None,
                payload={},
            ).to_dict())
        return plans

    def mark_spawned(self, session_map: dict[str, str]) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for shard_id, session_key in session_map.items():
            updated.append(self.lifecycle.mark_spawned(shard_id, session_key).to_dict())
        return updated

    def complete_and_delete(self, shard_ids: list[str]) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for shard_id in shard_ids:
            self.lifecycle.mark_completed(shard_id)
            updated.append(self.lifecycle.mark_deleted(shard_id).to_dict())
        return updated

    def _make_child_task(self, shard: WorkShard) -> str:
        return (
            f"Shard {shard.shard_id} ({shard.phase})\n"
            f"Goal: {shard.goal}\n"
            f"Owned paths: {', '.join(shard.owned_paths)}\n"
            f"Forbidden paths: {', '.join(shard.forbidden_paths)}\n"
            f"Input contracts: {'; '.join(shard.input_contracts)}\n"
            f"Output contracts: {'; '.join(shard.output_contracts)}\n"
            f"Local done criteria: {'; '.join(shard.local_done_criteria)}"
        )


@dataclass(slots=True)
class CodingBranchState:
    """One small-parent branch inside Coding Hand (A or B)."""

    branch: Literal["A", "B"]
    role: str
    shards: list[WorkShard] = field(default_factory=list)
    dispatch: list[dict[str, Any]] = field(default_factory=list)
    spawn_plans: list[dict[str, Any]] = field(default_factory=list)
    merge_board: dict[str, Any] = field(default_factory=dict)
    sessions: list[dict[str, Any]] = field(default_factory=list)
    decision: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "role": self.role,
            "shards": [s.to_dict() for s in self.shards],
            "dispatch": list(self.dispatch),
            "spawn_plans": list(self.spawn_plans),
            "merge_board": dict(self.merge_board),
            "sessions": list(self.sessions),
            "decision": dict(self.decision),
        }


class OpenClawSessionBinder:
    """Runtime binder that executes session action plans via injected callables.

    The binder is intentionally dependency-inverted so ViszBot/OpenClaw runtime
    can provide the actual tool-backed functions.
    """

    def __init__(self, *, spawn_fn: Any, send_fn: Any | None = None, delete_fn: Any | None = None):
        self.spawn_fn = spawn_fn
        self.send_fn = send_fn
        self.delete_fn = delete_fn

    def execute_spawn_plans(
        self,
        plans: list[dict[str, Any]],
        lifecycle: SessionLifecycleManager,
    ) -> list[dict[str, Any]]:
        executed: list[dict[str, Any]] = []
        for plan in plans:
            payload = dict(plan.get("payload") or {})
            result = self.spawn_fn(**payload)
            session_key = self._extract_session_key(result)
            if session_key:
                lifecycle.mark_spawned(plan["shard_id"], session_key)
            executed.append({
                "plan": dict(plan),
                "result": result,
                "session_key": session_key,
            })
        return executed

    def execute_send_plans(self, plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if self.send_fn is None:
            raise RuntimeError("send_fn_missing")
        executed: list[dict[str, Any]] = []
        for plan in plans:
            payload = dict(plan.get("payload") or {})
            result = self.send_fn(sessionKey=plan.get("session_key"), **payload)
            executed.append({"plan": dict(plan), "result": result})
        return executed

    def execute_delete_plans(
        self,
        plans: list[dict[str, Any]],
        lifecycle: SessionLifecycleManager,
    ) -> list[dict[str, Any]]:
        if self.delete_fn is None:
            raise RuntimeError("delete_fn_missing")
        executed: list[dict[str, Any]] = []
        for plan in plans:
            result = self.delete_fn(sessionKey=plan.get("session_key"), label=plan.get("label"))
            lifecycle.mark_deleted(plan["shard_id"])
            executed.append({"plan": dict(plan), "result": result})
        return executed

    @staticmethod
    def _extract_session_key(result: Any) -> str | None:
        if isinstance(result, dict):
            return result.get("sessionKey") or result.get("session_key") or result.get("key")
        return None


class CodingHand16SessionOrchestrator:
    """Coding Hand parent with A/B small-parents and 8+8 child sessions.

    A = analysis-oriented branch (8 children)
    B = implementation-oriented branch (8 children)
    """

    def __init__(self, parent_label: str = "coding-hand-parent"):
        self.parent_label = parent_label
        self.a_lifecycle = SessionLifecycleManager(parent_label=f"{parent_label}:A")
        self.b_lifecycle = SessionLifecycleManager(parent_label=f"{parent_label}:B")
        self.planner = ShardPlanner(max_children=8)
        self.judge = IntegrationJudge()

    def build(
        self,
        spec: GlobalSpec,
        a_path_groups: list[list[str]],
        b_path_groups: list[list[str]],
        *,
        a_results: list[WorkResult] | None = None,
        b_results: list[WorkResult] | None = None,
    ) -> dict[str, Any]:
        spec = SpecManager.validate_or_raise(spec)
        a_state = self._build_branch("A", "analysis", self.a_lifecycle, spec, a_path_groups, a_results or [])
        b_state = self._build_branch("B", "implementation", self.b_lifecycle, spec, b_path_groups, b_results or [])
        return {
            "coding_hand": {
                "parent_label": self.parent_label,
                "topology": {
                    "parent": 1,
                    "small_parents": 2,
                    "child_sessions": 16,
                    "branch_children": {"A": 8, "B": 8},
                },
                "spec": spec.to_dict(),
                "A_small_parent": a_state.to_dict(),
                "B_small_parent": b_state.to_dict(),
                "comparison": self._compare_branches(a_state, b_state),
            }
        }

    def _build_branch(
        self,
        branch: Literal["A", "B"],
        role: str,
        lifecycle: SessionLifecycleManager,
        spec: GlobalSpec,
        path_groups: list[list[str]],
        results: list[WorkResult],
    ) -> CodingBranchState:
        phase: Phase = "implement"
        shard_prefix = f"coding-{branch.lower()}"
        shards = self.planner.plan_from_path_groups(spec, phase, path_groups, shard_prefix=shard_prefix)
        if len(shards) != 8:
            raise ValueError(f"coding_{branch.lower()}_requires_exactly_8_shards:{len(shards)}")
        lifecycle.plan_sessions(shards)
        dispatcher = Dispatcher(lifecycle)
        dispatch = dispatcher.build_dispatch_packets(shards)
        spawn_plans = dispatcher.build_openclaw_spawn_plans(shards)
        collector = ResultCollector(phase, shards)
        for result in results:
            collector.collect(result)
        board = collector.finalize()
        decision = self.judge.judge(board)
        branch_sessions = [rec for rec in lifecycle.snapshot() if rec.get("shard_id", "").startswith(shard_prefix)]
        return CodingBranchState(
            branch=branch,
            role=role,
            shards=shards,
            dispatch=dispatch,
            spawn_plans=spawn_plans,
            merge_board=board.to_dict(),
            sessions=branch_sessions,
            decision=decision,
        )

    def _compare_branches(self, a_state: CodingBranchState, b_state: CodingBranchState) -> dict[str, Any]:
        a_paths = sorted({path for shard in a_state.shards for path in shard.owned_paths})
        b_paths = sorted({path for shard in b_state.shards for path in shard.owned_paths})
        return {
            "a_branch": a_state.role,
            "b_branch": b_state.role,
            "a_ready": a_state.merge_board.get("ready_for_next_phase", False),
            "b_ready": b_state.merge_board.get("ready_for_next_phase", False),
            "a_only_paths": sorted(set(a_paths) - set(b_paths)),
            "b_only_paths": sorted(set(b_paths) - set(a_paths)),
            "shared_paths": sorted(set(a_paths) & set(b_paths)),
            "a_decision": dict(a_state.decision),
            "b_decision": dict(b_state.decision),
        }


def build_step3_closed_loop(
    spec: GlobalSpec,
    implement_path_groups: list[list[str]],
    implement_results: list[WorkResult],
    *,
    parent_label: str = "coding-b-parent",
) -> dict[str, Any]:
    """Build a full inspectable implement→fix→test closed-loop plan.

    This does not execute sessions. It materializes the orchestration state,
    dispatch packets, judgments, and cleanup plan for ephemeral sessions.
    """
    planner = ShardPlanner(max_children=8)
    lifecycle = SessionLifecycleManager(parent_label=parent_label)
    judge = IntegrationJudge()

    implement_shards = planner.plan_from_path_groups(spec, "implement", implement_path_groups, shard_prefix="implement")
    lifecycle.plan_sessions(implement_shards)
    implement_dispatcher = Dispatcher(lifecycle)
    implement_dispatch = implement_dispatcher.build_dispatch_packets(implement_shards)
    implement_spawn_plans = implement_dispatcher.build_openclaw_spawn_plans(implement_shards)

    implement_collector = ResultCollector("implement", implement_shards)
    for result in implement_results:
        implement_collector.collect(result)
    implement_board = implement_collector.finalize()
    implement_decision = judge.judge(implement_board)

    fix_shards: list[WorkShard] = []
    fix_dispatch: list[dict[str, Any]] = []
    fix_board = build_empty_merge_board("fix", metadata={"collector": "ResultCollector"})
    if implement_decision["decision"] == "needs_fix":
        fix_planner = FixPlanner(max_children=8)
        fix_shards = fix_planner.plan(spec, implement_shards, implement_board, shard_prefix="fix")
        lifecycle.plan_sessions(fix_shards)
        fix_dispatch = implement_dispatcher.build_dispatch_packets(fix_shards)
        fix_spawn_plans = implement_dispatcher.build_openclaw_spawn_plans(fix_shards)
        fix_board = build_empty_merge_board("fix", metadata={"planned": True})
    else:
        fix_spawn_plans = []

    test_path_groups = [shard.owned_paths for shard in (fix_shards or implement_shards)]
    test_shards = planner.plan_from_path_groups(spec, "test", test_path_groups, shard_prefix="test")
    lifecycle.plan_sessions(test_shards)
    test_dispatch = implement_dispatcher.build_dispatch_packets(test_shards)
    test_spawn_plans = implement_dispatcher.build_openclaw_spawn_plans(test_shards)
    test_board = build_empty_merge_board("test", metadata={"planned": True})

    return {
        "spec": SpecManager.validate_or_raise(spec).to_dict(),
        "implement": {
            "shards": [s.to_dict() for s in implement_shards],
            "dispatch": implement_dispatch,
            "spawn_plans": implement_spawn_plans,
            "merge_board": implement_board.to_dict(),
            "decision": implement_decision,
        },
        "fix": {
            "shards": [s.to_dict() for s in fix_shards],
            "dispatch": fix_dispatch,
            "spawn_plans": fix_spawn_plans,
            "merge_board": fix_board.to_dict(),
        },
        "test": {
            "shards": [s.to_dict() for s in test_shards],
            "dispatch": test_dispatch,
            "spawn_plans": test_spawn_plans,
            "merge_board": test_board.to_dict(),
        },
        "cleanup_plans": implement_dispatcher.build_openclaw_delete_plans([s.shard_id for s in implement_shards + fix_shards + test_shards]),
        "sessions": lifecycle.snapshot(),
    }
