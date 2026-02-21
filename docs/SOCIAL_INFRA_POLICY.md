# Social Infrastructure Policy — 誰も排除しない入口 / 誰にも悪用させない出口

最終更新: 2026-02-21

## 核心

> 誰も排除しない入口（Inclusion by Default）
> 誰にも悪用させない出口（Abuse Resistance by Design）

Katalaは、無戸籍・ID未整備・脆弱な立場の人にも最低限の社会参入を保証しつつ、
なりすまし・強要・人生リセット悪用を防ぐ。

---

## 1) 思想（設計原則）

1. **Human First**: 国家IDの有無で人間価値を判定しない
2. **Least Power**: 最小権限から開始し、実績で段階解放
3. **No Store**: 生体/原本/生ログを保存しない
4. **Distilled Audit**: 蒸留信号のみ監査対象にする
5. **Recoverable but Non-Resettable**: 復旧はできるが、履歴の全消しリセットは不可

---

## 2) 入口（Inclusion Entry）

### Identity Tiers

- **T0 Guest**: 匿名閲覧・低リスク操作のみ
- **T1 Continuity**: Passkey + deviceで継続主体を確認
- **T2 Community Proof**: 複数証人VC（2-of-3）
- **T3 Legal Link**: 行政ID等との連携（任意/地域依存）

### 入口のルール

- T0/T1で社会参加の最低機能は開放
- T2/T3で高権限機能を段階開放
- T3がないことを理由に基本参加を拒否しない

---

## 3) 出口（Abuse-Resistant Exit）

### リスク対策

- **Replay防止**: nonce使い捨て
- **Coercion対策**: duress flag + delayed execution
- **Sybil対策**: 同一主体の再登録パターン検知（非可逆）
- **Privilege Freeze**: 異常時は高権限を即時凍結

### 監査

- 記録はイベント/カテゴリ/時刻/理由コードのみ
- 原文・生体・身分証原本は不保存

---

## 4) 実装マップ

- Policy: `src/lib/policy/inclusionGuard.ts`
- Resolve API統合: `src/app/api/mediation/resolve/route.ts`（次段）
- Security規約: `docs/SECURITY.md`
- 全体フロー: `docs/PLATFORM_FLOW_AND_CODEMAP.md`

---

## 5) 成功条件（KPI）

1. 低身分証明ユーザーの参加率
2. 高リスク操作での不正成立率
3. 乗っ取り/強要検知から凍結までの時間
4. 再登録悪用（人生リセット）検知率

---

## 6) 一言

「救済を例外ではなく標準機能にする。」
