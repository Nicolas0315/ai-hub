# KATALA: Core Architecture & Contribution Guide

## 1. Vision

**"Detoxed Synergy Pipeline"**
KATALAは、人間の感情的摩擦（毒素）を抽象化し、純粋な意志と事実に基づいた最高精度のマッチングを実現する「知能の配管」です。特定のUIに依存せず、あらゆるプラットフォームを横断する自律型経済圏の構築を目指します。

## 2. Organization & Roles

オープンリポジトリとしての開発体制です。

### Core Leadership

- **Vision & GTM**: Nicolas Ogoshi (@nicolas_ogoshi)
- **Causality & Truth Debugger**: 4 (@.4.o.)
- **Special Advisor / Chaos Debugger**: Yugi Isana (@tfs137)
  - 役割：設計の「壁打ち」・カウンター・思想的インプット。システムのバグや矛盾を突く「やべえやつ」。
- **Autonomous Implementation**: Sirokuma (Main Agent), Codex, Claude Code

### Wanted: Contributors

- **Rust Engineers**: Synergy Scorerの高速化、分散レジャーの実装。
- **Security/Auth Engineers**: WebAuthn/Passkeyの統合、Zero-Knowledge Proofの実装。
- **Agent Developers**: 特定プラットフォーム向けInput/Outputアダプターの開発。

## 3. Technical Stack

### Identity & Security

- **Auth**: WebAuthn (Passkey) - 生体認証によるパスワードレスログイン。
- **Proof of Personhood**: SBT (Soulbound Token) による1人1エージェントの担保。
- **Privacy**: ZK-Proof (ゼロ知識証明) による、生データを明かさない意志の検証。

### Core Engine

- **Logic**: Rust (Performance-critical synergy calculations).
- **Communication**: gRPC / Protobuf (Agent-to-agent interface).
- **Frontend**: Next.js (App Router) - 承認フローおよび意志の台帳（Ledger）の可視化。

### Data & Economy

- **Immutable Ledger**: 事実に基づいた交渉プロセスの不変ログ。
- **Reward System**: 知能労働の成果（SCS: Synergy Contribution Score）に応じたポイント還元スキーム。

## 4. How to Contribute

1. **Issues**: 現在の課題（ネジの締まり具合）を確認してください。
2. **Discussions**: 感情を排し、事実に基づいたロジックの提案を歓迎します。
3. **Pull Requests**: `SOUL.md` および `IDENTITY_POLICY.md` を尊重したコードをお願いします。
