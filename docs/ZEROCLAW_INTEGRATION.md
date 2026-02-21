## Source & Attribution

- **Source**: [ZeroClaw Labs - ZeroClaw](https://github.com/zeroclaw-labs/zeroclaw)
- **Concept**: Security sandboxing, channel abstraction, and memory hygiene logic.
- **Role in Katala**: Acts as the foundational infrastructure and security layer ("The Spinal Cord").

## 1. ZeroClaw Analysis Summary

ZeroClawは、Rustで構築された「エージェント・コア」であり、以下の点でKatalaの「UIレス・インフラ」構想と極めて親和性が高いです。

- **Sandboxing & Security**: Landlock, Firejail, Bubblewrap 等を用いた「エージェントの安全な隔離」。
- **Agnostic Channels**: Discord, Telegram, WhatsApp 等を「Traits（抽象インターフェース）」として統一管理。
- **Memory Hygiene**: SQLite/Vector を用いた、構造化された「記憶の衛生管理」。

## 2. Strategic Integration Points

### [A] Secure Agent Isolation (Inspired by src/security)

- **Katala's Gain**: 各ユーザーのエージェント（インスタンス）を物理的に隔離し、他のエージェントからの不正アクセスを防止する。
- **Action**: `Katala/packages/katala/gateway` に ZeroClaw のサンドボックス思想を注入し、セキュアな「意志の個室」を作る。

### [B] Platform-Agnostic Pipe (Inspired by src/channels)

- **Katala's Gain**: 「UIレス」の核心。全チャットツールを同一のプロトコルで扱える。
- **Action**: ZeroClaw の Channel Traits を参考にして、Katala の「意志のパイプライン（Mediation Protocol）」を各プラットフォームへブリッジするアダプターを構築。

### [C] Memory Hygiene & Siphoning (Inspired by src/memory/hygiene.rs)

- **Katala's Gain**: 膨大なログから「何を覚え、何を捨て、何をStagingに回すか」の整理技術。
- **Action**: `ProfilingEngine.ts` のロジックに、ZeroClaw の記憶衛生管理（Hygiene）のアルゴリズムを取り入れ、データの「純度」を高める。

### [D] Tailscale Tunneling (Inspired by src/tunnel/tailscale.rs)

- **Katala's Gain**: P2P通信を「安全かつ簡単」にする。
- **Action**: エージェント同士の直接通信（Mediation）の背後で、Tailscale を用いたセキュアなトンネリングを標準採用。
