"""Tests for Hypothesis-Driven Exploration Loop (HDEL)."""

import os
import sys
import time
import pytest

_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from hypothesis_loop import (
    Hypothesis, HypothesisStatus, Probe, BeliefModel, BeliefStore,
    HypothesisLoop, ExplorationResult,
    generate_hypotheses_from_observations,
    design_probe, update_belief, compute_curiosity,
    PRIOR_CONFIDENCE, CONVERGENCE_THRESHOLD, REJECTION_THRESHOLD,
    SURPRISE_THRESHOLD, MAX_PROBES_PER_HYPOTHESIS,
)


# ════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════

@pytest.fixture
def sample_hypothesis():
    return Hypothesis(
        hypothesis_id="h001",
        claim="Module X has a performance bottleneck in the sort phase",
        domain="performance",
        predicted_outcome="Profiling will show >50% time in sort",
        confidence=PRIOR_CONFIDENCE,
        source="pattern",
    )


@pytest.fixture
def sample_observations():
    return [
        {"domain": "performance", "data": "sort takes 500ms"},
        {"domain": "performance", "data": "sort takes 480ms"},
        {"domain": "correctness", "data": "output matches expected"},
        {"domain": "scalability", "data": "linear growth observed"},
    ]


@pytest.fixture
def belief_model():
    return BeliefModel()


# ════════════════════════════════════════════
# Hypothesis Tests
# ════════════════════════════════════════════

class TestHypothesis:

    def test_new_hypothesis_is_active(self, sample_hypothesis):
        assert sample_hypothesis.status == HypothesisStatus.ACTIVE

    def test_acceptance_ratio_no_probes(self, sample_hypothesis):
        assert sample_hypothesis.acceptance_ratio() == 0.5

    def test_acceptance_ratio_with_probes(self, sample_hypothesis):
        sample_hypothesis.probes_confirmed = 3
        sample_hypothesis.probes_refuted = 1
        assert sample_hypothesis.acceptance_ratio() == 0.75

    def test_is_terminal_active(self, sample_hypothesis):
        assert not sample_hypothesis.is_terminal()

    def test_is_terminal_accepted(self, sample_hypothesis):
        sample_hypothesis.status = HypothesisStatus.ACCEPTED
        assert sample_hypothesis.is_terminal()

    def test_average_surprise_empty(self, sample_hypothesis):
        assert sample_hypothesis.average_surprise() == 0.0

    def test_average_surprise(self, sample_hypothesis):
        sample_hypothesis.surprise_history = [0.1, 0.3, 0.2]
        assert sample_hypothesis.average_surprise() == pytest.approx(0.2, abs=0.01)


# ════════════════════════════════════════════
# Belief Update Tests
# ════════════════════════════════════════════

class TestBeliefUpdate:

    def test_low_error_increases_confidence(self, sample_hypothesis):
        probe = Probe("p1", "h001", "test", "expected")
        h = update_belief(sample_hypothesis, probe, prediction_error=0.1)
        assert h.confidence > PRIOR_CONFIDENCE
        assert probe.confirmed

    def test_high_error_decreases_confidence(self, sample_hypothesis):
        probe = Probe("p1", "h001", "test", "expected")
        h = update_belief(sample_hypothesis, probe, prediction_error=0.9)
        assert h.confidence < PRIOR_CONFIDENCE
        assert not probe.confirmed

    def test_convergence_to_accepted(self):
        h = Hypothesis("h1", "claim", "domain", "outcome", confidence=0.80)
        # Multiple confirming probes
        for i in range(5):
            probe = Probe(f"p{i}", "h1", "test", "expected")
            h = update_belief(h, probe, prediction_error=0.05)
        assert h.status == HypothesisStatus.ACCEPTED

    def test_convergence_to_rejected(self):
        h = Hypothesis("h1", "claim", "domain", "outcome", confidence=0.25)
        # Multiple refuting probes
        for i in range(5):
            probe = Probe(f"p{i}", "h1", "test", "expected")
            h = update_belief(h, probe, prediction_error=0.95)
        assert h.status == HypothesisStatus.REJECTED

    def test_probe_count_increments(self, sample_hypothesis):
        probe = Probe("p1", "h001", "test", "expected")
        h = update_belief(sample_hypothesis, probe, prediction_error=0.3)
        assert h.probes_run == 1

    def test_confidence_bounded_0_1(self):
        h = Hypothesis("h1", "claim", "domain", "outcome", confidence=0.01)
        probe = Probe("p1", "h1", "test", "expected")
        h = update_belief(h, probe, prediction_error=1.0)
        assert h.confidence >= 0.0
        assert h.confidence <= 1.0


