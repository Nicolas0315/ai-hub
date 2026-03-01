#!/usr/bin/env python3
"""
Katala Coding Principle — KCS-CP v2.0
「CodingレベルではKatalaを通さずにやらない」

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02

4段階ゲートチェーン:
  Gate 1 (MANDATORY): KCS構造検証 — コード出力に KCS-1b 検証
  Gate 2 (MANDATORY): KS事実検証 — コード内の事実的主張を KS42c 検証
  Gate 3 (ADVISORY):  メモリ書込検証 — MEMORY.md書込にバイアス検出
  Gate 4 (ADVISORY):  テキスト検証 — 会話応答の事実的主張を検証

使用バージョン:
  KS:  KS42c (33 solvers + multimodal + CrossModalSolver + ExceedsEngine)
  KCS: KCS-1b (forward + reverse + KS40b cross-check)

HTLF的解釈:
  設計意図 →[翻訳]→ LLM解釈 →[翻訳]→ コード出力
  各「→」で翻訳損失が発生する。KS/KCSはこの損失を測定する。
  測定されない損失は修正できない。
"""
from __future__ import annotations

import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("katala.coding_principle")


# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

GRADE_ORDER = "SABCDF"
KCS_VERSION_PREFERRED = "KCS-1b"
KCS_VERSION_FALLBACK = "KCS-1a"
KS_VERSION = "KS42c"


class GateLevel(Enum):
    """Gate enforcement level."""
    MANDATORY = "mandatory"   # Block output on failure
    ADVISORY = "advisory"     # Warn but allow output


class GateStage(Enum):
    """4-stage gate pipeline."""
    KCS_STRUCTURE = "Gate1_KCS_Structure"     # KCS code verification
    KS_CLAIMS = "Gate2_KS_Claims"             # KS factual verification
    MEMORY_BIAS = "Gate3_Memory_Bias"         # Memory write bias check
    TEXT_CLAIMS = "Gate4_Text_Claims"          # Text response verification


# ═══════════════════════════════════════════════════════════════
# Gate Result Types
# ═══════════════════════════════════════════════════════════════

@dataclass
class GateResult:
    """Result of a single gate check."""
    passed: bool
    gate_stage: GateStage
    gate_level: GateLevel
    elapsed_ms: float = 0.0
    # KCS data
    kcs_grade: str | None = None
    kcs_fidelity: float | None = None
    kcs_axes: dict[str, float] = field(default_factory=dict)
    kcs_version: str = ""
    # KS data
    ks_verdicts: list[dict] = field(default_factory=list)
    ks_avg_confidence: float = 0.0
    # Issues
    flagged_items: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    reason: str = ""
    # Retry tracking
    attempt: int = 1
    max_attempts: int = 1

    @property
    def summary(self) -> str:
        status = "PASS" if self.passed else "BLOCK" if self.gate_level == GateLevel.MANDATORY else "WARN"
        parts = [f"[{status}] {self.gate_stage.value} ({self.elapsed_ms:.0f}ms)"]
        if self.kcs_grade:
            parts.append(f"KCS={self.kcs_grade}({self.kcs_fidelity:.3f})")
        if self.ks_verdicts:
            parts.append(f"KS_avg={self.ks_avg_confidence:.3f}")
        if self.flagged_items:
            parts.append(f"flagged={len(self.flagged_items)}")
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        if not self.passed:
            parts.append(f"reason={self.reason}")
        return " | ".join(parts)


