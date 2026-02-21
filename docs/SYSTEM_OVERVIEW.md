# Katala System Overview（現行実装サマリー）

最終更新: 2026-02-21

このドキュメントは、Katalaの**現在の実装状態**を1枚で把握するための運用ドキュメントです。
「思想」「計画」ではなく、**今動いているもの**を基準に整理します。

---

## 1. 現在の実装スコープ（MVP）

### ✅ 実装済み

- 認証（暫定）
  - Auth.js/NextAuthベースのログインフロー
  - Human Layer署名検証（HMACベースのMVP実装）
  - World ID/OIDC統合の低リスク導入パターン（環境変数指定時のみ有効）
- Intent/Mediation API
  - `POST /api/intent/normalize`
  - `POST /api/mediation/propose`
  - `POST /api/mediation/resolve`
- Ledger
  - `ImmutableLedger`（ハッシュチェーン）
  - resolve時の`mediation.resolved`イベント記録
- Board表示
  - 直近合意ログの表示（トップページ）
- 既存API群
  - profiling / matchmaking / import / batch / ledger
- テスト
  - APIテスト（17/17 pass）

### ⏳ 進行中

- WebAuthn実署名（Passkey assertion）への置換
- 認証憲章（No Store / No Reconstruct）に沿った実装強化
- Ledger永続化（現状はインメモリ）

### ❌ 未実装（計画のみ）

- 本格的ZK証明
- DID/VCの本運用
- クロスチェーン認証
- 完全自律実行（決済・契約の自動執行）

---

## 2. アーキテクチャ（現行）

```text
Human Input
  ↓
Intent Normalize (Detox + Priority Inference)
  ↓
Mediation Propose / Resolve
  ↓ (signature verification)
Ledger Append (immutable hash chain)
  ↓
Board (recent agreement events)
```

### コンポーネント対応

- Human Layer（暫定）: `src/lib/auth/humanSignature.ts`
- Mediation Layer: `src/app/api/intent/*`, `src/app/api/mediation/*`
- Trust Layer: `packages/katala/core/ImmutableLedger.ts`, `src/lib/ledger/store.ts`
- UI Layer: `src/app/page.tsx`

---

## 3. 主要エンドポイント一覧（現行）

- `POST /api/intent/normalize` — 意志の正規化
- `POST /api/mediation/propose` — 提案生成
- `POST /api/mediation/resolve` — 合意/否決確定 + Ledger記録
- `GET /api/ledger` — 監査ログ取得
- `POST /api/ledger` — 任意イベント追記
- `POST /api/profiling` — プロファイル更新/調整
- `POST /api/matchmaking` — マッチ候補算出
- `POST /api/import` — CSVインポート
- `POST/GET /api/batch` — バッチ処理

---

## 4. 認証・セキュリティ方針（現行）

認証憲章（No-Store Charter）を採用。

- No Store
- No Reconstruct
- Code is Liability
- Explainable by Design
- Cannot Hand Over What We Don’t Have

参照:
- `AUTH_INTEGRATION.md`
- `SECURITY.md`

---

## 5. ドキュメント運用（更新ルール）

- 議論が実装に影響したら、同日中にdocs更新
- 実装済み/未実装を混在させない
- URL共有までを1セット

### 現在の基準ドキュメント（優先参照）

1. `SYSTEM_OVERVIEW.md`（このファイル）
2. `PLATFORM_FLOW_AND_CODEMAP.md`（コード単位の機能説明 + 蒸留パイプライン）
3. `MVP_COMM_PROTOCOL.md`
4. `AUTH_INTEGRATION.md`
5. `SECURITY.md`
6. `ROADMAP.md`
7. `PREDICTIONS.md`

---

## 6. 古い内容を含む可能性があるドキュメント

以下は歴史的価値はあるが、**現行仕様の単一ソースとしては使わない**。

- `AUTH.md`（認証の初期セットアップ中心）
- `IMPLEMENTATION_PLAN.md`（時点依存）
- `DAILY_TARGET_20260216.md`（日次計画）
- `GTM_REPORT_20260216.md`（日付固定レポート）

必要な情報は本ファイルと上位ドキュメントへ順次統合する。

---

## 7. 次の実装優先順位

1. WebAuthn assertion検証（HMAC暫定を卒業）
2. resolve時のnonce再利用防止（replay attack対策）
3. Ledger永続化（ファイル or DB）
4. Boardフィルタ（合意イベントのみ/actor別）

---

*Owner: しろくま*
*レビュー: Nicolas-san*
