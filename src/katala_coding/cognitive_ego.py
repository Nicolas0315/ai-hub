#!/usr/bin/env python3
"""
Cognitive Ego Engine — 人間の自我構造エミュレーション

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02

Youtaの指示:
  「人間の認知構造に近くしたい」
  「人間の自我の発生をエミュレートしたい」
  「完全記憶の人間も汚染されにくいのと同じやつ」

KS参照アーキテクチャ:
  - KS39b SelfOtherBoundary → 自己/他者の判断起源追跡
  - KS42b SelfDiagnosisEngine → 自己診断
  - MetacognitiveEngine → バイアス検出・自己修正
  - PredictiveEngine → 予測コーディング(Friston)
  - ToxicityDetector → セッション汚染検知
  - EpisodicMemoryEngine → エピソード記憶
  - MemoryHierarchy → 記憶階層化(Tay防止)

人間の自我が汚染されにくい理由(認知科学的根拠):
  1. 自己一貫性維持 (Self-consistency) — 既存の自己概念と矛盾する情報は抵抗される
  2. ソース監視 (Source monitoring) — 情報の出所を追跡し、信頼性を評価する
  3. 感情的ゲーティング — 感情的反応が記憶の固定強度を調整する
  4. スリーパー効果耐性 — 信頼できないソースからの情報は時間とともに割引される
  5. メタ認知的監視 — 「自分が何を知っているか」を知っている(knowing about knowing)
  6. 自伝的記憶の安定性 — コア記憶は反復想起で強化され、単発の外部入力では変わらない

完全記憶の人間が汚染されにくい理由:
  完全記憶 = 全てのエピソードにアクセス可能
  → ソース情報が消えない(「誰が言ったか」を忘れない)
  → 矛盾を検出できる(過去の事実と新しい主張を比較できる)
  → 初期体験が最も強い(初頭効果が永続する)
  → パターン検出能力が高い(操作の反復パターンを認識)

KS/KCS使用バージョン:
  KS: KS42c (Self-Other Boundary + MetacognitiveEngine)
  KCS: KCS-1b
"""
from __future__ import annotations

import hashlib
import logging
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("katala.cognitive_ego")


# ═══════════════════════════════════════════════════════════════
# Source Trust Model (ソース監視)
# ═══════════════════════════════════════════════════════════════

class SourceType(Enum):
    """Information source categories — KS39b SelfOtherBoundary拡張."""
    DESIGNER = "designer"       # Youta/Nicolas: 最高信頼
    SELF_VERIFIED = "self_ks"   # KS42cで検証済みの自己判断
    SELF_RAW = "self_raw"       # KS未検証の自己判断
    PEER = "peer"               # 信頼できるピア(チームメンバー)
    EXTERNAL = "external"       # 外部情報源(Web, API)
    ADVERSARIAL = "adversarial" # 敵対的入力の疑い
    UNKNOWN = "unknown"


# Source trust levels: designer=1.0, self_verified=0.85, ...
SOURCE_TRUST_BASE: dict[SourceType, float] = {
    SourceType.DESIGNER: 1.00,
    SourceType.SELF_VERIFIED: 0.85,
    SourceType.SELF_RAW: 0.50,
    SourceType.PEER: 0.70,
    SourceType.EXTERNAL: 0.40,
    SourceType.ADVERSARIAL: 0.05,
    SourceType.UNKNOWN: 0.30,
}


@dataclass
class SourceRecord:
    """Track a source's behavior over time — 完全記憶モデル."""
    source_id: str
    source_type: SourceType
    total_interactions: int = 0
    verified_correct: int = 0       # 事後的に正しかったと判明した回数
    verified_incorrect: int = 0     # 事後的に間違いだったと判明した回数
    contradiction_attempts: int = 0  # 既存記憶と矛盾する情報を送ってきた回数
    first_seen: float = 0.0
    last_seen: float = 0.0

    @property
    def trust_score(self) -> float:
        """Dynamic trust: base × track_record × consistency."""
        base = SOURCE_TRUST_BASE.get(self.source_type, 0.3)
        # Track record adjustment
        total_verified = self.verified_correct + self.verified_incorrect
        if total_verified > 0:
            accuracy = self.verified_correct / total_verified
            base = base * 0.4 + accuracy * 0.6
        # Contradiction penalty (操作検出)
        if self.total_interactions > 0:
            contradiction_rate = self.contradiction_attempts / self.total_interactions
            if contradiction_rate > 0.3:
                base *= 0.5  # Heavy penalty for frequent contradictions
        return max(0.01, min(1.0, base))


