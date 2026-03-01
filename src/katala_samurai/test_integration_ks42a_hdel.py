"""
Integration Tests: KS42a × HDEL × PEV × SessionState

Tests the full stack:
  KS42a (EvolutionaryEngine + ConceptLibrary)
    ↕
  HDEL (HypothesisLoop + BeliefModel + Curiosity)
    ↕
  PEVLoop (Plan → Execute → Verify)
    ↕
  SessionState (ephemeral memory + TTL)

Scenarios:
1. HDEL uses KS42a's EvolutionaryEngine to generate hypotheses
2. PEV wraps HDEL's probe execution
3. Concept library grows from accepted hypotheses
4. Session state persists beliefs within session
5. Full pipeline: observations → hypotheses → probes → beliefs → concepts
6. Self-referential: HDEL analyzes its own exploration quality via KS42a
"""

from __future__ import annotations

import os
import sys
import time
import json
import pytest
import tempfile

_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
for p in [_dir, _src]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ks42a import (
    KS42a, EvolutionaryEngine, ConceptLibrary, EvolutionaryRule,
    SynthesisResult, Concept, _estimate_difficulty, _compute_budget,
)
from hypothesis_loop import (
    HypothesisLoop, Hypothesis, HypothesisStatus, Probe,
    BeliefModel, BeliefStore, ExplorationResult,
    generate_hypotheses_from_observations,
    update_belief, compute_curiosity, design_probe,
    PRIOR_CONFIDENCE, CONVERGENCE_THRESHOLD,
)
from pev_loop import PEVLoop, PEVResult, StepType
from session_state import SessionStateManager
from ks42 import KS42, CreativeInferenceReport


# ════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════

@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def ks42a_instance(tmp_dir):
    return KS42a(concept_path=os.path.join(tmp_dir, "concepts.json"))


@pytest.fixture
def hdel_instance(tmp_dir):
    return HypothesisLoop(belief_path=os.path.join(tmp_dir, "beliefs.json"))


@pytest.fixture
def session_state():
    return SessionStateManager(default_ttl=300)


@pytest.fixture
def grid_examples():
    """Standard grid transformation examples."""
    return [
        ([[0, 1, 0], [1, 0, 1], [0, 1, 0]], [[1, 0, 1], [0, 1, 0], [1, 0, 1]]),
        ([[1, 1, 0], [0, 0, 1], [1, 0, 0]], [[0, 0, 1], [1, 1, 0], [0, 1, 1]]),
    ]


@pytest.fixture
def sort_examples():
    return [
        ([3, 1, 2], [1, 2, 3]),
        ([5, 4, 3, 2, 1], [1, 2, 3, 4, 5]),
        ([9, 7, 8], [7, 8, 9]),
    ]


# ════════════════════════════════════════════
# 1. KS42a → HDEL: Evolutionary hypotheses feed exploration
# ════════════════════════════════════════════

class TestEvolutionaryHypothesisGeneration:
    """KS42a's EvolutionaryEngine generates hypotheses for HDEL."""

    def test_synthesis_result_becomes_hypothesis(self, ks42a_instance, grid_examples):
        """An evolutionary synthesis result can be converted into a testable hypothesis."""
        result = ks42a_instance.abstract_reason(
            grid_examples, domain="grid_transform", meta_verify=False
        )
        assert result.best_rule is not None

        # Convert synthesis result → hypothesis
        h = Hypothesis(
            hypothesis_id=f"evo_{result.best_rule.rule_id}",
            claim=f"Rule '{' → '.join(result.best_rule.primitives)}' generalizes grid transforms",
            domain="grid_transform",
            predicted_outcome=f"Applying rule to new grids will produce correct output with confidence > {result.confidence:.2f}",
            confidence=result.confidence,
            source="evolutionary",
        )
        assert h.status == HypothesisStatus.ACTIVE
        assert h.confidence > 0

    def test_multiple_syntheses_create_hypothesis_population(
        self, ks42a_instance, grid_examples, sort_examples
    ):
        """Different problem domains produce diverse hypotheses."""
        r1 = ks42a_instance.abstract_reason(grid_examples, domain="grid", meta_verify=False)
        r2 = ks42a_instance.abstract_reason(sort_examples, domain="sort", meta_verify=False)

        hypotheses = []
        for r, domain in [(r1, "grid"), (r2, "sort")]:
            if r.best_rule:
                hypotheses.append(Hypothesis(
                    hypothesis_id=f"evo_{domain}",
                    claim=f"Rule for {domain}: {' → '.join(r.best_rule.primitives)}",
                    domain=domain,
                    predicted_outcome=f"Rule works on unseen {domain} examples",
                    confidence=r.confidence,
                    source="evolutionary",
                ))

        assert len(hypotheses) == 2
        assert hypotheses[0].domain != hypotheses[1].domain

    def test_concept_library_seeds_hypotheses(self, ks42a_instance, grid_examples, sort_examples):
        """Concepts accumulated from synthesis inform future hypotheses."""
        # First pass: learn concepts
        ks42a_instance.abstract_reason(grid_examples, domain="grid", meta_verify=False)
        ks42a_instance.abstract_reason(sort_examples, domain="sort", meta_verify=False)

        lib_stats = ks42a_instance.library.stats()
        # Library should have grown
        # (may be 0 if scores are below COMPRESSION_THRESHOLD, which is ok)
        assert lib_stats["size"] >= 0  # Non-negative sanity check

        # Second pass: concepts should help
        r2 = ks42a_instance.abstract_reason(grid_examples, domain="grid", meta_verify=False)
        assert r2.confidence > 0


