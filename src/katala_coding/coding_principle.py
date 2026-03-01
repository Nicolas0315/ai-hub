#!/usr/bin/env python3
"""
Katala Coding Principle — KCS-CP
「CodingレベルではKatalaを通さずにやらない」

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02

この原則はKatalaの設計構造に組み込まれたゲートである。
LLMが出力するコード・テキスト・メモリ書き込みの全てに対し、
KS (事実検証) と KCS (翻訳忠実度検証) を適用してから外部に出す。

HTLF的解釈:
  設計意図 →[翻訳]→ LLM解釈 →[翻訳]→ コード出力
  各「→」で翻訳損失が発生する。KS/KCSはこの損失を測定する。
  測定されない損失は修正できない。

使用バージョン:
  KS:  KS42c-v3 (33 solvers + 4 PhD-gap engines + HTLF)
  KCS: KCS-1b (KCS-1a + KCS-2a reverse inference + KS40b cross-check)
"""
from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass, field
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Gate Result Types
# ═══════════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """Result of a coding/memory gate check."""
    passed: bool
    gate_name: str
    elapsed_ms: float = 0.0
    kcs_grade: str | None = None
    kcs_fidelity: float | None = None
    kcs_axes: dict[str, float] = field(default_factory=dict)
    ks_verdicts: list[dict] = field(default_factory=list)
    ks_avg_confidence: float = 0.0
    flagged_items: list[dict] = field(default_factory=list)
    reason: str = ""

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "BLOCK"
        parts = [f"[{status}] {self.gate_name} ({self.elapsed_ms:.0f}ms)"]
        if self.kcs_grade:
            parts.append(f"KCS={self.kcs_grade}({self.kcs_fidelity:.3f})")
        if self.ks_verdicts:
            parts.append(f"KS_avg={self.ks_avg_confidence:.3f}")
        if self.flagged_items:
            parts.append(f"flagged={len(self.flagged_items)}")
        if not self.passed:
            parts.append(f"reason={self.reason}")
        return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class CodingPrincipleConfig:
    """Tunable thresholds for the coding principle gates."""
    # KCS thresholds
    kcs_min_grade: str = "C"                # Minimum KCS grade to pass
    kcs_grade_order: str = "SABCDF"         # Grade ordering (best→worst)

    # KS thresholds
    ks_confidence_floor: float = 0.3        # Below this = flag
    ks_max_biases: int = 3                  # Above this = flag for memory writes

    # Memory write thresholds
    memory_bias_threshold: int = 3          # Max biases per statement in memory writes

    # Behavior
    block_on_kcs_fail: bool = True          # Block code output on KCS failure
    block_on_memory_bias: bool = False      # Block memory writes (False = warn only)
    include_ks_in_coding: bool = True       # Run KS on code claims
    include_kcs_in_coding: bool = True      # Run KCS on code structure

    def grade_passes(self, grade: str) -> bool:
        """Check if a grade meets the minimum threshold."""
        try:
            return self.kcs_grade_order.index(grade) <= self.kcs_grade_order.index(self.kcs_min_grade)
        except ValueError:
            return False


# ═══════════════════════════════════════════════════════════════
# Claim Extraction
# ═══════════════════════════════════════════════════════════════

def extract_code_claims(code: str) -> list[str]:
    """Extract verifiable claims from code comments and docstrings.

    Targets:
    - Docstrings (triple-quoted)
    - Single-line comments (# ...)
    - Assert messages
    Filters out trivial/short strings and shebangs.
    """
    claims: list[str] = []

    # Docstrings
    for match in re.finditer(r'"""(.*?)"""', code, re.DOTALL):
        text = match.group(1).strip()
        # Split multi-line docstrings into sentences
        for line in text.split("\n"):
            line = line.strip().lstrip("- ")
            if len(line) > 15 and not line.startswith("Args:") and not line.startswith("Returns:"):
                claims.append(line)

    # Single-line comments
    for match in re.finditer(r'#\s*(.+)$', code, re.MULTILINE):
        text = match.group(1).strip()
        if len(text) > 15 and not text.startswith("!") and not text.startswith("type:"):
            claims.append(text)

    # Assert messages
    for match in re.finditer(r'assert\s+.+?,\s*["\'](.+?)["\']', code):
        text = match.group(1).strip()
        if len(text) > 10:
            claims.append(text)

    return claims


