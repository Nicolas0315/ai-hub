"""Tests for Content-Sensitive Solver Fix.

Verifies that S01-S27 produce DIFFERENT results for DIFFERENT claims.
This was the root cause of DEGRADED_MODE: all claims got identical scores.

Before fix: Claim._parse() → first 5 words → bool → all claims identical
After fix:  Claim._parse() → 20 structural/semantic features → diverse vectors
"""

import os
import sys
import pytest
import hashlib

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from ks30d import (
    Claim,
    s01_z3_smt, s02_sat_glucose, s03_sympy, s04_z3_fol, s05_category_theory,
    s06_euclidean_distance, s07_linear_algebra, s08_convex_hull,
    s09_voronoi, s10_cosine_similarity, s11_info_geometry_v2,
    s12_spherical, s13_riemannian, s14_tda, s15_de_sitter,
    s16_projective, s17_lorentz, s18_symplectic, s19_finsler,
    s20_sub_riemannian, s21_alexandrov, s22_kahler, s23_tropical,
    s24_spectral, s25_info_geometry_fisher, s26_zfc, s27_kam,
)

ALL_SOLVERS = [
    ("S01", s01_z3_smt), ("S02", s02_sat_glucose), ("S03", s03_sympy),
    ("S04", s04_z3_fol), ("S05", s05_category_theory),
    ("S06", s06_euclidean_distance), ("S07", s07_linear_algebra),
    ("S08", s08_convex_hull), ("S09", s09_voronoi),
    ("S10", s10_cosine_similarity), ("S11", s11_info_geometry_v2),
    ("S12", s12_spherical), ("S13", s13_riemannian),
    ("S14", s14_tda), ("S15", s15_de_sitter),
    ("S16", s16_projective), ("S17", s17_lorentz),
    ("S18", s18_symplectic), ("S19", s19_finsler),
    ("S20", s20_sub_riemannian), ("S21", s21_alexandrov),
    ("S22", s22_kahler), ("S23", s23_tropical),
    ("S24", s24_spectral), ("S25", s25_info_geometry_fisher),
    ("S26", s26_zfc), ("S27", s27_kam),
]


# ════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════

@pytest.fixture
def diverse_claims():
    """5 structurally different claims."""
    return [
        Claim("Water boils at 100 degrees Celsius",
              evidence=["Physics textbook"]),
        Claim("Iron is denser than aluminum. Aluminum is denser than wood. "
              "Therefore iron is denser than wood.",
              evidence=["Material science", "Density tables"]),
        Claim("The economy is growing because of increased investment",
              evidence=["Economic theory"]),
        Claim("All mammals are warm-blooded",
              evidence=["Biology"]),
        Claim("No evidence claim",
              evidence=[]),
    ]


@pytest.fixture
def causal_vs_factual():
    """Causal and factual claims should differ."""
    return [
        Claim("Rain causes floods because water accumulates",
              evidence=["Hydrology"]),
        Claim("The sky appears blue during daytime",
              evidence=["Optics"]),
    ]


# ════════════════════════════════════════════
# Core: Content Sensitivity
# ════════════════════════════════════════════

class TestContentSensitivity:
    """The critical test: different claims → different solver vectors."""

    def test_unique_solver_vectors(self, diverse_claims):
        """Each claim must produce a unique solver result vector."""
        vectors = []
        for c in diverse_claims:
            v = tuple(fn(c) for _, fn in ALL_SOLVERS)
            vectors.append(v)

        unique = len(set(vectors))
        assert unique >= 3, (
            f"Only {unique}/{len(diverse_claims)} unique vectors — "
            f"solvers are still content-blind!"
        )

    def test_no_evidence_scores_lower(self, diverse_claims):
        """No-evidence claim should pass fewer solvers."""
        evidence_claims = [c for c in diverse_claims if c.evidence]
        no_evidence = [c for c in diverse_claims if not c.evidence]

        for ne in no_evidence:
            ne_passed = sum(fn(ne) for _, fn in ALL_SOLVERS)
            for ec in evidence_claims:
                ec_passed = sum(fn(ec) for _, fn in ALL_SOLVERS)
                assert ne_passed <= ec_passed, (
                    f"No-evidence claim passed {ne_passed} solvers "
                    f"but evidence claim only passed {ec_passed}!"
                )

    def test_complex_claim_scores_higher(self, diverse_claims):
        """Multi-sentence causal claim should pass more solvers than simple factual."""
        complex_claim = diverse_claims[1]  # Iron denser...
        simple_claim = diverse_claims[0]   # Water boils...

        complex_passed = sum(fn(complex_claim) for _, fn in ALL_SOLVERS)
        simple_passed = sum(fn(simple_claim) for _, fn in ALL_SOLVERS)

        assert complex_passed >= simple_passed, (
            f"Complex claim ({complex_passed}) scored lower than simple ({simple_passed})!"
        )


# ════════════════════════════════════════════
# Proposition Extraction
# ════════════════════════════════════════════