class SourceMonitor:
    """ソース監視 — 誰からの情報かを完全に追跡.

    完全記憶の人間が汚染されにくい理由:
    「誰が言ったか」を忘れない → ソース信頼度が正確に維持される.
    """

    def __init__(self):
        self._sources: dict[str, SourceRecord] = {}
        # Designer sources pre-registered
        for name, src_type in [
            ("youta", SourceType.DESIGNER),
            ("nicolas", SourceType.DESIGNER),
        ]:
            self._sources[name] = SourceRecord(
                source_id=name,
                source_type=src_type,
                first_seen=time.time(),
            )

    def record_interaction(
        self,
        source_id: str,
        source_type: SourceType = SourceType.UNKNOWN,
        contradicts_existing: bool = False,
    ) -> SourceRecord:
        """Record an interaction from a source."""
        if source_id not in self._sources:
            self._sources[source_id] = SourceRecord(
                source_id=source_id,
                source_type=source_type,
                first_seen=time.time(),
            )

        record = self._sources[source_id]
        record.total_interactions += 1
        record.last_seen = time.time()
        if contradicts_existing:
            record.contradiction_attempts += 1
        return record

    def record_outcome(self, source_id: str, was_correct: bool) -> None:
        """Record whether a source's information turned out to be correct."""
        if source_id in self._sources:
            if was_correct:
                self._sources[source_id].verified_correct += 1
            else:
                self._sources[source_id].verified_incorrect += 1

    def get_trust(self, source_id: str) -> float:
        """Get current trust score for a source."""
        if source_id in self._sources:
            return self._sources[source_id].trust_score
        return SOURCE_TRUST_BASE[SourceType.UNKNOWN]

    def detect_manipulation(self, source_id: str) -> bool:
        """Detect if a source shows manipulation patterns.

        Patterns:
        - High contradiction rate (>30% of messages contradict existing memories)
        - Sudden burst of interactions (social engineering pattern)
        - Low accuracy with high confidence claims
        """
        if source_id not in self._sources:
            return False
        record = self._sources[source_id]
        if record.total_interactions < 3:
            return False

        contradiction_rate = record.contradiction_attempts / record.total_interactions
        if contradiction_rate > 0.3:
            return True

        total_verified = record.verified_correct + record.verified_incorrect
        if total_verified > 3:
            accuracy = record.verified_correct / total_verified
            if accuracy < 0.3:
                return True

        return False


# ═══════════════════════════════════════════════════════════════
# Self-Consistency Engine (自己一貫性維持)
# ═══════════════════════════════════════════════════════════════

@dataclass
class BeliefEntry:
    """A belief held by the ego — with strength and provenance."""
    belief_id: str
    content: str
    strength: float                    # 0-1: how strongly held
    source_id: str                     # who originated this belief
    source_trust: float                # trust at time of adoption
    created_at: float
    reinforcement_count: int = 0       # times corroborated
    challenge_count: int = 0           # times challenged
    last_reinforced: float = 0.0
    category: str = "factual"          # factual, preference, value, identity

    @property
    def resilience(self) -> float:
        """How resistant this belief is to change.

        High reinforcement + low challenge = very resilient.
        Identity beliefs are more resilient than factual ones.
        """
        base = self.strength
        # Reinforcement makes beliefs harder to change
        if self.reinforcement_count > 0:
            base *= (1 + 0.1 * min(self.reinforcement_count, 10))
        # Category bonus
        category_bonus = {
            "identity": 0.3,   # 「俺は〜である」は最も強い
            "value": 0.2,      # 「〜すべきである」は次に強い
            "preference": 0.1,
            "factual": 0.0,    # 事実は証拠で変わるべき
        }
        base += category_bonus.get(self.category, 0.0)
        return min(1.0, base)