# ════════════════════════════════════════════
# Hypothesis Generation Tests
# ════════════════════════════════════════════

class TestHypothesisGeneration:

    def test_generates_from_observations(self, sample_observations, belief_model):
        hypotheses = generate_hypotheses_from_observations(
            sample_observations, belief_model
        )
        assert len(hypotheses) >= 1
        assert all(isinstance(h, Hypothesis) for h in hypotheses)

    def test_generates_pattern_hypotheses(self, sample_observations, belief_model):
        hypotheses = generate_hypotheses_from_observations(
            sample_observations, belief_model
        )
        pattern_h = [h for h in hypotheses if h.source == "pattern"]
        assert len(pattern_h) >= 1  # "performance" appears 2x

    def test_generates_curiosity_hypotheses(self, sample_observations, belief_model):
        hypotheses = generate_hypotheses_from_observations(
            sample_observations, belief_model
        )
        curiosity_h = [h for h in hypotheses if h.source == "curiosity"]
        assert len(curiosity_h) >= 1  # Uncovered domains

    def test_no_duplicates(self, sample_observations, belief_model):
        hypotheses = generate_hypotheses_from_observations(
            sample_observations, belief_model
        )
        ids = [h.hypothesis_id for h in hypotheses]
        assert len(ids) == len(set(ids))

    def test_respects_max(self, sample_observations, belief_model):
        hypotheses = generate_hypotheses_from_observations(
            sample_observations, belief_model, max_hypotheses=2
        )
        assert len(hypotheses) <= 2


# ════════════════════════════════════════════
# Probe Design Tests
# ════════════════════════════════════════════

class TestProbeDesign:

    def test_initial_probe(self, sample_hypothesis):
        probe = design_probe(sample_hypothesis)
        assert probe.hypothesis_id == "h001"
        assert "Test:" in probe.action

    def test_boundary_probe_after_surprises(self, sample_hypothesis):
        sample_hypothesis.probes_run = 3
        sample_hypothesis.surprise_history = [0.6, 0.7, 0.5]
        probe = design_probe(sample_hypothesis)
        assert "Boundary" in probe.action or "boundary" in probe.action.lower()

    def test_edge_case_probe_after_confirmations(self, sample_hypothesis):
        sample_hypothesis.probes_run = 3
        sample_hypothesis.probes_confirmed = 3
        sample_hypothesis.probes_refuted = 0
        sample_hypothesis.surprise_history = [0.1, 0.1, 0.1]
        probe = design_probe(sample_hypothesis)
        assert "Edge" in probe.action or "edge" in probe.action.lower()


# ════════════════════════════════════════════
# Curiosity Tests
# ════════════════════════════════════════════

class TestCuriosity:

    def test_unexplored_domain_is_curious(self, sample_hypothesis, belief_model):
        score = compute_curiosity(sample_hypothesis, belief_model)
        assert score > 0.3

    def test_explored_domain_less_curious(self, sample_hypothesis, belief_model):
        belief_model.exploration_coverage["performance"] = 0.9
        score = compute_curiosity(sample_hypothesis, belief_model)
        score_unexplored = compute_curiosity(
            Hypothesis("h2", "claim", "new_domain", "outcome", 0.5),
            belief_model,
        )
        assert score_unexplored > score

    def test_high_confidence_less_curious(self, belief_model):
        h_uncertain = Hypothesis("h1", "c", "d", "o", confidence=0.5)
        h_certain = Hypothesis("h2", "c", "d", "o", confidence=0.95)
        assert compute_curiosity(h_uncertain, belief_model) > compute_curiosity(h_certain, belief_model)

    def test_curiosity_bounded(self, sample_hypothesis, belief_model):
        score = compute_curiosity(sample_hypothesis, belief_model)
        assert 0.0 <= score <= 1.0