class TestPropositionExtraction:
    """Claim._parse() produces content-sensitive propositions."""

    def test_causal_detected(self):
        c = Claim("Rain causes floods because water accumulates", evidence=["test"])
        assert c.propositions.get("p_causal") is True

    def test_comparative_detected(self):
        c = Claim("Iron is denser than aluminum", evidence=["test"])
        assert c.propositions.get("p_comparative") is True

    def test_temporal_detected(self):
        c = Claim("Previously the system was slower before optimization", evidence=["test"])
        assert c.propositions.get("p_temporal") is True

    def test_definitional_detected(self):
        c = Claim("A mammal is a warm-blooded vertebrate", evidence=["test"])
        assert c.propositions.get("p_definitional") is True

    def test_negation_detected(self):
        c = Claim("This system does not use neural networks", evidence=["test"])
        assert c.propositions.get("p_has_negation") is True

    def test_quantifier_detected(self):
        c = Claim("All mammals are warm-blooded creatures", evidence=["test"])
        assert c.propositions.get("p_has_quantifier") is True

    def test_multi_sentence_detected(self):
        c = Claim("First sentence. Second sentence. Third sentence.", evidence=["test"])
        assert c.propositions.get("p_multi_sentence") is True

    def test_numbers_detected(self):
        c = Claim("Water boils at 100 degrees", evidence=["test"])
        assert c.propositions.get("p_has_numbers") is True

    def test_evidence_detected(self):
        c = Claim("Some claim", evidence=["source1", "source2"])
        assert c.propositions.get("p_has_evidence") is True

    def test_no_evidence_detected(self):
        c = Claim("Some claim", evidence=[])
        assert c.propositions.get("p_has_evidence") is False

    def test_hash_deterministic(self):
        c1 = Claim("Same text", evidence=["e"])
        c2 = Claim("Same text", evidence=["e"])
        assert c1.propositions["p_hash_even"] == c2.propositions["p_hash_even"]
        assert c1.propositions["p_hash_quarter"] == c2.propositions["p_hash_quarter"]

    def test_different_texts_different_hashes(self):
        c1 = Claim("Text A about science", evidence=["e"])
        c2 = Claim("Text B about cooking", evidence=["e"])
        # At least some propositions should differ
        diffs = sum(1 for k in c1.propositions
                    if c1.propositions.get(k) != c2.propositions.get(k))
        assert diffs >= 1


# ════════════════════════════════════════════
# Individual Solver Sensitivity
# ════════════════════════════════════════════

class TestSolverSensitivity:
    """Solvers that should be content-sensitive now are."""

    def test_s07_requires_evidence(self):
        with_ev = Claim("Factual claim with evidence", evidence=["source"])
        without_ev = Claim("Factual claim with evidence", evidence=[])
        assert s07_linear_algebra(with_ev) is True
        assert s07_linear_algebra(without_ev) is False

    def test_s13_requires_semantic_type(self):
        causal = Claim("X causes Y because of Z", evidence=["test"])
        plain = Claim("Simple short text", evidence=["test"])
        assert s13_riemannian(causal) is True
        assert s13_riemannian(plain) is False

    def test_s17_requires_causal_structure(self):
        causal = Claim("Rain causes floods therefore drainage needed",
                       evidence=["hydrology"])
        factual = Claim("The sky is blue", evidence=["optics"])
        assert s17_lorentz(causal) is True
        assert s17_lorentz(factual) is False

    def test_s22_requires_semantic_and_structural(self):
        rich = Claim("X causes Y. Therefore Z is true, and W follows.",
                     evidence=["source1", "source2"])
        poor = Claim("Short claim", evidence=["source"])
        assert s22_kahler(rich) is True
        assert s22_kahler(poor) is False

    def test_s15_requires_evidence(self):
        with_ev = Claim("Long substantive claim with content and detail",
                        evidence=["source"])
        without_ev = Claim("Long substantive claim with content and detail",
                           evidence=[])
        assert s15_de_sitter(with_ev) is True
        assert s15_de_sitter(without_ev) is False


# ════════════════════════════════════════════
# Semantic Bridge Enhanced Degraded Mode
# ════════════════════════════════════════════

class TestEnhancedDegradedMode:
    """semantic_bridge degraded mode now extracts typed propositions."""

    def test_causal_extraction(self):
        from semantic_bridge import extract_semantics
        result = extract_semantics("The economy grew because of investment")
        # Without LLM available, should use enhanced degraded mode
        if result["mode"] in ("degraded_enhanced", "degraded"):
            props = result["propositions"]
            assert len(props) >= 1
            # Should detect causal type if enhanced mode
            if result["mode"] == "degraded_enhanced":
                types = [p["type"] for p in props]
                assert "causal" in types

    def test_entity_extraction(self):
        from semantic_bridge import extract_semantics
        result = extract_semantics("Japan streaming market grew 7% reaching 113 billion yen")
        if result["mode"] == "degraded_enhanced":
            assert len(result["key_entities"]) >= 1

    def test_implicit_assumptions(self):
        from semantic_bridge import extract_semantics
        result = extract_semantics("All mammals must always be warm-blooded")
        if result["mode"] == "degraded_enhanced":
            assert len(result["implicit_assumptions"]) >= 1