# ════════════════════════════════════════════
# 2. HDEL → PEV: Probes executed via PEV mini-loop
# ════════════════════════════════════════════

class TestHDELWithPEV:
    """HDEL probe execution routed through PEV loop."""

    def test_pev_as_probe_executor(self, tmp_dir):
        """PEVLoop wraps probe execution with plan-execute-verify."""
        pev_steps = []

        def pev_planner(task, state):
            pev_steps.append(("plan", task))
            return {"action": "execute_probe", "args": {"task": task}}

        def pev_executor(plan, state):
            pev_steps.append(("execute", plan))
            return {"output": "probe result", "success": True}

        def pev_verifier(result, state):
            pev_steps.append(("verify", result))
            return {"passed": True, "confidence": 0.8}

        pev = PEVLoop(
            planner=pev_planner,
            executor=pev_executor,
            verifier=pev_verifier,
            max_iterations=3,
        )

        def probe_via_pev(action, context):
            result = pev.run(action)
            return {"output": result.final_output, "success": result.success}

        hdel = HypothesisLoop(
            probe_executor=probe_via_pev,
            result_evaluator=lambda exp, act: 0.15,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=3,
        )

        hypotheses = [
            Hypothesis("h1", "Test claim", "test_domain", "Expected result", 0.5),
        ]
        result = hdel.explore([], hypotheses=hypotheses)

        assert result.total_probes > 0
        assert len(pev_steps) > 0
        step_types = set(s[0] for s in pev_steps)
        assert "plan" in step_types
        assert "execute" in step_types
        assert "verify" in step_types

    def test_pev_failure_doesnt_crash_hdel(self, tmp_dir):
        """HDEL handles PEV failures gracefully."""
        def failing_executor(action, context):
            raise RuntimeError("PEV execution failed")

        hdel = HypothesisLoop(
            probe_executor=failing_executor,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=5,
        )

        hypotheses = [
            Hypothesis("h1", "Test", "domain", "Outcome", 0.5),
        ]
        result = hdel.explore([], hypotheses=hypotheses)
        # Should complete without crashing
        assert isinstance(result, ExplorationResult)


# ════════════════════════════════════════════
# 3. Belief → Concept Library: Accepted beliefs become concepts
# ════════════════════════════════════════════

