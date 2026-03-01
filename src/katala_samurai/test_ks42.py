"""
Tests for KS42 — Creative Inference Engine

Combines property-based testing (Hypothesis) with traditional unit tests.
Property-based tests encode the *specification*, not the implementation,
so they survive refactors better (as KS42 itself recommended).

Design: Youta Hilono
Implementation: Shirokuma (OpenClaw AI)
"""

from __future__ import annotations

import math
import pytest

try:
    from hypothesis import given, settings, assume
    from hypothesis import strategies as st
    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False

import sys, os
_dir = os.path.dirname(os.path.abspath(__file__))
_src = os.path.dirname(_dir)
if _dir not in sys.path:
    sys.path.insert(0, _dir)
if _src not in sys.path:
    sys.path.insert(0, _src)

from ks42 import (
    KS42, LossVector, CreativeSolution, CreativeInferenceReport,
    AxisConflict, Donor, AXES, AXIS_LABELS,
    _classify_loss_pattern, _find_donors, _explore_voids,
    _detect_conflicts, _synthesize_paradox, _project_temporal,
    _compute_tension, _semantic_tension, _generate_leap_solution,
    LOSS_THRESHOLD, LEAP_MIN_DONOR_SCORE, NOVELTY_TRIVIAL,
)


# ════════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════════

SAMPLE_CODE = '''
def calculate_price(items, tax_rate=0.1):
    """Calculate total price with tax."""
    total = 0
    for item in items:
        total += item["price"] * item["quantity"]
    return total * (1 + tax_rate)
'''

SAMPLE_DESIGN = '''
A pricing engine that calculates total cost with tax.
Should support multiple tax jurisdictions and discount codes.
Must be extensible for future payment methods.
'''

SAMPLE_CORPUS = [
    {
        "name": "module_a",
        "loss_vector": {"r_struct": 0.90, "r_context": 0.85, "r_qualia": 0.80,
                        "r_cultural": 0.88, "r_temporal": 0.82},
        "features": {"classes": 2, "functions": 8},
    },
    {
        "name": "module_b",
        "loss_vector": {"r_struct": 0.70, "r_context": 0.60, "r_qualia": 0.90,
                        "r_cultural": 0.40, "r_temporal": 0.55},
        "features": {"classes": 0, "functions": 3},
    },
]


@pytest.fixture
def ks42():
    return KS42()


@pytest.fixture
def high_lv():
    return LossVector(0.90, 0.85, 0.88, 0.82, 0.91)


@pytest.fixture
def low_lv():
    return LossVector(0.40, 0.35, 0.30, 0.25, 0.45)


@pytest.fixture
def single_drop_lv():
    return LossVector(0.85, 0.80, 0.30, 0.82, 0.88)


@pytest.fixture
def conflict_lv():
    return LossVector(0.55, 0.80, 0.58, 0.80, 0.85)


# ════════════════════════════════════════════════════════════════
# LossVector Tests
# ════════════════════════════════════════════════════════════════

class TestLossVector:

    def test_from_tuple(self):
        lv = LossVector(0.9, 0.8, 0.7, 0.6, 0.5)
        assert lv.as_tuple() == (0.9, 0.8, 0.7, 0.6, 0.5)

    def test_magnitude_perfect(self):
        lv = LossVector(1.0, 1.0, 1.0, 1.0, 1.0)
        assert lv.magnitude() == pytest.approx(0.0, abs=1e-9)

    def test_magnitude_worst(self):
        lv = LossVector(0.0, 0.0, 0.0, 0.0, 0.0)
        assert lv.magnitude() == pytest.approx(math.sqrt(5), abs=1e-6)

    def test_mean(self):
        lv = LossVector(0.8, 0.6, 0.4, 0.2, 1.0)
        assert lv.mean() == pytest.approx(0.6, abs=1e-9)

    def test_dominant_loss_axis(self, single_drop_lv):
        assert single_drop_lv.dominant_loss_axis() == "r_qualia"

    def test_void_dimensions_none(self, high_lv):
        assert high_lv.void_dimensions() == []

    def test_void_dimensions_multiple(self, low_lv):
        voids = low_lv.void_dimensions()
        assert len(voids) >= 3
        assert all(low_lv.axis_score(v) < LOSS_THRESHOLD for v in voids)

    def test_distance_to_self(self, high_lv):
        assert high_lv.distance_to(high_lv) == pytest.approx(0.0, abs=1e-9)

    def test_distance_symmetry(self, high_lv, low_lv):
        assert high_lv.distance_to(low_lv) == pytest.approx(
            low_lv.distance_to(high_lv), abs=1e-9
        )

    def test_axis_score(self):
        lv = LossVector(0.1, 0.2, 0.3, 0.4, 0.5)
        assert lv.axis_score("r_struct") == 0.1
        assert lv.axis_score("r_temporal") == 0.5

    def test_static_constructor(self):
        lv = KS42.loss_vector(r_struct=0.9, r_qualia=0.4)
        assert lv.r_struct == 0.9
        assert lv.r_qualia == 0.4
        assert lv.r_context == 0.5  # default


