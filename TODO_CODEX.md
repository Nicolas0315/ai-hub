# TODO_CODEX.md — Codex向けタスク分解

> 生成日: 2026-02-17
> 状態: 分析完了、各タスクは独立して実行可能

---

## 現状評価サマリー

| レイヤー | ファイル | 完成度 | 備考 |
|---|---|---|---|
| Profiling Engine | `packages/katala/core/ProfilingEngine.ts` | 30% | LLM呼び出しがモック。Dialogue Tuningはハードコード |
| Identity Vector | `packages/katala/core/types.ts` | 50% | スキーマ定義済みだがバリデーション・永続化なし |
| Matchmaking | `packages/katala/core/MatchmakingEngine.ts` | 60% | アルゴリズム実装済み。テストなし |
| Synergy Scorer | `packages/katala/core/SynergyScorer.ts` | 40% | X-Algorithm移植済みだが、Katala固有のスコアリングと混在 |
| Mediation Service | `packages/katala/core/MediationService.ts` | 30% | 型が`any`、protoインポートがモック |
| Mediation Client | `packages/katala/mediation-client/client.ts` | 20% | handshakeテストのみ |
| Frontend (UI) | `src/app/page.tsx` | 40% | デモUI。認証・ルーティングなし |
| Immutable Ledger | なし | 0% | 未着手 |
| Synergy Rewards | なし | 0% | 未着手 |

---

## Task 1: IdentityVector のバリデーション＆ファクトリー

**ファイルパス**: `packages/katala/core/IdentityVector.ts` (新規)、`packages/katala/core/types.ts` (修正)

**何をするか**:
- `IdentityVector` の Zod スキーマを作成（各フィールドの min/max 制約含む）
- `createDefaultVector(): IdentityVector` ファクトリー関数を実装
- `validateVector(input: unknown): IdentityVector` バリデーション関数を実装
- 既存 `types.ts` はそのまま維持し、Zod スキーマから型を推論する形に移行

**受け入れ条件**:
- [ ] `zod` を devDependencies に追加
- [ ] 不正な入力に対して ZodError をスロー
- [ ] `personality` の各値が 0.0〜1.0 の範囲であることをバリデート
- [ ] `createDefaultVector()` が有効な IdentityVector を返す
- [ ] ユニットテスト（Vitest）: 正常系3件、異常系3件

---

## Task 2: ProfilingEngine に実 LLM 呼び出しを統合

**ファイルパス**: `packages/katala/core/ProfilingEngine.ts` (修正)、`packages/katala/core/llm-adapter.ts` (新規)

**何をするか**:
- `LLMAdapter` インターフェースを定義（`analyze(messages: ChatMessage[]): Promise<PartialIdentityVector>`）
- Claude API を使った `ClaudeLLMAdapter` を実装（`.env` から `ANTHROPIC_API_KEY` を取得、dotenv使用）
- テスト用 `MockLLMAdapter` も用意
- `ProfilingEngine` のコンストラクタで DI（`constructor(adapter: LLMAdapter)`）
- `simulateLLMAnalysis` を `adapter.analyze()` に置き換え

**受け入れ条件**:
- [ ] `LLMAdapter` インターフェースが定義されている
- [ ] `MockLLMAdapter` でのユニットテストが通る
- [ ] `ClaudeLLMAdapter` が `process.env.ANTHROPIC_API_KEY` でAPIキーを取得し、Claude Messages API を叩く
- [ ] System Prompt で「チャット履歴から性格特性・価値観・専門分野を JSON で抽出」と指示
- [ ] `.env` ファイル + `dotenv` パッケージでAPIキー管理（`.env` は `.gitignore` に追加）

---

## Task 3: MatchmakingEngine のユニットテスト＆エッジケース修正

**ファイルパス**: `packages/katala/core/__tests__/MatchmakingEngine.test.ts` (新規)

**何をするか**:
- `calculateSynergy` のユニットテストを網羅的に書く
- `findMatches` のテスト（空配列、全員閾値未満、ソート順）
- エッジケース: 空の values/professionalFocus 配列、confidenceScore=0 の場合
- 発見したバグがあれば `MatchmakingEngine.ts` を修正

**受け入れ条件**:
- [ ] Vitest テストファイルが存在し、`npm test` で実行可能
- [ ] テストケース最低10件（正常系5、境界値3、異常系2）
- [ ] カバレッジ: `MatchmakingEngine.ts` の行カバレッジ 90%以上
- [ ] `package.json` に `"test": "vitest"` スクリプトが追加されている

---

## Task 4: ImmutableLedger の基盤実装（ハッシュチェーン）

**ファイルパス**: `packages/katala/core/ImmutableLedger.ts` (新規)、`packages/katala/core/__tests__/ImmutableLedger.test.ts` (新規)

**何をするか**:
- `LedgerEntry` 型定義: `{ id, timestamp, eventType, payload, previousHash, hash }`
- `ImmutableLedger` クラス:
  - `append(eventType: string, payload: Record<string, unknown>): LedgerEntry`
  - `verify(): boolean` — チェーン全体の整合性検証
  - `getHistory(limit?: number): LedgerEntry[]`
- ハッシュは `crypto.subtle.digest('SHA-256', ...)` を使用（Node.js組み込み）
- インメモリ実装（永続化は後続タスク）

**受け入れ条件**:
- [ ] `append` がエントリを追加し、前エントリの hash を `previousHash` に設定
- [ ] `verify()` が改ざんを検出できる（エントリ書き換え後に false を返す）
- [ ] Genesis エントリ（最初のエントリ）の `previousHash` が `"0"` である
- [ ] ユニットテスト: 追加、検証成功、改ざん検出、空チェーン の4パターン以上
- [ ] 外部依存なし（Node.js 標準 crypto のみ）

---

## Task 5: MediationService の型安全化＆APIルート整備

**ファイルパス**: `packages/katala/core/MediationService.ts` (修正)、`src/app/api/kani/route.ts` (修正)

**何をするか**:
- `MediationService.calculateSynergy` の引数・返値を `any` から具体的な型に変更
- `SynergyRequest` / `SynergyResponse` 型を `types.ts` に定義
- `src/app/api/kani/route.ts` にリクエストバリデーション追加（Zod）
- エラーレスポンスを統一フォーマットに（`{ error: string, code: number }`）

**受け入れ条件**:
- [ ] `MediationService` 内に `any` 型が存在しない
- [ ] `SynergyRequest` / `SynergyResponse` が `types.ts` にエクスポートされている
- [ ] API ルートが不正リクエストに 400 を返す
- [ ] `npm run build` がエラーなく通る
- [ ] ユニットテスト: 正常リクエスト、不正リクエスト、レガシー形式の3パターン
