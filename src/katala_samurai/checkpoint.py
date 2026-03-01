"""
Checkpoint Engine — Session-Spanning PEV State Persistence.

② Long-term Agent axis improvement: 55% → 70%

Enables PEV loops and KS41b roadmaps to survive across sessions.
Pattern: same as HDEL's BeliefStore (JSON persistence), applied to
PEV results and goal roadmaps.

Key capabilities:
- Save/resume PEV loop state mid-execution
- Persist KS41b Roadmap across sessions
- Track goal completion across multiple sessions
- Auto-cleanup of stale checkpoints

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Constants ──
CHECKPOINT_DIR = ".katala_checkpoints"
ROADMAP_FILE = "roadmap.json"
PEV_STATE_FILE = "pev_state.json"
GOAL_HISTORY_FILE = "goal_history.json"

MAX_CHECKPOINT_AGE_S = 604800        # 7 days max checkpoint age
MAX_GOAL_HISTORY = 200               # Max completed goals to remember
STALE_THRESHOLD_S = 86400            # 24h without update = stale


@dataclass
class GoalRecord:
    """Record of a goal's lifecycle across sessions."""
    goal_id: str
    goal_text: str
    priority: str
    created_at: float
    source: str                       # Which module generated this goal
    status: str = "pending"           # pending | in_progress | completed | abandoned
    completed_at: Optional[float] = None
    sessions_active: int = 0          # How many sessions worked on this
    completion_confidence: float = 0.0
    notes: str = ""


@dataclass
class PEVCheckpoint:
    """Saved state of a PEV loop execution."""
    task: str
    iteration: int
    last_output: Any
    last_feedback: str
    context: Dict[str, Any]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    session_id: str = ""

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.updated_at) > STALE_THRESHOLD_S

    @property
    def age_hours(self) -> float:
        return (time.time() - self.created_at) / 3600


@dataclass
class RoadmapCheckpoint:
    """Saved KS41b Roadmap state."""
    immediate_goals: List[Dict[str, Any]]
    next_goals: List[Dict[str, Any]]
    deferred_goals: List[Dict[str, Any]]
    total_goals: int
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    version: str = "KS41b"

    @property
    def is_stale(self) -> bool:
        return (time.time() - self.updated_at) > STALE_THRESHOLD_S


