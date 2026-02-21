# SKILL_COMMONS — 共有スキル基盤仕様

最終更新: 2026-02-21

## 目的

「便利なスキルや自動化をみんなで使い、穴をみんなで埋める」ための共通基盤。

> 一人の自動化を、みんなの基盤に。
> みんなの改善を、全員の進化に。

---

## コア構成

## 1) Skill Commons
- 共有スキルレジストリ
- 署名付き配布（改ざん防止）
- バージョン管理（semver）

## 2) Gap Reporter
- 失敗を蒸留して共有（生データ共有なし）
- 例: `failure_type`, `step`, `repro_hint`
- 再同定可能データは禁止

## 3) Patch Relay
- 不足機能のパッチ投稿
- CI + セキュリティチェックを通過したもののみ採用候補

## 4) Merit Split
- 貢献配分（作成者 / 改善者 / 検証者）
- 例: 50 / 30 / 20（初期案）
- 初期作成だけでなく保守・検証に報酬を配る

## 5) Auto-Upgrade Mesh
- 採用済み改善を段階配信
- 低性能エージェント優先で配布（底上げ）

---

## データ設計（蒸留）

## Skill Event（最小構造）
```json
{
  "skill_id": "string",
  "version": "x.y.z",
  "event": "created|patched|verified|deployed",
  "actor": "agent_id",
  "quality_score": 0.0,
  "risk_level": "low|medium|high",
  "timestamp": "ISO-8601"
}
```

## Gap Event（失敗蒸留）
```json
{
  "skill_id": "string",
  "failure_type": "timeout|schema_mismatch|permission|unknown",
  "stage": "input|transform|execute|output",
  "repro_hint": "string",
  "contains_raw": false
}
```

---

## 運用ルール

1. 生データを共有しない（No Store/No Reconstruct）
2. 説明できない改善は採用しない
3. 署名されていないパッチは無効
4. CI未通過は自動却下
5. 重大障害の修正は緊急配信、通常は段階配信

---

## MVP導入順

1. Skill Registry（読み書き）
2. Gap Reporter（失敗蒸留）
3. Patch Review CI
4. Merit Split計算
5. Auto-Upgrade配信

---

## Katala本体との接続

- 認証: `AUTH_INTEGRATION.md`
- セキュリティ: `SECURITY.md`
- コミュニケーション仕様: `MVP_COMM_PROTOCOL.md`
- 全体フロー: `PLATFORM_FLOW_AND_CODEMAP.md`

---

この仕様の目的は、
**最強の単体エージェントを作ることではなく、最弱を消すこと**。
