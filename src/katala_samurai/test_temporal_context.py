"""Tests for R_temporal Phase 1: Temporal Context Verification."""

import os
import sys
import pytest

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from temporal_context import (
    detect_domain, extract_temporal_signals, estimate_knowledge_year,
    compute_decay, verify_temporal_context, temporal_score_for_ks31,
    format_temporal_verdict, TemporalRisk, TemporalVerdict,
    DOMAIN_HALF_LIFE, REFERENCE_YEAR,
)


# ════════════════════════════════════════════
# Domain Detection
# ════════════════════════════════════════════

class TestDomainDetection:

    def test_ai_domain(self):
        assert detect_domain("GPT-4 is a large language model by OpenAI") == "ai_ml"

    def test_physics_domain(self):
        assert detect_domain("Quantum entanglement violates locality") == "physics"

    def test_economics_domain(self):
        assert detect_domain("GDP growth indicates economic recovery") == "economics"

    def test_software_domain(self):
        assert detect_domain("Python 3.14 deprecated this API in the latest release") == "software"

    def test_unknown_domain(self):
        assert detect_domain("Simple text with no domain keywords") == "unknown"

    def test_sports_domain(self):
        assert detect_domain("The championship tournament ended this season") == "sports"


# ════════════════════════════════════════════
# Temporal Signal Extraction
# ════════════════════════════════════════════

class TestTemporalSignals:

    def test_year_extraction(self):
        signals = extract_temporal_signals("In 2024, GPT-5 was released")
        years = [s for s in signals if s.signal_type == "year"]
        assert len(years) >= 1
        assert years[0].year == 2024

    def test_multiple_years(self):
        signals = extract_temporal_signals("From 2020 to 2025, AI evolved rapidly")
        years = [s for s in signals if s.signal_type == "year"]
        assert len(years) >= 2

    def test_relative_time(self):
        signals = extract_temporal_signals("Currently the best model available")
        relative = [s for s in signals if s.signal_type == "relative"]
        assert len(relative) >= 1

    def test_superlative(self):
        signals = extract_temporal_signals("GPT-4 is the best model")
        superlatives = [s for s in signals if s.signal_type == "superlative"]
        assert len(superlatives) >= 1

    def test_version_number(self):
        signals = extract_temporal_signals("Python v3.14 supports this feature")
        versions = [s for s in signals if s.signal_type == "version"]
        assert len(versions) >= 1

    def test_no_signals(self):
        signals = extract_temporal_signals("Water is composed of hydrogen and oxygen")
        assert len(signals) == 0


# ════════════════════════════════════════════
# Knowledge Year Estimation
# ════════════════════════════════════════════

class TestKnowledgeYear:

    def test_explicit_year(self):
        signals = extract_temporal_signals("In 2023 this was true")
        year = estimate_knowledge_year(signals, "ai_ml")
        assert year == 2023

    def test_relative_time_is_current(self):
        signals = extract_temporal_signals("Currently the standard approach")
        year = estimate_knowledge_year(signals, "software")
        assert year == REFERENCE_YEAR

    def test_timeless_domain_no_signals(self):
        signals = extract_temporal_signals("Euler's identity is remarkable")
        year = estimate_knowledge_year(signals, "mathematics")
        assert year is None  # Timeless

    def test_default_fallback(self):
        signals = extract_temporal_signals("Some AI claim")
        year = estimate_knowledge_year(signals, "ai_ml")
        assert year == 2024  # LLM training cutoff


# ════════════════════════════════════════════
# Decay Function
# ════════════════════════════════════════════

class TestDecay:

    def test_no_age(self):
        assert compute_decay(0, 1.0) == 1.0

    def test_one_half_life(self):
        assert compute_decay(1.0, 1.0) == pytest.approx(0.5, abs=0.01)

    def test_two_half_lives(self):
        assert compute_decay(2.0, 1.0) == pytest.approx(0.25, abs=0.01)

    def test_negative_age(self):
        assert compute_decay(-1.0, 1.0) == 1.0

    def test_long_half_life(self):
        # Physics: half-life 20 years, 2 years old → barely decayed
        d = compute_decay(2.0, 20.0)
        assert d > 0.9


# ════════════════════════════════════════════
# Full Verification
# ════════════════════════════════════════════

class TestTemporalVerification:

    def test_timeless_claim(self):
        v = verify_temporal_context("Water boils at 100 degrees Celsius according to thermodynamic laws")
        assert v.freshness_score > 0.8
        assert v.risk_level in (TemporalRisk.NONE, TemporalRisk.LOW)

    def test_outdated_ai_claim(self):
        v = verify_temporal_context("In 2020, GPT-3 was the most advanced LLM")
        assert v.domain == "ai_ml"
        assert v.freshness_score < 0.3  # 6 years old in AI = very stale
        assert v.risk_level in (TemporalRisk.HIGH, TemporalRisk.CRITICAL)
        assert v.recommendation == "likely_outdated"

    def test_recent_claim(self):
        v = verify_temporal_context(
            f"In {REFERENCE_YEAR}, the system was updated",
            evidence=[f"Release notes {REFERENCE_YEAR}"],
        )
        assert v.freshness_score > 0.7

    def test_superlative_penalty(self):
        v1 = verify_temporal_context("X is the best framework")
        v2 = verify_temporal_context("X is a popular framework")
        # Superlative should get lower freshness
        assert v1.freshness_score <= v2.freshness_score

    def test_math_is_timeless(self):
        v = verify_temporal_context("The Pythagorean theorem states a² + b² = c²")
        assert v.freshness_score >= 0.9
        assert v.risk_level == TemporalRisk.NONE

    def test_format_output(self):
        v = verify_temporal_context("GPT-4 is the best model in 2023")
        text = format_temporal_verdict(v)
        assert "Temporal Context" in text
        assert "Freshness" in text


# ════════════════════════════════════════════
# KS31 Integration
# ════════════════════════════════════════════

class TestKS31Integration:

    def test_ks31_format(self):
        result = temporal_score_for_ks31("Water boils at 100 degrees")
        assert "temporal_freshness" in result
        assert "temporal_risk" in result
        assert "temporal_domain" in result
        assert "recommendation" in result

    def test_ks31_outdated(self):
        result = temporal_score_for_ks31(
            "GPT-3 is the state-of-the-art model in 2020",
            source_llm="gpt-4",
        )
        assert result["temporal_freshness"] < 0.3
        assert result["temporal_risk"] in ("high", "critical")

    def test_ks31_fresh(self):
        result = temporal_score_for_ks31(
            f"Current system status as of {REFERENCE_YEAR}",
            source_llm="claude-opus-4-6",
        )
        assert result["temporal_freshness"] > 0.5
