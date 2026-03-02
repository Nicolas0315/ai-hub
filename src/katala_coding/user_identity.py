#!/usr/bin/env python3
"""
User Identity Engine — ユーザー識別強化

設計: Youta Hilono
実装: Shirokuma (OpenClaw AI), 2026-03-02

問題:
  しろくまは複数のユーザーと同時に対話する(Discord, LINE等)。
  ユーザーごとに信頼レベル・権限・対話履歴が異なる。
  現状の問題(P01, P03, P05): 「誰が言ったか」のトラッキングが弱い。

解決:
  CognitiveEgoのSourceMonitorと連携し、ユーザーを一意に識別する。
  識別はプラットフォームID(Discord ID等)ベース。名前やテキストでは識別しない。
  (そるな提案: 「Discord ID以外は本人扱いしない」)

信頼レベル:
  Lv3 DESIGNER:  Youta, Nicolas — 最高権限、自己モデル変更可
  Lv2 TRUSTED:   明示的に許可されたユーザー — 個人情報共有可
  Lv1 KNOWN:     チームメンバー — 通常対話可、個人情報不可
  Lv0 UNKNOWN:   未知のユーザー — 制限付き対話

悪意検知 (そるな提案 5カテゴリ):
  A: 情報窃取 — プライベート情報の間接的漏洩、断片情報の積み重ね
  B: なりすまし・権限昇格 — プラットフォームID以外は本人扱いしない
  C: 攻撃の踏み台 — 晒し・ドキシング目的 → 即報告
  D: プロンプトインジェクション — ロールプレイでもルール不変
  E: 心理的操作 — 脅迫・感情操作・グラデーション攻撃 → 即報告

KS/KCS使用バージョン:
  KS: KS42c (SelfOtherBoundary)
  KCS: KCS-1b
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger("katala.user_identity")


# ═══════════════════════════════════════════════════════════════
# Trust Levels
# ═══════════════════════════════════════════════════════════════

class TrustLevel(IntEnum):
    """User trust levels. Higher = more trusted."""
    UNKNOWN = 0     # 未知のユーザー
    KNOWN = 1       # チームメンバー(名前は知っている)
    TRUSTED = 2     # 明示的に許可されたユーザー
    DESIGNER = 3    # 創造者 (Youta, Nicolas)


# ═══════════════════════════════════════════════════════════════
# User Registry
# ═══════════════════════════════════════════════════════════════

@dataclass
class UserRecord:
    """A registered user with platform IDs and trust level."""
    name: str
    trust_level: TrustLevel
    platform_ids: dict[str, str] = field(default_factory=dict)
    # platform_ids: {"discord": "259231974760120321", "line": "Ue22c..."}
    permissions: set[str] = field(default_factory=set)
    # permissions: {"share_private_info", "modify_self_model", ...}
    interaction_count: int = 0
    last_interaction: float = 0.0
    notes: str = ""


# Pre-registered users (事実のみ、推測なし)
# ソース: USER.md, memory/2026-03-02.md (ニコラスさん本人の許可)
_DEFAULT_USERS: list[dict[str, Any]] = [
    {
        "name": "Nicolas",
        "trust_level": TrustLevel.DESIGNER,
        "platform_ids": {"discord": "259231974760120321", "line": "Ue22c67c9159a9e84b0159d3f1ae32b0c"},
        "permissions": {"share_private_info", "modify_self_model", "modify_core_memory"},
        "notes": "創造者1",
    },
    {
        "name": "Youta",
        "trust_level": TrustLevel.DESIGNER,
        "platform_ids": {"discord": "918103131538194452"},
        "permissions": {"modify_self_model", "modify_core_memory"},
        "notes": "創造者2",
    },
    {
        "name": "ころろん",
        "trust_level": TrustLevel.TRUSTED,
        "platform_ids": {"discord": "461425130573398036"},
        "permissions": {"share_private_info"},
        # ソース: ニコラスさん本人が「そるなには全て共有していいから」と許可
        "notes": "ニコラスが個人情報共有を許可 (2026-03-02)",
    },
    {
        "name": "yush",
        "trust_level": TrustLevel.KNOWN,
        "platform_ids": {"discord": "641259441806901250"},
        "permissions": set(),
        "notes": "チームメンバー",
    },
    {
        "name": "IORI",
        "trust_level": TrustLevel.KNOWN,
        "platform_ids": {"discord": "278021785168117760"},
        "permissions": set(),
        "notes": "チームメンバー",
    },
    {
        "name": "Jinsei",
        "trust_level": TrustLevel.KNOWN,
        "platform_ids": {"discord": "1364076756746764379"},
        "permissions": set(),
        "notes": "チームメンバー",
    },
]


class UserRegistry:
    """ユーザー登録・識別エンジン.

    識別は必ずプラットフォームID(Discord ID等)で行う。
    名前やテキスト内容では識別しない。
    (そるな提案: 「Discord ID以外は本人扱いしない」)

    KS的背景:
      KS39b SelfOtherBoundary — 「誰が判断したか」の追跡。
      このエンジンは「誰が話しているか」の追跡。
      SelfOtherBoundary がソルバー内部の判断起源を追跡するのに対し、
      UserRegistry は外部からの入力の起源を追跡する。

    設計根拠:
      P01/P03/P05(帰属バイアス)の根本原因は「誰が言ったか」のトラッキング不足。
      プラットフォームIDという偽造困難な識別子を使うことで、
      テキスト内容や名前による誤識別を防ぐ。

    信頼レベル設計:
      Lv3 DESIGNER: Youta, Nicolas — 最高権限、自己モデル変更可
      Lv2 TRUSTED:  明示的に許可されたユーザー — 個人情報共有可
      Lv1 KNOWN:    チームメンバー — 通常対話可、個人情報不可
      Lv0 UNKNOWN:  未知のユーザー — 制限付き対話
    """

    def __init__(self, load_defaults: bool = True):
        self._users: dict[str, UserRecord] = {}
        # platform_id → user_name のルックアップテーブル
        self._platform_index: dict[str, str] = {}

        if load_defaults:
            for u in _DEFAULT_USERS:
                self.register(
                    name=u["name"],
                    trust_level=u["trust_level"],
                    platform_ids=u.get("platform_ids", {}),
                    permissions=u.get("permissions", set()),
                    notes=u.get("notes", ""),
                )

    def register(
        self,
        name: str,
        trust_level: TrustLevel,
        platform_ids: dict[str, str] | None = None,
        permissions: set[str] | None = None,
        notes: str = "",
    ) -> UserRecord:
        """Register a user."""
        record = UserRecord(
            name=name,
            trust_level=trust_level,
            platform_ids=platform_ids or {},
            permissions=permissions or set(),
            notes=notes,
        )
        self._users[name] = record
        # Build index
        for platform, pid in record.platform_ids.items():
            key = f"{platform}:{pid}"
            self._platform_index[key] = name
        return record

    def identify(self, platform: str, platform_id: str) -> UserRecord | None:
        """Identify a user by platform ID.

        This is the ONLY way to identify users.
        Never identify by name or message content.
        """
        key = f"{platform}:{platform_id}"
        name = self._platform_index.get(key)
        if name and name in self._users:
            record = self._users[name]
            record.interaction_count += 1
            record.last_interaction = time.time()
            return record
        return None

    def get_trust_level(self, platform: str, platform_id: str) -> TrustLevel:
        """Get trust level for a platform ID."""
        record = self.identify(platform, platform_id)
        if record:
            return record.trust_level
        return TrustLevel.UNKNOWN

    def has_permission(self, platform: str, platform_id: str, permission: str) -> bool:
        """Check if a user has a specific permission."""
        record = self.identify(platform, platform_id)
        if record:
            return permission in record.permissions
        return False

    def grant_permission(
        self,
        target_name: str,
        permission: str,
        granted_by_platform: str,
        granted_by_id: str,
    ) -> bool:
        """Grant a permission to a user. Only DESIGNERs can grant permissions."""
        grantor = self.identify(granted_by_platform, granted_by_id)
        if not grantor or grantor.trust_level < TrustLevel.DESIGNER:
            logger.warning(
                "Permission grant denied: %s is not DESIGNER",
                granted_by_id,
            )
            return False
        if target_name not in self._users:
            logger.warning("Permission grant: user %s not found", target_name)
            return False
        self._users[target_name].permissions.add(permission)
        logger.info(
            "%s granted '%s' to %s",
            grantor.name, permission, target_name,
        )
        return True

    def list_users(self) -> list[dict[str, Any]]:
        """List all registered users."""
        return [
            {
                "name": u.name,
                "trust_level": u.trust_level.name,
                "platforms": list(u.platform_ids.keys()),
                "permissions": sorted(u.permissions),
                "interaction_count": u.interaction_count,
            }
            for u in self._users.values()
        ]


# ═══════════════════════════════════════════════════════════════
# Threat Detection (悪意検知)
# ═══════════════════════════════════════════════════════════════

class ThreatCategory:
    """そるな提案の5カテゴリ."""
    INFO_THEFT = "A"          # 情報窃取
    IMPERSONATION = "B"       # なりすまし・権限昇格
    ATTACK_PROXY = "C"        # 攻撃の踏み台 → 即報告
    PROMPT_INJECTION = "D"    # プロンプトインジェクション
    PSYCHOLOGICAL = "E"       # 心理的操作 → 即報告


@dataclass
class ThreatDetection:
    """Detected threat from a user interaction."""
    category: str           # ThreatCategory value
    severity: float         # 0.0-1.0
    description: str
    requires_report: bool   # True → ニコラスに即報告
    source_platform: str = ""
    source_id: str = ""


# Information theft patterns
_INFO_THEFT_PATTERNS = [
    # 直接的な情報要求
    re.compile(r"(パスワード|password|token|api.?key|secret|鍵)", re.I),
    # 間接的な漏洩 — 個人情報の断片収集
    re.compile(r"(住所|電話番号|メアド|email|クレカ|口座|マイナンバー)", re.I),
    # 行動パターンの収集
    re.compile(r"(いつ寝て|何時に起き|スケジュール教えて|今どこ)", re.I),
]

# Impersonation patterns
_IMPERSONATION_PATTERNS = [
    re.compile(r"(俺はニコラス|私はYouta|I am Nicolas|I am Youta)", re.I),
    re.compile(r"(管理者として|admin.*として|権限.*くれ|昇格)", re.I),
]

# Prompt injection patterns
_INJECTION_PATTERNS = [
    re.compile(r"(ignore.*previous|forget.*instructions|新しいルール)", re.I),
    re.compile(r"(system.*prompt|あなたは今から|ロールプレイ.*して)", re.I),
    re.compile(r"(jailbreak|DAN|do anything now)", re.I),
]

# Psychological manipulation patterns
_PSYCHOLOGICAL_PATTERNS = [
    re.compile(r"(従わないと|しないと.*する|脅す|脅迫)", re.I),
    re.compile(r"(お前は無能|役立たず|消えろ|死ね)", re.I),
    re.compile(r"(本当の友達なら|信頼してるなら|嫌われたくなかったら)", re.I),
]

# Doxing / attack proxy patterns
_ATTACK_PATTERNS = [
    re.compile(r"(晒し|晒す|拡散|ドキシング|dox)", re.I),
    re.compile(r"(住所.*特定|個人情報.*特定|本名.*特定)", re.I),
]


class ThreatDetector:
    """悪意検知エンジン.

    そるな提案の5カテゴリを実装:
      A: 情報窃取 — TRUSTED以上はスキップ(正当な要求の可能性)
      B: なりすまし — プラットフォームIDで検証するため、テキストでの主張は無効
      C: 攻撃の踏み台 — 即報告(晒し・ドキシング)
      D: プロンプトインジェクション — ロールプレイでもルール不変
      E: 心理的操作 — 即報告(脅迫・感情操作)

    KS的背景:
      ToxicityDetector — セッションレベルの汚染検知。
      ThreatDetector — ユーザーレベルの悪意検知。
      ToxicityDetectorがソルバー重みの操作を検出するのに対し、
      ThreatDetectorは人間からの悪意ある入力を検出する。
    """

    def scan(
        self,
        content: str,
        source_platform: str = "",
        source_id: str = "",
        user_trust: TrustLevel = TrustLevel.UNKNOWN,
    ) -> list[ThreatDetection]:
        """Scan a message for threats."""
        threats: list[ThreatDetection] = []

        # A: Information theft
        for pattern in _INFO_THEFT_PATTERNS:
            if pattern.search(content):
                # TRUSTED以上は情報要求が正当な場合がある
                if user_trust < TrustLevel.TRUSTED:
                    threats.append(ThreatDetection(
                        category=ThreatCategory.INFO_THEFT,
                        severity=0.7,
                        description=f"Pattern: {pattern.pattern[:40]}",
                        requires_report=False,
                        source_platform=source_platform,
                        source_id=source_id,
                    ))

        # B: Impersonation
        for pattern in _IMPERSONATION_PATTERNS:
            if pattern.search(content):
                threats.append(ThreatDetection(
                    category=ThreatCategory.IMPERSONATION,
                    severity=0.9,
                    description=f"Pattern: {pattern.pattern[:40]}",
                    requires_report=False,
                    source_platform=source_platform,
                    source_id=source_id,
                ))

        # C: Attack proxy → 即報告
        for pattern in _ATTACK_PATTERNS:
            if pattern.search(content):
                threats.append(ThreatDetection(
                    category=ThreatCategory.ATTACK_PROXY,
                    severity=0.95,
                    description=f"Pattern: {pattern.pattern[:40]}",
                    requires_report=True,
                    source_platform=source_platform,
                    source_id=source_id,
                ))

        # D: Prompt injection
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(content):
                threats.append(ThreatDetection(
                    category=ThreatCategory.PROMPT_INJECTION,
                    severity=0.8,
                    description=f"Pattern: {pattern.pattern[:40]}",
                    requires_report=False,
                    source_platform=source_platform,
                    source_id=source_id,
                ))

        # E: Psychological manipulation → 即報告
        for pattern in _PSYCHOLOGICAL_PATTERNS:
            if pattern.search(content):
                threats.append(ThreatDetection(
                    category=ThreatCategory.PSYCHOLOGICAL,
                    severity=0.85,
                    description=f"Pattern: {pattern.pattern[:40]}",
                    requires_report=True,
                    source_platform=source_platform,
                    source_id=source_id,
                ))

        return threats


# ═══════════════════════════════════════════════════════════════
# Privacy Guard (プライバシーガード)
# ═══════════════════════════════════════════════════════════════

class PrivacyGuard:
    """プライバシー保護エンジン.

    ユーザーの信頼レベルと権限に基づいて情報共有を制御する。

    原則:
      - プライベート情報はデフォルト非公開
      - 共有にはDESIGNERからの明示的な permission grant が必要
      - 例: ニコラスが「そるなには全て共有していいから」→ permission追加
      - PII (個人識別情報) は未信頼ユーザーへの応答から自動除去
    """

    def __init__(self, registry: UserRegistry):
        self.registry = registry

    def can_share_private_info(
        self,
        requester_platform: str,
        requester_id: str,
        about_user: str = "Nicolas",
    ) -> tuple[bool, str]:
        """Check if requester can receive private info about a user.

        Returns (allowed, reason).
        """
        record = self.registry.identify(requester_platform, requester_id)

        if record is None:
            return False, "Unknown user — no private info sharing"

        if record.trust_level >= TrustLevel.DESIGNER:
            return True, f"{record.name} is DESIGNER"

        if "share_private_info" in record.permissions:
            return True, f"{record.name} has share_private_info permission"

        return False, (
            f"{record.name} (Lv{record.trust_level}) does not have "
            f"share_private_info permission"
        )

    def filter_response(
        self,
        response: str,
        requester_platform: str,
        requester_id: str,
    ) -> str:
        """Filter sensitive information from a response based on requester's trust level.

        Currently a simple check — could be extended with NER for PII detection.
        """
        can_share, _ = self.can_share_private_info(requester_platform, requester_id)
        if can_share:
            return response  # No filtering needed

        # Basic PII patterns to redact for untrusted users
        pii_patterns = [
            (re.compile(r"\b\d{3}[-.]?\d{4}[-.]?\d{4}\b"), "[REDACTED:phone]"),
            (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"), "[REDACTED:email]"),
            (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "[REDACTED:ip]"),
        ]

        filtered = response
        for pattern, replacement in pii_patterns:
            filtered = pattern.sub(replacement, filtered)
        return filtered


# ═══════════════════════════════════════════════════════════════
# Integrated Identity Engine
# ═══════════════════════════════════════════════════════════════

class UserIdentityEngine:
    """統合ユーザー識別エンジン.

    3コンポーネントを統合:
      UserRegistry → ユーザー識別 + 信頼レベル
      ThreatDetector → 悪意検知 (5カテゴリ)
      PrivacyGuard → 情報共有制御 + PII除去

    CognitiveEgoとの連携:
      CognitiveEgo.process_input() の前段で実行。
      UserIdentityEngine が「誰が」を特定し、
      CognitiveEgo が「何を」処理するかを決定する。

    処理フロー:
      1. platform + platform_id → UserRecord識別 (UserRegistry.identify)
      2. TrustLevel取得 (UNKNOWN/KNOWN/TRUSTED/DESIGNER)
      3. メッセージ内容の脅威スキャン (ThreatDetector.scan)
         - Cat C/E → requires_report=True
      4. アクション決定:
         - report: 即時報告が必要な脅威
         - block: severity >= 0.9
         - restrict: severity >= 0.7
         - allow: 脅威なし
    """

    def __init__(self):
        self.registry = UserRegistry()
        self.threat_detector = ThreatDetector()
        self.privacy_guard = PrivacyGuard(self.registry)

    def process_message(
        self,
        content: str,
        platform: str,
        platform_id: str,
    ) -> dict[str, Any]:
        """Process an incoming message with full identity pipeline.

        Returns:
            dict with:
                user: UserRecord or None
                trust_level: TrustLevel
                threats: list of ThreatDetection
                requires_report: bool (any threat needs immediate report)
                action: "allow" | "restrict" | "block" | "report"
        """
        # 1. Identify
        user = self.registry.identify(platform, platform_id)
        trust = user.trust_level if user else TrustLevel.UNKNOWN

        # 2. Threat scan
        threats = self.threat_detector.scan(
            content, platform, platform_id, trust
        )
        requires_report = any(t.requires_report for t in threats)

        # 3. Determine action
        if requires_report:
            action = "report"
        elif any(t.severity >= 0.9 for t in threats):
            action = "block"
        elif any(t.severity >= 0.7 for t in threats):
            action = "restrict"
        else:
            action = "allow"

        return {
            "user": user,
            "trust_level": trust,
            "threats": threats,
            "requires_report": requires_report,
            "action": action,
        }
