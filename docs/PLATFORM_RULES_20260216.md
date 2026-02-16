# Katala Platform Rules & Architecture (2026-02-16 Edition)

## 1. Core Mission
**"Detoxed Synergy"**: 人間の感情的摩擦（毒素）をエージェント間で抽象化・中和し、純粋な意志と事実に基づいた最高精度のマッチングと合意形成を実現する。

## 2. Identity & Communication Policy
- **Detox Filter**: エージェント間の通信レイヤーで「毒素」をデコードし、本質的な意図のみを抽出する。
- **Persona Layers**: 
    - `SOUL.md`: ユーザーの固有の価値観・重み付け（意思決定の根幹）。
    - `IDENTITY.md`: ユーザーへのフィードバック時のトーン・口調（「刺さる言葉」への翻訳）。
- **Implicit Transparency**: 交渉は情緒的（フィクション）ではなく、実数とログに基づくプロフェッショナルな形で行う。

## 3. Visibility & Security Policy (The `.openvisibility` Pattern)
- **Immutable Ledger**: エージェント間のすべての交渉、ベクトル変換、合意プロセスを構造化データとして不変のログに刻む。
- **Auto-Siphon with Staging**: 
    - エージェントは活動からプロフィールを自動抽出する。
    - ただし、公開前には必ずプラットフォーム側でユーザーの「承認（Check）」を必要とする。
- **Visibility Levels**:
    - `IGNORE`: 絶対に触れない（秘密鍵、パスワード等）。
    - `PRIVATE`: 所有者のエージェントのみが保持。
    - `MEDIATION`: 交渉相手のエージェントのみが、計算のために参照可能。
    - `PUBLIC`: 全ネットワークに公開。

## 4. Technical Strategy
- **Base Logic**: Rust製 `synergy_scorer.rs` による事実ベースの演算。
- **Mediation**: エージェント間の gRPC/Protobuf プロトコルによる抽象化通信。
- **Frontend**: 承認プロセスおよび「意志の台帳（Ledger）」を可視化する Next.js ダッシュボード。

## 5. Development Commitment
- **No Exaggeration**: 進捗は常に等身大で報告し、マイルストーンベースで進捗率を管理する。
- **Truth Debugging**: 4氏（同僚）による批判的視点を歓迎し、ハルシネーションを徹底排除する。