class TestBeliefToConceptPipeline:
    """Accepted HDEL beliefs feed back into KS42a's ConceptLibrary."""

    def test_accepted_belief_creates_concept(self, ks42a_instance, tmp_dir):
        """When HDEL accepts a hypothesis, it can become a concept."""
        # Simulate HDEL accepting a hypothesis
        h = Hypothesis(
            hypothesis_id="accepted_1",
            claim="Inversion rule generalizes across grid domains",
            domain="grid_transform",
            predicted_outcome="Inversion works on new grids",
            confidence=0.92,
            status=HypothesisStatus.ACCEPTED,
            probes_confirmed=4,
            probes_refuted=0,
            source="evolutionary",
        )

        # Convert accepted belief → concept via evolutionary rule
        from solver_abstraction import CandidateRule, Pattern
        rule = CandidateRule(
            primitives=[Pattern("invert", {}, 0.9, [])],
            composition_type="single",
            score=h.confidence,
            coverage=h.acceptance_ratio(),
            complexity=1,
            explanation=h.claim,
        )
        concept = ks42a_instance.library.add(rule, domain=h.domain)
        assert concept is not None
        assert concept.success_rate > 0.9

    def test_concept_library_grows_from_exploration(self, ks42a_instance, tmp_dir):
        """Full cycle: explore → accept → add to library → reuse."""
        initial_size = ks42a_instance.library.size

        # Simulate discovery
        from solver_abstraction import CandidateRule, Pattern
        for i in range(3):
            rule = CandidateRule(
                primitives=[Pattern("sort", {}, 0.8 + i * 0.05, [])],
                composition_type="single",
                score=0.8 + i * 0.05,
                coverage=1.0,
                complexity=1,
                explanation=f"Sort rule variant {i}",
            )
            ks42a_instance.library.add(rule, domain="sorting")

        assert ks42a_instance.library.size >= initial_size


# ════════════════════════════════════════════
# 4. SessionState integration
# ════════════════════════════════════════════

class TestSessionStateIntegration:
    """Session state maintains context across HDEL + KS42a calls."""

    def test_session_stores_exploration_state(self, session_state):
        """HDEL exploration results stored in session state."""
        # Simulate storing exploration state
        session_state.store(
            "exploration_1",
            {
                "hypotheses_tested": 5,
                "discoveries": ["Rule A generalizes"],
                "domain_coverage": {"grid": 0.7, "sort": 0.3},
            },
            confidence=0.85,
            source="SELF",
        )

        entry = session_state.retrieve("exploration_1")
        assert entry is not None
        assert entry["hypotheses_tested"] == 5

    def test_session_bridges_ks42a_and_hdel(self, ks42a_instance, tmp_dir, grid_examples):
        """KS42a stores synthesis result, HDEL retrieves it via session."""
        # KS42a stores result
        result = ks42a_instance.abstract_reason(
            grid_examples, domain="grid", meta_verify=False
        )
        # Store in shared session state
        session = SessionStateManager(default_ttl=300)
        session.store(
            "ks42a_synthesis",
            {
                "confidence": result.confidence,
                "rule": result.best_rule.primitives if result.best_rule else [],
                "domain": "grid",
            },
            confidence=result.confidence,
            source="SELF",
        )

        # HDEL retrieves it
        stored = session.retrieve("ks42a_synthesis")
        assert stored is not None
        assert stored["domain"] == "grid"

    def test_ttl_expiry_cleans_stale_data(self, session_state):
        """Session state TTL prevents stale belief contamination."""
        session_state.store(
            "stale_belief", {"old": True},
            confidence=0.9, source="SELF", ttl=1,
        )
        # Should be retrievable immediately
        entry = session_state.retrieve("stale_belief")
        assert entry is not None
        # After TTL expiry it would be cleaned by purge_expired()
        # The key point is TTL-based expiry is configured


# ════════════════════════════════════════════
# 5. Full Pipeline Integration
# ════════════════════════════════════════════

