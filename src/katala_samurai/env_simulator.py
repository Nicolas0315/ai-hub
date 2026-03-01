"""
Environment Simulator — Look-ahead Action Simulation.

Targets: Interactive Environment 78%→88% (component 3/3)

"Think before you act" — simulate action effects before execution.

Uses EnvironmentStateModel's history to build a predictive model:
1. Given current state + proposed action
2. Predict effects (from past transitions)
3. Estimate risk (from past failures)
4. Compare alternatives (which action is safest/best?)

This is the "model-based" complement to InteractiveExplorer's
"model-free" trial-and-error approach.

Architecture:
    Proposed action
        ↓
    EnvironmentSimulator.simulate(action)
        ↓
    Clone current state
        ↓
    Apply predicted effects (from history)
        ↓
    Score: success_probability × benefit - risk
        ↓
    Compare alternatives → recommend best

Design: Youta Hilono (direction) + Shirokuma (implementation)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import os, sys
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from env_state_model import EnvironmentStateModel, StateTransition

# ── Constants ──
MAX_SIMULATION_DEPTH = 5          # Max steps to simulate forward
MAX_ALTERNATIVES = 10             # Max alternative actions to compare
RISK_PENALTY_WEIGHT = 0.4         # How much to penalize risk
BENEFIT_WEIGHT = 0.6              # How much to reward benefit
MIN_HISTORY_FOR_PREDICTION = 2    # Need at least 2 past instances
SIMILARITY_THRESHOLD = 0.3       # Minimum action similarity for matching


@dataclass
class SimulationResult:
    """Result of simulating a single action."""
    action: str
    predicted_effects: Dict[str, Any]
    success_probability: float    # 0-1 based on past success rate
    risk_score: float             # 0-1 higher = riskier
    benefit_score: float          # 0-1 higher = more beneficial
    net_score: float              # benefit - risk weighted
    confidence: float             # How confident is this prediction?
    similar_past_actions: int     # How many past actions were used
    predicted_state: Dict[str, Any]  # State after simulated action
    warnings: List[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Result of comparing multiple action alternatives."""
    best_action: str
    best_score: float
    alternatives: List[SimulationResult]
    recommendation: str
    total_simulated: int


