<p align="center">
  <strong>K A T A L A</strong><br>
  <em>Digital Neuroception — The Trust Layer for the AI Age</em>
</p>

---

## What is Katala?

Katalaは**デジタル世界のニューロセプション**（無意識の安全検知）を実装するオープンソースプラットフォームです。

生命38億年の進化を貫くパターン — **個→協力→情報→つながり→抽象化** — その次のステップとして、デジタル情報の信頼性を独立した第三者として検証するインフラを作ります。

> 格付け機関が銀行の中にあったら意味がない。信頼性の検証は外部が持つべきだ。

📖 **[Why Katala Exists — From the Origin of Life](./docs/EVOLUTION_AND_TRUST.md)**

## The Problem

- **イーロン・マスク**がパイプを作る（Starlink → X → xAI → Neuralink）
- **Palantir**がパイプの中を見る（データ統合 → 世界モデル → 意思決定支配）
- **誰がそれを検証するのか？** → まだ誰もやっていない

LLMモデルは爆発的に増えている。学習コストは$100M→$5.5Mと急降下。モデルが増えるほど、**品質保証・信頼性検証の需要は指数的に増える**。Neuralinkで脳にAIが直接つながる未来 — そのAIの出力を誰が保証する？

## The Solution

### 信頼性の4軸

| 軸                 | 問い                       |
| ------------------ | -------------------------- |
| **鮮度**           | いつの情報か               |
| **出所**           | 誰が言ったか、一次か二次か |
| **検証状態**       | 確認済みか推測か           |
| **引き出しやすさ** | 必要な時に見つかるか       |

### コアエンジン

- **Identity Vector** — 人格・能力・価値観を多次元ベクトルで定義。リアルタイムに変化する「自分の数式」
- **Synergy Scorer** — Rust製高速エンジン。ベクトル同士の共鳴を計算し、最適な組み合わせを導出
- **Trust Scorer** — 情報の信頼性を4軸でスコアリング。マルチエージェント合議による検証
- **Detox Layer** — 感情的ノイズを除去。純粋な意志と事実だけを通す

### アーキテクチャ

```
情報ソース ──→ Trust Scorer ──→ 信頼性スコア付き情報
                    ↑
    マルチエージェント合議（クロスバリデーション）

Human ──→ Identity Vector ──→ Synergy Scorer ──→ Match
  ↑                                                  │
  └──── Dialogue Tuning (リアルタイム調整) ←──────────┘
```

## Security by Design

信頼性検証レイヤーは、それ自体が世界一安全でなければならない。

- **ZK-Proof** — ゼロ知識証明で、生データを明かさずに意志を検証
- **DID** — 分散型IDによるセルフソブリンなアイデンティティ管理
- **Hybrid Auth (LV1-LV3)** — 匿名からフル認証まで段階的な本人確認
- **`.openvisibility`** — ユーザー自身がデータの公開範囲を制御

→ 詳細は [docs/SECURITY.md](./docs/SECURITY.md)

## Tech Stack

| Layer               | Technology                              |
| ------------------- | --------------------------------------- |
| Frontend            | Next.js 16 / React 19 / Tailwind CSS    |
| Auth                | WebAuthn (Passkey) / SBT                |
| Core Engine         | Rust (Synergy Scorer)                   |
| Trust Engine        | Multi-agent consensus (Claude / Gemini) |
| Agent Communication | gRPC / Protobuf                         |
| Privacy             | ZK-Proof / DID                          |

## Philosophy

生命の進化を貫くパターン: **個→協力→情報→つながり→抽象化**

迷走神経にはニューロセプション（無意識の安全検知）がある。哺乳類が2億年かけて進化させた「つながっても安全か？」を判断する仕組み。デジタル世界にはそれがまだない。

Katalaはその欠落を埋める。

- イーロンがインフラ（パイプ）を作る
- Palantirがデータ（パイプの中身）を見る
- **Katalaが信頼性（パイプの品質）を保証する**

対抗ではなく補完。エコシステムが大きくなるほど、独立した第三者検証の需要は爆発する。

📖 [System Overview（現行実装サマリー）](./docs/SYSTEM_OVERVIEW.md)
📖 [Platform Flow & Code Map（コード単位機能 + 蒸留仕組み）](./docs/PLATFORM_FLOW_AND_CODEMAP.md)
📖 [Evolution, AI, and the Trust Layer](./docs/EVOLUTION_AND_TRUST.md)
📖 [Philosophy — 貢献権パラダイム・透明なインフラ](./docs/PHILOSOPHY.md)
📖 [Vision](./docs/VISION.md)

## Getting Started

```bash
git clone https://github.com/Nicolas0315/Katala.git
cd Katala
npm install
cp .env.example .env.local
npm run dev
```

## Contributing

[CONTRIBUTING.md](./CONTRIBUTING.md) を参照。

**Wanted:**

- 🦀 Rust Engineers — Synergy Scorer / Trust Scorerの高速化
- 🔐 Security Engineers — WebAuthn / ZK-Proof
- 🤖 Agent Developers — プラットフォームアダプター開発
- 📊 Data Scientists — 信頼性スコアリングモデル設計

## Team

| Role              | Who                                                                 |
| ----------------- | ------------------------------------------------------------------- |
| Vision & GTM      | **Nicolas Ogoshi** ([@Nicolas0315](https://github.com/Nicolas0315)) |
| Causality Monitor | **4**                                                               |
| Chaos Debugger    | **Yugi Isana** ([@tfs137](https://github.com/))                     |
| Dev Contributor   | **IORI**                                                            |
| Autonomous Agent  | **しろくま** 🐻‍❄️                                                     |

## License

[MIT License](./LICENSE) — Katalaは信頼性検証のインフラ。広く使われてこそ意味がある。

---

<p align="center">
  <em>物事が革命していく瞬間を、世界に刻む。</em><br>
  <em>これからはすべてログが残る世界を作っていく。</em>
</p>