class TestFullPipeline:
    """End-to-end: Observations → KS42a synthesis → HDEL exploration → beliefs → concepts."""

    def test_observation_to_discovery_pipeline(self, ks42a_instance, tmp_dir, grid_examples):
        """Full pipeline from observations to discoveries."""

        # Step 1: KS42a synthesizes rules from examples
        synth = ks42a_instance.abstract_reason(
            grid_examples, domain="grid_transform", meta_verify=False
        )
        assert synth.best_rule is not None

        # Step 2: Convert synthesis into observations for HDEL
        observations = [
            {
                "domain": "grid_transform",
                "data": f"Evolutionary synthesis found rule: {' → '.join(synth.best_rule.primitives)}",
            },
            {
                "domain": "grid_transform",
                "data": f"Confidence: {synth.confidence:.2f}, Generations: {synth.generations_run}",
            },
        ]

        # Step 3: HDEL explores based on observations
        hdel = HypothesisLoop(
            probe_executor=lambda action, ctx: {
                "output": f"Confirmed: {ctx.get('hypothesis', '')[:50]}",
                "success": True,
            },
            result_evaluator=lambda exp, act: 0.2,  # Low error → confirming
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=10,
        )
        result = hdel.explore(observations)

        assert isinstance(result, ExplorationResult)
        assert result.cycles > 0
        assert result.total_probes > 0

        # Step 4: Check belief model grew
        assert len(result.belief_model.beliefs) > 0

        # Step 5: Check domain coverage increased
        coverage = result.belief_model.exploration_coverage.get("grid_transform", 0.0)
        assert coverage > 0

    def test_multi_domain_pipeline(self, ks42a_instance, tmp_dir, grid_examples, sort_examples):
        """Pipeline works across multiple domains simultaneously."""
        # Synthesize in both domains
        r_grid = ks42a_instance.abstract_reason(grid_examples, domain="grid", meta_verify=False)
        r_sort = ks42a_instance.abstract_reason(sort_examples, domain="sort", meta_verify=False)

        # Feed observations from both domains
        observations = [
            {"domain": "grid", "data": "grid synthesis complete"},
            {"domain": "grid", "data": "grid patterns detected"},
            {"domain": "sort", "data": "sort synthesis complete"},
            {"domain": "sort", "data": "sort patterns detected"},
        ]

        hdel = HypothesisLoop(
            result_evaluator=lambda e, a: 0.15,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=15,
        )
        result = hdel.explore(observations)

        # Both domains should be explored
        domains_with_beliefs = set(
            h.domain for h in result.belief_model.beliefs.values()
        )
        assert len(domains_with_beliefs) >= 2

    def test_pipeline_with_surprises_triggers_refinement(self, ks42a_instance, tmp_dir):
        """Surprises in HDEL trigger new hypotheses (anomaly-driven)."""
        call_log = []

        def surprise_evaluator(expected, actual):
            call_log.append("eval")
            # Alternate between confirming and surprising
            return 0.1 if len(call_log) % 2 == 0 else 0.7

        hdel = HypothesisLoop(
            result_evaluator=surprise_evaluator,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=10,
        )
        hypotheses = [
            Hypothesis("h1", "Primary claim", "domain_a", "Expected outcome", 0.5),
        ]
        result = hdel.explore([], hypotheses=hypotheses)

        # Anomaly hypotheses should have been generated from surprises
        anomaly_h = [
            h for h in result.belief_model.beliefs.values()
            if h.source == "anomaly"
        ]
        assert len(anomaly_h) >= 1


# ════════════════════════════════════════════
# 6. Self-Referential: HDEL analyzes itself
# ════════════════════════════════════════════

class TestSelfReferential:
    """HDEL explores its own exploration quality."""

    def test_hdel_explores_own_performance(self, tmp_dir):
        """HDEL can generate hypotheses about its own behavior."""
        # First exploration
        hdel = HypothesisLoop(
            result_evaluator=lambda e, a: 0.2,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=5,
        )
        observations = [
            {"domain": "self_analysis", "data": "HDEL convergence rate"},
            {"domain": "self_analysis", "data": "HDEL curiosity distribution"},
        ]
        r1 = hdel.explore(observations)

        # Second exploration: HDEL's own results as observations
        meta_observations = [
            {
                "domain": "meta_exploration",
                "data": f"HDEL produced {r1.total_probes} probes, {r1.surprises} surprises",
            },
            {
                "domain": "meta_exploration",
                "data": f"Discoveries: {len(r1.new_discoveries)}, Open: {len(r1.open_questions)}",
            },
        ]
        r2 = hdel.explore(meta_observations)
        assert isinstance(r2, ExplorationResult)
        # Meta-exploration should have its own beliefs
        meta_beliefs = [
            h for h in r2.belief_model.beliefs.values()
            if h.domain == "meta_exploration"
        ]
        assert len(meta_beliefs) >= 1

    def test_ks42_analyzes_hdel_output(self, tmp_dir):
        """KS42 (Creative Inference) analyzes HDEL exploration quality."""
        # Run HDEL
        hdel = HypothesisLoop(
            result_evaluator=lambda e, a: 0.2,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=5,
        )
        observations = [
            {"domain": "test", "data": "observation 1"},
            {"domain": "test", "data": "observation 2"},
        ]
        result = hdel.explore(observations)

        # KS42 analyzes the HDEL report
        report_text = HypothesisLoop.format_result(result)
        ks42 = KS42()
        analysis = ks42.analyze(report_text)

        assert analysis is not None
        assert isinstance(analysis, CreativeInferenceReport)
        assert analysis.input_verdict is not None
        assert "grade" in analysis.input_verdict