# ════════════════════════════════════════════════════════════════
# Pattern Classification Tests
# ════════════════════════════════════════════════════════════════

class TestPatternClassification:

    def test_single_axis_drop(self, single_drop_lv):
        assert _classify_loss_pattern(single_drop_lv) == "single_axis_drop"

    def test_multi_axis_void(self, low_lv):
        assert _classify_loss_pattern(low_lv) == "multi_axis_void"

    def test_temporal_decay(self):
        lv = LossVector(0.80, 0.85, 0.75, 0.78, 0.35)
        assert _classify_loss_pattern(lv) == "temporal_decay"

    def test_axis_conflict(self, conflict_lv):
        result = _classify_loss_pattern(conflict_lv)
        assert result in ("axis_conflict", "single_axis_drop", "mixed")

    def test_healthy_code_mixed(self, high_lv):
        # High scores → no strong pattern → mixed
        result = _classify_loss_pattern(high_lv)
        assert result == "mixed"


# ════════════════════════════════════════════════════════════════
# Cross-Axis Leap Tests
# ════════════════════════════════════════════════════════════════

class TestCrossAxisLeap:

    def test_find_donors_returns_sorted(self):
        corpus = [
            {"name": "a", "loss_vector": {"r_struct": 0.60, "r_context": 0.50,
             "r_qualia": 0.90, "r_cultural": 0.70, "r_temporal": 0.80}},
            {"name": "b", "loss_vector": {"r_struct": 0.70, "r_context": 0.60,
             "r_qualia": 0.95, "r_cultural": 0.80, "r_temporal": 0.85}},
        ]
        donors = _find_donors("r_qualia", LossVector(0.8, 0.8, 0.3, 0.8, 0.8), corpus)
        assert len(donors) == 2
        assert donors[0].donor_score >= donors[1].donor_score

    def test_find_donors_filters_below_threshold(self):
        corpus = [
            {"name": "weak", "loss_vector": {"r_struct": 0.40, "r_context": 0.40,
             "r_qualia": 0.40, "r_cultural": 0.40, "r_temporal": 0.40}},
        ]
        donors = _find_donors("r_struct", LossVector(0.3, 0.3, 0.3, 0.3, 0.3), corpus)
        assert len(donors) == 0

    def test_generate_leap_solution_structure(self):
        donor = Donor("test_mod", "r_qualia", 0.90,
                      LossVector(0.8, 0.8, 0.9, 0.7, 0.8))
        sol = _generate_leap_solution("r_qualia", donor, 0.40)
        assert sol.mechanism == "cross_axis_leap"
        assert sol.target_axis == "r_qualia"
        assert "r_qualia" in sol.predicted_improvement
        assert sol.predicted_improvement["r_qualia"] > 0.40
        assert len(sol.reasoning_chain) >= 3


# ════════════════════════════════════════════════════════════════
# Void Exploration Tests
# ════════════════════════════════════════════════════════════════

class TestVoidExploration:

    def test_no_voids_returns_empty(self, high_lv):
        assert _explore_voids(high_lv, []) == []

    def test_single_void_returns_solution(self):
        lv = LossVector(0.80, 0.85, 0.30, 0.82, 0.88)
        sols = _explore_voids(lv, [])
        assert len(sols) >= 1
        assert any(s.target_axis == "r_qualia" for s in sols)

    def test_multi_void_returns_unified_solution(self, low_lv):
        sols = _explore_voids(low_lv, [])
        unified = [s for s in sols if "統合" in s.description or "同時" in s.description]
        assert len(unified) >= 1

    def test_covered_void_has_higher_confidence(self):
        lv = LossVector(0.80, 0.85, 0.30, 0.82, 0.88)
        corpus_with = [{"name": "helper", "loss_vector": {
            "r_struct": 0.5, "r_context": 0.5, "r_qualia": 0.95,
            "r_cultural": 0.5, "r_temporal": 0.5
        }}]
        sols_with = _explore_voids(lv, corpus_with)
        sols_without = _explore_voids(lv, [])
        # Covered void should have higher confidence
        conf_with = max(s.confidence for s in sols_with if s.target_axis == "r_qualia")
        conf_without = max(s.confidence for s in sols_without if s.target_axis == "r_qualia")
        assert conf_with >= conf_without


# ════════════════════════════════════════════════════════════════
# Paradox Synthesis Tests
# ════════════════════════════════════════════════════════════════

