# WORLDCOIN Adoption Matrix (Katala)

最終更新: 2026-02-21

方針: **導入リスクの低いものから段階導入**。
評価軸: No-Store適合 / 実装難易度 / 法務リスク / Katala親和性

## サマリー

| Repo | 用途 | No-Store適合 | 実装難易度 | 法務リスク | Katala親和性 | 推奨 |
|---|---|---:|---:|---:|---:|---|
| `world-id-nextauth-template` | Auth.js統合パターン | 高 | 低 | 低 | 高 | **導入候補A** |
| `idkit-js` | World ID連携SDK（フロント） | 中 | 低〜中 | 中 | 中〜高 | **導入候補B（限定）** |
| `semaphore-rs` | 匿名一意性/ZK系基盤 | 高 | 中〜高 | 低〜中 | 高 | **導入候補C（PoC）** |
| `wallet-bridge` | ZKP受け渡しブリッジ | 中〜高 | 中 | 中 | 中 | 後段 |
| `open-iris` | 虹彩推論 | 低（運用次第） | 高 | 高 | 低〜中 | 研究限定 |

---

## 1) low-risk first（今やる）

### A. NextAuth統合パターン取り込み
- 対象: `world-id-nextauth-template`
- 狙い: Katala既存Auth.js構成に差分少なく接続
- 実装範囲: まずは「連携パターン調査 + サンプルブランチ作成」

### B. SDK境界の分離
- 対象: `idkit-js`
- 狙い: PoPを「任意の外部証明手段」として扱う
- ルール: No-Store Charterを破るパスは無効化（生体原本/生ログ不保存）

---

## 2) PoC枠（次）

### C. semaphore-rs で匿名一意性PoC
- 狙い: 「本人特定しない一意性」をKatalaに接続
- 成果物: 1) PoC API 2) 検証手順 3) 失敗条件

---

## 3) 導入禁止/研究限定

### open-iris
- 生体運用を伴うため法務・倫理リスク高
- Katalaでは本番導入しない（研究サンドボックス限定）

---

## 4) 実装ガードレール

1. 生体/身分証原本は保存しない
2. 目的外利用禁止（Purpose Limitation）
3. 収集は蒸留信号のみ
4. 監査ログは保持、原文は保持しない

---

## 5) 決定

- 先行導入: `world-id-nextauth-template` の統合パターン
- 並行調査: `idkit-js` の限定導入
- PoC: `semaphore-rs`
- 保留: `wallet-bridge`
- 研究限定: `open-iris`
