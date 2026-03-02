<p align="center">
  <strong>K A T A L A</strong><br>
  <em>Digital Neuroception — The Trust Layer for the AI Age</em>
</p>

---

## Prelude

"In the beginning God created the heaven and the earth." (Genesis 1:1)

The world once had "one language and one speech." (Genesis 11:1)  
Then Babel confounded language, and understanding was scattered. (Genesis 11:7–9)

Now we build new towers with models, data, and compute.  
Power scales fast. Understanding does not.

Katala begins here:  
to gather the world's questions and doubts,  
and to verify what should be trusted before it governs human judgment.

---

## What is Katala?

Katalaは**デジタル世界のニューロセプション**（無意識の安全検知）を実装するオープンソースプラットフォームです。

生命38億年の進化を貫くパターン — **個→協力→情報→つながり→抽象化** — その次のステップとして、デジタル情報の信頼性を独立した第三者として検証するインフラを作ります。

> 格付け機関が銀行の中にあったら意味がない。信頼性の検証は外部が持つべきだ。

📖 **[Why Katala Exists — From the Origin of Life](./docs/EVOLUTION_AND_TRUST.md)**

## The Problem

AIは急速に普及している。  
モデル数は増え、学習・推論コストは下がり、供給は拡大し続ける。

しかし、信頼性検証はその速度で整備されていない。

- 生成はスケールする
- 配信もスケールする
- だが、信頼は自動ではスケールしない

計算資源への投資は過熱し、社会は「より多く計算した」という事実に安心し始めている。  
しかし本当に必要なのは、計算量ではなく**検証可能性**だ。

**誰が、AIの出力を、意思決定の前に検証するのか。**

この空白を埋める検証インフラが、まだ足りていない。

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

進化は、ひとつの反復パターンを持つ。  
**個 → 協力 → 情報 → つながり → 抽象化。**

生物は「この接続は安全か」を先に問う仕組みを進化させた。  
だがデジタル文明は、接続を先に拡大し、検証を後回しにしてきた。

ある者はパイプを太くする。  
ある者はパイプの中身を最適化する。  
Katalaは、その先で欠落しがちな役割を担う。  
**信頼性を独立に検証する第三者レイヤー**である。

対抗ではなく補完。  
エコシステムが拡大するほど、第三者検証は「機能」ではなく「基盤」になる。

> "Let all that you do be done in love." — 1 Corinthians 16:14

Katalaにおける「愛」とは、責任のことだ。  
信頼の前に検証する責任。  
デプロイの前に試験する責任。  
未検証の機械判断から人間を守る責任。

私たちは、スケールそのものを崇拝しない。  
スケールを検証する。  
加速そのものを否定しない。  
加速の内部に説明責任を埋め込む。

機械知能が社会インフラになる時代に、  
独立検証は贅沢ではない。  
公共の必需である。

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

| Role | Who | Vision & GTM |
| --- | --- | --- |
| Vision | **Nicolas Hidemaru Ogoshi** ([@Nicolas0315](https://github.com/Nicolas0315)) | Defines Katala's mission: leave no one behind, restore trust through verification, and convert verification discipline into global adoption. |
| Architect | **Youta Hilono** | Designs Katala's verification philosophy and core architecture to ensure scalability, falsifiability, and operational robustness. |
| Katalysts | **All Contributors** | Every contributor is a Katalyst—turning principles into implementable systems and ideas into reproducible impact. |

## License

[MIT License](./LICENSE) — Katalaは信頼性検証のインフラ。広く使われてこそ意味がある。

---

<p align="center">
  <em>物事が革命していく瞬間を、世界に刻む。</em><br>
  <em>これからはすべてログが残る世界を作っていく。</em>
</p>
