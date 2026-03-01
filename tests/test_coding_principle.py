#!/usr/bin/env python3
"""Tests for KatalaCodingPrinciple (KCS-CP)."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.katala_coding.coding_principle import (
    CodingPrincipleConfig,
    CodingGate,
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


def test_coding_gate_basic():
    gate = CodingGate(CodingPrincipleConfig(include_kcs_in_coding=False))
    code = '''
def verify(claim):
    """Verify a claim using independent solvers."""
    # Each solver judges only its own domain
    return {"verified": True}
'''
    result = gate.check_code(code)
    assert "CodingGate" in result.gate_name
    assert result.elapsed_ms >= 0
    assert isinstance(result.passed, bool)
    assert len(result.ks_verdicts) >= 1


def test_coding_gate_with_kcs():
    gate = CodingGate()
    code = '''
def hello():
    """Say hello."""
    print("hello")
'''
    result = gate.check_code(code, design_spec="A function that greets the user")
    assert result.kcs_grade is not None
    assert result.kcs_fidelity is not None


def test_text_gate():
    gate = CodingGate(CodingPrincipleConfig(include_kcs_in_coding=False))
    result = gate.check_text("KSは翻訳損失を測定するフレームワークである。33のソルバーが独立に動作する。")
    assert result.gate_name == "TextGate"
    assert len(result.ks_verdicts) >= 1


def test_memory_write_gate():
    gate = MemoryWriteGate()
    content = "ニコラスさんはプロテスタント・ホーリネス教会の有神論者。Youtaは設計者。"
    result = gate.check(content)
    assert result.gate_name == "MemoryWriteGate"
    assert len(result.ks_verdicts) >= 1


def test_unified_principle():
    principle = KatalaCodingPrinciple()
    
    # Code gate
    r1 = principle.gate_code("def f(): pass", design_spec="A no-op function")
    assert "CodingGate" in r1.gate_name
    
    # Text gate
    r2 = principle.gate_text("Katalaは翻訳損失を測定するフレームワークである。")
    assert r2.gate_name == "TextGate"
    
    # Memory gate
    r3 = principle.gate_memory("今日の議論でCoding Principleを実装した。")
    assert r3.gate_name == "MemoryWriteGate"
    
    # Stats
    stats = principle.stats
    assert stats["total"] == 3


def test_format_result():
    principle = KatalaCodingPrinciple()
    result = principle.gate_text("テスト文。KSは検証フレームワーク。")
    formatted = principle.format_result(result)
    assert "TextGate" in formatted
    assert "PASS" in formatted or "BLOCK" in formatted


def test_convenience_functions():
    r1 = gate_code("def f(): pass")
    assert "CodingGate" in r1.gate_name
    
    r2 = gate_text("テスト文。これは検証される。")
    assert r2.gate_name == "TextGate"
    
    r3 = gate_memory("メモリに書き込むテスト内容。十分長い文。")
    assert r3.gate_name == "MemoryWriteGate"


def test_result_summary():
    gate = CodingGate(CodingPrincipleConfig(include_kcs_in_coding=False))
    result = gate.check_code("def f(): pass")
    summary = result.summary
    assert "CodingGate" in summary or "Gate" in summary


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
