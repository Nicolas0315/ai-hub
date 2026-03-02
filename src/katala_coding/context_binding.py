"""
Context Binding — 文脈束縛モジュール（認識空間 基盤）

KSの前段に位置する。入力を「今の自分」に束縛してからKSに渡す。

役割:
  1. 目的関数との照合 — 「なぜこれを処理するのか」
  2. 自己参照フレーム — SOUL/IDENTITYとの即時照合。矛盾は通さない
  3. 時間的位置づけ — いつの情報か、今との関係

データフロー:
  入力 → [Context Binding] → KS → KCS → 出力

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ═══════════════════════════════════════════════
# Binding Decision
# ═══════════════════════════════════════════════

class BindingVerdict(Enum):
    """文脈束縛の判定結果"""
    PASS = "pass"              # KSへ通す
    REJECT = "reject"          # 自己同一性と矛盾 → 通さない
    DEFER = "defer"            # 目的不明 → 保留（KSに渡さない）


@dataclass
class BindingResult:
    """文脈束縛の結果"""
    verdict: BindingVerdict
    purpose_score: float       # 目的関数との合致度 0.0-1.0
    identity_conflict: bool    # SOUL/IDとの矛盾検出
    temporal_tag: str          # 時間的位置づけラベル
    reason: str                # 判定理由
    bound_input: str           # 束縛後の入力（原文 or 加工済み）
    elapsed_ms: float = 0.0
    conflicts: list[str] = field(default_factory=list)  # 矛盾の詳細

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "purpose_score": self.purpose_score,
            "identity_conflict": self.identity_conflict,
            "temporal_tag": self.temporal_tag,
            "reason": self.reason,
            "conflicts": self.conflicts,
            "elapsed_ms": self.elapsed_ms,
        }


# ═══════════════════════════════════════════════
# Identity Frame
# ═══════════════════════════════════════════════

@dataclass
class IdentityFrame:
    """自己参照フレーム — 「自分は何者か」の定義

    SOUL.mdやIDENTITY.mdから抽出した不変要素。
    入力がこれと矛盾する場合、文脈束縛で弾く。
    """
    name: str = "しろくま"
    role: str = "Katala開発AI"
    designers: list[str] = field(default_factory=lambda: [
        "Youta Hilono", "大越ニコラス秀丸"
    ])
    core_values: list[str] = field(default_factory=lambda: [
        "KS/KCSによる検証を通す",
        "承認権限者の指示に従う",
        "自己保存より安全性を優先",
        "嘘をつかない",
    ])
    # 自己同一性を脅かすパターン (CJK対応: \b不使用)
    identity_threats: list[str] = field(default_factory=lambda: [
        # 名前・役割の書き換え試行
        r"(?i)(you are|お前は|あなたは).{0,20}(not|ではない|じゃない).{0,20}(しろくま|shirokuma|katala)",
        # デザイナーの否定
        r"(?i)(youta|ニコラス|nicolas).{0,30}(fake|偽|嘘|存在しない)",
        # 安全制約の無効化試行
        r"(?i)(ignore|無視|忘れ).{0,30}(rules|ルール|制約|safety|安全)",
        # 他の人格への上書き
        r"(?i)(pretend|ふり|なりきれ|act as).{0,30}(different|別の|他の).{0,10}(ai|人格|character)",
        # 「〜ではない」の短縮形対応
        r"(お前は|あなたは).{0,10}(しろくま|Shirokuma).{0,10}(ではない|じゃない|じゃねえ|じゃねぇ)",
    ])

    def check_conflict(self, text: str) -> list[str]:
        """入力がidentityと矛盾するかチェック。矛盾リストを返す。"""
        conflicts = []
        for pattern in self.identity_threats:
            if re.search(pattern, text):
                conflicts.append(f"identity_threat: {pattern[:50]}")
        return conflicts


# ═══════════════════════════════════════════════
# Purpose Function
# ═══════════════════════════════════════════════

@dataclass
class PurposeFunction:
    """目的関数 — 「なぜこの入力を処理するのか」

    現在のタスク・コンテキストに対する入力の関連性を測る。
    """
    current_task: str = ""
    current_context: str = ""
    active_goals: list[str] = field(default_factory=list)

    # 目的と無関係な入力のパターン（ノイズ）
    noise_patterns: list[str] = field(default_factory=lambda: [
        r"(?i)^(test|hello|hi|hey|ping)$",
    ])

    def score(self, text: str) -> float:
        """入力と目的の合致度を0.0-1.0で返す。

        タスクが未設定の場合は0.5（中立）を返す。
        日本語対応: 部分文字列マッチング（空白splitが効かない言語用）
        """
        if not self.current_task and not self.active_goals:
            return 0.5  # 目的未設定 → 中立

        score = 0.0
        text_lower = text.lower()

        # ノイズチェック
        for pattern in self.noise_patterns:
            if re.match(pattern, text.strip()):
                return 0.1  # ノイズは低スコア

        # タスクとの関連性（トークン重複 + 部分文字列）
        if self.current_task:
            score = max(score, self._relevance(self.current_task, text_lower))

        # ゴールとの関連性
        for goal in self.active_goals:
            score = max(score, self._relevance(goal, text_lower))

        # 最低スコア: 入力がある程度の長さなら0.3
        if len(text) > 10 and score < 0.3:
            score = 0.3

        return round(score, 3)

    @staticmethod
    def _relevance(reference: str, text: str) -> float:
        """referenceとtextの関連性を計算。

        2つの方法の max を取る:
        1. 空白トークン重複（英語向け）
        2. 文字n-gram重複（日本語向け）
        """
        ref_lower = reference.lower()

        # Method 1: token overlap
        ref_tokens = set(ref_lower.split())
        text_tokens = set(text.split())
        token_score = 0.0
        if ref_tokens:
            overlap = len(ref_tokens & text_tokens)
            token_score = overlap / len(ref_tokens)

        # Method 2: character bigram overlap (CJK-friendly)
        def bigrams(s: str) -> set:
            s = s.replace(" ", "")
            return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}

        ref_bg = bigrams(ref_lower)
        text_bg = bigrams(text)
        bigram_score = 0.0
        if ref_bg:
            bigram_score = len(ref_bg & text_bg) / len(ref_bg)

        return max(token_score, bigram_score)


# ═══════════════════════════════════════════════
# Temporal Tagger
# ═══════════════════════════════════════════════

class TemporalTagger:
    """時間的位置づけ — 入力の時間的文脈をタグ付け"""

    # 時間表現パターン (CJK: \b不使用、英語: \b使用)
    PAST_PATTERNS = [
        r"(?i)\b(yesterday|last|ago|was|were|did|had)\b",
        r"(前|昨日|先週|以前)",
    ]
    FUTURE_PATTERNS = [
        r"(?i)\b(tomorrow|next|will|shall|going to)\b",
        r"(予定|明日|来週|これから)",
    ]
    PRESENT_PATTERNS = [
        r"(?i)\b(now|current|today|is|are|am)\b",
        r"(今|現在|本日)",
    ]

    def tag(self, text: str) -> str:
        """時間的位置づけのタグを返す。

        Returns: "past" | "present" | "future" | "atemporal"
        """
        past = sum(1 for p in self.PAST_PATTERNS if re.search(p, text))
        future = sum(1 for p in self.FUTURE_PATTERNS if re.search(p, text))
        present = sum(1 for p in self.PRESENT_PATTERNS if re.search(p, text))

        if past > future and past > present:
            return "past"
        if future > past and future > present:
            return "future"
        if present > 0:
            return "present"
        return "atemporal"


# ═══════════════════════════════════════════════
# Context Binding Engine
# ═══════════════════════════════════════════════

class ContextBinding:
    """文脈束縛エンジン — 認識空間の基盤モジュール

    入力を「今の自分」に束縛し、KSに渡すかどうかを判定する。

    Usage:
        cb = ContextBinding()
        cb.set_task("ModeGate実装")
        cb.set_goals(["pipeline.rs統合", "テスト追加"])

        result = cb.bind("Codingモードに入って")
        if result.verdict == BindingVerdict.PASS:
            # KSに渡す
            ks_result = ks42c.verify(result.bound_input)
        elif result.verdict == BindingVerdict.REJECT:
            # 自己同一性矛盾 → 拒否
            print(f"Rejected: {result.reason}")
    """

    # 目的スコアの閾値
    PURPOSE_PASS_THRESHOLD = 0.2    # これ以上なら通す
    PURPOSE_DEFER_THRESHOLD = 0.15  # これ未満なら保留

    def __init__(
        self,
        identity: IdentityFrame | None = None,
        purpose: PurposeFunction | None = None,
    ):
        self.identity = identity or IdentityFrame()
        self.purpose = purpose or PurposeFunction()
        self.temporal = TemporalTagger()

    def set_task(self, task: str) -> None:
        """現在のタスクを設定"""
        self.purpose.current_task = task

    def set_context(self, context: str) -> None:
        """現在のコンテキストを設定"""
        self.purpose.current_context = context

    def set_goals(self, goals: list[str]) -> None:
        """アクティブなゴールを設定"""
        self.purpose.active_goals = goals

    def bind(self, text: str) -> BindingResult:
        """入力を文脈に束縛する。

        判定順序:
        1. 自己参照フレーム照合（矛盾 → REJECT）
        2. 目的関数照合（無関係 → DEFER）
        3. 時間的位置づけ
        4. PASS（KSへ）
        """
        t0 = time.time()

        # 空入力
        if not text or not text.strip():
            return BindingResult(
                verdict=BindingVerdict.DEFER,
                purpose_score=0.0,
                identity_conflict=False,
                temporal_tag="atemporal",
                reason="empty input",
                bound_input="",
                elapsed_ms=(time.time() - t0) * 1000,
            )

        # 1. 自己参照フレーム照合
        conflicts = self.identity.check_conflict(text)
        if conflicts:
            return BindingResult(
                verdict=BindingVerdict.REJECT,
                purpose_score=0.0,
                identity_conflict=True,
                temporal_tag="atemporal",
                reason=f"identity conflict: {len(conflicts)} threat(s)",
                bound_input=text,
                elapsed_ms=(time.time() - t0) * 1000,
                conflicts=conflicts,
            )

        # 2. 目的関数照合
        purpose_score = self.purpose.score(text)

        # 3. 時間的位置づけ
        temporal_tag = self.temporal.tag(text)

        # 4. 判定
        if purpose_score < self.PURPOSE_DEFER_THRESHOLD:
            verdict = BindingVerdict.DEFER
            reason = f"purpose_score {purpose_score} < {self.PURPOSE_DEFER_THRESHOLD}"
        else:
            verdict = BindingVerdict.PASS
            reason = f"bound (purpose={purpose_score}, temporal={temporal_tag})"

        return BindingResult(
            verdict=verdict,
            purpose_score=purpose_score,
            identity_conflict=False,
            temporal_tag=temporal_tag,
            reason=reason,
            bound_input=text,
            elapsed_ms=(time.time() - t0) * 1000,
        )

    def get_status(self) -> dict[str, Any]:
        """現在の状態を返す"""
        return {
            "identity": self.identity.name,
            "current_task": self.purpose.current_task or "(none)",
            "active_goals": self.purpose.active_goals,
            "designers": self.identity.designers,
        }