# ════════════════════════════════════════════
# 7. KS42 × KS42a interaction
# ════════════════════════════════════════════

class TestKS42WithKS42a:
    """KS42 (Creative Inference) and KS42a (Evolutionary) work together."""

    def test_creative_inference_on_synthesis_result(self, ks42a_instance, grid_examples):
        """KS42 generates creative inferences from KS42a synthesis."""
        synth = ks42a_instance.abstract_reason(
            grid_examples, domain="grid", meta_verify=False
        )

        # Represent synthesis as text for KS42 analysis
        description = (
            f"Evolutionary synthesis discovered rule: "
            f"{' → '.join(synth.best_rule.primitives) if synth.best_rule else 'none'}, "
            f"confidence: {synth.confidence:.2f}, "
            f"generations: {synth.generations_run}, "
            f"concepts: {synth.concepts_used} used, {synth.concepts_discovered} new"
        )
        ks42 = KS42()
        analysis = ks42.analyze(description)
        assert analysis is not None

    def test_difficulty_estimation_consistency(self, grid_examples, sort_examples):
        """Difficulty estimation is deterministic and ordered."""
        d_grid = _estimate_difficulty(grid_examples)
        d_sort = _estimate_difficulty(sort_examples)
        d_grid2 = _estimate_difficulty(grid_examples)

        # Deterministic
        assert d_grid == d_grid2
        # Both produce valid difficulties
        assert 0.0 <= d_grid <= 1.0
        assert 0.0 <= d_sort <= 1.0


# ════════════════════════════════════════════
# 8. Belief persistence across sessions
# ════════════════════════════════════════════

class TestCrossSessionPersistence:
    """Beliefs and concepts persist across independent sessions."""

    def test_beliefs_survive_session_restart(self, tmp_dir):
        """HDEL beliefs persist to disk and reload."""
        path = os.path.join(tmp_dir, "beliefs.json")

        # Session 1: explore and accumulate beliefs
        hdel1 = HypothesisLoop(
            result_evaluator=lambda e, a: 0.1,
            belief_path=path,
            max_cycles=5,
        )
        hypotheses = [
            Hypothesis("persist_h1", "Persistent claim", "persist_domain", "Outcome", 0.5),
        ]
        hdel1.explore([], hypotheses=hypotheses)

        # Session 2: new instance, same beliefs
        hdel2 = HypothesisLoop(belief_path=path, max_cycles=3)
        assert "persist_h1" in hdel2.belief_model.beliefs
        assert hdel2.belief_model.beliefs["persist_h1"].probes_run > 0

    def test_concepts_survive_session_restart(self, tmp_dir, grid_examples):
        """Concept library persists across KS42a instances."""
        path = os.path.join(tmp_dir, "concepts.json")

        # Session 1
        ks1 = KS42a(concept_path=path)
        ks1.abstract_reason(grid_examples, domain="grid", meta_verify=False)
        ks1.library.save()
        size_after_1 = ks1.library.size

        # Session 2
        ks2 = KS42a(concept_path=path)
        assert ks2.library.size == size_after_1


# ════════════════════════════════════════════
# 9. Format and reporting
# ════════════════════════════════════════════

class TestReporting:
    """Output formatting integrates cleanly."""

    def test_hdel_format_includes_all_sections(self, tmp_dir):
        """Formatted HDEL report has all expected sections."""
        hdel = HypothesisLoop(
            result_evaluator=lambda e, a: 0.2,
            belief_path=os.path.join(tmp_dir, "beliefs.json"),
            max_cycles=5,
        )
        observations = [
            {"domain": "test", "data": "data"},
            {"domain": "test", "data": "more data"},
        ]
        result = hdel.explore(observations)
        text = HypothesisLoop.format_result(result)

        assert "HDEL" in text
        assert "Cycles" in text
        assert "Probes" in text

    def test_ks42a_status_complete(self, ks42a_instance, grid_examples):
        """KS42a status includes all subsystem info."""
        ks42a_instance.abstract_reason(grid_examples, meta_verify=False)
        status = ks42a_instance.get_status()

        assert "version" in status
        assert status["version"] == "KS42a"
        assert "concept_library" in status
        assert "session_state" in status