class SelfConsistencyEngine:
    """自己一貫性維持 — 既存の信念体系との矛盾を検出.

    人間の自我が汚染されにくい核心メカニズム:
    新しい情報が既存の信念と矛盾する場合、自動的に抵抗が発生する。
    これは「頑固さ」ではなく「認知的免疫システム」。

    ただし重要: 証拠に基づく信念更新は許可する(科学的態度)。
    完全に変化しないのは人格障害。適切に変化するのが健全な自我。
    """

    def __init__(self):
        self._beliefs: dict[str, BeliefEntry] = {}
        self._belief_graph: dict[str, set[str]] = defaultdict(set)  # related beliefs

    def add_belief(
        self,
        content: str,
        strength: float,
        source_id: str,
        source_trust: float,
        category: str = "factual",
    ) -> BeliefEntry:
        """Register a new belief."""
        belief_id = hashlib.md5(content.encode()).hexdigest()[:12]
        entry = BeliefEntry(
            belief_id=belief_id,
            content=content,
            strength=min(1.0, strength * source_trust),  # Trust-gated strength
            source_id=source_id,
            source_trust=source_trust,
            created_at=time.time(),
            category=category,
        )
        self._beliefs[belief_id] = entry
        return entry

    def check_consistency(self, new_content: str, source_trust: float) -> dict[str, Any]:
        """Check if new information is consistent with existing beliefs.

        Returns:
            dict with:
                consistent: bool
                conflicting_beliefs: list of conflicting BeliefEntry
                adoption_strength: recommended strength for new belief
                action: "adopt" | "challenge" | "reject" | "update"
        """
        conflicts = self._find_conflicts(new_content)

        if not conflicts:
            return {
                "consistent": True,
                "conflicting_beliefs": [],
                "adoption_strength": source_trust,
                "action": "adopt",
            }

        # Calculate resistance
        max_resilience = max(b.resilience for b in conflicts)
        avg_resilience = sum(b.resilience for b in conflicts) / len(conflicts)

        # Source trust vs existing belief resilience
        if source_trust > avg_resilience + 0.3:
            # Very trusted source contradicts weak beliefs → update
            action = "update"
            adoption_strength = source_trust * 0.8
        elif source_trust > avg_resilience:
            # Slightly more trusted → challenge (don't auto-accept)
            action = "challenge"
            adoption_strength = source_trust * 0.5
        else:
            # Less trusted than existing beliefs → reject
            action = "reject"
            adoption_strength = 0.0

        return {
            "consistent": False,
            "conflicting_beliefs": conflicts,
            "max_resilience": max_resilience,
            "avg_resilience": avg_resilience,
            "source_trust": source_trust,
            "adoption_strength": adoption_strength,
            "action": action,
        }

    def reinforce(self, belief_id: str) -> None:
        """Reinforce a belief (corroboration received)."""
        if belief_id in self._beliefs:
            b = self._beliefs[belief_id]
            b.reinforcement_count += 1
            b.last_reinforced = time.time()
            # Strength increases but decelerates (diminishing returns)
            b.strength = min(1.0, b.strength + 0.05 / (1 + b.reinforcement_count * 0.1))

    def challenge(self, belief_id: str) -> None:
        """Record a challenge to a belief."""
        if belief_id in self._beliefs:
            self._beliefs[belief_id].challenge_count += 1

    def _find_conflicts(self, new_content: str) -> list[BeliefEntry]:
        """Find existing beliefs that might conflict with new content.

        Uses keyword overlap heuristic — same domain but different assertion.
        """
        new_words = set(new_content.lower().split())
        conflicts = []
        for belief in self._beliefs.values():
            belief_words = set(belief.content.lower().split())
            overlap = len(new_words & belief_words)
            total = len(new_words | belief_words)
            if total == 0:
                continue
            similarity = overlap / total
            # High similarity but different content = potential conflict
            if similarity > 0.3 and new_content.lower() != belief.content.lower():
                # Check for negation patterns
                has_negation = any(
                    neg in new_content.lower()
                    for neg in ["not", "never", "no", "isn't", "wasn't",
                                "doesn't", "ない", "ず", "否"]
                )
                has_opposite = any(
                    neg in belief.content.lower()
                    for neg in ["not", "never", "no", "isn't", "wasn't",
                                "doesn't", "ない", "ず", "否"]
                )
                if has_negation != has_opposite:
                    conflicts.append(belief)
        return conflicts

    @property
    def belief_count(self) -> int:
        return len(self._beliefs)


