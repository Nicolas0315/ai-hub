# MVP Communication Protocol — Katala

## 目的

人と人のコミュニケーションを、
**会話 → 誤解 → 消耗** から
**意志 → 検証 → 合意** に進化させる。

MVPでは「最小で動く」ことを優先し、複雑な自律実行は後段に回す。

---

## MVPスコープ

### In Scope（MVPで実装）

- 意志入力（Intent Input）
- デトックス変換（表現ノイズ削減）
- 本人性確認（Human Layer）
- 合意案の提示（Synergy-based Proposal）
- 合意ログの不変記録（Ledger）

### Out of Scope（Phase 2以降）

- 完全自律実行（支払い/契約の自動執行）
- 高度な法務判定
- クロスチェーン決済

---

## 3レイヤー構成

### 1) Human Layer（本人性）

- Passkey / WebAuthn
- Device binding
- Agent ID（SBT/DID想定、MVPは仮ID可）

**目的:** 「誰の代理エージェントか」を証明する

### 2) Mediation Layer（意味変換）

- 入力文を Intent Schema に正規化
- 感情過多・攻撃語をデトックス
- 交渉に必要な条件（目的/制約/期限）を抽出

**目的:** 誤解コストを下げる

### 3) Trust Layer（検証・記録）

- 合意内容を Ledger に記録
- 変更履歴をハッシュ連鎖で保持
- 監査可能性を担保

**目的:** 後から検証できる状態を作る

---

## Intent Schema（MVP）

```json
{
  "intent": "string",
  "goal": "string",
  "constraints": ["string"],
  "deadline": "ISO-8601|null",
  "priority": "low|medium|high",
  "counterparty": "agent_id|string"
}
```

---

## MVPフロー

1. Human A が意志を入力
2. A-Agent が Intent Schema へ変換
3. Detox Filter で表現ノイズを削減
4. B-Agent へ提案送信
5. B側も同様に正規化して評価
6. Synergy Engine が合意候補を生成
7. 両者承認で Ledger に記録
8. 人間へ「合意結果のみ」通知

---

## 受け入れ基準（Acceptance Criteria）

- [ ] 同一入力でもIntent Schemaが安定して再現される
- [ ] 攻撃的表現を含む入力でも、交渉可能な中立表現に変換される
- [ ] 合意の全イベントがLedgerに記録され、ハッシュ検証が通る
- [ ] 合意不成立時に「どの条件が衝突したか」を説明できる
- [ ] APIレスポンス95%が1.5秒以内（MVP目標）

---

## API案（MVP）

### POST /api/intent/normalize

入力文をIntent Schemaに変換

### POST /api/mediation/propose

相手エージェントへ提案生成

### POST /api/mediation/resolve

合意/非合意を確定

### GET /api/ledger/:id

合意ログ取得（監査用）

---

## セキュリティ要件（MVP）

- すべてのAPIは認証必須（最低JWT + session）
- PII検知時は `Mediation Only` 扱いで外部送信を抑制
- 失敗ログにも機微情報を残さない（マスキング）

---

## 実装優先順位

1. `intent/normalize` API
2. Detox Filter（最小ルールベース）
3. `mediation/propose` + `resolve`
4. Ledger記録
5. シンプルUI（Boardに合意結果表示）

---

## 備考

- このプロトコルは「人間を置き換える」ためではなく、
  **人間同士の接続の質を上げる**ためのもの。
- MVPは「完全自律」ではなく「合意形成の補助」にフォーカスする。

_Last updated: 2026-02-21_