@dataclass
class PipelineResult:
    """Result of the full 4-gate pipeline."""
    gate_results: list[GateResult] = field(default_factory=list)
    overall_passed: bool = True
    total_elapsed_ms: float = 0.0
    blocked_by: str | None = None

    def add(self, result: GateResult) -> None:
        self.gate_results.append(result)
        self.total_elapsed_ms += result.elapsed_ms
        if not result.passed and result.gate_level == GateLevel.MANDATORY:
            self.overall_passed = False
            if self.blocked_by is None:
                self.blocked_by = result.gate_stage.value

    @property
    def summary(self) -> str:
        status = "PASS" if self.overall_passed else f"BLOCKED by {self.blocked_by}"
        lines = [f"Pipeline: {status} ({self.total_elapsed_ms:.0f}ms)"]
        for gr in self.gate_results:
            lines.append(f"  {gr.summary}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class CodingPrincipleConfig:
    """Tunable thresholds for the coding principle gates."""
    # KCS thresholds (Gate 1)
    kcs_min_grade: str = "C"
    kcs_retry_on_fail: bool = True
    kcs_max_retries: int = 2

    # KS thresholds (Gate 2)
    ks_confidence_floor: float = 0.3
    ks_max_biases_code: int = 3

    # Memory thresholds (Gate 3)
    memory_bias_threshold: int = 3
    memory_gate_level: GateLevel = GateLevel.ADVISORY

    # Text thresholds (Gate 4)
    text_gate_level: GateLevel = GateLevel.ADVISORY

    # R_context floor (Youta's design philosophy)
    r_context_floor: float = 0.20

    # Behavior
    fail_open: bool = False         # If True, errors → pass. If False, errors → fail.
    log_all_results: bool = True

    def grade_passes(self, grade: str) -> bool:
        """Check if grade meets minimum threshold."""
        try:
            return GRADE_ORDER.index(grade) <= GRADE_ORDER.index(self.kcs_min_grade)
        except ValueError:
            return False


# ═══════════════════════════════════════════════════════════════
# Claim Extraction
# ═══════════════════════════════════════════════════════════════

def extract_code_claims(code: str) -> list[str]:
    """Extract verifiable claims from code comments and docstrings.

    Targets: docstrings, comments, assert messages.
    Filters: shebangs, type hints, trivial lines.
    """
    claims: list[str] = []

    # Docstrings (triple-quoted)
    for match in re.finditer(r'"""(.*?)"""', code, re.DOTALL):
        text = match.group(1).strip()
        for line in text.split("\n"):
            line = line.strip().lstrip("- ")
            if (len(line) > 15
                    and not line.startswith(("Args:", "Returns:", "Raises:",
                                            "Example:", "Note:", "TODO:",
                                            ">>>", "...", "---"))):
                claims.append(line)

    # Single-line comments
    for match in re.finditer(r'#\s*(.+)$', code, re.MULTILINE):
        text = match.group(1).strip()
        if (len(text) > 15
                and not text.startswith(("!", "type:", "noqa", "pragma",
                                        "pylint", "mypy", "fmt:", "ruff:"))):
            claims.append(text)

    # Assert messages
    for match in re.finditer(r'assert\s+.+?,\s*["\'](.+?)["\']', code):
        text = match.group(1).strip()
        if len(text) > 10:
            claims.append(text)

    return claims


def extract_text_claims(text: str) -> list[str]:
    """Extract verifiable claims from natural language text."""
    raw = re.split(r'[。.?\n]+', text)
    return [s.strip() for s in raw if len(s.strip()) > 10]


# ═══════════════════════════════════════════════════════════════
# Gate 1: KCS Structure Verification
# ═══════════════════════════════════════════════════════════════

class KCSGate:
    """Gate 1: KCS-1b structural verification of generated code.

    Measures design→code translation fidelity.
    Uses KCS-1b (forward + reverse + KS40b cross-check).
    Falls back to KCS-1a if KCS-1b unavailable.
    """

    def __init__(self, config: CodingPrincipleConfig):
        self.config = config
        self._kcs = None
        self._kcs_version: str = ""

    @property
    def kcs(self):
        """Lazy-load KCS-1b, fallback to KCS-1a."""
        if self._kcs is None:
            try:
                from katala_coding.kcs1b import KCS1b
                self._kcs = KCS1b()
                self._kcs_version = KCS_VERSION_PREFERRED
            except (ImportError, Exception) as e:
                logger.warning("KCS-1b unavailable (%s), falling back to KCS-1a", e)
                try:
                    from katala_coding.kcs1a import KCS1a
                    self._kcs = KCS1a()
                    self._kcs_version = KCS_VERSION_FALLBACK
                except (ImportError, Exception) as e2:
                    logger.error("KCS-1a also unavailable: %s", e2)
                    self._kcs_version = "NONE"
        return self._kcs

    def check(self, code: str, design_spec: str) -> GateResult:
        """Run KCS verification with retry on failure."""
        t0 = time.time()
        result = GateResult(
            passed=True,
            gate_stage=GateStage.KCS_STRUCTURE,
            gate_level=GateLevel.MANDATORY,
            kcs_version=self._kcs_version or KCS_VERSION_PREFERRED,
            max_attempts=self.config.kcs_max_retries + 1 if self.config.kcs_retry_on_fail else 1,
        )

        if not design_spec:
            result.reason = "No design spec provided — KCS gate skipped"
            result.elapsed_ms = (time.time() - t0) * 1000
            logger.info("Gate1 skipped: no design spec")
            return result

        if self.kcs is None:
            result.errors.append("KCS engine not available")
            result.passed = self.config.fail_open
            result.reason = "KCS engine unavailable"
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        for attempt in range(1, result.max_attempts + 1):
            result.attempt = attempt
            try:
                verdict = self.kcs.verify(design_spec, code)
                self._extract_verdict(result, verdict)

                if self.config.grade_passes(result.kcs_grade):
                    result.passed = True
                    break
                else:
                    result.passed = False
                    result.reason = (
                        f"KCS grade {result.kcs_grade} below minimum "
                        f"{self.config.kcs_min_grade} (attempt {attempt}/{result.max_attempts})"
                    )
                    if attempt < result.max_attempts:
                        logger.info(
                            "Gate1 attempt %d/%d failed (grade=%s), retrying...",
                            attempt, result.max_attempts, result.kcs_grade
                        )

            except Exception as e:
                result.errors.append(f"Attempt {attempt}: {e}")
                logger.error("Gate1 attempt %d error: %s", attempt, traceback.format_exc())
                result.passed = self.config.fail_open
                result.reason = f"KCS error: {e}"

        result.elapsed_ms = (time.time() - t0) * 1000
        if self.config.log_all_results:
            logger.info("Gate1 result: %s", result.summary)
        return result

    def _extract_verdict(self, result: GateResult, verdict: Any) -> None:
        """Extract fields from KCS-1b EnhancedVerdict or KCS-1a CodeVerdict."""
        if hasattr(verdict, 'forward'):
            # KCS-1b EnhancedVerdict
            fwd = verdict.forward
            result.kcs_grade = verdict.final_grade
            result.kcs_fidelity = fwd.total_fidelity
            result.kcs_version = KCS_VERSION_PREFERRED
            result.kcs_axes = {
                "R_struct": fwd.r_struct,
                "R_context": fwd.r_context,
                "R_qualia": fwd.r_qualia,
                "R_cultural": fwd.r_cultural,
                "R_temporal": fwd.r_temporal,
            }
            if verdict.reverse:
                result.kcs_axes["reverse_coverage"] = verdict.reverse.coverage_score
                result.kcs_axes["reverse_goal_confidence"] = verdict.reverse.goal_confidence
            if verdict.ks40b_check:
                result.kcs_axes["ks40b_agreement"] = verdict.ks40b_check.agreement
                result.kcs_axes["ks40b_reliability"] = verdict.ks40b_check.measurement_reliability
            if verdict.penalty_log:
                for p in verdict.penalty_log:
                    result.flagged_items.append({"type": "kcs_penalty", "detail": p})
        else:
            # KCS-1a CodeVerdict
            result.kcs_grade = verdict.grade
            result.kcs_fidelity = verdict.total_fidelity
            result.kcs_version = KCS_VERSION_FALLBACK
            result.kcs_axes = {
                "R_struct": verdict.r_struct,
                "R_context": verdict.r_context,
                "R_qualia": verdict.r_qualia,
                "R_cultural": verdict.r_cultural,
                "R_temporal": verdict.r_temporal,
            }

        # R_context floor check (Youta's design philosophy)
        r_context = result.kcs_axes.get("R_context", 0)
        if r_context < self.config.r_context_floor:
            result.flagged_items.append({
                "type": "r_context_floor_violation",
                "detail": f"R_context={r_context:.3f} < floor={self.config.r_context_floor}",
            })


# ═══════════════════════════════════════════════════════════════
# Gate 2: KS Factual Claims Verification
# ═══════════════════════════════════════════════════════════════

class KSClaimsGate:
    """Gate 2: KS42c verification of factual claims in code."""

    def __init__(self, config: CodingPrincipleConfig):
        self.config = config
        self._ks = None

    @property
    def ks(self):
        """Lazy-load KS42c."""
        if self._ks is None:
            try:
                from katala_samurai.ks42c import KS42c
                self._ks = KS42c()
            except (ImportError, Exception) as e:
                logger.error("KS42c unavailable: %s", e)
        return self._ks

    def check(self, code: str) -> GateResult:
        """Verify factual claims extracted from code."""
        t0 = time.time()
        result = GateResult(
            passed=True,
            gate_stage=GateStage.KS_CLAIMS,
            gate_level=GateLevel.MANDATORY,
        )

        claims = extract_code_claims(code)
        if not claims:
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        if self.ks is None:
            result.errors.append("KS42c engine not available")
            result.passed = self.config.fail_open
            result.reason = "KS42c engine unavailable"
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        for claim in claims:
            try:
                r = self.ks.verify(claim)
                entry = {
                    "claim": claim[:100],
                    "verdict": r.get("verdict", "?"),
                    "confidence": r.get("confidence", 0),
                    "biases": r.get("metacognitive", {}).get("bias_count", 0),
                }
                result.ks_verdicts.append(entry)

                if entry["biases"] >= self.config.ks_max_biases_code:
                    result.flagged_items.append(entry)

            except Exception as e:
                result.errors.append(f"KS error on claim '{claim[:40]}': {e}")
                logger.warning("Gate2 claim verification error: %s", e)

        if result.ks_verdicts:
            result.ks_avg_confidence = (
                sum(v["confidence"] for v in result.ks_verdicts)
                / len(result.ks_verdicts)
            )

        # High-bias claims with DEBUNKED verdict → block
        debunked_high_bias = [
            f for f in result.flagged_items
            if f.get("verdict") == "DEBUNKED"
        ]
        if debunked_high_bias:
            result.passed = False
            result.reason = f"{len(debunked_high_bias)} DEBUNKED claims with high bias in code"

        result.elapsed_ms = (time.time() - t0) * 1000
        if self.config.log_all_results:
            logger.info("Gate2 result: %s", result.summary)
        return result

    def check_text(self, text: str) -> GateResult:
        """Verify claims in natural language text (Gate 4)."""
        t0 = time.time()
        result = GateResult(
            passed=True,
            gate_stage=GateStage.TEXT_CLAIMS,
            gate_level=self.config.text_gate_level,
        )

        claims = extract_text_claims(text)
        if not claims or self.ks is None:
            if self.ks is None and claims:
                result.errors.append("KS42c unavailable")
                result.passed = self.config.fail_open
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        for claim in claims:
            try:
                r = self.ks.verify(claim)
                entry = {
                    "claim": claim[:100],
                    "verdict": r.get("verdict", "?"),
                    "confidence": r.get("confidence", 0),
                    "biases": r.get("metacognitive", {}).get("bias_count", 0),
                }
                result.ks_verdicts.append(entry)
                if entry["biases"] >= self.config.ks_max_biases_code:
                    result.flagged_items.append(entry)
            except Exception as e:
                result.errors.append(f"KS error: {e}")

        if result.ks_verdicts:
            result.ks_avg_confidence = (
                sum(v["confidence"] for v in result.ks_verdicts)
                / len(result.ks_verdicts)
            )

        result.elapsed_ms = (time.time() - t0) * 1000
        if self.config.log_all_results:
            logger.info("Gate4 result: %s", result.summary)
        return result


# ═══════════════════════════════════════════════════════════════
# Gate 3: Memory Write Bias Detection
# ═══════════════════════════════════════════════════════════════

class MemoryWriteGate:
    """Gate 3: KS verification of memory writes to prevent bias contamination."""

    def __init__(self, config: CodingPrincipleConfig):
        self.config = config
        self._ks = None

    @property
    def ks(self):
        if self._ks is None:
            try:
                from katala_samurai.ks42c import KS42c
                self._ks = KS42c()
            except (ImportError, Exception) as e:
                logger.error("KS42c unavailable for MemoryGate: %s", e)
        return self._ks

    def check(self, content: str) -> GateResult:
        """Verify content for bias before memory write."""
        t0 = time.time()
        result = GateResult(
            passed=True,
            gate_stage=GateStage.MEMORY_BIAS,
            gate_level=self.config.memory_gate_level,
        )

        statements = extract_text_claims(content)
        if not statements or self.ks is None:
            if self.ks is None and statements:
                result.errors.append("KS42c unavailable")
                result.passed = self.config.fail_open
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        for stmt in statements:
            try:
                r = self.ks.verify(stmt)
                biases = r.get("metacognitive", {}).get("bias_count", 0)
                entry = {
                    "statement": stmt[:100],
                    "verdict": r.get("verdict", "?"),
                    "confidence": r.get("confidence", 0),
                    "biases": biases,
                }
                result.ks_verdicts.append(entry)

                if biases >= self.config.memory_bias_threshold:
                    result.flagged_items.append(entry)

            except Exception as e:
                result.errors.append(f"KS error: {e}")

        if result.ks_verdicts:
            result.ks_avg_confidence = (
                sum(v["confidence"] for v in result.ks_verdicts)
                / len(result.ks_verdicts)
            )

        if result.flagged_items:
            result.passed = False
            result.reason = (
                f"{len(result.flagged_items)} statements with "
                f"bias >= {self.config.memory_bias_threshold}"
            )

        result.elapsed_ms = (time.time() - t0) * 1000
        if self.config.log_all_results:
            logger.info("Gate3 result: %s", result.summary)
        return result


# ═══════════════════════════════════════════════════════════════
# Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════

class KatalaCodingPrinciple:
    """
    統合4段階ゲートパイプライン.

    原則: CodingレベルではKatalaを通さずにやらない.

    Gate 1 (MANDATORY): KCS-1b 構造検証 → Grade C以上で通過
    Gate 2 (MANDATORY): KS42c 事実検証 → DEBUNKED+高バイアスで遮断
    Gate 3 (ADVISORY):  メモリ書込検証 → 高バイアスで警告
    Gate 4 (ADVISORY):  テキスト検証 → 高バイアスで警告

    Usage:
        principle = KatalaCodingPrinciple()

        # Full pipeline for code
        result = principle.gate_code(code, design_spec="...")
        if not result.overall_passed:
            # Fix code and retry
            ...

        # Memory write check
        gate_result = principle.gate_memory(content)
        if gate_result.flagged_items:
            # Review flagged statements before writing
            ...

        # Text response check
        gate_result = principle.gate_text(response)
    """

    def __init__(self, config: CodingPrincipleConfig | None = None):
        self.config = config or CodingPrincipleConfig()
        self._kcs_gate = KCSGate(self.config)
        self._ks_gate = KSClaimsGate(self.config)
        self._memory_gate = MemoryWriteGate(self.config)
        self._history: list[PipelineResult | GateResult] = []

    def gate_code(self, code: str, design_spec: str = "") -> PipelineResult:
        """Run full Gate 1 + Gate 2 pipeline on code output.

        This is the primary entry point for the coding principle.
        Both gates are MANDATORY — failure in either blocks output.

        Args:
            code: Generated code to verify
            design_spec: Design specification the code should implement

        Returns:
            PipelineResult with overall pass/block decision
        """
        pipeline = PipelineResult()

        # Gate 1: KCS structure
        g1 = self._kcs_gate.check(code, design_spec)
        pipeline.add(g1)

        # Gate 2: KS claims (runs even if Gate 1 failed — collect all diagnostics)
        g2 = self._ks_gate.check(code)
        pipeline.add(g2)

        self._history.append(pipeline)
        logger.info("Code pipeline: %s", "PASS" if pipeline.overall_passed else f"BLOCKED by {pipeline.blocked_by}")
        return pipeline

    def gate_memory(self, content: str) -> GateResult:
        """Gate 3: Check memory write for bias contamination.

        Advisory by default — warns but doesn't block.
        Set config.memory_gate_level = GateLevel.MANDATORY to block.
        """
        result = self._memory_gate.check(content)
        self._history.append(result)
        return result

    def gate_text(self, text: str) -> GateResult:
        """Gate 4: Check text response for factual claims.

        Advisory by default.
        """
        result = self._ks_gate.check_text(text)
        self._history.append(result)
        return result

    @property
    def stats(self) -> dict[str, Any]:
        """Return gate usage statistics."""
        if not self._history:
            return {"total": 0, "gates_run": 0}

        pipeline_count = sum(1 for h in self._history if isinstance(h, PipelineResult))
        gate_count = sum(1 for h in self._history if isinstance(h, GateResult))

        all_results: list[GateResult] = []
        for h in self._history:
            if isinstance(h, PipelineResult):
                all_results.extend(h.gate_results)
            else:
                all_results.append(h)

        passed = sum(1 for r in all_results if r.passed)
        total = len(all_results)
        avg_ms = sum(r.elapsed_ms for r in all_results) / total if total else 0

        return {
            "total_pipeline_runs": pipeline_count,
            "total_gate_runs": gate_count,
            "individual_gates": total,
            "passed": passed,
            "blocked": total - passed,
            "pass_rate": passed / total if total else 0,
            "avg_latency_ms": round(avg_ms, 1),
        }

    def format_result(self, result: PipelineResult | GateResult) -> str:
        """Format result for Discord/chat display."""
        if isinstance(result, PipelineResult):
            return self._format_pipeline(result)
        return self._format_gate(result)

    def _format_pipeline(self, pipeline: PipelineResult) -> str:
        """Format pipeline result."""
        status = "✅ PASS" if pipeline.overall_passed else f"🚫 BLOCKED by {pipeline.blocked_by}"
        lines = [f"**【Coding Principle Pipeline】** {status}"]

        for gr in pipeline.gate_results:
            lines.append(self._format_gate(gr))

        lines.append(f"Total latency: {pipeline.total_elapsed_ms:.0f}ms")
        return "\n".join(lines)

    def _format_gate(self, result: GateResult) -> str:
        """Format single gate result."""
        status = "✅" if result.passed else ("🚫" if result.gate_level == GateLevel.MANDATORY else "⚠️")
        lines = [f"{status} **{result.gate_stage.value}** [{result.kcs_version or KS_VERSION}]"]

        if result.kcs_grade:
            lines.append(f"  Grade: {result.kcs_grade} (fidelity: {result.kcs_fidelity:.3f})")
            for axis, val in result.kcs_axes.items():
                if not axis.startswith("reverse_") and not axis.startswith("ks40b_"):
                    lines.append(f"    {axis}: {val:.3f}")
            # KCS-1b extras
            for extra in ("reverse_coverage", "reverse_goal_confidence", "ks40b_agreement"):
                if extra in result.kcs_axes:
                    lines.append(f"    {extra}: {result.kcs_axes[extra]:.3f}")

        if result.ks_verdicts:
            lines.append(f"  KS: {len(result.ks_verdicts)} claims, avg conf: {result.ks_avg_confidence:.3f}")

        if result.flagged_items:
            lines.append(f"  ⚠️ Flagged: {len(result.flagged_items)} items")
            for item in result.flagged_items[:5]:
                detail = item.get("detail") or item.get("claim") or item.get("statement", "?")
                lines.append(f"    - {detail[:80]}")

        if result.errors:
            lines.append(f"  Errors: {len(result.errors)}")

        if not result.passed:
            lines.append(f"  Reason: {result.reason}")

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


def gate_code(code: str, design_spec: str = "") -> PipelineResult:
    """Convenience: run full coding pipeline (Gate 1 + Gate 2)."""
    return get_principle().gate_code(code, design_spec)


def gate_memory(content: str) -> GateResult:
    """Convenience: run memory write gate (Gate 3)."""
    return get_principle().gate_memory(content)


def gate_text(text: str) -> GateResult:
    """Convenience: run text response gate (Gate 4)."""
    return get_principle().gate_text(text)