def extract_text_claims(text: str) -> list[str]:
    """Extract verifiable claims from natural language text.

    Splits on sentence boundaries (。.\\n) and filters short fragments.
    """
    raw = re.split(r'[。.?\n]+', text)
    return [s.strip() for s in raw if len(s.strip()) > 10]


# ═══════════════════════════════════════════════════════════════
# Coding Gate
# ═══════════════════════════════════════════════════════════════

class CodingGate:
    """Gate: no code leaves without KS+KCS verification.

    Usage:
        gate = CodingGate()
        result = gate.check_code(code, design_spec="...")
        if not result.passed:
            # re-prompt or block
    """

    def __init__(self, config: CodingPrincipleConfig | None = None):
        self.config = config or CodingPrincipleConfig()
        self._ks = None
        self._kcs = None

    @property
    def ks(self):
        if self._ks is None:
            from src.katala_samurai.ks42c import KS42c
            self._ks = KS42c()
        return self._ks

    @property
    def kcs(self):
        """Lazy-load KCS-1b (latest). Falls back to KCS-1a if 1b unavailable."""
        if self._kcs is None:
            try:
                from src.katala_coding.kcs1b import KCS1b
                self._kcs = KCS1b()
                self._kcs_version = "KCS-1b"
            except (ImportError, Exception):
                from src.katala_coding.kcs1a import KCS1a
                self._kcs = KCS1a()
                self._kcs_version = "KCS-1a"
        return self._kcs

    @property
    def kcs_version(self) -> str:
        """Return which KCS version is loaded."""
        _ = self.kcs  # ensure loaded
        return getattr(self, "_kcs_version", "unknown")

    def check_code(self, code: str, design_spec: str = "") -> GateResult:
        """Run KCS + KS verification on generated code.

        Uses KCS-1b (with reverse inference + KS40b cross-check) when available,
        falls back to KCS-1a.

        Args:
            code: Generated code string
            design_spec: Design specification the code should implement

        Returns:
            GateResult with pass/block decision and diagnostics
        """
        t0 = time.time()
        result = GateResult(passed=True, gate_name=f"CodingGate[{self.kcs_version}]")

        # ── Step 1: KCS structural analysis ──
        if self.config.include_kcs_in_coding and design_spec:
            kcs_verdict = self.kcs.verify(design_spec, code)

            # KCS-1b returns EnhancedVerdict with .forward (CodeVerdict) + .final_grade
            # KCS-1a returns CodeVerdict directly
            if hasattr(kcs_verdict, 'forward'):
                # KCS-1b path
                forward = kcs_verdict.forward
                result.kcs_grade = kcs_verdict.final_grade
                result.kcs_fidelity = forward.total_fidelity
                result.kcs_axes = {
                    "R_struct": forward.r_struct,
                    "R_context": forward.r_context,
                    "R_qualia": forward.r_qualia,
                    "R_cultural": forward.r_cultural,
                    "R_temporal": forward.r_temporal,
                }
                # Add KCS-1b specific data
                if kcs_verdict.reverse:
                    result.kcs_axes["reverse_coverage"] = kcs_verdict.reverse.coverage_score
                    result.kcs_axes["reverse_goal_confidence"] = kcs_verdict.reverse.goal_confidence
                if kcs_verdict.ks40b_check:
                    result.kcs_axes["ks40b_agreement"] = kcs_verdict.ks40b_check.agreement
                    result.kcs_axes["ks40b_reliability"] = kcs_verdict.ks40b_check.measurement_reliability
                if kcs_verdict.penalty_log:
                    result.flagged_items.extend(
                        [{"type": "kcs_penalty", "detail": p} for p in kcs_verdict.penalty_log]
                    )
            else:
                # KCS-1a path
                result.kcs_grade = kcs_verdict.grade
                result.kcs_fidelity = kcs_verdict.total_fidelity
                result.kcs_axes = {
                    "R_struct": kcs_verdict.r_struct,
                    "R_context": kcs_verdict.r_context,
                    "R_qualia": kcs_verdict.r_qualia,
                    "R_cultural": kcs_verdict.r_cultural,
                    "R_temporal": kcs_verdict.r_temporal,
                }

            if not self.config.grade_passes(result.kcs_grade):
                result.passed = False
                result.reason = f"KCS grade {result.kcs_grade} below minimum {self.config.kcs_min_grade}"

        # ── Step 2: KS verification of code claims ──
        if self.config.include_ks_in_coding:
            claims = extract_code_claims(code)
            for claim in claims:
                r = self.ks.verify(claim)
                verdict_entry = {
                    "claim": claim[:80],
                    "verdict": r.get("verdict", "?"),
                    "confidence": r.get("confidence", 0),
                    "biases": r.get("metacognitive", {}).get("bias_count", 0),
                }
                result.ks_verdicts.append(verdict_entry)

                if verdict_entry["biases"] >= self.config.ks_max_biases:
                    result.flagged_items.append(verdict_entry)

            if result.ks_verdicts:
                result.ks_avg_confidence = (
                    sum(v["confidence"] for v in result.ks_verdicts)
                    / len(result.ks_verdicts)
                )

        result.elapsed_ms = (time.time() - t0) * 1000
        return result

    def check_text(self, text: str) -> GateResult:
        """Run KS verification on natural language output.

        For conversational responses — verifies factual claims.
        """
        t0 = time.time()
        result = GateResult(passed=True, gate_name="TextGate")

        claims = extract_text_claims(text)
        for claim in claims:
            r = self.ks.verify(claim)
            verdict_entry = {
                "claim": claim[:80],
                "verdict": r.get("verdict", "?"),
                "confidence": r.get("confidence", 0),
                "biases": r.get("metacognitive", {}).get("bias_count", 0),
            }
            result.ks_verdicts.append(verdict_entry)

            if verdict_entry["biases"] >= self.config.ks_max_biases:
                result.flagged_items.append(verdict_entry)

        if result.ks_verdicts:
            result.ks_avg_confidence = (
                sum(v["confidence"] for v in result.ks_verdicts)
                / len(result.ks_verdicts)
            )

        result.elapsed_ms = (time.time() - t0) * 1000
        return result