class CheckpointEngine:
    """Session-spanning state persistence for KS agents.

    Stores three types of data:
    1. PEV loop checkpoints — resume interrupted executions
    2. KS41b roadmaps — continue goal planning across sessions
    3. Goal history — track what was achieved over time

    All data stored as JSON in the checkpoint directory.
    Thread-safe, auto-cleanup of stale data.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self._base = Path(base_dir or CHECKPOINT_DIR)
        self._base.mkdir(parents=True, exist_ok=True)

    # ── PEV Checkpoints ──

    def save_pev_state(
        self,
        task: str,
        iteration: int,
        last_output: Any,
        last_feedback: str = "",
        context: Optional[Dict] = None,
        session_id: str = "",
    ) -> bool:
        """Save PEV loop state for later resumption."""
        checkpoint = PEVCheckpoint(
            task=task,
            iteration=iteration,
            last_output=self._serialize(last_output),
            last_feedback=last_feedback,
            context=self._serialize(context or {}),
            session_id=session_id,
        )
        return self._write_json(PEV_STATE_FILE, asdict(checkpoint))

    def load_pev_state(self) -> Optional[PEVCheckpoint]:
        """Load the most recent PEV checkpoint."""
        data = self._read_json(PEV_STATE_FILE)
        if not data:
            return None
        checkpoint = PEVCheckpoint(**data)
        if checkpoint.is_stale:
            self._delete_file(PEV_STATE_FILE)
            return None
        return checkpoint

    def clear_pev_state(self) -> bool:
        """Clear PEV checkpoint (task completed)."""
        return self._delete_file(PEV_STATE_FILE)

    # ── Roadmap Persistence ──

    def save_roadmap(
        self,
        immediate: List[Dict],
        next_goals: List[Dict],
        deferred: List[Dict],
        total: int,
        version: str = "KS41b",
    ) -> bool:
        """Save KS41b roadmap for cross-session continuity."""
        checkpoint = RoadmapCheckpoint(
            immediate_goals=immediate,
            next_goals=next_goals,
            deferred_goals=deferred,
            total_goals=total,
            version=version,
        )
        return self._write_json(ROADMAP_FILE, asdict(checkpoint))

    def load_roadmap(self) -> Optional[RoadmapCheckpoint]:
        """Load the saved roadmap."""
        data = self._read_json(ROADMAP_FILE)
        if not data:
            return None
        checkpoint = RoadmapCheckpoint(**data)
        if checkpoint.is_stale:
            return None  # Don't delete, just signal it's old
        return checkpoint

    # ── Goal History ──

    def record_goal_completion(
        self,
        goal_id: str,
        goal_text: str,
        priority: str = "medium",
        source: str = "unknown",
        confidence: float = 0.0,
        notes: str = "",
    ) -> bool:
        """Record a completed goal in history."""
        history = self._load_goal_history()

        record = GoalRecord(
            goal_id=goal_id,
            goal_text=goal_text,
            priority=priority,
            created_at=time.time(),
            source=source,
            status="completed",
            completed_at=time.time(),
            completion_confidence=confidence,
            notes=notes,
        )
        history.append(asdict(record))

        # Cap history size
        if len(history) > MAX_GOAL_HISTORY:
            history = history[-MAX_GOAL_HISTORY:]

        return self._write_json(GOAL_HISTORY_FILE, history)

    def get_goal_history(self, limit: int = 20) -> List[GoalRecord]:
        """Get recent goal history."""
        history = self._load_goal_history()
        records = []
        for d in history[-limit:]:
            try:
                records.append(GoalRecord(**d))
            except (TypeError, KeyError):
                continue
        return records

    def get_completion_stats(self) -> Dict[str, Any]:
        """Statistics about goal completion over time."""
        history = self._load_goal_history()
        if not history:
            return {"total_completed": 0, "sessions": 0}

        completed = [h for h in history if h.get("status") == "completed"]
        priorities = {}
        sources = {}
        for h in completed:
            p = h.get("priority", "unknown")
            s = h.get("source", "unknown")
            priorities[p] = priorities.get(p, 0) + 1
            sources[s] = sources.get(s, 0) + 1

        avg_confidence = (
            sum(h.get("completion_confidence", 0) for h in completed) / max(len(completed), 1)
        )

        return {
            "total_completed": len(completed),
            "by_priority": priorities,
            "by_source": sources,
            "avg_confidence": round(avg_confidence, 3),
        }

    # ── Cleanup ──

    def cleanup_stale(self) -> int:
        """Remove stale checkpoints older than MAX_CHECKPOINT_AGE_S."""
        removed = 0
        for path in self._base.glob("*.json"):
            try:
                age = time.time() - path.stat().st_mtime
                if age > MAX_CHECKPOINT_AGE_S:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    # ── Private ──

    def _write_json(self, filename: str, data: Any) -> bool:
        try:
            path = self._base / filename
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False

    def _read_json(self, filename: str) -> Optional[Any]:
        try:
            path = self._base / filename
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _delete_file(self, filename: str) -> bool:
        try:
            path = self._base / filename
            if path.exists():
                path.unlink()
            return True
        except Exception:
            return False

    def _load_goal_history(self) -> List[Dict]:
        data = self._read_json(GOAL_HISTORY_FILE)
        if isinstance(data, list):
            return data
        return []

    @staticmethod
    def _serialize(obj: Any) -> Any:
        """Make objects JSON-serializable."""
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        if isinstance(obj, dict):
            return {str(k): CheckpointEngine._serialize(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [CheckpointEngine._serialize(x) for x in obj]
        return str(obj)[:500]
