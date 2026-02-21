# Katala Mock & LP Structure: "The Gateway to the Pipeline"

## 1. Landing Page (LP) - Rule-First Design

- **Concept**: 「画面のないプラットフォーム」の意義を伝える最小限のLP。
- **Sections**:
  - **Manifesto**: 2026-02-16に策定されたプラットフォーム憲法（PLATFORM_RULES_20260216.md）の要約。
  - **How to Connect**: 各プラットフォーム（Discord, WhatsApp, Telegram等）へのエージェント接続手順。
  - **Trust Dashboard**: 自分が承認した公開情報（Staging）と、エージェント間の「意志の台帳（Immutable Ledger）」のプレビュー表示。

## 2. Backend Mock Development (Priority)

- **Identity Mock**: 既存のチャットログから `.openvisibility` ルールに従ってデータを抽出し、Staging（承認待ち）に入れる模擬ロジックの実装。
- **Mediation Mock**: 2つのエージェントが、共通の「台帳（Ledger）」に合意事項を書き込む P2P 通信のシミュレーション。
- **API Mock**:
  - `GET /api/ledger`: 交渉ログの取得。
  - `POST /api/visibility/approve`: Staging データの承認。
  - `POST /api/intent`: 新規意志（Intent）のパイプライン投入。

## 3. Staging Process Mock

- ユーザーに「エージェントが以下のスキルを抽出しました：[Rust, Solidity]. 公開しますか？」と問いかけ、承認を得るまでのステートマシンの構築。
