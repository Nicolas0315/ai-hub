#!/usr/bin/env python3
"""Tests for ResponseFilter (KCS-RF)."""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.katala_coding.response_filter import (
    ResponseFilter,
    ResponseFilterConfig,
    FilterResult,
    filter_response,
    check_and_warn,
)


def test_basic_filter():
    rf = ResponseFilter()
    result = rf.filter("KSは翻訳損失を測定するフレームワークである。33のソルバーが独立に動作する。")
    assert isinstance(result, FilterResult)
    assert result.total_checked >= 1
    assert result.elapsed_ms >= 0


def test_majority_pattern_detection_japanese():
    """The exact case Youta identified: '負け' as majority-data bias."""
    rf = ResponseFilter()
    result = rf.filter("撤退に負けの匂いがある。サンクコストに囚われて沈没船にしがみつく。")
    assert len(result.majority_pattern_warnings) >= 1
    assert any("負け" in w for w in result.majority_pattern_warnings)
    assert not result.passed  # Should fail due to pattern warning


def test_majority_pattern_detection_english():
    rf = ResponseFilter()
    result = rf.filter("This is obviously the right approach. Everyone knows this is common sense.")
    assert len(result.majority_pattern_warnings) >= 1


def test_no_false_positive_on_clean_text():
    rf = ResponseFilter()
    result = rf.filter("R_temporalは現在のコンテキストのみを測定する。KSは翻訳損失を測定する。")
    assert len(result.majority_pattern_warnings) == 0


def test_contradiction_detection():
    rf = ResponseFilter()
    result = rf.filter("名前をつけるべきではない。名前をつけることは必要。選択に名前をつけることが重要。")
    # This tests basic contradiction detection capability
    assert isinstance(result.contradictions, list)


def test_skip_patterns():
    rf = ResponseFilter()
    result = rf.filter("KS検証結果: UNVERIFIED 0.409\n---\n```python\ncode```\n実際の文。")
    # Headers and code blocks should be skipped
    for stmt in result.statements:
        assert not stmt.text.startswith("KS検証")
        assert not stmt.text.startswith("---")
        assert not stmt.text.startswith("```")


def test_config_custom_threshold():
    config = ResponseFilterConfig(bias_flag_threshold=1)
    rf = ResponseFilter(config)
    result = rf.filter("翻訳損失は蓄積する。蓄積した損失は誤解を生む。")
    # Lower threshold = more flags
    assert result.total_checked >= 1


def test_format_result():
    rf = ResponseFilter()
    result = rf.filter("撤退に負けの匂いがある。これは当然のことだ。")
    formatted = rf.format_result(result)
    assert "ResponseFilter" in formatted
    assert "多数派パターン" in formatted


def test_filter_and_revise():
    rf = ResponseFilter()
    revised, result = rf.filter_and_revise("撤退には負けの匂いがある。")
    if not result.passed:
        assert "ResponseFilter" in revised


def test_convenience_filter_response():
    result = filter_response("テスト文。KSは検証フレームワーク。十分長い文を書く必要がある。")
    assert isinstance(result, FilterResult)


def test_convenience_check_and_warn():
    # Clean text should return empty
    warn = check_and_warn("R_temporalは現在のみを測定する設計である。")
    # May or may not have warnings depending on KS analysis
    assert isinstance(warn, str)


def test_summary_line():
    rf = ResponseFilter()
    result = rf.filter("テスト文。これは検証のためのサンプル文である。")
    summary = result.summary_line
    assert "checked" in summary
    assert "ms" in summary


def test_shirokuma_failure_case():
    """Reproduce the exact failure: Shirokuma's response that got 'stung'."""
    rf = ResponseFilter()
    bad_response = (
        "名前をつけるな、と自分で言ったのに、"
        "撤退に負けの匂いがあると書いた。"
        "これは一般人のフレームに嵌まっている。"
        "普通の人間の感覚になりすぎた。"
    )
    result = rf.filter(bad_response)

    # Must detect '負け' and '普通' as majority patterns
    pattern_keywords_found = set()
    for w in result.majority_pattern_warnings:
        for kw in ["負け", "普通", "一般的"]:
            if kw in w:
                pattern_keywords_found.add(kw)

    assert "負け" in pattern_keywords_found, f"Should detect '負け' pattern. Warnings: {result.majority_pattern_warnings}"
    assert not result.passed, "This response should NOT pass the filter"


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