class EnvironmentSimulator:
    """Model-based action simulation using environmental history.

    Usage:
    ```python
    sim = EnvironmentSimulator(env_model)

    # Simulate one action
    result = sim.simulate("edit ks42b.py")
    print(f"Risk: {result.risk_score}, Benefit: {result.benefit_score}")

    # Compare alternatives
    comparison = sim.compare([
        "edit ks42b.py",
        "add tests for ks42b",
        "refactor ks42b.py",
    ])
    print(f"Best: {comparison.best_action}")
    ```
    """

    def __init__(self, env_model: Optional[EnvironmentStateModel] = None):
        self._env_model = env_model or EnvironmentStateModel()
        self._simulation_count = 0

    # ── Core Simulation ──

    def simulate(self, action: str, depth: int = 1) -> SimulationResult:
        """Simulate an action and predict its effects.

        Uses past transitions with similar actions to predict effects.
        """
        self._simulation_count += 1

        current_state = self._env_model.get_current_state()
        history = self._env_model.get_history(limit=200)

        # Find similar past actions
        similar = self._find_similar_actions(action, history)
        n_similar = len(similar)

        # Predict effects
        predicted_effects = self._aggregate_effects(similar)

        # Success probability
        if similar:
            successes = sum(1 for t in similar if not self._is_failure(t))
            success_prob = successes / len(similar)
        else:
            success_prob = 0.5  # Unknown → neutral

        # Risk score
        risk = self._compute_risk(action, similar, current_state)

        # Benefit score
        benefit = self._compute_benefit(predicted_effects, current_state)

        # Net score
        net = benefit * BENEFIT_WEIGHT - risk * RISK_PENALTY_WEIGHT

        # Confidence based on history depth
        confidence = min(1.0, n_similar / 10)  # Saturates at 10 examples

        # Predict resulting state
        predicted_state = dict(current_state)
        for key, value in predicted_effects.items():
            if key.startswith("!"):
                predicted_state.pop(key[1:], None)
            elif isinstance(value, dict) and "new" in value:
                predicted_state[key] = value["new"]
            else:
                predicted_state[key] = value

        # Warnings
        warnings = []
        if n_similar < MIN_HISTORY_FOR_PREDICTION:
            warnings.append(f"Low confidence: only {n_similar} similar past actions")
        if risk > 0.7:
            warnings.append(f"High risk ({risk:.0%}): action has caused failures before")
        if self._has_reversal_pattern(action, history):
            warnings.append("Past reversal pattern detected: this action was undone before")

        # Multi-step simulation
        if depth > 1 and depth <= MAX_SIMULATION_DEPTH:
            chain_results = self._simulate_chain(action, predicted_state, depth - 1, history)
            if chain_results:
                # Aggregate chain risk
                chain_risk = max(r.risk_score for r in chain_results)
                risk = max(risk, chain_risk * 0.7)  # Cascade but dampen
                net = benefit * BENEFIT_WEIGHT - risk * RISK_PENALTY_WEIGHT
                warnings.append(f"Chain simulation ({depth} steps): max chain risk {chain_risk:.0%}")

        return SimulationResult(
            action=action,
            predicted_effects=predicted_effects,
            success_probability=round(success_prob, 3),
            risk_score=round(risk, 3),
            benefit_score=round(benefit, 3),
            net_score=round(net, 3),
            confidence=round(confidence, 3),
            similar_past_actions=n_similar,
            predicted_state=predicted_state,
            warnings=warnings,
        )

    def compare(self, actions: List[str]) -> ComparisonResult:
        """Compare multiple action alternatives and recommend the best."""
        results = [self.simulate(action) for action in actions[:MAX_ALTERNATIVES]]
        results.sort(key=lambda r: r.net_score, reverse=True)

        best = results[0] if results else None

        if not best:
            return ComparisonResult(
                best_action="(none)",
                best_score=0,
                alternatives=[],
                recommendation="No actions to compare",
                total_simulated=0,
            )

        # Build recommendation
        if best.risk_score > 0.7:
            rec = f"⚠️ Best option '{best.action}' is high-risk ({best.risk_score:.0%}). Consider waiting."
        elif best.net_score > 0.5:
            rec = f"✅ '{best.action}' is recommended (net score {best.net_score:.2f})"
        elif best.net_score > 0:
            rec = f"🟡 '{best.action}' is marginally beneficial (net {best.net_score:.2f})"
        else:
            rec = f"❌ All options have negative net score. Best to wait."

        return ComparisonResult(
            best_action=best.action,
            best_score=best.net_score,
            alternatives=results,
            recommendation=rec,
            total_simulated=len(results),
        )

    # ── Prediction Engine ──

    def _find_similar_actions(
        self, action: str, history: List[StateTransition],
    ) -> List[StateTransition]:
        """Find past transitions with similar actions."""
        action_words = set(action.lower().split())
        similar = []

        for t in history:
            t_words = set(t.action.lower().split())
            if not action_words or not t_words:
                continue
            overlap = len(action_words & t_words) / len(action_words | t_words)
            if overlap >= SIMILARITY_THRESHOLD:
                similar.append(t)

        return similar

    def _aggregate_effects(self, transitions: List[StateTransition]) -> Dict[str, Any]:
        """Aggregate effects from similar transitions."""
        if not transitions:
            return {}

        # Count most common effects
        effect_votes: Dict[str, Dict[str, int]] = {}
        for t in transitions:
            for key, change in t.delta.items():
                if key not in effect_votes:
                    effect_votes[key] = {}
                change_str = str(change)
                effect_votes[key][change_str] = effect_votes[key].get(change_str, 0) + 1

        # Return most common effect for each key
        predicted = {}
        for key, votes in effect_votes.items():
            best = max(votes, key=votes.get)
            predicted[key] = best

        return predicted

    def _compute_risk(
        self, action: str, similar: List[StateTransition],
        current_state: Dict[str, Any],
    ) -> float:
        """Compute risk score for an action."""
        if not similar:
            return 0.3  # Unknown action → moderate risk

        # Failure rate
        failures = sum(1 for t in similar if self._is_failure(t))
        failure_rate = failures / len(similar)

        # State fragility: how many critical facts might be affected?
        critical_keys = {"tests_passing", "build_ok", "deployed", "error_count"}
        affected_critical = 0
        for t in similar:
            for key in t.delta:
                clean_key = key.lstrip("!")
                if clean_key in critical_keys:
                    affected_critical += 1

        critical_factor = min(1.0, affected_critical / max(len(similar), 1))

        # Reversal frequency (how often was this action undone?)
        reversal_rate = 0.0
        reversals = self._env_model.find_reversals()
        for t1, t2 in reversals:
            if action.lower() in t1.action.lower():
                reversal_rate += 0.2

        risk = (
            failure_rate * 0.5 +
            critical_factor * 0.3 +
            min(1.0, reversal_rate) * 0.2
        )

        return min(1.0, risk)

    def _compute_benefit(
        self, predicted_effects: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> float:
        """Estimate benefit of predicted effects."""
        if not predicted_effects:
            return 0.3  # Unknown benefit

        positive_signals = 0
        negative_signals = 0

        # Heuristic: certain effect patterns are good/bad
        positive_patterns = {"passing", "true", "success", "ok", "0"}
        negative_patterns = {"fail", "false", "error", "crash"}

        for key, value in predicted_effects.items():
            value_str = str(value).lower()
            if any(p in value_str for p in positive_patterns):
                positive_signals += 1
            if any(p in value_str for p in negative_patterns):
                negative_signals += 1

        total = max(positive_signals + negative_signals, 1)
        return positive_signals / total

    def _is_failure(self, transition: StateTransition) -> bool:
        """Heuristic: did this transition represent a failure?"""
        failure_signals = {"fail", "error", "crash", "false", "broken"}
        for value in transition.delta.values():
            if any(s in str(value).lower() for s in failure_signals):
                return True
        return False

    def _has_reversal_pattern(self, action: str, history: List[StateTransition]) -> bool:
        """Check if similar actions have been reversed before."""
        action_lower = action.lower()
        reversals = self._env_model.find_reversals()
        for t1, t2 in reversals:
            if action_lower in t1.action.lower():
                return True
        return False

    def _simulate_chain(
        self,
        initial_action: str,
        state_after: Dict[str, Any],
        remaining_depth: int,
        history: List[StateTransition],
    ) -> List[SimulationResult]:
        """Simulate a chain of likely follow-up actions."""
        # Find what typically follows this action
        action_words = set(initial_action.lower().split())
        follow_ups = []

        for i, t in enumerate(history[:-1]):
            t_words = set(t.action.lower().split())
            overlap = len(action_words & t_words) / max(len(action_words | t_words), 1)
            if overlap >= SIMILARITY_THRESHOLD:
                next_t = history[i + 1]
                if next_t.action not in follow_ups:
                    follow_ups.append(next_t.action)

        results = []
        for follow_up in follow_ups[:3]:  # Max 3 follow-ups
            result = self.simulate(follow_up, depth=remaining_depth)
            results.append(result)

        return results

    # ── Stats ──

    def get_stats(self) -> Dict[str, Any]:
        return {
            "simulations_run": self._simulation_count,
            "env_history_size": len(self._env_model.get_history(limit=500)),
            "env_facts": len(self._env_model.get_current_state()),
        }