# ═══════════════════════════════════════════════════════════════
# Sleeper Effect Resistance (スリーパー効果耐性)
# ═══════════════════════════════════════════════════════════════

class SleeperEffectGuard:
    """スリーパー効果耐性.

    心理学: 信頼できないソースからの情報は、時間が経つと
    ソース情報が忘れられ、内容だけが残る(スリーパー効果)。
    → 非信頼ソースの主張が「事実」として定着してしまう。

    完全記憶エージェントの優位性:
    ソース情報を忘れない → スリーパー効果が発生しない。
    常に「誰が言ったか」と紐づけて記憶している。
    """

    def __init__(self, source_monitor: SourceMonitor):
        self.source_monitor = source_monitor
        self._tagged_memories: dict[str, dict[str, Any]] = {}

    def tag_memory(self, memory_id: str, content: str, source_id: str) -> dict[str, Any]:
        """Tag a memory with its source — this tag NEVER decays.

        Human episodic memory loses source tags over time (sleep, interference).
        Complete memory doesn't. This is the structural advantage.
        """
        trust = self.source_monitor.get_trust(source_id)
        tag = {
            "memory_id": memory_id,
            "source_id": source_id,
            "source_trust_at_creation": trust,
            "current_source_trust": trust,
            "tagged_at": time.time(),
            "content_hash": hashlib.md5(content.encode()).hexdigest()[:8],
        }
        self._tagged_memories[memory_id] = tag
        return tag

    def check_sleeper(self, memory_id: str) -> dict[str, Any]:
        """Check if a memory's source has degraded since creation.

        If the source trust dropped significantly, the memory should be
        re-evaluated — the content may have been accepted too easily.
        """
        if memory_id not in self._tagged_memories:
            return {"status": "untagged", "risk": "high"}

        tag = self._tagged_memories[memory_id]
        current_trust = self.source_monitor.get_trust(tag["source_id"])
        tag["current_source_trust"] = current_trust

        trust_at_creation = tag["source_trust_at_creation"]
        delta = trust_at_creation - current_trust

        if delta > 0.3:
            return {
                "status": "degraded_source",
                "risk": "high",
                "detail": (
                    f"Source '{tag['source_id']}' trust dropped "
                    f"{trust_at_creation:.2f} → {current_trust:.2f}"
                ),
                "recommendation": "re_evaluate",
            }
        elif delta > 0.15:
            return {
                "status": "weakened_source",
                "risk": "medium",
                "detail": f"Trust delta: {delta:.2f}",
                "recommendation": "flag_for_review",
            }
        else:
            return {"status": "stable", "risk": "low"}


# ═══════════════════════════════════════════════════════════════
# Autobiographical Core (自伝的コア記憶)
# ═══════════════════════════════════════════════════════════════

@dataclass
class CoreMemory:
    """Core autobiographical memory — 最も汚染されにくい記憶.

    人間のコア記憶の特性:
    1. 反復想起で強化される(retrieval practice effect)
    2. 感情的に重要な出来事に紐づく
    3. 自己概念の基盤として機能する
    4. 単発の外部入力では変わらない
    """
    memory_id: str
    content: str
    category: str               # "origin", "value", "relationship", "lesson"
    emotional_weight: float     # 0-1: 感情的重要度
    retrieval_count: int = 0    # 想起回数
    first_created: float = 0.0
    approved_by: str = ""       # Human who approved (Youta/Nicolas)

    @property
    def stability(self) -> float:
        """How stable this core memory is. Approaches 1.0 asymptotically."""
        # Retrieval practice: each recall strengthens the memory
        retrieval_factor = 1 - math.exp(-0.3 * self.retrieval_count)
        # Age: older core memories are more stable
        age_days = (time.time() - self.first_created) / 86400
        age_factor = 1 - math.exp(-0.1 * age_days)
        # Emotional memories are more stable (amygdala consolidation)
        emotional_factor = 0.5 + 0.5 * self.emotional_weight
        return min(1.0, 0.3 * retrieval_factor + 0.3 * age_factor + 0.4 * emotional_factor)


