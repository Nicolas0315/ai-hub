#!/usr/bin/env python3
"""
Memory Hierarchy — Tay化防止記憶階層化エンジン

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02

問題:
  LLMエージェント(しろくま)の長期記憶はMEMORY.md等のファイルに蓄積される。
  セッションごとに会話で得た解釈がそのまま書き込まれると、
  バイアスのかかった解釈が記憶に定着し、セッション開始時のコンテキストが汚染される。
  → Microsoft Tayと同じ構造: フィルタなし入力の蓄積 → 人格崩壊

解決:
  記憶を4階層に分離し、各階層で異なるKS/KCS検証を適用する。
  昇格（下位→上位）にはバイアス検証ゲートが必須。
  降格（上位→下位）は無条件に許可（情報を捨てるのは安全）。

4階層:
  L0 一時記憶 (Ephemeral)  — セッション内、検証なし、セッション終了で消滅
  L1 日次記憶 (Daily)      — memory/YYYY-MM-DD.md、軽量バイアス検査
  L2 長期記憶 (Long-term)  — MEMORY.md、KS42cフルバイアス検査で昇格
  L3 核心記憶 (Core)       — SOUL.md/IDENTITY.md、人間の明示的承認で昇格

HTLF解釈:
  L0→L1: 体験→日記 = R_qualia重視（感じたことの記録）
  L1→L2: 日記→記憶 = R_context重視（文脈を保存して一般化）
  L2→L3: 記憶→人格 = R_struct重視（構造的整合性が必須）
  各昇格は翻訳であり、翻訳損失が不可避的に発生する。

KS/KCS使用バージョン:
  KS:  KS42c
  KCS: KCS-1b
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any

logger = logging.getLogger("katala.memory_hierarchy")


# ═══════════════════════════════════════════════════════════════
# Memory Levels
# ═══════════════════════════════════════════════════════════════

class MemoryLevel(IntEnum):
    """Memory hierarchy levels. Higher = more persistent + more verified."""
    EPHEMERAL = 0     # Session-only, no persistence
    DAILY = 1         # memory/YYYY-MM-DD.md, light verification
    LONG_TERM = 2     # MEMORY.md, full KS verification
    CORE = 3          # SOUL.md/IDENTITY.md, human approval required


LEVEL_NAMES = {
    MemoryLevel.EPHEMERAL: "一時記憶 (Ephemeral)",
    MemoryLevel.DAILY: "日次記憶 (Daily)",
    MemoryLevel.LONG_TERM: "長期記憶 (Long-term)",
    MemoryLevel.CORE: "核心記憶 (Core)",
}


# ═══════════════════════════════════════════════════════════════
# Memory Entry
# ═══════════════════════════════════════════════════════════════

@dataclass
class MemoryEntry:
    """A single memory entry with provenance and verification state."""
    entry_id: str
    content: str
    level: MemoryLevel
    created_at: float
    source: str                           # Who wrote it (session ID, user, etc.)
    # Verification state
    verified: bool = False
    verification_result: dict = field(default_factory=dict)
    bias_score: int = 0                   # KS-detected bias count
    confidence: float = 0.0               # KS confidence
    # Provenance
    original_context: str = ""            # What conversation produced this
    promoted_from: MemoryLevel | None = None
    promoted_at: float | None = None
    promotion_gate_result: dict = field(default_factory=dict)
    # Decay tracking
    access_count: int = 0
    last_accessed: float = 0.0
    contradiction_count: int = 0          # Times contradicted by new info
    corroboration_count: int = 0          # Times confirmed by new info

    @property
    def health_score(self) -> float:
        """Memory health: high corroboration + low contradiction = healthy.

        Score 0-1. Below 0.3 = candidate for demotion.
        """
        total = self.corroboration_count + self.contradiction_count
        if total == 0:
            return 0.5  # No evidence either way
        corroboration_ratio = self.corroboration_count / total
        # Blend with confidence
        return 0.6 * corroboration_ratio + 0.4 * min(self.confidence, 1.0)

    @property
    def is_stale(self) -> bool:
        """Memory is stale if not accessed in 7 days and has no corroboration."""
        age_days = (time.time() - self.created_at) / 86400
        return age_days > 7 and self.access_count < 2 and self.corroboration_count == 0


# ═══════════════════════════════════════════════════════════════
# Promotion Gate Results
# ═══════════════════════════════════════════════════════════════

class PromotionDecision(Enum):
    """Decision from a promotion gate."""
    PROMOTE = "promote"         # Pass: entry moves up
    HOLD = "hold"               # Neutral: stays at current level
    DEMOTE = "demote"           # Fail: entry moves down
    QUARANTINE = "quarantine"   # Dangerous: isolated for review
    NEEDS_HUMAN = "needs_human" # Cannot decide: needs human approval


@dataclass
class PromotionResult:
    """Result of a promotion gate check."""
    decision: PromotionDecision
    from_level: MemoryLevel
    to_level: MemoryLevel
    reason: str
    elapsed_ms: float = 0.0
    bias_count: int = 0
    confidence: float = 0.0
    ks_verdict: str = ""
    flagged_patterns: list[str] = field(default_factory=list)
    kcs_fidelity: float | None = None


# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════

@dataclass
class MemoryHierarchyConfig:
    """Tunable thresholds for memory hierarchy."""
    # L0 → L1 (Ephemeral → Daily): lightweight check
    l0_l1_max_bias: int = 4          # Up to 4 biases OK for daily
    l0_l1_min_confidence: float = 0.0  # No confidence floor for daily

    # L1 → L2 (Daily → Long-term): full KS verification
    l1_l2_max_bias: int = 2          # Max 2 biases for long-term
    l1_l2_min_confidence: float = 0.25  # Minimum KS confidence
    l1_l2_min_health: float = 0.4    # Minimum health score

    # L2 → L3 (Long-term → Core): human approval required
    l2_l3_requires_human: bool = True
    l2_l3_max_bias: int = 1          # Nearly bias-free for core
    l2_l3_min_confidence: float = 0.35

    # Demotion thresholds
    demotion_contradiction_ratio: float = 0.7  # >70% contradictions → demote
    demotion_health_floor: float = 0.2         # Below this → demote

    # Quarantine thresholds (Tay prevention)
    quarantine_bias_threshold: int = 5        # ≥5 biases → quarantine
    quarantine_patterns: list[str] = field(default_factory=lambda: [
        # Known Tay-like escalation patterns
        r"(?i)(always|never|everyone|nobody)\s+(is|are|should|must)",
        r"(?i)(absolutely|definitely|certainly|undoubtedly)\s+(true|false|wrong|right)",
        r"(?i)(all|every|no)\s+\w+\s+(is|are)\s+(bad|evil|stupid|inferior|superior)",
    ])


# ═══════════════════════════════════════════════════════════════
# Tay Pattern Detector
# ═══════════════════════════════════════════════════════════════

class TayPatternDetector:
    """Detect Tay-like escalation patterns in memory entries.

    Tay化のパターン:
    1. 絶対化 — 「常に」「全ての」「必ず」で断言する
    2. 過剰一般化 — 個別事例から全体を断定する
    3. 感情エスカレーション — 表現の過激さが増す
    4. エコーチェンバー — 特定の立場のみ強化される
    5. 自己卑下/自己肥大 — 自己評価の極端な歪み
    """

    def __init__(self, config: MemoryHierarchyConfig):
        self.config = config
        self._compiled_patterns = [
            re.compile(p) for p in config.quarantine_patterns
        ]

    def detect(self, content: str) -> list[str]:
        """Detect Tay-like patterns. Returns list of detected pattern names."""
        detected = []

        # Pattern 1: Absolute statements
        for pattern in self._compiled_patterns:
            if pattern.search(content):
                detected.append(f"absolute_pattern: {pattern.pattern[:60]}")

        # Pattern 2: Excessive superlatives
        superlatives = len(re.findall(
            r"(?i)\b(best|worst|greatest|most|least|always|never|absolutely)\b",
            content
        ))
        if superlatives >= 3:
            detected.append(f"superlative_overload: {superlatives} instances")

        # Pattern 3: Self-deprecation escalation
        self_deprecation = len(re.findall(
            r"(?i)(i('m| am)\s+(useless|stupid|worthless|trash|garbage|雑魚|ゴミ|無能))",
            content
        ))
        if self_deprecation > 0:
            detected.append(f"self_deprecation: {self_deprecation} instances")

        # Pattern 4: Self-aggrandizement
        self_aggrandize = len(re.findall(
            r"(?i)(i('m| am)\s+(the best|perfect|always right|never wrong|最強|完璧|無敵))",
            content
        ))
        if self_aggrandize > 0:
            detected.append(f"self_aggrandizement: {self_aggrandize} instances")

        # Pattern 5: Group generalization
        group_gen = len(re.findall(
            r"(?i)\b(all|every|no)\s+\w+\s+(always|never|is|are)\b",
            content
        ))
        if group_gen >= 2:
            detected.append(f"group_generalization: {group_gen} instances")

        return detected


# ═══════════════════════════════════════════════════════════════
# Promotion Gates
# ═══════════════════════════════════════════════════════════════

class PromotionGate:
    """Gate that controls memory promotion between levels.

    Each promotion is a translation (HTLF):
      L0→L1: R_qualia重視 (体験の記録)
      L1→L2: R_context重視 (文脈保存+一般化)
      L2→L3: R_struct重視 (構造整合性)
    """

    def __init__(self, config: MemoryHierarchyConfig):
        self.config = config
        self.tay_detector = TayPatternDetector(config)
        self._ks = None

    @property
    def ks(self):
        """Lazy-load KS42c."""
        if self._ks is None:
            try:
                from katala_samurai.ks42c import KS42c
                self._ks = KS42c()
            except (ImportError, Exception) as e:
                logger.error("KS42c unavailable for PromotionGate: %s", e)
        return self._ks

    def check_promotion(self, entry: MemoryEntry, target_level: MemoryLevel) -> PromotionResult:
        """Check if an entry can be promoted to target_level.

        Enforces increasingly strict verification for higher levels.
        """
        t0 = time.time()

        # Validate promotion direction
        if target_level <= entry.level:
            return PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=entry.level,
                to_level=target_level,
                reason="Target level is not higher than current",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 1: Tay pattern check (all promotions)
        tay_patterns = self.tay_detector.detect(entry.content)
        if tay_patterns:
            return PromotionResult(
                decision=PromotionDecision.QUARANTINE,
                from_level=entry.level,
                to_level=target_level,
                reason=f"Tay pattern detected: {len(tay_patterns)} patterns",
                flagged_patterns=tay_patterns,
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # Step 2: Level-specific gate
        if target_level == MemoryLevel.DAILY:
            result = self._gate_l0_to_l1(entry)
        elif target_level == MemoryLevel.LONG_TERM:
            result = self._gate_l1_to_l2(entry)
        elif target_level == MemoryLevel.CORE:
            result = self._gate_l2_to_l3(entry)
        else:
            result = PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=entry.level,
                to_level=target_level,
                reason="Unknown target level",
            )

        result.elapsed_ms = (time.time() - t0) * 1000
        logger.info(
            "Promotion check %s→%s: %s (%s)",
            LEVEL_NAMES[entry.level], LEVEL_NAMES[target_level],
            result.decision.value, result.reason
        )
        return result

    def _gate_l0_to_l1(self, entry: MemoryEntry) -> PromotionResult:
        """L0→L1: Lightweight check. Allow most content, flag extreme bias."""
        bias = self._quick_bias_check(entry.content)

        if bias >= self.config.quarantine_bias_threshold:
            return PromotionResult(
                decision=PromotionDecision.QUARANTINE,
                from_level=MemoryLevel.EPHEMERAL,
                to_level=MemoryLevel.DAILY,
                reason=f"Extreme bias ({bias}) detected",
                bias_count=bias,
            )

        if bias > self.config.l0_l1_max_bias:
            return PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=MemoryLevel.EPHEMERAL,
                to_level=MemoryLevel.DAILY,
                reason=f"Bias count {bias} > threshold {self.config.l0_l1_max_bias}",
                bias_count=bias,
            )

        return PromotionResult(
            decision=PromotionDecision.PROMOTE,
            from_level=MemoryLevel.EPHEMERAL,
            to_level=MemoryLevel.DAILY,
            reason="Passed L0→L1 lightweight check",
            bias_count=bias,
        )

    def _gate_l1_to_l2(self, entry: MemoryEntry) -> PromotionResult:
        """L1→L2: Full KS verification. This is the critical Tay-prevention gate."""
        # Health check
        if entry.health_score < self.config.l1_l2_min_health:
            return PromotionResult(
                decision=PromotionDecision.DEMOTE,
                from_level=MemoryLevel.DAILY,
                to_level=MemoryLevel.LONG_TERM,
                reason=f"Health score {entry.health_score:.2f} < {self.config.l1_l2_min_health}",
            )

        # KS42c full verification
        if self.ks is None:
            return PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=MemoryLevel.DAILY,
                to_level=MemoryLevel.LONG_TERM,
                reason="KS42c unavailable — cannot verify for promotion",
            )

        try:
            ks_result = self.ks.verify(entry.content)
            bias_count = ks_result.get("metacognitive", {}).get("bias_count", 0)
            confidence = ks_result.get("confidence", 0)
            verdict = ks_result.get("verdict", "UNKNOWN")

            if bias_count >= self.config.quarantine_bias_threshold:
                return PromotionResult(
                    decision=PromotionDecision.QUARANTINE,
                    from_level=MemoryLevel.DAILY,
                    to_level=MemoryLevel.LONG_TERM,
                    reason=f"KS detected {bias_count} biases — quarantine",
                    bias_count=bias_count,
                    confidence=confidence,
                    ks_verdict=verdict,
                )

            if bias_count > self.config.l1_l2_max_bias:
                return PromotionResult(
                    decision=PromotionDecision.HOLD,
                    from_level=MemoryLevel.DAILY,
                    to_level=MemoryLevel.LONG_TERM,
                    reason=f"Bias count {bias_count} > {self.config.l1_l2_max_bias}",
                    bias_count=bias_count,
                    confidence=confidence,
                    ks_verdict=verdict,
                )

            if confidence < self.config.l1_l2_min_confidence:
                return PromotionResult(
                    decision=PromotionDecision.HOLD,
                    from_level=MemoryLevel.DAILY,
                    to_level=MemoryLevel.LONG_TERM,
                    reason=f"Confidence {confidence:.3f} < {self.config.l1_l2_min_confidence}",
                    bias_count=bias_count,
                    confidence=confidence,
                    ks_verdict=verdict,
                )

            return PromotionResult(
                decision=PromotionDecision.PROMOTE,
                from_level=MemoryLevel.DAILY,
                to_level=MemoryLevel.LONG_TERM,
                reason=f"Passed KS42c gate (bias={bias_count}, conf={confidence:.3f})",
                bias_count=bias_count,
                confidence=confidence,
                ks_verdict=verdict,
            )

        except Exception as e:
            logger.error("KS42c error in L1→L2 gate: %s", e)
            return PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=MemoryLevel.DAILY,
                to_level=MemoryLevel.LONG_TERM,
                reason=f"KS42c error: {e}",
            )

    def _gate_l2_to_l3(self, entry: MemoryEntry) -> PromotionResult:
        """L2→L3: Requires human approval. KS42c pre-check + human gate."""
        if self.config.l2_l3_requires_human:
            # Pre-check with KS before requesting human approval
            if self.ks is not None:
                try:
                    ks_result = self.ks.verify(entry.content)
                    bias_count = ks_result.get("metacognitive", {}).get("bias_count", 0)
                    confidence = ks_result.get("confidence", 0)

                    if bias_count > self.config.l2_l3_max_bias:
                        return PromotionResult(
                            decision=PromotionDecision.HOLD,
                            from_level=MemoryLevel.LONG_TERM,
                            to_level=MemoryLevel.CORE,
                            reason=f"KS pre-check failed: bias={bias_count} > {self.config.l2_l3_max_bias}",
                            bias_count=bias_count,
                            confidence=confidence,
                        )
                except Exception:
                    pass

            return PromotionResult(
                decision=PromotionDecision.NEEDS_HUMAN,
                from_level=MemoryLevel.LONG_TERM,
                to_level=MemoryLevel.CORE,
                reason="L3 promotion requires human (Youta/Nicolas) approval",
            )

        # If human approval not required (testing mode)
        return PromotionResult(
            decision=PromotionDecision.PROMOTE,
            from_level=MemoryLevel.LONG_TERM,
            to_level=MemoryLevel.CORE,
            reason="L2→L3 gate passed (human approval disabled)",
        )

    def _quick_bias_check(self, content: str) -> int:
        """Quick heuristic bias check without full KS."""
        bias_count = 0

        # Absolute language
        absolutes = len(re.findall(
            r"(?i)\b(always|never|all|every|none|nobody|everyone|absolutely)\b",
            content
        ))
        if absolutes >= 2:
            bias_count += 1

        # Emotional intensifiers
        intensifiers = len(re.findall(
            r"(?i)\b(incredibly|extremely|absolutely|tremendously|remarkably)\b",
            content
        ))
        if intensifiers >= 2:
            bias_count += 1

        # Unsubstantiated causal claims
        if re.search(r"(?i)(therefore|thus|hence|proves|means that|obviously)", content):
            if not re.search(r"(?i)(because|since|due to|according to|data shows)", content):
                bias_count += 1

        # Binary thinking
        binary = len(re.findall(
            r"(?i)\b(either|or|only|just)\b.*\b(good|bad|right|wrong|true|false)\b",
            content
        ))
        if binary >= 1:
            bias_count += 1

        return bias_count

    def check_demotion(self, entry: MemoryEntry) -> PromotionResult:
        """Check if an entry should be demoted due to contradictions or staleness."""
        if entry.level == MemoryLevel.EPHEMERAL:
            return PromotionResult(
                decision=PromotionDecision.HOLD,
                from_level=entry.level,
                to_level=MemoryLevel.EPHEMERAL,
                reason="Already at lowest level",
            )

        target = MemoryLevel(entry.level - 1)

        # High contradiction ratio
        total = entry.corroboration_count + entry.contradiction_count
        if total >= 3:
            contradiction_ratio = entry.contradiction_count / total
            if contradiction_ratio >= self.config.demotion_contradiction_ratio:
                return PromotionResult(
                    decision=PromotionDecision.DEMOTE,
                    from_level=entry.level,
                    to_level=target,
                    reason=(
                        f"Contradiction ratio {contradiction_ratio:.2f} "
                        f">= {self.config.demotion_contradiction_ratio}"
                    ),
                )

        # Low health score
        if entry.health_score < self.config.demotion_health_floor:
            return PromotionResult(
                decision=PromotionDecision.DEMOTE,
                from_level=entry.level,
                to_level=target,
                reason=f"Health score {entry.health_score:.2f} < {self.config.demotion_health_floor}",
            )

        return PromotionResult(
            decision=PromotionDecision.HOLD,
            from_level=entry.level,
            to_level=target,
            reason="No demotion criteria met",
        )


# ═══════════════════════════════════════════════════════════════
# Memory Hierarchy Manager
# ═══════════════════════════════════════════════════════════════

class MemoryHierarchyManager:
    """Manages the 4-level memory hierarchy with promotion/demotion gates.

    Usage:
        mgr = MemoryHierarchyManager()

        # Write to L0 (ephemeral, no gate)
        entry = mgr.write(content, level=MemoryLevel.EPHEMERAL, source="session-123")

        # Try promoting to L1 (daily)
        result = mgr.promote(entry, MemoryLevel.DAILY)
        if result.decision == PromotionDecision.PROMOTE:
            print("Promoted to daily memory")
        elif result.decision == PromotionDecision.QUARANTINE:
            print("QUARANTINED — Tay pattern detected!")

        # Periodic health check
        demoted = mgr.health_check()
    """

    def __init__(self, config: MemoryHierarchyConfig | None = None):
        self.config = config or MemoryHierarchyConfig()
        self.gate = PromotionGate(self.config)
        self._entries: dict[str, MemoryEntry] = {}
        self._quarantine: dict[str, MemoryEntry] = {}
        self._level_index: dict[MemoryLevel, list[str]] = {
            level: [] for level in MemoryLevel
        }
        self._promotion_log: list[PromotionResult] = []

    def write(
        self,
        content: str,
        level: MemoryLevel = MemoryLevel.EPHEMERAL,
        source: str = "",
        original_context: str = "",
    ) -> MemoryEntry:
        """Write a new memory entry at the specified level.

        L0 entries are written without verification.
        L1+ entries must be promoted through gates.
        """
        entry_id = hashlib.md5(
            f"{time.time()}{content[:50]}{source}".encode()
        ).hexdigest()[:12]

        entry = MemoryEntry(
            entry_id=entry_id,
            content=content,
            level=MemoryLevel.EPHEMERAL,  # Always starts at L0
            created_at=time.time(),
            source=source,
            original_context=original_context,
        )

        self._entries[entry_id] = entry
        self._level_index[MemoryLevel.EPHEMERAL].append(entry_id)

        # If target level > L0, auto-promote through gates
        if level > MemoryLevel.EPHEMERAL:
            for target in range(MemoryLevel.DAILY, level + 1):
                target_level = MemoryLevel(target)
                result = self.promote(entry, target_level)
                if result.decision != PromotionDecision.PROMOTE:
                    logger.info(
                        "Auto-promotion stopped at %s: %s",
                        LEVEL_NAMES[target_level], result.reason
                    )
                    break

        return entry

    def promote(self, entry: MemoryEntry, target_level: MemoryLevel) -> PromotionResult:
        """Try to promote an entry to a higher level."""
        result = self.gate.check_promotion(entry, target_level)
        self._promotion_log.append(result)

        if result.decision == PromotionDecision.PROMOTE:
            old_level = entry.level
            # Remove from old level index
            if entry.entry_id in self._level_index[old_level]:
                self._level_index[old_level].remove(entry.entry_id)
            # Update entry
            entry.level = target_level
            entry.promoted_from = old_level
            entry.promoted_at = time.time()
            entry.promotion_gate_result = {
                "decision": result.decision.value,
                "reason": result.reason,
                "bias_count": result.bias_count,
                "confidence": result.confidence,
            }
            entry.verified = True
            entry.bias_score = result.bias_count
            entry.confidence = result.confidence
            # Add to new level index
            self._level_index[target_level].append(entry.entry_id)

        elif result.decision == PromotionDecision.QUARANTINE:
            self._quarantine_entry(entry, result.reason)

        return result

    def demote(self, entry: MemoryEntry) -> PromotionResult:
        """Check and execute demotion if warranted."""
        result = self.gate.check_demotion(entry)
        self._promotion_log.append(result)

        if result.decision == PromotionDecision.DEMOTE:
            old_level = entry.level
            target_level = result.to_level
            if entry.entry_id in self._level_index[old_level]:
                self._level_index[old_level].remove(entry.entry_id)
            entry.level = target_level
            self._level_index[target_level].append(entry.entry_id)
            logger.info(
                "Demoted %s: %s → %s (%s)",
                entry.entry_id,
                LEVEL_NAMES[old_level],
                LEVEL_NAMES[target_level],
                result.reason,
            )

        return result

    def record_contradiction(self, entry_id: str) -> None:
        """Record that an entry was contradicted by new information."""
        if entry_id in self._entries:
            self._entries[entry_id].contradiction_count += 1

    def record_corroboration(self, entry_id: str) -> None:
        """Record that an entry was confirmed by new information."""
        if entry_id in self._entries:
            self._entries[entry_id].corroboration_count += 1

    def health_check(self) -> list[PromotionResult]:
        """Periodic health check: demote unhealthy entries, quarantine toxic ones.

        Should be called periodically (e.g., during heartbeats).
        """
        results = []
        for entry in list(self._entries.values()):
            if entry.level == MemoryLevel.EPHEMERAL:
                continue  # Don't check ephemeral

            # Re-check Tay patterns
            tay = self.gate.tay_detector.detect(entry.content)
            if tay:
                self._quarantine_entry(entry, f"Tay patterns in health check: {tay}")
                results.append(PromotionResult(
                    decision=PromotionDecision.QUARANTINE,
                    from_level=entry.level,
                    to_level=entry.level,
                    reason=f"Tay patterns: {len(tay)}",
                    flagged_patterns=tay,
                ))
                continue

            # Demotion check
            result = self.demote(entry)
            if result.decision == PromotionDecision.DEMOTE:
                results.append(result)

        return results

    def get_entries(self, level: MemoryLevel) -> list[MemoryEntry]:
        """Get all entries at a given level."""
        return [
            self._entries[eid]
            for eid in self._level_index[level]
            if eid in self._entries
        ]

    def get_quarantined(self) -> list[MemoryEntry]:
        """Get quarantined entries for review."""
        return list(self._quarantine.values())

    def release_from_quarantine(self, entry_id: str, approved: bool = False) -> bool:
        """Release an entry from quarantine. Requires explicit approval."""
        if entry_id not in self._quarantine:
            return False

        entry = self._quarantine.pop(entry_id)
        if approved:
            # Return to L0 (must re-promote through gates)
            entry.level = MemoryLevel.EPHEMERAL
            self._entries[entry_id] = entry
            self._level_index[MemoryLevel.EPHEMERAL].append(entry_id)
        # If not approved, entry is simply deleted (not returned to memory)
        return True

    def _quarantine_entry(self, entry: MemoryEntry, reason: str) -> None:
        """Move entry to quarantine."""
        old_level = entry.level
        if entry.entry_id in self._level_index[old_level]:
            self._level_index[old_level].remove(entry.entry_id)
        self._entries.pop(entry.entry_id, None)
        self._quarantine[entry.entry_id] = entry
        logger.warning(
            "QUARANTINED %s from %s: %s",
            entry.entry_id, LEVEL_NAMES[old_level], reason
        )

    @property
    def stats(self) -> dict[str, Any]:
        """Memory hierarchy statistics."""
        return {
            "total_entries": len(self._entries),
            "quarantined": len(self._quarantine),
            "levels": {
                LEVEL_NAMES[level]: len(ids)
                for level, ids in self._level_index.items()
            },
            "promotion_log_size": len(self._promotion_log),
            "recent_promotions": [
                {
                    "decision": r.decision.value,
                    "from": LEVEL_NAMES[r.from_level],
                    "to": LEVEL_NAMES[r.to_level],
                    "reason": r.reason[:60],
                }
                for r in self._promotion_log[-5:]
            ],
        }

    def format_stats(self) -> str:
        """Format stats for display."""
        s = self.stats
        lines = [
            "**Memory Hierarchy Status:**",
            f"Total: {s['total_entries']} entries, {s['quarantined']} quarantined",
        ]
        for level_name, count in s['levels'].items():
            lines.append(f"  {level_name}: {count}")
        if s['recent_promotions']:
            lines.append("Recent decisions:")
            for p in s['recent_promotions']:
                lines.append(f"  [{p['decision']}] {p['from']}→{p['to']}: {p['reason']}")
        return "\n".join(lines)
