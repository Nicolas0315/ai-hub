# inf-Coding-Assist

inf-Coding から利用する補助ツール層。

- `assist-exec.sh` を経由してコマンドを実行
- Orderレイヤの設定で使用可否を強制（`assist-on` でのみ実行可）

## Layout

- `diagrams/` : 生成済みPNG/JPGなどの図版
- `docs/` : handoff/spec/plan などの補助資料
- `data/generated/` : 生成済みJSON/JSONL成果物
- `cache/` : 一時キャッシュ置き場（現状は空）
- ルート直下 : 実行スクリプト (`.py` / `.sh`) と実行起点に近いファイル

方針:
- **実行ファイルは極力動かさない**
- まずは参照専用の成果物だけを分離
- 削除はせず、壊しにくい整理を優先

## Workflow Tools

### 1) 3-cycle task workflow（絶対条件）
`assist-cycle.sh` はタスク単位で以下を実行します:
- KS + KCS を毎サイクル実行（必須）
- `test/build/fix` を 3 回ループ
- 最後に 1 回だけ確認を返す（3行固定フォーマット）

```bash
./inf-Coding-Assist/assist-cycle.sh <task-id> [target-file]
```

固定出力フォーマット:
1. `RESULT: ...`
2. `DETAIL: ...`
3. `NEXT: ...`

### 2) heavy path rustization
`assist-rustize.sh` は重い処理のRust化候補を抽出します。

```bash
./inf-Coding-Assist/assist-rustize.sh
```

### 3) KL/KS47 router (fast/strict)
`ksi1-route.sh` は `inf-Bridge` 前段（plan→route→verify）を通した後、既定で **`Katala_Labyrinth_001 (KL)`** として扱う導線を使ってコマンドを判定し、fast/strict で実行ルーティングします。

- 既定: `[Katala_Labyrinth][KL]シリーズを使用`（現行内部実装は互換のため旧KQ系識別子を一部保持）
- 外部由来コンテキストは `untrusted` 扱い（拒否ではなく慎重ルーティング）
- inf-Bridgeは `collect -> normalize -> context-bind -> pattern-detect -> external-signals -> adversarial-pretest -> hardware-batch-observe -> plan -> kl-payload` の運用フローを実装
- `meta_visualization` で判定サマリー（risk_score / pattern_groups / route_hint）を出力
- External Signals / Adversarial Pretest / Hardware Batch Telemetry を前段レイヤとして保持
- inf-Bridge監査ログは一時キャッシュ出力のみで、タスク完了時に自動削除
- GoalHistoryTracker は一時キャッシュ（`.tmp-goal-history`）で保持し、出力完了時に完全削除
- **KL ルート通過時のみ** 表示は **`[Katala思考済]`** を絶対プレフィックスとする
- KS47 直結や KL 非通過時はこのプレフィックスを付けない
- 明示時のみ: `KS47` 直結（`ks-bridge.py`。自動フォールバックなし）

```bash
./inf-Coding-Assist/ksi1-route.sh git status
# KS47 を明示利用（失敗時は即エラー）
KSI_MODEL=KS47 ./inf-Coding-Assist/ksi1-route.sh git status
```

### 4) adapter analysis
`ksi1-analyze.sh` は `inf-Coding-run/ksi-bridge.ndjson` を集計して、
ルーティング比率や判定傾向を可視化します。

```bash
./inf-Coding-Assist/ksi1-analyze.sh
```

### 5) Human vs Katala 実測%（A/B）
`ab-percent.py` で human/katala の同一タスクCSVから実測%を算出します。

```bash
python3 ./inf-Coding-Assist/ab-percent.py \
  --human ./inf-Coding-run/human_metrics_template.csv \
  --katala ./inf-Coding-run/katala_metrics_template.csv
```

CSV列:
- `task_id,time_min,bugs,rework`