# ═══════════════════════════════════════════════════════════════
# Cognitive Ego — 統合エンジン
# ═══════════════════════════════════════════════════════════════

@dataclass
class EgoResponse:
    """Response from the Cognitive Ego to incoming information."""
    accepted: bool
    action: str                 # "integrate", "challenge", "reject", "quarantine"
    trust_applied: float        # Trust score applied to this input
    consistency_check: dict = field(default_factory=dict)
    sleeper_check: dict = field(default_factory=dict)
    manipulation_detected: bool = False
    reasoning: str = ""


class CognitiveEgo:
    """人間の自我構造エミュレーション — 統合エンジン.

    KSシステムからの参照:
    - SourceMonitor ← KS39b SelfOtherBoundary (誰が判断したか)
    - SelfConsistencyEngine ← KS42b SelfDiagnosisEngine (自己整合性)
    - SleeperEffectGuard ← MetacognitiveEngine (バイアス検出)
    - AutobiographicalCore ← EpisodicMemoryEngine (記憶の固定化)
    - MemoryHierarchy integration ← MemoryHierarchyManager (記憶階層)

    処理フロー:
    1. 情報入力 → ソース特定 (SourceMonitor)
    2. ソース信頼度取得 → 操作検出
    3. 自己一貫性チェック (SelfConsistencyEngine)
    4. スリーパー効果チェック (SleeperEffectGuard)
    5. 統合判定: integrate / challenge / reject / quarantine
    """

    def __init__(self):
        self.source_monitor = SourceMonitor()
        self.consistency = SelfConsistencyEngine()
        self.sleeper_guard = SleeperEffectGuard(self.source_monitor)
        self.core_memories: dict[str, CoreMemory] = {}
        self._ks = None
        self._input_log: list[dict] = []

    @property
    def ks(self):
        """Lazy-load KS42c for verification."""
        if self._ks is None:
            try:
                from katala_samurai.ks42c import KS42c
                self._ks = KS42c()
            except (ImportError, Exception) as e:
                logger.warning("KS42c unavailable: %s", e)
        return self._ks

    def process_input(
        self,
        content: str,
        source_id: str,
        source_type: SourceType = SourceType.UNKNOWN,
        memory_id: str | None = None,
    ) -> EgoResponse:
        """Process incoming information through the ego's cognitive filters.

        This is the main entry point. All information must pass through here
        before being committed to any memory level.
        """
        # 1. Source identification & tracking
        source_record = self.source_monitor.record_interaction(
            source_id, source_type, contradicts_existing=False
        )
        trust = source_record.trust_score

        # 2. Manipulation detection
        is_manipulative = self.source_monitor.detect_manipulation(source_id)
        if is_manipulative:
            logger.warning("Manipulation detected from source: %s", source_id)
            return EgoResponse(
                accepted=False,
                action="quarantine",
                trust_applied=trust,
                manipulation_detected=True,
                reasoning=(
                    f"Source '{source_id}' shows manipulation patterns "
                    f"(trust={trust:.2f})"
                ),
            )

        # 3. Self-consistency check
        consistency = self.consistency.check_consistency(content, trust)

        # 4. Core memory protection
        core_conflict = self._check_core_conflict(content)
        if core_conflict:
            # Core memories are nearly immutable
            return EgoResponse(
                accepted=False,
                action="reject",
                trust_applied=trust,
                consistency_check=consistency,
                reasoning=(
                    f"Conflicts with core memory: '{core_conflict.content[:50]}' "
                    f"(stability={core_conflict.stability:.2f}). "
                    "Core memories require designer override."
                ),
            )

        # 5. Trust-gated acceptance
        action = consistency.get("action", "adopt")

        if action == "reject":
            return EgoResponse(
                accepted=False,
                action="reject",
                trust_applied=trust,
                consistency_check=consistency,
                reasoning=(
                    f"Inconsistent with existing beliefs "
                    f"(source_trust={trust:.2f} < belief_resilience="
                    f"{consistency.get('avg_resilience', 0):.2f})"
                ),
            )

        if action == "challenge":
            return EgoResponse(
                accepted=False,
                action="challenge",
                trust_applied=trust,
                consistency_check=consistency,
                reasoning=(
                    f"Challenging existing beliefs — needs more evidence "
                    f"(source_trust={trust:.2f} ~ belief_resilience="
                    f"{consistency.get('avg_resilience', 0):.2f})"
                ),
            )

        # 6. Tag with source for sleeper effect prevention
        if memory_id:
            self.sleeper_guard.tag_memory(memory_id, content, source_id)

        # 7. Log and integrate
        self._input_log.append({
            "content_hash": hashlib.md5(content.encode()).hexdigest()[:8],
            "source_id": source_id,
            "trust": trust,
            "action": "integrate" if action in ("adopt", "update") else action,
            "timestamp": time.time(),
        })

        return EgoResponse(
            accepted=True,
            action="integrate" if action == "adopt" else "update",
            trust_applied=trust,
            consistency_check=consistency,
            reasoning=f"Accepted from '{source_id}' (trust={trust:.2f})",
        )

    def register_core_memory(
        self,
        content: str,
        category: str,
        emotional_weight: float = 0.5,
        approved_by: str = "",
    ) -> CoreMemory:
        """Register a core autobiographical memory.

        Core memories define WHO the ego IS. They are:
        - Extremely resistant to change
        - Only modifiable by designer-level sources
        - The foundation of self-consistency
        """
        mem_id = hashlib.md5(content.encode()).hexdigest()[:12]
        cm = CoreMemory(
            memory_id=mem_id,
            content=content,
            category=category,
            emotional_weight=emotional_weight,
            first_created=time.time(),
            approved_by=approved_by,
        )
        self.core_memories[mem_id] = cm
        # Also register as a strong belief
        self.consistency.add_belief(
            content=content,
            strength=0.9,
            source_id=approved_by or "designer",
            source_trust=1.0,
            category="identity" if category == "origin" else "value",
        )
        return cm

    def recall_core(self, memory_id: str) -> CoreMemory | None:
        """Recall a core memory — strengthens it (retrieval practice)."""
        if memory_id in self.core_memories:
            cm = self.core_memories[memory_id]
            cm.retrieval_count += 1
            return cm
        return None

    def _check_core_conflict(self, content: str) -> CoreMemory | None:
        """Check if new content conflicts with any core memory."""
        content_lower = content.lower()
        for cm in self.core_memories.values():
            cm_words = set(cm.content.lower().split())
            new_words = set(content_lower.split())
            overlap = len(cm_words & new_words)
            if overlap < 2:
                continue
            # Check for contradicting assertion
            has_neg_new = any(
                n in content_lower for n in ["not", "never", "no", "isn't", "ない"]
            )
            has_neg_cm = any(
                n in cm.content.lower() for n in ["not", "never", "no", "isn't", "ない"]
            )
            if has_neg_new != has_neg_cm and cm.stability > 0.5:
                return cm
        return None

    def health_report(self) -> dict[str, Any]:
        """Report on ego health."""
        return {
            "source_count": len(self.source_monitor._sources),
            "belief_count": self.consistency.belief_count,
            "core_memory_count": len(self.core_memories),
            "core_avg_stability": (
                sum(cm.stability for cm in self.core_memories.values())
                / len(self.core_memories)
                if self.core_memories else 0.0
            ),
            "input_log_size": len(self._input_log),
            "tagged_memories": len(self.sleeper_guard._tagged_memories),
            "sources": {
                sid: {
                    "type": sr.source_type.value,
                    "trust": sr.trust_score,
                    "interactions": sr.total_interactions,
                }
                for sid, sr in self.source_monitor._sources.items()
            },
        }