# ═══════════════════════════════════════════════════════════════
# Memory Write Gate
# ═══════════════════════════════════════════════════════════════

class MemoryWriteGate:
    """Gate: no memory write without KS verification.

    Checks each statement in content for bias count.
    High-bias statements are flagged or blocked.
    """

    def __init__(self, config: CodingPrincipleConfig | None = None):
        self.config = config or CodingPrincipleConfig()
        self._ks = None

    @property
    def ks(self):
        if self._ks is None:
            from src.katala_samurai.ks42c import KS42c
            self._ks = KS42c()
        return self._ks

    def check(self, content: str) -> GateResult:
        """Verify content before writing to memory files.

        Args:
            content: Text to be written to MEMORY.md or similar

        Returns:
            GateResult with pass/warn decision
        """
        t0 = time.time()
        result = GateResult(passed=True, gate_name="MemoryWriteGate")

        statements = extract_text_claims(content)
        for stmt in statements:
            r = self.ks.verify(stmt)
            biases = r.get("metacognitive", {}).get("bias_count", 0)
            verdict_entry = {
                "statement": stmt[:80],
                "verdict": r.get("verdict", "?"),
                "confidence": r.get("confidence", 0),
                "biases": biases,
            }
            result.ks_verdicts.append(verdict_entry)

            if biases >= self.config.memory_bias_threshold:
                result.flagged_items.append(verdict_entry)

        if result.ks_verdicts:
            result.ks_avg_confidence = (
                sum(v["confidence"] for v in result.ks_verdicts)
                / len(result.ks_verdicts)
            )

        if result.flagged_items and self.config.block_on_memory_bias:
            result.passed = False
            result.reason = f"{len(result.flagged_items)} statements with bias >= {self.config.memory_bias_threshold}"

        result.elapsed_ms = (time.time() - t0) * 1000
        return result


