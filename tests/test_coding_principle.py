#!/usr/bin/env python3
"""Tests for KatalaCodingPrinciple (KCS-CP)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.katala_coding.coding_principle import (
    CodingPrincipleConfig,
    GateLevel,
    GateStage,
    KCSGate,
    KSClaimsGate,
    MemoryWriteGate,
    KatalaCodingPrinciple,
    extract_code_claims,
    extract_text_claims,
    gate_code,
    gate_memory,
    gate_text,
)


def test_extract_code_claims_docstring():
    code = '''
def foo():
    """This function calculates the translation loss between layers."""
    pass
'''
    claims = extract_code_claims(code)
    assert len(claims) >= 1
    assert any("translation loss" in c for c in claims)


def test_extract_code_claims_comments():
    code = '''
# KS42c uses 33 independent solvers for verification
x = compute()
# Short
'''
    claims = extract_code_claims(code)
    assert len(claims) >= 1
    assert any("33 independent solvers" in c for c in claims)


def test_extract_code_claims_assert():
    code = '''
assert score > 0.5, "Score must exceed threshold for verification"
'''
    claims = extract_code_claims(code)
    assert len(claims) >= 1


def test_extract_text_claims():
    text = "KSは33のソルバーを使用する。翻訳損失を独立に測定する仕組みである。短い。"
    claims = extract_text_claims(text)
    assert len(claims) >= 2  # "短い" is too short (<=10 chars)


def test_config_grade_passes():
    config = CodingPrincipleConfig(kcs_min_grade="C")
    assert config.grade_passes("S")
    assert config.grade_passes("A")
    assert config.grade_passes("B")
    assert config.grade_passes("C")
    assert not config.grade_passes("D")
    assert not config.grade_passes("F")


def test_config_grade_passes_strict():
    config = CodingPrincipleConfig(kcs_min_grade="A")
    assert config.grade_passes("S")
    assert config.grade_passes("A")
    assert not config.grade_passes("B")


def test_kcs_gate_basic():
    gate = KCSGate(CodingPrincipleConfig())
    code = '''
def verify(claim):
    """Verify a claim using independent solvers."""
    # Each solver judges only its own domain
    return {"verified": True}
'''
    result = gate.check(code, design_spec="verify claim with independent checks")
    assert result.gate_stage == GateStage.KCS_STRUCTURE
    assert result.elapsed_ms >= 0
    assert isinstance(result.passed, bool)
    assert result.kcs_version in {"KCS-1b", "KCS-1a", "NONE"}


def test_kcs_gate_with_design_spec():
    gate = KCSGate(CodingPrincipleConfig())
    code = '''
def hello():
    """Say hello."""
    print("hello")
'''
    result = gate.check(code, design_spec="A function that greets the user")
    assert result.gate_stage == GateStage.KCS_STRUCTURE
    assert result.kcs_grade is None or result.kcs_grade in {"S", "A", "B", "C", "D", "F"}
    assert result.kcs_fidelity is None or 0.0 <= result.kcs_fidelity <= 1.0


def test_ksclaims_text_gate():
    gate = KSClaimsGate(CodingPrincipleConfig())
    result = gate.check_text("KSは翻訳損失を測定するフレームワークである。33のソルバーが独立に動作する。")
    assert result.gate_stage == GateStage.TEXT_CLAIMS
    assert result.gate_level in {GateLevel.ADVISORY, GateLevel.MANDATORY}


def test_memory_write_gate():
    gate = MemoryWriteGate(CodingPrincipleConfig())
    content = "ニコラスさんはプロテスタント・ホーリネス教会の有神論者。Youtaは設計者。"
    result = gate.check(content)
    assert result.gate_stage == GateStage.MEMORY_BIAS
    assert result.gate_level in {GateLevel.ADVISORY, GateLevel.MANDATORY}


def test_unified_principle():
    principle = KatalaCodingPrinciple()

    # Code gate
    r1 = principle.gate_code("def f(): pass", design_spec="A no-op function")
    assert len(r1.gate_results) == 2

    # Text gate
    r2 = principle.gate_text("Katalaは翻訳損失を測定するフレームワークである。")
    assert r2.gate_stage == GateStage.TEXT_CLAIMS

    # Memory gate
    r3 = principle.gate_memory("今日の議論でCoding Principleを実装した。")
    assert r3.gate_stage == GateStage.MEMORY_BIAS

    # Stats
    stats = principle.stats
    assert stats["total_pipeline_runs"] == 1
    assert stats["total_gate_runs"] == 2


def test_format_result():
    principle = KatalaCodingPrinciple()
    result = principle.gate_text("テスト文。KSは検証フレームワーク。")
    formatted = principle.format_result(result)
    assert "Gate4_Text_Claims" in formatted
    assert any(token in formatted for token in ("✅", "⚠️", "🚫"))


def test_convenience_functions():
    r1 = gate_code("def f(): pass")
    assert len(r1.gate_results) == 2

    r2 = gate_text("テスト文。これは検証される。")
    assert r2.gate_stage == GateStage.TEXT_CLAIMS

    r3 = gate_memory("メモリに書き込むテスト内容。十分長い文。")
    assert r3.gate_stage == GateStage.MEMORY_BIAS


def test_result_summary():
    gate = KCSGate(CodingPrincipleConfig())
    result = gate.check("def f(): pass", design_spec="no-op function")
    summary = result.summary
    assert "Gate1_KCS_Structure" in summary


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} tests passed")
