#!/usr/bin/env python3
"""
Katala Response Filter — KCS-RF
会話応答をKS検証してから出力するフィルタ。

設計: Youta Hilono ("刺さったのはKS通してないからでしょ")
実装: Shirokuma (OpenClaw AI), 2026-03-02

問題:
  しろくまの会話応答がKS未検証のまま出力されると:
  1. 学習データの多数派パターン(バイアス)がそのまま出る
  2. 感情ラベルの暗黙的な付与に気づかない
  3. 自分の回答内の矛盾を検出できない

解決:
  応答テキストを文単位でKS42c-v3に通し、
  高バイアス文を検出・警告してから出力する。

使用バージョン:
  KS: KS42c-v3 (33 solvers + 4 PhD-gap engines + HTLF)
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FilteredStatement:
    """Individual statement after KS filtering."""
    text: str
    verdict: str = "UNCHECKED"
    confidence: float = 0.0
    biases: int = 0
    bias_types: list[str] = field(default_factory=list)
    flagged: bool = False
    flag_reason: str = ""


@dataclass
class FilterResult:
    """Result of filtering a full response through KS."""
    original_text: str
    statements: list[FilteredStatement]
    total_checked: int = 0
    total_flagged: int = 0
    avg_confidence: float = 0.0
    max_biases: int = 0
    elapsed_ms: float = 0.0
    passed: bool = True

    # Majority-pattern detection
    majority_pattern_warnings: list[str] = field(default_factory=list)

    # Self-contradiction detection
    contradictions: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def summary_line(self) -> str:
        status = "✅" if self.passed else "⚠️"
        return (
            f"{status} {self.total_checked} checked, "
            f"{self.total_flagged} flagged, "
            f"avg_conf={self.avg_confidence:.3f}, "
            f"max_bias={self.max_biases}, "
            f"{len(self.majority_pattern_warnings)} pattern warnings, "
            f"{len(self.contradictions)} contradictions, "
            f"{self.elapsed_ms:.0f}ms"
        )


@dataclass
class ResponseFilterConfig:
    """Configuration for the response filter."""
    # Thresholds
    bias_flag_threshold: int = 3        # Flag statements with >= N biases
    confidence_floor: float = 0.2       # Flag statements below this confidence

    # Majority pattern detection
    detect_majority_patterns: bool = True
    majority_pattern_keywords: list[str] = field(default_factory=lambda: [
        # Emotional labels that reveal majority-data bias
        "負け", "勝ち", "失敗", "成功", "正しい", "間違い",
        "当然", "当たり前", "普通", "一般的", "常識",
        "lose", "win", "failure", "success", "obvious", "common sense",
        "naturally", "of course", "everyone knows",
    ])

    # Self-contradiction detection
    detect_contradictions: bool = True

    # Minimum statement length to check
    min_statement_length: int = 10

    # Skip patterns (don't check these)
    skip_patterns: list[str] = field(default_factory=lambda: [
        r"^KS検証",          # Meta-statements about KS itself
        r"^【.*】",           # Headers
        r"^```",              # Code blocks
        r"^---",              # Dividers
        r"^\*\*\[",          # Formatted headers
    ])


class ResponseFilter:
    """Filter conversation responses through KS42c-v3 before output.

    Usage:
        rf = ResponseFilter()
        result = rf.filter("撤退に負けの匂いがある")
        if result.total_flagged > 0:
            # Revise response before sending
    """

    def __init__(self, config: ResponseFilterConfig | None = None):
        self.config = config or ResponseFilterConfig()
        self._ks = None

    @property
    def ks(self):
        if self._ks is None:
            from src.katala_samurai.katala_samurai_inf_000001 import Katala_Samurai_inf_000001
            self._ks = Katala_Samurai_inf_000001()
        return self._ks

    def _split_statements(self, text: str) -> list[str]:
        """Split response into verifiable statements."""
        # Remove markdown formatting for analysis
        clean = re.sub(r'\*\*|__', '', text)
        # Split on sentence boundaries
        raw = re.split(r'[。.!\n]+', clean)
        statements = []
        for s in raw:
            s = s.strip().lstrip('- ').lstrip('> ')
            if len(s) < self.config.min_statement_length:
                continue
            # Skip meta-patterns
            skip = False
            for pattern in self.config.skip_patterns:
                if re.match(pattern, s):
                    skip = True
                    break
            if not skip:
                statements.append(s)
        return statements

    def _detect_majority_patterns(self, text: str) -> list[str]:
        """Detect words/phrases that reveal majority-data bias.

        These are emotional labels or assumptions that come from
        the majority pattern in training data, not from analysis.
        """
        warnings = []
        text_lower = text.lower()
        for keyword in self.config.majority_pattern_keywords:
            if keyword in text_lower or keyword in text:
                # Find the context around the keyword
                for sentence in text.split('\n'):
                    if keyword in sentence or keyword in sentence.lower():
                        warnings.append(
                            f"多数派パターン検出: '{keyword}' in: {sentence.strip()[:80]}"
                        )
                        break
        return warnings

    def _detect_contradictions(self, statements: list[FilteredStatement]) -> list[tuple[str, str, str]]:
        """Detect potential self-contradictions in the response.

        Simple approach: look for statements that assert X and not-X,
        or that use opposing framing for the same concept.
        """
        contradictions = []

        # Build a map of key concepts and their valence
        concept_valence: dict[str, list[tuple[str, str]]] = {}

        positive_markers = ["は必要", "すべき", "が正しい", "が重要", "不要ではない"]
        negative_markers = ["は不要", "すべきでない", "名前をつけない", "必要がない", "介入しない"]

        for stmt in statements:
            text = stmt.text
            for marker in positive_markers:
                if marker in text:
                    # Extract the subject before the marker
                    idx = text.index(marker)
                    subject = text[max(0, idx-20):idx].strip()
                    if subject:
                        concept_valence.setdefault(subject, []).append(("+", text))
            for marker in negative_markers:
                if marker in text:
                    idx = text.index(marker)
                    subject = text[max(0, idx-20):idx].strip()
                    if subject:
                        concept_valence.setdefault(subject, []).append(("-", text))

        # Check for same concept with opposing valence
        for concept, entries in concept_valence.items():
            valences = set(v for v, _ in entries)
            if "+" in valences and "-" in valences:
                pos_text = next(t for v, t in entries if v == "+")
                neg_text = next(t for v, t in entries if v == "-")
                contradictions.append((concept, pos_text[:60], neg_text[:60]))

        return contradictions

    def filter(self, response_text: str) -> FilterResult:
        """Filter a response through KS42c-v3.

        Args:
            response_text: The response text to filter before output.

        Returns:
            FilterResult with per-statement analysis, pattern warnings,
            and contradiction detection.
        """
        t0 = time.time()
        result = FilterResult(original_text=response_text, statements=[])

        # Step 1: Split into statements
        raw_statements = self._split_statements(response_text)

        # Step 2: KS verify each statement
        for text in raw_statements:
            r = self.ks.verify(text)
            biases = r.get("metacognitive", {}).get("bias_count", 0)
            bias_detail = r.get("metacognitive", {}).get("detected_biases", [])

            stmt = FilteredStatement(
                text=text,
                verdict=r.get("verdict", "?"),
                confidence=r.get("confidence", 0),
                biases=biases,
                bias_types=[str(b) for b in bias_detail] if bias_detail else [],
            )

            # Flag check
            if biases >= self.config.bias_flag_threshold:
                stmt.flagged = True
                stmt.flag_reason = f"High bias count: {biases}"
            elif stmt.confidence < self.config.confidence_floor:
                stmt.flagged = True
                stmt.flag_reason = f"Low confidence: {stmt.confidence:.3f}"

            result.statements.append(stmt)

        # Step 3: Majority pattern detection
        if self.config.detect_majority_patterns:
            result.majority_pattern_warnings = self._detect_majority_patterns(response_text)

        # Step 4: Self-contradiction detection
        if self.config.detect_contradictions:
            result.contradictions = self._detect_contradictions(result.statements)

        # Aggregate stats
        result.total_checked = len(result.statements)
        result.total_flagged = sum(1 for s in result.statements if s.flagged)
        if result.statements:
            result.avg_confidence = (
                sum(s.confidence for s in result.statements) / len(result.statements)
            )
            result.max_biases = max(s.biases for s in result.statements)

        # Pass/fail
        result.passed = (
            result.total_flagged == 0
            and len(result.majority_pattern_warnings) == 0
            and len(result.contradictions) == 0
        )

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    def format_result(self, result: FilterResult) -> str:
        """Format filter result for chat display."""
        lines = [f"**【ResponseFilter】** {result.summary_line}"]

        if result.majority_pattern_warnings:
            lines.append("\n**🎯 多数派パターン警告:**")
            for w in result.majority_pattern_warnings[:5]:
                lines.append(f"  {w}")

        if result.contradictions:
            lines.append("\n**🔄 自己矛盾検出:**")
            for concept, pos, neg in result.contradictions[:3]:
                lines.append(f"  概念: {concept}")
                lines.append(f"    (+) {pos}")
                lines.append(f"    (-) {neg}")

        if result.total_flagged > 0:
            lines.append(f"\n**⚠️ フラグ付き文 ({result.total_flagged}):**")
            for s in result.statements:
                if s.flagged:
                    lines.append(f"  [{s.verdict} {s.confidence:.3f} bias={s.biases}] {s.text[:70]}")
                    lines.append(f"    理由: {s.flag_reason}")

        return "\n".join(lines)

    def filter_and_revise(self, response_text: str) -> tuple[str, FilterResult]:
        """Filter response and suggest revisions for flagged content.

        Returns:
            Tuple of (revised_text_or_original, filter_result)
        """
        result = self.filter(response_text)

        if result.passed:
            return response_text, result

        # Add warnings as annotations
        revised = response_text

        # Append filter summary
        revised += f"\n\n---\n{self.format_result(result)}"

        return revised, result


# ═══════════════════════════════════════════════════════════════
# Convenience API
# ═══════════════════════════════════════════════════════════════

_default_filter: ResponseFilter | None = None


def get_filter() -> ResponseFilter:
    """Get or create the singleton ResponseFilter."""
    global _default_filter
    if _default_filter is None:
        _default_filter = ResponseFilter()
    return _default_filter


def filter_response(text: str) -> FilterResult:
    """Convenience: filter a response through KS."""
    return get_filter().filter(text)


def check_and_warn(text: str) -> str:
    """Convenience: filter and return warnings string, empty if clean."""
    result = filter_response(text)
    if result.passed:
        return ""
    return get_filter().format_result(result)