# ═══════════════════════════════════════════════════════════════
# Unified Principle Enforcer
# ═══════════════════════════════════════════════════════════════

class KatalaCodingPrinciple:
    """
    統合ゲート: Katalaの設計原則を強制する。

    原則: CodingレベルではKatalaを通さずにやらない。

    レベル:
    1. MANDATORY — 全コード出力に KCS検証 (Grade C以上)
    2. MANDATORY — コード内の事実的主張に KS検証
    3. ADVISORY  — MEMORY.md書き込みに KS検証 (バイアス3以上で警告)
    4. ADVISORY  — 会話応答の事実的主張に KS検証
    """

    def __init__(self, config: CodingPrincipleConfig | None = None):
        self.config = config or CodingPrincipleConfig()
        self.coding_gate = CodingGate(self.config)
        self.memory_gate = MemoryWriteGate(self.config)
        self._history: list[GateResult] = []

    def gate_code(self, code: str, design_spec: str = "") -> GateResult:
        """Level 1+2: Mandatory code gate."""
        result = self.coding_gate.check_code(code, design_spec)
        self._history.append(result)
        return result

    def gate_memory(self, content: str) -> GateResult:
        """Level 3: Advisory memory write gate."""
        result = self.memory_gate.check(content)
        self._history.append(result)
        return result

    def gate_text(self, text: str) -> GateResult:
        """Level 4: Advisory text response gate."""
        result = self.coding_gate.check_text(text)
        self._history.append(result)
        return result

    @property
    def stats(self) -> dict[str, Any]:
        """Return gate usage statistics."""
        if not self._history:
            return {"total": 0}
        passed = sum(1 for r in self._history if r.passed)
        blocked = sum(1 for r in self._history if not r.passed)
        avg_ms = sum(r.elapsed_ms for r in self._history) / len(self._history)
        return {
            "total": len(self._history),
            "passed": passed,
            "blocked": blocked,
            "pass_rate": passed / len(self._history),
            "avg_latency_ms": round(avg_ms, 1),
        }

    def format_result(self, result: GateResult) -> str:
        """Format a gate result for Discord/chat display."""
        lines = [f"**【{result.gate_name}】** {'✅ PASS' if result.passed else '🚫 BLOCK'}"]

        if result.kcs_grade:
            lines.append(f"KCS Grade: {result.kcs_grade} (fidelity: {result.kcs_fidelity:.3f})")
            for axis, val in result.kcs_axes.items():
                lines.append(f"  {axis}: {val:.3f}")

        if result.ks_verdicts:
            lines.append(f"KS: {len(result.ks_verdicts)} claims checked, avg confidence: {result.ks_avg_confidence:.3f}")

        if result.flagged_items:
            lines.append(f"⚠️ Flagged: {len(result.flagged_items)} items")
            for item in result.flagged_items[:3]:
                claim = item.get("claim") or item.get("statement", "?")
                lines.append(f"  - [{item['verdict']} bias={item['biases']}] {claim}")

        if not result.passed:
            lines.append(f"Reason: {result.reason}")

        lines.append(f"Latency: {result.elapsed_ms:.0f}ms")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Module-level convenience
# ═══════════════════════════════════════════════════════════════

_default_principle: KatalaCodingPrinciple | None = None


def get_principle() -> KatalaCodingPrinciple:
    """Get or create the singleton KatalaCodingPrinciple."""
    global _default_principle
    if _default_principle is None:
        _default_principle = KatalaCodingPrinciple()
    return _default_principle


def gate_code(code: str, design_spec: str = "") -> GateResult:
    """Convenience: run coding gate."""
    return get_principle().gate_code(code, design_spec)


def gate_memory(content: str) -> GateResult:
    """Convenience: run memory write gate."""
    return get_principle().gate_memory(content)


def gate_text(text: str) -> GateResult:
    """Convenience: run text response gate."""
    return get_principle().gate_text(text)
