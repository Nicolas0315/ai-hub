"""
Goal Emergence Engine — Environment-driven autonomous goal discovery.

Target: Goal Discovery 87% → 94%+ (25% of remaining gap)

What was missing:
  KS41a generates goals from structural analysis (static).
  KS41b plans them (ordering, dependencies).
  But NO module watches the *changing environment* to discover goals dynamically.

  Key difference:
  - KS41a: "What gaps exist in this claim?" (static analysis)
  - GoalEmergence: "What changed? What's now worth investigating?" (dynamic sensing)

Sources of emergent goals:
  E1: State Delta Detection — what changed between sessions
  E2: Anomaly-Triggered Goals — unusual patterns spawn investigation goals
  E3: Opportunity Detection — new capabilities enable previously impossible goals
  E4: Regression Detection — previously achieved goals that degraded

Philosophical basis:
  - Affordance theory (Gibson): goals emerge from environment possibilities
  - Exploration-exploitation (bandits): balance known improvements vs new territory
  - Youta: "Goal generation ≠ goal planning" — this is the third leg: goal DISCOVERY

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Constants ──
VERSION = "1.0.0"

# Detection thresholds
STATE_CHANGE_THRESHOLD = 0.1        # Minimum delta to trigger attention
ANOMALY_THRESHOLD = 2.0             # Standard deviations for anomaly detection
REGRESSION_THRESHOLD = 0.05         # Score drop to trigger regression goal
OPPORTUNITY_WINDOW = 5              # Look at last N state snapshots

# Goal generation
MAX_EMERGENT_GOALS = 10             # Cap per detection cycle
GOAL_COOLDOWN_S = 300               # Don't re-emit same goal within 5 min
NOVELTY_WEIGHT = 0.4                # How much novelty affects priority
URGENCY_WEIGHT = 0.3                # How much urgency affects priority
IMPACT_WEIGHT = 0.3                 # How much estimated impact affects priority

# Persistence
EMERGENCE_STATE_FILE = "goal_emergence_state.json"


class GoalSource(str):
    """Source type constants (using plain strings for cross-module compat)."""
    STATE_DELTA = "state_delta"
    ANOMALY = "anomaly"
    OPPORTUNITY = "opportunity"
    REGRESSION = "regression"


@dataclass
class StateSnapshot:
    """Point-in-time snapshot of system state."""
    timestamp: float
    metrics: Dict[str, float]        # metric_name → value
    capabilities: Set[str] = field(default_factory=set)  # Available capabilities
    active_goals: Set[str] = field(default_factory=set)   # Currently active goal IDs
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "metrics": self.metrics,
            "capabilities": list(self.capabilities),
            "active_goals": list(self.active_goals),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateSnapshot":
        return cls(
            timestamp=data.get("timestamp", 0),
            metrics=data.get("metrics", {}),
            capabilities=set(data.get("capabilities", [])),
            active_goals=set(data.get("active_goals", [])),
            session_id=data.get("session_id", ""),
        )


@dataclass
class EmergentGoal:
    """A goal that emerged from environment observation."""
    goal_id: str
    goal_text: str
    source: str               # GoalSource value
    priority: float           # 0.0 - 1.0
    novelty: float            # How novel this goal is (0-1)
    urgency: float            # How time-sensitive (0-1)
    estimated_impact: float   # Expected improvement (0-1)
    trigger: str              # What triggered this goal
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    expires_at: float = 0.0   # 0 = no expiry


class GoalEmergenceEngine:
    """
    Watches environment state changes and discovers new goals.

    Usage:
        engine = GoalEmergenceEngine()
        engine.record_snapshot(current_metrics, capabilities)
        goals = engine.detect_emergent_goals()
    """

    def __init__(self, checkpoint_dir: Optional[str] = None):
        self._checkpoint_dir = Path(checkpoint_dir or ".katala_checkpoints")
        self._snapshots: List[StateSnapshot] = []
        self._emitted_goals: Dict[str, float] = {}  # goal_hash → last_emit_time
        self._baseline_metrics: Dict[str, List[float]] = defaultdict(list)
        self._load_state()

    def record_snapshot(self, metrics: Dict[str, float],
                        capabilities: Optional[Set[str]] = None,
                        active_goals: Optional[Set[str]] = None) -> None:
        """Record a state snapshot for change detection."""
        snapshot = StateSnapshot(
            timestamp=time.time(),
            metrics=metrics,
            capabilities=capabilities or set(),
            active_goals=active_goals or set(),
            session_id=hashlib.md5(str(time.time()).encode()).hexdigest()[:8],
        )
        self._snapshots.append(snapshot)

        # Update baseline statistics
        for key, value in metrics.items():
            self._baseline_metrics[key].append(value)
            # Keep last 50 values for statistics
            if len(self._baseline_metrics[key]) > 50:
                self._baseline_metrics[key] = self._baseline_metrics[key][-50:]

        # Trim snapshot history
        if len(self._snapshots) > 100:
            self._snapshots = self._snapshots[-100:]

        self._save_state()

    def detect_emergent_goals(self) -> List[EmergentGoal]:
        """Run all detection engines and return emergent goals."""
        if len(self._snapshots) < 2:
            return []

        goals: List[EmergentGoal] = []
        now = time.time()

        # E1: State Delta Detection
        goals.extend(self._detect_state_deltas())

        # E2: Anomaly Detection
        goals.extend(self._detect_anomalies())

        # E3: Opportunity Detection
        goals.extend(self._detect_opportunities())

        # E4: Regression Detection
        goals.extend(self._detect_regressions())

        # Filter: cooldown + dedup + cap
        filtered = []
        for g in goals:
            g_hash = hashlib.md5(g.goal_text.encode()).hexdigest()[:12]
            last_emit = self._emitted_goals.get(g_hash, 0)
            if now - last_emit > GOAL_COOLDOWN_S:
                g.goal_id = f"emerge_{g_hash}"
                g.created_at = now
                self._emitted_goals[g_hash] = now
                filtered.append(g)

        # Sort by priority and cap
        filtered.sort(key=lambda g: g.priority, reverse=True)
        return filtered[:MAX_EMERGENT_GOALS]

    # ── E1: State Delta Detection ──

    def _detect_state_deltas(self) -> List[EmergentGoal]:
        """Detect significant changes between snapshots."""
        if len(self._snapshots) < 2:
            return []

        current = self._snapshots[-1]
        previous = self._snapshots[-2]
        goals = []

        for key in set(current.metrics) | set(previous.metrics):
            curr_val = current.metrics.get(key, 0)
            prev_val = previous.metrics.get(key, 0)

            if prev_val == 0:
                delta = curr_val
            else:
                delta = (curr_val - prev_val) / abs(prev_val) if prev_val != 0 else 0

            if abs(delta) >= STATE_CHANGE_THRESHOLD:
                direction = "improved" if delta > 0 else "degraded"
                urgency = min(abs(delta) * 2, 1.0)

                goals.append(EmergentGoal(
                    goal_id="",  # Set in filter
                    goal_text=f"Investigate {key} {direction}: {prev_val:.3f} → {curr_val:.3f} ({delta:+.1%})",
                    source=GoalSource.STATE_DELTA,
                    priority=self._compute_priority(
                        novelty=0.5,
                        urgency=urgency,
                        impact=min(abs(delta), 1.0),
                    ),
                    novelty=0.5,
                    urgency=urgency,
                    estimated_impact=min(abs(delta), 1.0),
                    trigger=f"{key}: {prev_val:.3f} → {curr_val:.3f}",
                ))

        return goals

    # ── E2: Anomaly Detection ──

    def _detect_anomalies(self) -> List[EmergentGoal]:
        """Detect anomalous metric values using z-score."""
        if len(self._snapshots) < 3:
            return []

        current = self._snapshots[-1]
        goals = []

        for key, value in current.metrics.items():
            history = self._baseline_metrics.get(key, [])
            if len(history) < 5:
                continue

            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std = variance ** 0.5

            if std == 0:
                continue

            z_score = abs(value - mean) / std

            if z_score >= ANOMALY_THRESHOLD:
                direction = "spike" if value > mean else "drop"
                goals.append(EmergentGoal(
                    goal_id="",
                    goal_text=f"Anomaly in {key}: {direction} to {value:.3f} (z={z_score:.1f}, mean={mean:.3f})",
                    source=GoalSource.ANOMALY,
                    priority=self._compute_priority(
                        novelty=0.8,
                        urgency=min(z_score / 5, 1.0),
                        impact=0.6,
                    ),
                    novelty=0.8,
                    urgency=min(z_score / 5, 1.0),
                    estimated_impact=0.6,
                    trigger=f"z-score={z_score:.2f}",
                ))

        return goals

    # ── E3: Opportunity Detection ──

    def _detect_opportunities(self) -> List[EmergentGoal]:
        """Detect new capabilities that enable previously impossible goals."""
        if len(self._snapshots) < 2:
            return []

        current = self._snapshots[-1]
        previous = self._snapshots[-2]
        goals = []

        new_caps = current.capabilities - previous.capabilities
        for cap in new_caps:
            goals.append(EmergentGoal(
                goal_id="",
                goal_text=f"New capability available: {cap} — explore applications",
                source=GoalSource.OPPORTUNITY,
                priority=self._compute_priority(
                    novelty=0.9,
                    urgency=0.3,
                    impact=0.5,
                ),
                novelty=0.9,
                urgency=0.3,
                estimated_impact=0.5,
                trigger=f"new_capability: {cap}",
            ))

        # Also detect metric thresholds being crossed
        for key, value in current.metrics.items():
            prev_val = previous.metrics.get(key, 0)
            # Threshold crossings at 80%, 90%, 95%
            for threshold in [0.80, 0.90, 0.95]:
                if prev_val < threshold <= value:
                    goals.append(EmergentGoal(
                        goal_id="",
                        goal_text=f"{key} crossed {threshold:.0%} threshold ({value:.3f}) — consolidate gains",
                        source=GoalSource.OPPORTUNITY,
                        priority=self._compute_priority(
                            novelty=0.6,
                            urgency=0.4,
                            impact=0.7,
                        ),
                        novelty=0.6,
                        urgency=0.4,
                        estimated_impact=0.7,
                        trigger=f"threshold_{threshold:.0%}_crossed",
                    ))

        return goals

    # ── E4: Regression Detection ──

    def _detect_regressions(self) -> List[EmergentGoal]:
        """Detect metrics that have regressed from their peak."""
        goals = []

        for key, history in self._baseline_metrics.items():
            if len(history) < 3:
                continue

            peak = max(history)
            current = history[-1]
            regression = peak - current

            if regression >= REGRESSION_THRESHOLD and current < peak:
                goals.append(EmergentGoal(
                    goal_id="",
                    goal_text=f"Regression in {key}: peak={peak:.3f}, now={current:.3f} (-{regression:.3f})",
                    source=GoalSource.REGRESSION,
                    priority=self._compute_priority(
                        novelty=0.3,     # Not novel — it worked before
                        urgency=0.7,     # But urgent — we're going backwards
                        impact=regression,
                    ),
                    novelty=0.3,
                    urgency=0.7,
                    estimated_impact=min(regression * 2, 1.0),
                    trigger=f"peak={peak:.3f}, current={current:.3f}",
                ))

        return goals

    # ── Priority Computation ──

    def _compute_priority(self, novelty: float, urgency: float,
                          impact: float) -> float:
        """Weighted priority computation."""
        return (
            NOVELTY_WEIGHT * novelty +
            URGENCY_WEIGHT * urgency +
            IMPACT_WEIGHT * impact
        )

    # ── Persistence ──

    def _save_state(self) -> None:
        """Save engine state for cross-session persistence."""
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "snapshots": [s.to_dict() for s in self._snapshots[-20:]],
            "emitted_goals": self._emitted_goals,
            "baseline_metrics": dict(self._baseline_metrics),
            "saved_at": time.time(),
        }
        path = self._checkpoint_dir / EMERGENCE_STATE_FILE
        path.write_text(json.dumps(state, indent=2, default=str))

    def _load_state(self) -> None:
        """Load previous state."""
        path = self._checkpoint_dir / EMERGENCE_STATE_FILE
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text())
            self._snapshots = [
                StateSnapshot.from_dict(s) for s in data.get("snapshots", [])
            ]
            self._emitted_goals = data.get("emitted_goals", {})
            for k, v in data.get("baseline_metrics", {}).items():
                self._baseline_metrics[k] = v
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    # ── Module Identity ──

    def get_status(self) -> Dict[str, Any]:
        """Module status for KCS diagnosis."""
        return {
            "module": "goal_emergence",
            "version": VERSION,
            "snapshots": len(self._snapshots),
            "tracked_metrics": len(self._baseline_metrics),
            "emitted_goals": len(self._emitted_goals),
            "detectors": ["state_delta", "anomaly", "opportunity", "regression"],
        }


def get_status() -> Dict[str, Any]:
    """Module-level status for KCS."""
    return {
        "module": "goal_emergence",
        "version": VERSION,
        "targets": {
            "goal_discovery": "87% → 94%",
            "mechanism": "Environment-driven goal detection (delta/anomaly/opportunity/regression)",
        },
    }
