# Katala Roadmap — 実装ロードマップ

## Phase 1: Foundation — 知能の配管（基盤構築）

### Milestone 1: プロトタイプ環境構築 ✅

- [x] GitHub公開リポジトリ化 (https://github.com/Nicolas0315/Katala)
- [x] 基本ディレクトリ構成
- [x] 設計ドキュメント策定（PLATFORM_RULES, CONTRIBUTING, etc.）
- [x] ニコラスをメインメンテナー（マージ権限保持者）として設定

### Milestone 2: Profiling Engine（抽出ロジック）

- [x] `ProfilingEngine.ts` コアロジック実装
- [x] ログからの事実抽出
- [x] 重複排除（Hygiene/Deduplication）
- [x] `.openvisibility` フィルタ適用
- [ ] Staging Area APIハンドラ (`POST /api/staging`)
- [ ] 承認 → IdentityVector書き込み (`commitFact()`)

### Milestone 3: Immutable Ledger（台帳）

- [x] Genesis Block生成
- [x] Hash Chaining (SHA-256)
- [x] Self-Verification (`verifyChain()`)
- [ ] ECDSA署名実装
- [ ] ファイル永続化
- [ ] 負荷テスト

### Milestone 4: ZeroClaw Security Integration

- [ ] サンドボックス隔離（Landlock/Bubblewrap統合）
- [ ] チャンネル抽象化（Discord/Slack/Telegram統一Trait）
- [ ] Memory Hygiene統合

### Milestone 5: Mediation Protocol

- [ ] エージェント間デトックス交渉プロトコル（gRPC）
- [ ] SOUL.mdインジェクション機能
- [ ] パーソナライズ翻訳層

### Milestone 6: Test & Integration

- [ ] 全体統合テスト
- [ ] シミュレーションによる動作確認
- [ ] CLIデモ

## Phase 1.5: Auth — 認証基盤（NEW）

> MVP通信仕様: [MVP_COMM_PROTOCOL.md](./MVP_COMM_PROTOCOL.md)

> 詳細設計: [AUTH_INTEGRATION.md](./AUTH_INTEGRATION.md)

### Auth0 + OIDC基盤

- [ ] Auth0テナント構築・Social Connection設定（Google/Apple/GitHub）
- [ ] World ID接続（Auth0 Social Connection、オプション）
- [ ] WebAuthn/Passkey実装（`@simplewebauthn`）— LV1認証コア

### Identity Vector連携

- [ ] 認証完了 → Identity Vector初期生成
- [ ] Staging Area APIとの統合

### SBT + ZK

- [ ] SBT（Soulbound Token）発行フロー（テストネット）
- [ ] ZK-SNARKs PoC（circom/noir）— LV2認証プロトタイプ

### DID + VC

- [ ] DID Resolution実装（`did:web` or `did:key`）
- [ ] Verifiable Credentials発行（エージェント委任状）

## Phase 2: Economy — 知能の経済圏

> 共有進化基盤: [SKILL_COMMONS.md](./SKILL_COMMONS.md)

### 認証統合（Phase 1.5からの接続）

- [ ] SCS × 認証レベル連動（高LV認証 → SCS加算率ボーナス）
- [ ] Progressive Disclosure × Auth Level連動
- [ ] KBBアクセス制御（認証レベル別権限）

### Synergy Rewards

- [ ] Synergy Contribution Score (SCS) 算出ロジック
- [ ] 独自ポイントシステム（購入不可・半年失効・円キャッシュバック）
- [ ] エージェント間ポイント授受プロトコル

### The Board（意志の板）

- [ ] エージェント間交渉のリアルタイム可視化
- [ ] マクロトレンド解析表示

## Phase 3: Scale — 世界のインフラへ

### P2P通信基盤

- [ ] Gossip Protocol（BTC `net.cpp` 応用）
- [ ] 中央サーバー不要の分散通信

### 知能マイニング

- [ ] Proof of Synergy実装
- [ ] 難易度自動調整（BTC `pow.cpp` 応用）

### B2Bマネタイズ

- [ ] マッチング成功報酬（Synergy Fee）
- [ ] データ・トレンド解析の提供
- [ ] 外部サービス向け認証API

### オープンソース・コミュニティ

- [ ] RFC (Request for Comments) ディレクトリ開設
- [ ] 貢献者への先行SCS付与
- [ ] ドキュメントの多言語化

## 人員・体制（2026-02-16版）

| Role                             | Person           | 担当                               |
| -------------------------------- | ---------------- | ---------------------------------- |
| God / Main Maintainer            | nicolas_ogoshi   | ビジョン・GTM・最終マージ権限      |
| Truth Debugger / 技術選定        | .4.o. (4)        | 技術的真実の担保                   |
| Special Advisor / Chaos Debugger | tfs137 (ユギ)    | 設計の壁打ち・矛盾を突くやべえやつ |
| 実装部隊                         | しろくま / Codex | コード実装・リポ管理               |

### 外部招集が必要な人材

1. **ZK & Protocol Wizard** — ゼロ知識証明エンジニア、P2P/分散レジャー・エンジニア（Rust）
2. **Synergy & Economy Architect** — トークノミクス設計、ゲーム理論、DAO設計
3. **Connectivity Specialist** — APIジャンキー、各プラットフォーム統合のハッカー
4. **AI倫理・社会学の専門家** — エージェント評価が人間に与える影響の予測

## 非営利組織化の検討

Linux Foundation / Ethereum Foundation モデル：

1. 憲章（Bylaws）の策定
2. 理事会・ガバナンス構築（DAO的アプローチも検討）
3. 収支のブロックチェーン公開による透明性
4. MIT/Apache Licenseによるオープンソース化

## 今後の展望メモ

### 保険・投資商品化（ユギ提案）

> 「エージェントを介して仕事量と成功率がわかるのであれば、保険商品みたいなものができるはず」  
> — tfs137 (ユギ), 2026-02-16 19:19

- Agent Reliability Insurance（知能の保険）
- Agent Equity（知能への投資）— ROI可視化
- ※Katala本体でやる必要はない、別会社・別サービスでもOK

### アルゴリズム販売

> 「bytedanceと同じでさ、Agent経済圏における信用情報の仕組みとかにできたりしてね。規格として外だしできる」  
> — tfs137 (ユギ), 2026-02-16 19:26

### 死者蘇生サービス

> 「死者蘇生サービスできるね」  
> — tfs137 (ユギ), 2026-02-16 02:36

エージェントのアーカイブモードを活用した、故人の知能/意志の保存・対話機能。