class TestParadoxSynthesis:

    def test_indeterminate_generates_solution(self):
        conflict = AxisConflict("r_struct", "r_qualia", 0.40, "indeterminate")
        lv = LossVector(0.55, 0.80, 0.58, 0.80, 0.85)
        sol = _synthesize_paradox(conflict, lv)
        assert sol is not None
        assert sol.mechanism == "paradox_synthesis"
        assert "三値論理" in sol.description

    def test_non_indeterminate_returns_none(self):
        conflict = AxisConflict("r_struct", "r_qualia", 0.40, "true_a")
        lv = LossVector(0.80, 0.80, 0.50, 0.80, 0.85)
        sol = _synthesize_paradox(conflict, lv)
        assert sol is None

    def test_synthesis_predicts_both_axes_improve(self):
        conflict = AxisConflict("r_struct", "r_qualia", 0.35, "indeterminate")
        lv = LossVector(0.55, 0.80, 0.58, 0.80, 0.85)
        sol = _synthesize_paradox(conflict, lv)
        assert sol.predicted_improvement["r_struct"] > 0.55
        assert sol.predicted_improvement["r_qualia"] > 0.58


# ════════════════════════════════════════════════════════════════
# Temporal Projection Tests
# ════════════════════════════════════════════════════════════════

class TestTemporalProjection:

    def test_healthy_returns_empty(self):
        lv = LossVector(0.80, 0.85, 0.75, 0.78, 0.90)
        assert _project_temporal(lv, []) == []

    def test_no_tests_detected(self):
        lv = LossVector(0.80, 0.85, 0.75, 0.78, 0.50)
        sols = _project_temporal(lv, ["No test files found"])
        assert any("test" in s.description.lower() or "テスト" in s.description for s in sols)

    def test_global_state_detected(self):
        lv = LossVector(0.80, 0.85, 0.75, 0.78, 0.50)
        sols = _project_temporal(lv, ["Global state: 15 module-level variables"])
        assert any("グローバル" in s.description or "global" in s.description.lower() for s in sols)

    def test_general_low_temporal(self):
        lv = LossVector(0.80, 0.85, 0.75, 0.78, 0.45)
        sols = _project_temporal(lv, [])
        assert len(sols) >= 1


# ════════════════════════════════════════════════════════════════
# Tension / Conflict Detection Tests
# ════════════════════════════════════════════════════════════════

class TestTension:

    def test_semantic_tension_known_pair(self):
        t = _semantic_tension("r_struct", "r_qualia")
        assert t == 0.35

    def test_semantic_tension_unknown_pair(self):
        t = _semantic_tension("r_struct", "r_temporal")
        assert t == 0.05

    def test_compute_tension_sparse_falls_back(self):
        scores = {"r_struct": [0.5], "r_qualia": [0.6]}  # < 3 values
        t = _compute_tension("r_struct", "r_qualia", scores)
        assert t == _semantic_tension("r_struct", "r_qualia")

    def test_compute_tension_positive_correlation(self):
        # Positive correlation → 0 tension
        scores = {
            "r_struct": [0.3, 0.5, 0.7, 0.9],
            "r_qualia": [0.3, 0.5, 0.7, 0.9],
        }
        t = _compute_tension("r_struct", "r_qualia", scores)
        assert t == pytest.approx(0.0, abs=0.01)

    def test_compute_tension_negative_correlation(self):
        # Negative correlation → high tension
        scores = {
            "r_struct": [0.3, 0.5, 0.7, 0.9],
            "r_qualia": [0.9, 0.7, 0.5, 0.3],
        }
        t = _compute_tension("r_struct", "r_qualia", scores)
        assert t > 0.8


# ════════════════════════════════════════════════════════════════
# Integration: KS42.infer()
# ════════════════════════════════════════════════════════════════

class TestKS42Integration:

    def test_infer_returns_report(self, ks42):
        report = ks42.infer(code=SAMPLE_CODE, design=SAMPLE_DESIGN)
        assert isinstance(report, CreativeInferenceReport)
        assert report.version == "KS42"

    def test_infer_with_corpus(self, ks42):
        report = ks42.infer(code=SAMPLE_CODE, design=SAMPLE_DESIGN,
                            corpus=SAMPLE_CORPUS)
        assert report.loss_map is not None
        assert report.pattern in (
            "single_axis_drop", "multi_axis_void",
            "axis_conflict", "temporal_decay", "mixed"
        )

    def test_solutions_have_required_fields(self, ks42):
        report = ks42.infer(code=SAMPLE_CODE, design=SAMPLE_DESIGN,
                            corpus=SAMPLE_CORPUS)
        for sol in report.solutions:
            assert sol.mechanism in (
                "cross_axis_leap", "void_exploration",
                "paradox_synthesis", "temporal_projection"
            )
            assert sol.target_axis in AXES
            assert 0.0 <= sol.confidence <= 1.0
            assert 0.0 <= sol.novelty_score <= 1.0
            assert len(sol.reasoning_chain) >= 1

    def test_verified_subset_of_solutions(self, ks42):
        report = ks42.infer(code=SAMPLE_CODE, design=SAMPLE_DESIGN,
                            corpus=SAMPLE_CORPUS)
        for v in report.verified_solutions:
            assert v in report.solutions

    def test_format_report_returns_string(self, ks42):
        report = ks42.infer(code=SAMPLE_CODE, design=SAMPLE_DESIGN)
        text = KS42.format_report(report)
        assert isinstance(text, str)
        assert "KS42" in text

    def test_analyze_alias(self, ks42):
        report = ks42.analyze(SAMPLE_CODE, SAMPLE_DESIGN)
        assert isinstance(report, CreativeInferenceReport)

    def test_quick_report(self, ks42):
        text = ks42.quick_report(SAMPLE_CODE, SAMPLE_DESIGN)
        assert "KS42" in text
        assert "Grade" in text


