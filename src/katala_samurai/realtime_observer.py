"""
Realtime Observer — Continuous Environment Monitoring Engine.

Targets: Interactive Environment 78%→88% (component 1/3)

Bridges the gap between "record what happened" (EnvironmentStateModel)
and "detect what's happening now" (this module).

Architecture:
    Watchers (file/process/git/custom)
        ↓
    Change Detection (diff-based)
        ↓
    Event Stream (typed, timestamped)
        ↓
    Subscribers (HTN replanner, HDEL belief updater, etc.)

Design philosophy: Poll-based (no OS-specific watchers),
portable, zero external dependencies.

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from collections import deque
from pathlib import Path

# ── Constants ──
POLL_INTERVAL_S = 2.0            # Default poll interval
MAX_EVENTS = 1000                # Max events in buffer
MAX_WATCHERS = 50                # Max concurrent watchers
FILE_HASH_CHUNK = 8192           # Bytes to read for file hashing
CHANGE_DEBOUNCE_S = 0.5          # Debounce rapid changes


class EventType(Enum):
    FILE_MODIFIED = "file_modified"
    FILE_CREATED = "file_created"
    FILE_DELETED = "file_deleted"
    PROCESS_STARTED = "process_started"
    PROCESS_ENDED = "process_ended"
    GIT_COMMIT = "git_commit"
    GIT_BRANCH_CHANGE = "git_branch_change"
    TEST_PASS = "test_pass"
    TEST_FAIL = "test_fail"
    CUSTOM = "custom"
    ENV_VAR_CHANGE = "env_var_change"
    METRIC_THRESHOLD = "metric_threshold"


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class EnvironmentEvent:
    """A detected environment change."""
    event_id: str
    event_type: EventType
    source: str              # What watcher detected this
    description: str
    data: Dict[str, Any] = field(default_factory=dict)
    severity: Severity = Severity.INFO
    timestamp: float = field(default_factory=time.time)

    @property
    def is_critical(self) -> bool:
        return self.severity == Severity.CRITICAL


@dataclass
class WatchTarget:
    """A target being monitored."""
    target_id: str
    target_type: str         # "file" | "directory" | "process" | "git" | "metric" | "custom"
    path_or_key: str
    last_state: Any = None
    last_check: float = 0.0
    poll_interval: float = POLL_INTERVAL_S
    change_count: int = 0


# ════════════════════════════════════════════════
# Watchers
# ════════════════════════════════════════════════

class FileWatcher:
    """Watch files/directories for changes."""

    @staticmethod
    def check(target: WatchTarget) -> List[EnvironmentEvent]:
        events = []
        path = Path(target.path_or_key)

        if not path.exists():
            if target.last_state is not None:
                events.append(EnvironmentEvent(
                    event_id=f"evt_fdel_{target.change_count}",
                    event_type=EventType.FILE_DELETED,
                    source=f"file_watcher:{target.target_id}",
                    description=f"File deleted: {path}",
                    data={"path": str(path)},
                    severity=Severity.WARNING,
                ))
                target.last_state = None
                target.change_count += 1
            return events

        if path.is_file():
            current_hash = FileWatcher._hash_file(path)
            if target.last_state is None:
                events.append(EnvironmentEvent(
                    event_id=f"evt_fcre_{target.change_count}",
                    event_type=EventType.FILE_CREATED,
                    source=f"file_watcher:{target.target_id}",
                    description=f"File appeared: {path}",
                    data={"path": str(path), "size": path.stat().st_size},
                ))
                target.change_count += 1
            elif current_hash != target.last_state:
                events.append(EnvironmentEvent(
                    event_id=f"evt_fmod_{target.change_count}",
                    event_type=EventType.FILE_MODIFIED,
                    source=f"file_watcher:{target.target_id}",
                    description=f"File modified: {path}",
                    data={
                        "path": str(path),
                        "size": path.stat().st_size,
                        "old_hash": target.last_state[:8] if target.last_state else "",
                        "new_hash": current_hash[:8],
                    },
                ))
                target.change_count += 1
            target.last_state = current_hash

        elif path.is_dir():
            current_listing = set(str(p) for p in path.iterdir())
            if target.last_state is None:
                target.last_state = current_listing
            else:
                added = current_listing - target.last_state
                removed = target.last_state - current_listing
                for a in added:
                    events.append(EnvironmentEvent(
                        event_id=f"evt_fcre_{target.change_count}",
                        event_type=EventType.FILE_CREATED,
                        source=f"file_watcher:{target.target_id}",
                        description=f"New file: {a}",
                        data={"path": a},
                    ))
                    target.change_count += 1
                for r in removed:
                    events.append(EnvironmentEvent(
                        event_id=f"evt_fdel_{target.change_count}",
                        event_type=EventType.FILE_DELETED,
                        source=f"file_watcher:{target.target_id}",
                        description=f"File removed: {r}",
                        data={"path": r},
                        severity=Severity.WARNING,
                    ))
                    target.change_count += 1
                target.last_state = current_listing

        return events

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                chunk = f.read(FILE_HASH_CHUNK)
                h.update(chunk)
                # Also include mtime for speed
                h.update(str(path.stat().st_mtime_ns).encode())
        except (OSError, PermissionError):
            pass
        return h.hexdigest()


class GitWatcher:
    """Watch git repository for commits and branch changes."""

    @staticmethod
    def check(target: WatchTarget) -> List[EnvironmentEvent]:
        events = []
        repo_path = target.path_or_key

        try:
            # Current HEAD
            head = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            if head.returncode != 0:
                return events

            current_head = head.stdout.strip()

            # Current branch
            branch = subprocess.run(
                ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, timeout=5,
            )
            current_branch = branch.stdout.strip() if branch.returncode == 0 else "unknown"

            if target.last_state is None:
                target.last_state = {"head": current_head, "branch": current_branch}
                return events

            old = target.last_state
            if current_head != old.get("head"):
                # Get commit message
                msg = subprocess.run(
                    ["git", "-C", repo_path, "log", "-1", "--pretty=%s"],
                    capture_output=True, text=True, timeout=5,
                )
                commit_msg = msg.stdout.strip() if msg.returncode == 0 else ""
                events.append(EnvironmentEvent(
                    event_id=f"evt_git_{target.change_count}",
                    event_type=EventType.GIT_COMMIT,
                    source=f"git_watcher:{target.target_id}",
                    description=f"New commit: {current_head[:8]} — {commit_msg}",
                    data={
                        "old_head": old["head"][:8],
                        "new_head": current_head[:8],
                        "message": commit_msg,
                        "branch": current_branch,
                    },
                ))
                target.change_count += 1

            if current_branch != old.get("branch"):
                events.append(EnvironmentEvent(
                    event_id=f"evt_gitb_{target.change_count}",
                    event_type=EventType.GIT_BRANCH_CHANGE,
                    source=f"git_watcher:{target.target_id}",
                    description=f"Branch changed: {old['branch']} → {current_branch}",
                    data={"old_branch": old["branch"], "new_branch": current_branch},
                    severity=Severity.WARNING,
                ))
                target.change_count += 1

            target.last_state = {"head": current_head, "branch": current_branch}

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        return events


class MetricWatcher:
    """Watch numeric metrics for threshold crossings."""

    def __init__(self):
        self._metric_fns: Dict[str, Callable[[], float]] = {}

    def register_metric(self, name: str, fn: Callable[[], float]) -> None:
        self._metric_fns[name] = fn

    def check(self, target: WatchTarget) -> List[EnvironmentEvent]:
        events = []
        metric_name = target.path_or_key
        fn = self._metric_fns.get(metric_name)
        if not fn:
            return events

        try:
            value = fn()
        except Exception:
            return events

        threshold = target.last_state or {}
        upper = threshold.get("upper")
        lower = threshold.get("lower")

        if upper is not None and value > upper:
            events.append(EnvironmentEvent(
                event_id=f"evt_met_{target.change_count}",
                event_type=EventType.METRIC_THRESHOLD,
                source=f"metric_watcher:{target.target_id}",
                description=f"Metric {metric_name} crossed upper threshold: {value} > {upper}",
                data={"metric": metric_name, "value": value, "threshold": upper, "direction": "above"},
                severity=Severity.WARNING,
            ))
            target.change_count += 1

        if lower is not None and value < lower:
            events.append(EnvironmentEvent(
                event_id=f"evt_met_{target.change_count}",
                event_type=EventType.METRIC_THRESHOLD,
                source=f"metric_watcher:{target.target_id}",
                description=f"Metric {metric_name} crossed lower threshold: {value} < {lower}",
                data={"metric": metric_name, "value": value, "threshold": lower, "direction": "below"},
                severity=Severity.WARNING,
            ))
            target.change_count += 1

        return events


# ════════════════════════════════════════════════
# Observer Engine
# ════════════════════════════════════════════════

class RealtimeObserver:
    """Continuous environment monitoring with typed event streams.

    Usage:
    ```python
    observer = RealtimeObserver()
    observer.watch_file("/path/to/important.py")
    observer.watch_git("/path/to/repo")
    observer.subscribe(my_handler)  # EnvironmentEvent → None

    # Poll loop (or call once per PEV iteration)
    events = observer.poll()
    ```
    """

    def __init__(self):
        self._targets: Dict[str, WatchTarget] = {}
        self._file_watcher = FileWatcher()
        self._git_watcher = GitWatcher()
        self._metric_watcher = MetricWatcher()
        self._events: deque = deque(maxlen=MAX_EVENTS)
        self._subscribers: List[Callable[[EnvironmentEvent], None]] = []
        self._target_counter = 0

    # ── Watch Registration ──

    def watch_file(self, path: str, interval: float = POLL_INTERVAL_S) -> str:
        tid = self._new_id("file")
        self._targets[tid] = WatchTarget(
            target_id=tid, target_type="file",
            path_or_key=path, poll_interval=interval,
        )
        return tid

    def watch_directory(self, path: str, interval: float = POLL_INTERVAL_S) -> str:
        tid = self._new_id("dir")
        self._targets[tid] = WatchTarget(
            target_id=tid, target_type="directory",
            path_or_key=path, poll_interval=interval,
        )
        return tid

    def watch_git(self, repo_path: str, interval: float = 5.0) -> str:
        tid = self._new_id("git")
        self._targets[tid] = WatchTarget(
            target_id=tid, target_type="git",
            path_or_key=repo_path, poll_interval=interval,
        )
        return tid

    def watch_metric(
        self, name: str, fn: Callable[[], float],
        upper: Optional[float] = None, lower: Optional[float] = None,
        interval: float = 10.0,
    ) -> str:
        self._metric_watcher.register_metric(name, fn)
        tid = self._new_id("metric")
        self._targets[tid] = WatchTarget(
            target_id=tid, target_type="metric",
            path_or_key=name,
            last_state={"upper": upper, "lower": lower},
            poll_interval=interval,
        )
        return tid

    def unwatch(self, target_id: str) -> bool:
        return self._targets.pop(target_id, None) is not None

    # ── Subscription ──

    def subscribe(self, handler: Callable[[EnvironmentEvent], None]) -> None:
        self._subscribers.append(handler)

    # ── Polling ──

    def poll(self) -> List[EnvironmentEvent]:
        """Check all watchers and return new events."""
        now = time.time()
        new_events = []

        for target in list(self._targets.values()):
            if now - target.last_check < target.poll_interval:
                continue
            target.last_check = now

            events = []
            if target.target_type in ("file", "directory"):
                events = FileWatcher.check(target)
            elif target.target_type == "git":
                events = GitWatcher.check(target)
            elif target.target_type == "metric":
                events = self._metric_watcher.check(target)

            for event in events:
                self._events.append(event)
                new_events.append(event)
                # Notify subscribers
                for handler in self._subscribers:
                    try:
                        handler(event)
                    except Exception:
                        pass

        return new_events

    # ── Query ──

    def get_recent_events(self, limit: int = 20, event_type: Optional[EventType] = None) -> List[EnvironmentEvent]:
        events = list(self._events)
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def get_critical_events(self, since: Optional[float] = None) -> List[EnvironmentEvent]:
        events = [e for e in self._events if e.is_critical]
        if since:
            events = [e for e in events if e.timestamp >= since]
        return events

    def get_stats(self) -> Dict[str, Any]:
        return {
            "watchers": len(self._targets),
            "total_events": len(self._events),
            "subscribers": len(self._subscribers),
            "watcher_types": {
                t: sum(1 for w in self._targets.values() if w.target_type == t)
                for t in set(w.target_type for w in self._targets.values())
            },
        }

    # ── Private ──

    def _new_id(self, prefix: str) -> str:
        self._target_counter += 1
        return f"watch_{prefix}_{self._target_counter:04d}"