# ════════════════════════════════════════════
# Belief Persistence Tests
# ════════════════════════════════════════════

class TestBeliefPersistence:

    def test_save_and_load(self, tmp_path, sample_hypothesis, belief_model):
        path = str(tmp_path / "beliefs.json")
        belief_model.add_hypothesis(sample_hypothesis)
        belief_model.total_probes = 5

        store = BeliefStore(path)
        store.save(belief_model)

        loaded = store.load()
        assert loaded.total_probes == 5
        assert "h001" in loaded.beliefs
        assert loaded.beliefs["h001"].claim == sample_hypothesis.claim

    def test_load_nonexistent(self, tmp_path):
        store = BeliefStore(str(tmp_path / "nonexistent.json"))
        model = store.load()
        assert isinstance(model, BeliefModel)
        assert len(model.beliefs) == 0


# ════════════════════════════════════════════
# Integration: HypothesisLoop
# ════════════════════════════════════════════

class TestHypothesisLoop:

    def test_explore_with_defaults(self, sample_observations):
        hdel = HypothesisLoop(max_cycles=5)
        result = hdel.explore(sample_observations)
        assert isinstance(result, ExplorationResult)
        assert result.cycles <= 5
        assert result.total_probes >= 0

    def test_explore_with_custom_executor(self, sample_observations):
        probes_run = []

        def custom_executor(action, context):
            probes_run.append(action)
            return {"output": "confirmed", "success": True}

        def custom_evaluator(expected, actual):
            return 0.1  # Always low error → confirm

        hdel = HypothesisLoop(
            probe_executor=custom_executor,
            result_evaluator=custom_evaluator,
            max_cycles=20,
        )
        result = hdel.explore(sample_observations)
        assert len(probes_run) > 0
        # With error=0.1, beliefs should converge toward acceptance
        accepted_or_high_conf = [
            h for h in result.belief_model.beliefs.values()
            if h.status == HypothesisStatus.ACCEPTED or h.confidence > 0.7
        ]
        assert len(accepted_or_high_conf) >= 1

    def test_explore_with_seeded_hypotheses(self):
        hypotheses = [
            Hypothesis("seed1", "Test claim A", "domain_a", "Outcome A", 0.5),
            Hypothesis("seed2", "Test claim B", "domain_b", "Outcome B", 0.5),
        ]
        hdel = HypothesisLoop(max_cycles=5)
        result = hdel.explore([], hypotheses=hypotheses)
        assert result.cycles <= 5

    def test_belief_model_persists(self, tmp_path, sample_observations):
        path = str(tmp_path / "beliefs.json")
        hdel = HypothesisLoop(belief_path=path, max_cycles=5)
        hdel.explore(sample_observations)

        # Load again — beliefs should persist
        hdel2 = HypothesisLoop(belief_path=path, max_cycles=5)
        assert len(hdel2.belief_model.beliefs) > 0

    def test_format_result(self, sample_observations):
        hdel = HypothesisLoop(max_cycles=3)
        result = hdel.explore(sample_observations)
        text = HypothesisLoop.format_result(result)
        assert "HDEL" in text
        assert "Cycles" in text

    def test_surprises_generate_anomaly_hypotheses(self):
        """High prediction error should spawn anomaly hypotheses."""
        call_count = [0]

        def always_wrong_evaluator(expected, actual):
            return 0.9  # Always high error

        def counter_executor(action, context):
            call_count[0] += 1
            return {"output": "unexpected", "success": True}

        hypotheses = [
            Hypothesis("h1", "Claim", "domain", "Outcome", 0.5),
        ]
        hdel = HypothesisLoop(
            probe_executor=counter_executor,
            result_evaluator=always_wrong_evaluator,
            max_cycles=8,
        )
        result = hdel.explore([], hypotheses=hypotheses)
        assert result.surprises >= 1
        # Anomaly hypotheses should have been generated
        anomaly_h = [h for h in result.belief_model.beliefs.values()
                     if h.source == "anomaly"]
        assert len(anomaly_h) >= 1