# ════════════════════════════════════════════════════════════════
# Self-Referential Test: KS42 analyzes itself
# ════════════════════════════════════════════════════════════════

class TestSelfReference:

    def test_ks42_can_analyze_itself(self, ks42):
        """KS42 must be able to analyze its own source code without crashing."""
        with open(os.path.join(_dir, "ks42.py")) as f:
            own_code = f.read()

        report = ks42.infer(
            code=own_code,
            design="KS42 Creative Inference Engine: loss space as exploration space",
        )
        assert report.version == "KS42"
        assert report.loss_map.magnitude() < 2.0  # Not catastrophically bad
        assert report.input_verdict["grade"] in ("S", "A", "B", "C", "D", "F")

    def test_self_analysis_is_stable(self, ks42):
        """Running self-analysis twice produces consistent results."""
        with open(os.path.join(_dir, "ks42.py")) as f:
            own_code = f.read()

        r1 = ks42.infer(code=own_code, design="KS42")
        r2 = ks42.infer(code=own_code, design="KS42")

        assert r1.input_verdict["grade"] == r2.input_verdict["grade"]
        assert r1.pattern == r2.pattern
        assert r1.loss_map.magnitude() == pytest.approx(
            r2.loss_map.magnitude(), abs=0.01
        )


# ════════════════════════════════════════════════════════════════
# Property-Based Tests (Hypothesis)
# ════════════════════════════════════════════════════════════════

if HAS_HYPOTHESIS:
    # Strategy for valid axis scores (0.0–1.0)
    score = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

    class TestLossVectorProperties:

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_magnitude_bounded(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            assert 0.0 <= lv.magnitude() <= math.sqrt(5) + 1e-9

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_mean_bounded(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            assert 0.0 <= lv.mean() <= 1.0

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_dominant_loss_is_valid_axis(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            assert lv.dominant_loss_axis() in AXES

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_void_dimensions_all_below_threshold(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            for v in lv.void_dimensions():
                assert lv.axis_score(v) < LOSS_THRESHOLD

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_distance_to_self_is_zero(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            assert lv.distance_to(lv) == pytest.approx(0.0, abs=1e-9)

        @given(s1=score, c1=score, q1=score, cu1=score, t1=score,
               s2=score, c2=score, q2=score, cu2=score, t2=score)
        @settings(max_examples=50)
        def test_triangle_inequality(self, s1, c1, q1, cu1, t1,
                                     s2, c2, q2, cu2, t2):
            a = LossVector(s1, c1, q1, cu1, t1)
            b = LossVector(s2, c2, q2, cu2, t2)
            origin = LossVector(0.5, 0.5, 0.5, 0.5, 0.5)
            # Triangle inequality: d(a,b) <= d(a,o) + d(o,b)
            assert a.distance_to(b) <= a.distance_to(origin) + origin.distance_to(b) + 1e-9

    class TestPatternClassificationProperties:

        @given(s=score, c=score, q=score, cu=score, t=score)
        @settings(max_examples=50)
        def test_always_returns_valid_pattern(self, s, c, q, cu, t):
            lv = LossVector(s, c, q, cu, t)
            pattern = _classify_loss_pattern(lv)
            assert pattern in (
                "single_axis_drop", "multi_axis_void",
                "axis_conflict", "temporal_decay", "mixed"
            )

    class TestTensionProperties:

        @given(
            vals=st.lists(
                st.tuples(score, score),
                min_size=4, max_size=20,
            )
        )
        @settings(max_examples=30)
        def test_tension_bounded(self, vals):
            a_vals = [v[0] for v in vals]
            b_vals = [v[1] for v in vals]
            scores = {"ax_a": a_vals, "ax_b": b_vals}
            t = _compute_tension("ax_a", "ax_b", scores)
            assert 0.0 <= t <= 1.0 + 1e-9
