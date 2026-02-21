# Katala Platform Flow & Code Map（コード単位の機能整理）

最終更新: 2026-02-21

このドキュメントは、Katalaの必要性を説明するために、
**「どのコードが何をしているか」** と **「全体フロー」** を蒸留して示す。

---

## 0. Katalaが必要な理由（要約）

AI時代のボトルネックは、生成能力ではなく**信頼性と合意形成**。

- モデルは増える（低コスト化）
- 出力の品質はばらつく
- 人間同士は誤解と感情ノイズで消耗する

Katalaはこの問題に対して、
**意志の正規化（Detox）→ 交渉 → 合意 → 不変ログ化（Ledger）** を提供する。

---

## 1. 全体フロー（実装ベース）

```text
[Human Input]
   ↓
/api/intent/normalize
   - テキスト正規化
   - 優先度推定
   - 意志スキーマ化
   ↓
/api/mediation/propose
   - A→Bへの提案作成
   - 中立表現へ変換
   ↓
/api/mediation/resolve
   - 人間署名の検証
   - 合意/否決を確定
   - Ledgerへ記録
   ↓
Immutable Ledger (hash chain)
   ↓
Board UI (直近合意イベント表示)
```

---

## 2. コードマップ（機能ごと）

## A. Human Layer（本人性・責任帰属）

### `src/lib/auth/humanSignature.ts`
- 役割: Human Layer署名の生成・検証
- 現在の方式: HMAC-SHA256（MVP暫定）
- 目的: 「誰が承認したか」を機械的に検証する
- 次段階: WebAuthn assertion検証へ置換

### `src/auth.ts`
- 役割: Auth.js（NextAuth）設定
- 役割範囲: セッション管理、ログイン状態
- 注意: 本人性の最終保証は `humanSignature` 側で実施（MVP）

---

## B. Mediation Layer（意志変換・交渉）

### `src/lib/mediation/detox.ts`
- 役割: 攻撃的/過剰表現の中立化（Detox）
- 実装: ルールベース変換 + priority推定
- 目的: 誤解コストと対立コストを下げる

### `src/app/api/intent/normalize/route.ts`
- 役割: 生テキストをIntent Schemaに変換
- 出力: intent, goal, constraints, deadline, priority, counterparty
- 目的: 会話を機械可読な交渉データに変える

### `src/app/api/mediation/propose/route.ts`
- 役割: 交渉提案の生成
- 出力: proposalId付き提案オブジェクト
- 目的: A→Bの提案を標準形式で流通させる

### `src/app/api/mediation/resolve/route.ts`
- 役割: 合意/否決の確定
- 重要処理:
  1) Human署名検証
  2) resolution生成
  3) ledger.append("mediation.resolved", ...)
- 目的: 「署名された合意」だけを事実として残す

---

## C. Trust Layer（不変ログ・監査）

### `packages/katala/core/ImmutableLedger.ts`
- 役割: ハッシュチェーン型の不変ログ
- 機能:
  - append(eventType, payload)
  - verify()（チェーン整合性検証）
  - getHistory(limit)
- 目的: 後から改ざん不能に近い監査証跡を提供

### `src/lib/ledger/store.ts`
- 役割: shared singleton ledger
- 目的: API間で同一Ledgerインスタンスを共有（MVP）

### `src/app/api/ledger/route.ts`
- GET: 履歴取得 + チェーン検証結果
- POST: 任意イベント追加
- 目的: 監査/可視化の基盤API

---

## D. UI Layer（可視化）

### `src/app/page.tsx`
- 役割: トップ画面
- 現在表示:
  - 認証状態
  - Board（直近合意ログ）
  - SynergyDashboard
- 目的: 結果だけを人間に返す（UIレス思想の入口）

---

## E. Profiling / Matchmaking / Import（既存機能）

### `src/app/api/profiling/route.ts`
- プロファイル更新（会話履歴から）
- tune mode（指示でベクトル調整）

### `src/app/api/matchmaking/route.ts`
- source/candidatesのシナジー計算
- マッチ候補返却

### `src/app/api/import/route.ts`
- CSVインポート
- 構造化データへの変換

### `src/app/api/batch/route.ts`
- バッチ処理の受付・状態取得

---

## 3. 蒸留する仕組み（重要）

Katalaの本質は、**情報をそのまま増やすことではなく、意味を蒸留してから残すこと**。

### 蒸留パイプライン

1. **Raw Input**
   - 人間の自然文、感情、ノイズ

2. **Normalization**
   - Intent Schema化
   - 目的/制約/期限/優先度を抽出

3. **Detox**
   - 感情ノイズ除去
   - 交渉可能な中立表現へ変換

4. **Decision Point**
   - 提案/合意/否決を明示
   - Human署名で責任帰属

5. **Open Threshold判定**
   - L0/L1/L2を機械判定
   - 高リスクは収集禁止、 中リスクは蒸留後のみ

6. **Immutable Record**
   - 必要最小の事実だけをLedgerへ記録
   - 後から検証可能な形で保存

### なぜこれが必要か

- 生成AI時代は「情報過多」になる
- そのまま保存するとノイズが支配する
- だからKatalaは「事実に必要な最小構造」へ蒸留して残す

> 目的: 記録を増やすことではなく、意思決定コストを下げること。

---

## 4. 現在の限界（正直ベース）

- Human署名はHMAC暫定（Passkey実署名は次段）
- Ledgerはインメモリ（永続化未完了）
- Detoxはルールベース（高度文脈対応は未実装）
- 提案管理は短命（DBでの状態遷移管理は未実装）

---

## 5. 次に実装すべき4点

1. WebAuthn assertion検証（Human署名の本番化）
2. nonce再利用防止（replay対策）
3. Ledger永続化（DB/ファイル）
4. 蒸留ポリシーの設定可能化（領域別Detox）

---

## 6. 関連ドキュメント

- `SYSTEM_OVERVIEW.md`（現行状態の俯瞰）
- `MVP_COMM_PROTOCOL.md`（MVP通信仕様）
- `AUTH_INTEGRATION.md`（認証方針）
- `SECURITY.md`（攻撃シナリオと防御）
- `ROADMAP.md`（時系列計画）

---

*この文書は「必要性を説明するための技術根拠」として維持する。*
