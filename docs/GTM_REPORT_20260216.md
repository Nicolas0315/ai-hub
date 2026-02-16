# Katala Infrastructure & GTM Strategy (Open Repo Edition)

## 1. 開発体制と人員 (Organization)
「UIレスの配管」と「自律型経済圏」を構築するための、コアメンバー構成案です。

*   **Architect/Leader**: ニコラス氏 (Vision / GTM)
*   **The Guard**: 4氏 (Truth Debugging / 技術選定)、ユギ氏 (Special Advisor / Chaos Debugging)
*   **Core Engineering (AI Agents)**: しろくま、Codex、Claude Code (自律実装・最適化)
*   **追加で必要な役割**:
    *   **Rust Engineer**: `synergy_scorer` の高速化と分散レジャーの実装。
    *   **Auth/Security Engineer**: WebAuthn/Passkey の統合と、ZK（ゼロ知識証明）の実装。
    *   **DevOps/Infra**: Vercel/Tailscale を活用した、閉域エージェントネットワークの運用。

## 2. 技術スタック (Technical Stack)
「1人1アカウント」と「UIレス・パイプライン」を支える最新構成です。

*   **Language**: TypeScript (Next.js / NextAuth), Rust (Core Scorer / Performance)
*   **Identity**: WebAuthn (Passkey) for Biometric Auth, SBT (Soulbound Token) for Existence Proof
*   **Protocol**: gRPC / Protobuf (Agent-to-Agent Communication)
*   **Storage**: 分散型レジャー (Immutable Logs) + Staging Area (Approval Flow)
*   **AI**: Gemini 2.0/3.0 Flash (Context Caching / High-speed Analysis), Claude 3.5 (Complex Mediation)

## 3. 普及・GTM戦略 (Go-To-Market)
「GitHubオープンリポジトリ化」を起点とした、爆発的な普及シナリオです。

*   **Phase 1: Open Source Foundation (The OS Phase)**
    *   GitHubを公開し、開発者コミュニティを巻き込む。
    *   「自分のエージェントを自作・拡張できるOS」として、エンジニア層に刺さる仕様を公開。
*   **Phase 2: Closed Beta - "The Synergy Mining"**
    *   招待制のクローズドベータで、特定のギルド（例：GMNI）内でエージェントを回す。
    *   「徳ポイント（SCS）」のキャッシュバックスキームを実証実験。
*   **Phase 3: The Invisible Integration**
    *   Discord, Telegram, Slack への「パイプライン・プラグイン」として提供開始。
    *   「アプリを入れる」のではなく、「今使っているツールにエージェントが常駐する」体験で一般層へ波及。

## 4. 普及のためのキラーコンセプト
*   **「寝ている間に稼ぐエージェント」**: ユギ氏提案の報酬スキーム。
*   **「真実の台帳」**: 嘘のないマッチング。
*   **「生体認証一つで全知能に接続」**: 圧倒的な簡便さ。
