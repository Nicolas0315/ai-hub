# Katala Auth Integration — 認証統合設計書

## 概要

Katalaの認証レイヤーは **ハイブリッド認証（LV1-LV3）** を採用する。
本ドキュメントでは、World ID / OIDC統合の技術調査結果と、Katala独自の認証アーキテクチャへの適用プランを記載する。

## 技術調査: World ID × OIDC

**参照**: [Worldcoin / World IDを自作アプリと統合する](https://qiita.com/trickstar03/items/18a121f8d89f070ce9da)

### World IDの技術的特徴
- **OIDC準拠**: OpenID Connectプロバイダとして動作
- **Auth0連携**: ソーシャルコネクションとして追加可能
- **統合パターン**: Auth0をブリッジにし、アプリ側はAuth0のSDKだけで完結
- **認証フロー**: QRコード → World App → ZKP検証 → IDトークン発行

### Katalaへの評価

| 観点 | 評価 | 理由 |
|------|------|------|
| OIDC基盤として | ✅ 採用可 | 標準規格。Auth0/Cognito統合パターンはKatalaのLV1認証にそのまま使える |
| Proof of Personhood | ⚠️ 部分採用 | 虹彩認証はLV3の選択肢の一つ。ただしKatalaは身体≠IDの立場（PHILOSOPHY.md参照） |
| プライバシー | ✅ 参考 | ZKPベースの認証はKatalaのLV2設計と合致 |
| 依存リスク | ❌ 非採用 | World IDをプライマリ認証にはしない。Katalaは意志ベースのID（Identity Vector）が核心 |

### Katalaの立場: 身体 ≠ ID、意志 = ID

> 「Worldcoinは身体をIDにする。Katalaは意志をIDにする。」

World IDの技術（OIDC + ZKP）は優れているが、虹彩スキャンへの依存はKatalaの思想に反する。
**採用するのは技術パターンであり、思想ではない。**

## Katala認証アーキテクチャ v2

### 3層認証モデル（更新版）

```
┌─────────────────────────────────────────────────┐
│  LV3: 高額取引・全権委任                          │
│  ├─ 虹彩認証（World ID等、オプション）             │
│  ├─ マルチバイオメトリクス                         │
│  └─ Hardware Security Key (FIDO2)               │
├─────────────────────────────────────────────────┤
│  LV2: 重要交渉・エージェント委任                   │
│  ├─ ZK-SNARKs（条件証明、内容非開示）              │
│  ├─ Verifiable Credentials (VC)                 │
│  └─ DID Resolution                              │
├─────────────────────────────────────────────────┤
│  LV1: 初期登録・日常利用                          │
│  ├─ WebAuthn / Passkey（パスキー）               │
│  ├─ OIDC Social Login（Auth0ブリッジ）            │
│  │   ├─ Google / Apple / GitHub                 │
│  │   ├─ World ID（オプション）                   │
│  │   └─ 将来の認証プロバイダ                     │
│  └─ SBT（Soulbound Token）紐付け                │
└─────────────────────────────────────────────────┘
```

### Auth0をIDブローカーとして採用する理由

1. **OIDC準拠プロバイダを統一的に管理** — Google, Apple, World IDを同一フローで扱える
2. **Katala独自認証との共存** — Auth0のCustom Connectionで Identity Vector検証を組み込み可能
3. **コンプライアンス** — SOC 2, GDPR準拠のインフラを外部委託
4. **拡張性** — 新しい認証プロバイダ追加が設定のみで完結

### 実装計画

```
Auth Flow:
  User → Auth0 (OIDC) → Katala Backend
                ↓
         Social Providers (Google/Apple/World ID)
                ↓
         Katala Identity Vector 生成
                ↓
         SBT Mint (1人1エージェント制)
                ↓
         Agent Activation
```

## 今後のアップデートプラン

### Phase 1.5: 認証基盤（新規追加フェーズ）

**優先度: 高** — Phase 2（Economy）に入る前に認証が必須

| タスク | 詳細 | 担当 | 期間目安 |
|--------|------|------|---------|
| Auth0テナント構築 | テナント作成、Social Connection設定 | しろくま | 1日 |
| WebAuthn/Passkey実装 | LV1認証のコア。`@simplewebauthn`ライブラリ使用 | 実装部隊 | 3日 |
| OIDC統合 | Google/Apple/GitHub Social Login | 実装部隊 | 2日 |
| World ID接続（オプション） | Auth0 Social ConnectionとしてWorld ID追加 | 実装部隊 | 1日 |
| Identity Vector初期生成 | 認証完了時にベクトル初期化、Staging Area連携 | 実装部隊 | 3日 |
| SBT発行フロー | 認証→ウォレット生成→SBT Mint（テストネット） | ZK Wizard（要採用） | 5日 |
| ZK-SNARKs PoC | LV2認証のプロトタイプ。circomまたはnoir使用 | ZK Wizard（要採用） | 2週間 |

### Phase 2 アップデート: Economy層への認証統合

| タスク | 詳細 |
|--------|------|
| SCS × 認証レベル連動 | 高LV認証ユーザーのSCS加算率ボーナス |
| エージェント委任状（VC発行） | LV2認証でDID署名付き委任状をエージェントに付与 |
| Progressive Disclosure × Auth | L0→L3の開示レベルが認証レベルに連動 |
| KBB（掲示板）アクセス制御 | 認証レベルに応じた閲覧・投稿権限 |

### Phase 3 アップデート: スケール

| タスク | 詳細 |
|--------|------|
| Auth0→自前IdP移行 | スケール時にAuth0依存を脱却、独自OIDC Provider構築 |
| クロスチェーン認証 | 複数チェーンのSBTを統合した認証 |
| Federated Identity | 他のKatalaノード間でのID連携 |

## 技術スタック追加

| Layer | Technology | 新規/既存 |
|-------|-----------|----------|
| IdP (Identity Provider) | Auth0 → 将来自前 | 新規 |
| LV1 Auth | WebAuthn (`@simplewebauthn`) | 新規 |
| LV2 Auth | ZK-SNARKs (circom / noir) | 新規 |
| LV3 Auth | World ID OIDC + FIDO2 | 新規 |
| Wallet | ethers.js + ERC-5192 (SBT) | 新規 |
| DID | `did:web` or `did:key` | 新規 |
| VC | W3C Verifiable Credentials | 新規 |

## 参考資料

- [World ID × Auth0統合チュートリアル](https://qiita.com/trickstar03/items/18a121f8d89f070ce9da)
- [W3C DID Specification](https://www.w3.org/TR/did-core/)
- [W3C Verifiable Credentials](https://www.w3.org/TR/vc-data-model/)
- [WebAuthn Guide](https://webauthn.guide/)
- [ERC-5192: Soulbound Token](https://eips.ethereum.org/EIPS/eip-5192)
- [circom (ZK-SNARKs)](https://docs.circom.io/)
- [Noir (ZK Language)](https://noir-lang.org/)

---

*Last updated: 2026-02-18 by しろくま*
*Source: World ID技術調査 + Katala SECURITY.md / ARCHITECTURE.md / ROADMAP.md 統合*
