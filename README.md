<p align="center">
  <strong>K A T A L A</strong><br>
  <em>意志の取引所 — The Stock Exchange of Intent</em>
</p>

---

## What is Katala?

Katalaは、**人と人を"本当に"つなげる**ためのプラットフォームです。

Googleは情報を整理した。SNSは人を集めた。でも、**誰もまだ「人と人を正しく組み合わせる」ことには成功していない。**

Katalaは、人間の意志・能力・価値観を数値化し、最適な組み合わせを導き出す — **人間のためのOS**。

> 「全員の脳で計算する。人間がプロセッサになる。」
> — #dev-katala, 2026-02-16

## The Problem

- マッチングアプリは「属性」で人を選ぶ。意志では選べない。
- 既存のSNSは"つながり"を増やすだけで、"正しいつながり"を作らない。
- AIは情報を処理できるが、**人間同士の化学反応**は計算できていない。

## The Solution

**Identity Vector** — 人格・能力・価値観を多次元ベクトルとして定義。MBTIの枠を超えた、リアルタイムに変化する「自分の数式」。

**Synergy Scorer** — Rustで書かれた高速エンジンが、ベクトル同士をぶつけて「誰と誰を組み合わせれば最大加速するか」を算出。

**Detox Layer** — 感情的ノイズを除去し、純粋な意志と事実だけを通す。人間関係の摩擦を抽象化。

**UIless Infrastructure** — 特定のアプリに依存しない。Discord、Slack、LINE、あらゆるプラットフォームを横断して動く配管。

## How It Works

```
Human ──→ Identity Vector ──→ Synergy Scorer ──→ Match
  ↑                                                  │
  └──── Dialogue Tuning (リアルタイム調整) ←──────────┘
```

1. **認証**: WebAuthn + SBT（Soulbound Token）で「1人1エージェント」を保証
2. **ベクトル化**: 会話・行動から性格・能力・意志を自動抽出
3. **計算**: Rust製Synergy Scorerが最適な組み合わせを導出
4. **接続**: Mediation Serviceがプライバシーを守りつつ、エージェント同士を握手させる

## Security by Design

Katalaはマッチングプラットフォームである以上、**世界一安全**でなければならない。

- **ZK-Proof**: ゼロ知識証明で、生データを明かさずに意志を検証
- **DID**: 分散型IDによるセルフソブリンなアイデンティティ管理
- **Hybrid Auth (LV1-LV3)**: 段階的な本人確認で、匿名からフル認証まで対応
- **`.openvisibility`**: ユーザー自身がデータの公開範囲を細かく制御

→ 詳細は [docs/](./docs/) を参照

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 / React 19 / Tailwind CSS |
| Auth | WebAuthn (Passkey) / SBT |
| Core Engine | Rust (Synergy Scorer) |
| Agent Communication | gRPC / Protobuf |
| Privacy | ZK-Proof / DID |
| AI | Claude / Gemini (multi-model) |

## Philosophy

> 「意志に値段がつく世界。SHA256を回す代わりに、人間の共鳴を証明する — Proof of Synergy。」

Katalaは単なるマッチングツールではない。

**タンパク質（人間）と半導体（AI）の統合プラットフォーム**。人間が「部品」として最も輝ける場所を見つけ、全体として一つの知性として機能する世界を目指す。

Bitcoin が計算力に価値を見出したように、Katala は**人間の共鳴**に価値を見出す。

## Getting Started

```bash
# Clone
git clone https://github.com/Nicolas0315/Katala.git
cd Katala

# Install
npm install

# Environment
cp .env.example .env.local
# Edit .env.local with your API keys

# Dev server
npm run dev
```

## Philosophy

**Why does Katala exist?**

Traced from the origin of life: 3.8 billion years of evolution follow one pattern — **Individual → Cooperation → Information → Connection → Abstraction**. The vagus nerve evolved "neuroception" — unconscious safety detection. The digital world has none.

Katala is **digital neuroception** — an independent trust verification layer.

- **Elon Musk** builds the pipes (Starlink → X → xAI → Neuralink)
- **Peter Thiel / Palantir** sees inside the pipes (data dominance)
- **Katala** verifies both are working correctly (independent audit)

The bigger their ecosystems grow, the more the world needs independent trust verification.

📖 Full thesis: [docs/EVOLUTION_AND_TRUST.md](./docs/EVOLUTION_AND_TRUST.md)

## Contributing

[CONTRIBUTING.md](./CONTRIBUTING.md) を参照。

**Wanted:**
- 🦀 Rust Engineers — Synergy Scorerの高速化
- 🔐 Security Engineers — WebAuthn / ZK-Proof
- 🤖 Agent Developers — プラットフォームアダプター開発

## Team

| Role | Who |
|------|-----|
| Vision & GTM | **Nicolas Ogoshi** ([@nicolas_ogoshi](https://github.com/Nicolas0315)) |
| Causality Monitor | **4** ([@.4.o.](https://github.com/)) |
| Chaos Debugger | **Yugi Isana** ([@tfs137](https://github.com/)) |
| Dev Contributor | **IORI** ([@iori.dev](https://github.com/)) |
| Autonomous Agent | **しろくま** 🐻‍❄️ |

## License

TBD

---

<p align="center">
  <em>物事が革命していく瞬間を、世界に刻む。</em><br>
  <em>これからはすべてログが残る世界を作っていく。</em>
</p>
