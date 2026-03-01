"""
Environment State Model — Causal State Tracking for Interactive Agents.

Tracks environment state transitions and their causal relationships.
"Edit file A" → "Test breaks" → "Revert file A" → "Test passes"
= causal chain that the agent can reason about.

Builds on CheckpointEngine (persistence) + SessionStateManager (ephemeral).

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

# ── Constants ──
MAX_STATE_HISTORY = 500          # Max state transitions to remember
MAX_CAUSAL_CHAIN = 20            # Max chain length before pruning
CAUSAL_DECAY_RATE = 0.9          # Confidence decay per chain link
STATE_SNAPSHOT_INTERVAL = 10     # Snapshot state every N transitions


@dataclass
class StateTransition:
    """A single state change in the environment."""
    transition_id: str
    action: str                  # What caused this transition
    before: Dict[str, Any]       # State facts before
    after: Dict[str, Any]        # State facts after
    delta: Dict[str, Any]        # What changed (diff)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    parent_id: Optional[str] = None  # Previous transition in chain

    @property
    def is_reversal(self) -> bool:
        """Did this transition undo a previous one?"""
        # If delta restores values that were changed
        return bool(self.delta) and any(
            k.startswith("!") for k in self.delta
        )


@dataclass
class CausalLink:
    """A causal relationship between transitions."""
    cause_id: str
    effect_id: str
    strength: float = 1.0        # 0-1 causal strength
    link_type: str = "direct"    # direct | indirect | correlational


@dataclass
class EnvironmentSnapshot:
    """Point-in-time snapshot of environment state."""
    snapshot_id: str
    facts: Dict[str, Any]
    timestamp: float
    transition_count: int


class EnvironmentStateModel:
    """Tracks environment state transitions with causal reasoning.

    Enables the agent to:
    1. Know what changed and why
    2. Predict effects of actions
    3. Detect and reverse harmful changes
    4. Learn causal patterns across sessions
    """

    def __init__(self):
        self._current_state: Dict[str, Any] = {}
        self._history: deque = deque(maxlen=MAX_STATE_HISTORY)
        self._causal_links: List[CausalLink] = []
        self._snapshots: List[EnvironmentSnapshot] = []
        self._transition_counter = 0

    # ── Public API ──

    def record_transition(
        self,
        action: str,
        effects: Dict[str, Any],
        confidence: float = 1.0,
    ) -> StateTransition:
        """Record a state transition caused by an action.

        Parameters
        ----------
        action : str
            Description of what was done
        effects : dict
            Key-value pairs that changed (use "!key" to remove)
        confidence : float
            How confident we are this transition happened
        """
        before = dict(self._current_state)

        # Apply effects
        delta = {}
        for key, value in effects.items():
            if key.startswith("!"):
                real_key = key[1:]
                if real_key in self._current_state:
                    delta[key] = self._current_state.pop(real_key)
            else:
                old_value = self._current_state.get(key)
                if old_value != value:
                    delta[key] = {"old": old_value, "new": value}
                self._current_state[key] = value

        self._transition_counter += 1
        tid = f"t_{self._transition_counter:06d}"

        parent_id = self._history[-1].transition_id if self._history else None

        transition = StateTransition(
            transition_id=tid,
            action=action,
            before=before,
            after=dict(self._current_state),
            delta=delta,
            confidence=confidence,
            parent_id=parent_id,
        )

        self._history.append(transition)

        # Auto-detect causal links
        if parent_id:
            self._causal_links.append(CausalLink(
                cause_id=parent_id,
                effect_id=tid,
                strength=confidence,
            ))

        # Periodic snapshot
        if self._transition_counter % STATE_SNAPSHOT_INTERVAL == 0:
            self._take_snapshot()

        return transition

    def predict_effects(self, action: str) -> Dict[str, Any]:
        """Predict what effects an action will have based on history.

        Looks at past transitions with similar actions and returns
        the most common effects.
        """
        action_lower = action.lower()
        relevant = [
            t for t in self._history
            if any(word in t.action.lower() for word in action_lower.split()[:3])
        ]

        if not relevant:
            return {}

        # Aggregate effects weighted by recency
        effect_counts: Dict[str, Dict[Any, float]] = {}
        for i, t in enumerate(relevant):
            recency = (i + 1) / len(relevant)  # More recent = higher weight
            for key, change in t.delta.items():
                if key not in effect_counts:
                    effect_counts[key] = {}
                change_str = str(change)
                effect_counts[key][change_str] = (
                    effect_counts[key].get(change_str, 0) + recency
                )

        # Return most likely effects
        predicted = {}
        for key, changes in effect_counts.items():
            best_change = max(changes, key=changes.get)
            predicted[key] = best_change

        return predicted

    def find_reversals(self) -> List[Tuple[StateTransition, StateTransition]]:
        """Find pairs of transitions where one reversed the other.

        Useful for detecting: "I broke it, then fixed it" patterns.
        """
        reversals = []
        history_list = list(self._history)

        for i in range(len(history_list) - 1):
            for j in range(i + 1, min(i + 10, len(history_list))):
                t1 = history_list[i]
                t2 = history_list[j]

                # Check if t2's after ≈ t1's before
                if t1.before and t2.after:
                    restored = sum(
                        1 for k in t1.delta
                        if not k.startswith("!") and t2.after.get(k) == t1.before.get(k)
                    )
                    if restored > 0 and restored >= len(t1.delta) * 0.5:
                        reversals.append((t1, t2))

        return reversals

    def get_causal_chain(self, transition_id: str, max_depth: int = MAX_CAUSAL_CHAIN) -> List[str]:
        """Trace the causal chain leading to a transition."""
        chain = [transition_id]
        current = transition_id
        depth = 0

        while depth < max_depth:
            # Find cause
            cause_link = next(
                (l for l in self._causal_links if l.effect_id == current),
                None,
            )
            if not cause_link:
                break
            chain.insert(0, cause_link.cause_id)
            current = cause_link.cause_id
            depth += 1

        return chain

    def get_current_state(self) -> Dict[str, Any]:
        """Return current environment state."""
        return dict(self._current_state)

    def get_history(self, limit: int = 20) -> List[StateTransition]:
        """Get recent transition history."""
        return list(self._history)[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """State model statistics."""
        return {
            "total_transitions": self._transition_counter,
            "current_facts": len(self._current_state),
            "history_size": len(self._history),
            "causal_links": len(self._causal_links),
            "snapshots": len(self._snapshots),
        }

    # ── Private ──

    def _take_snapshot(self) -> None:
        self._snapshots.append(EnvironmentSnapshot(
            snapshot_id=f"snap_{len(self._snapshots):04d}",
            facts=dict(self._current_state),
            timestamp=time.time(),
            transition_count=self._transition_counter,
        ))
