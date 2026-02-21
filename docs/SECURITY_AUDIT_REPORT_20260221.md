# Security & Logic Audit Report (2026-02-21)

対象: https://github.com/Nicolas0315/Katala
目的: No-Store / 蒸留監査 / 複合認証 / 入口救済・出口悪用防止 との整合性監査

## Critical / High / Medium 一覧

## Critical

### C1. Hardcoded弱認証（admin/admin）
- 影響: 即時侵入リスク
- 根拠: `src/auth.ts`（修正前）
- 再現: `/login` で既知資格情報入力
- 対応: Dev-only credentials + env必須へ変更 ✅

### C2. ミドルウェア保護無効
- 影響: 非ログインアクセス許容
- 根拠: `src/middleware.ts`（保護処理コメントアウト）
- 再現: 未ログインで保護対象ページへ遷移
- 対応: 未ログイン時 `/login` リダイレクト有効化 ✅

### C3. 本人署名と再送攻撃耐性不足
- 影響: replayで同一操作再実行可能
- 根拠: `src/app/api/mediation/resolve/route.ts`（nonce使い捨て未実装）
- 再現: 同一payloadを再POST
- 対応: nonce store導入 + 再利用時409返却 ✅

## High

### H1. Ledger永続化未実装
- 影響: 再起動で監査証跡消失
- 根拠: `src/lib/ledger/store.ts`（インメモリ）
- 対応: DB/append-only file化（次スプリント）

### H2. HMAC署名は暫定
- 影響: 真の本人署名（Passkey assertion）未達
- 根拠: `src/lib/auth/humanSignature.ts`
- 対応: WebAuthn assertion検証へ移行（Issue化）

## Medium

### M1. docsと実装のズレが発生しやすい
- 影響: 意思決定ミス
- 対応: `SYSTEM_OVERVIEW.md` を一次ソース化（実施済み）

---

## 修正順序（24h / 3日 / 1週間）

### 24h（即時）
- C1/C2/C3 を修正・反映 ✅

### 3日
- WebAuthn assertion導入（HMAC暫定卒業）
- nonceストア永続化（Redis/DB）

### 1週間
- Ledger永続化
- 監査イベント署名（tamper-evident export）
- 自動セキュリティテスト追加

---

## パッチ適用状況

- `src/auth.ts`: Dev-only credentials化（env必須）
- `src/middleware.ts`: 未ログイン保護有効化
- `src/lib/auth/nonceStore.ts`: 使い捨てnonce導入
- `src/app/api/mediation/resolve/route.ts`: replay防止統合
- `src/app/api/__tests__/api-routes.test.ts`: replayテスト追加

---

## 判定

- **現時点判定**: Go（MVP継続可）
- 条件: High項目（Ledger永続化 / WebAuthn本実装）を次スプリントで完了すること
