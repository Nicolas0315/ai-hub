# OpenClaw 障害分析レポート (KS/KCS)

- 作成日時: 2026-03-02
- 対象期間: 2026-02-27 〜 2026-03-01 (JST/UTC混在ログを日付キーで集計)
- 対象: `/Users/nicolas/work/openclaw-agent-workspace` と `~/.openclaw` 実ログ

## 1. 結論（先に要点）

「やると言ってやらなくなった」主因は、**記憶そのものの破損よりも、実行基盤の不安定化（Gateway多重起動ループ + API制限 + Context overflow）**。

Opus運用期 (2/27〜3/1) は実際にはツール実行自体は継続していたが、以下が重なって完走率を下げた。

1. 2/27: **Gateway競合ループ**（同一ポート再起動試行の連打）
2. 2/27〜2/28: **API rate limit / timeout / UNAVAILABLE** の多発
3. 2/28: **Context overflowの連鎖再試行**（同runIdで複数回失敗）
4. 3/1前後: **設定値の急変更**（`contextTokens=12000` 時期 → 後で 200000 + reserve floor へ修正）
5. 2/27〜3/1: セッション `.deleted/.reset` 多発により会話継続性が断片化

## 2. KS/KCS 判定

### KS（Knowledge State: 記憶・知識）

- 判定: **副次要因**
- 根拠:
  - セッションログ上、Opusは `memory_search` / `memory_get` / `exec` を継続実行しており、記憶検索機能が全面停止した証拠はない。
  - ただし `.deleted/.reset` 多発により、会話連続性（継続推論の土台）は弱化。

### KCS（Knowledge/Context/System）

- K（Knowledgeデータ）: **中**
  - データ欠損より、運用中の断片化（セッション整理の多発）が問題。
- C（Context管理）: **高**
  - `Context overflow` が2/28に集中発生。
  - `contextTokens=12000` が3/1 00:44〜00:55のバックアップで確認され、文脈不足を誘発しうる。
- S（System実行基盤）: **最重**
  - Gateway多重起動競合、restart drain、timeout/rate-limit多発が同時に発生。

## 3. 定量結果（2/27〜3/1）

### 3.1 セッション集計

- Assistantメッセージ数: 2/27=284, 2/28=3819, 3/1=9179
- Assistant `toolUse` 停止理由率:
  - 2/27: 191/284 = 67.3%
  - 2/28: 2381/3819 = 62.3%
  - 3/1: 6752/9179 = 73.6%
- ToolResultエラー（message.isError=true）:
  - 2/28=1, 3/1=7
- モデル別 Assistant件数（上位）:
  - `claude-opus-4-6`: 11324
  - `delivery-mirror`: 1274
  - `claude-sonnet-4-6`: 349
  - `claude-haiku-4-5`: 234
  - `gpt-5.3-codex`: 96
  - `gemini-3.1-pro-preview`: 5

解釈: 「まったく実行しない」のではなく、**実行は多数だが途中失敗で完了率が低下**。

### 3.2 Gatewayログ集計

- `gateway.err.20260301.log`:
  - `timeout`: 2/27=27, 2/28=86
  - `UNAVAILABLE`: 2/27=14, 2/28=21
  - `rate_limit/429`: 2/27=113, 2/28=76
  - `context overflow`: 2/28=54
  - `restart_failed`: 2/28=6
- `gateway.20260301.log`:
  - `channels unresolved`: 2/27=45, 2/28=40
  - `draining active task(s) before restart`: 2/27=2, 2/28=7

## 4. 重要証拠（抜粋）

1. Gateway競合ループ（2/27 00:00台から約4時間）
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:762894`
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:762896`
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:762898`

2. API rate limit 連発
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:775970`

3. Context overflow 連発（2/28）
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:780695`
   - `/Users/nicolas/.openclaw/logs/gateway.err.20260301.log:782060`

4. セッション内でのContext overflow明示
   - `/Users/nicolas/.openclaw/agents/main/sessions/70c9a8d0-b148-497f-812f-2dd3b7134696.jsonl.deleted:2`

5. 3/1時点の危険設定（`contextTokens=12000`）
   - `/Users/nicolas/.openclaw/openclaw.json.bak-20260301-0056:230`

6. その後の是正（`contextTokens=200000`, `reserveTokensFloor=20000→40000`）
   - `/Users/nicolas/.openclaw/openclaw.json.bak-20260301-0246:305`
   - `/Users/nicolas/.openclaw/openclaw.json.bak-20260301-0246:319`
   - `/Users/nicolas/.openclaw/openclaw.json.bak-20260301-0250:319`

7. モデル主系統の遷移（Opus→Geminiは3/2）
   - 2/27〜3/1 バックアップは `primary=anthropic/claude-opus-4-6`
   - 3/2 18:22以降のバックアップで `primary=google/gemini-3.1-pro-preview`

## 5. 「Opus→Gemini→Codex」時系列（確認結果）

- Opus主運用: 少なくとも 2026-02-27 13:50 〜 2026-03-02 15:17 のバックアップで確認
- Gemini主運用化: 2026-03-02 18:22 バックアップで確認
- Codex主運用化: 2026-03-02 21:27 バックアップで確認

## 6. 原因判定（最終）

- 第一原因（S）: Gateway/実行基盤の不安定化（多重起動・再起動・timeout）
- 第二原因（C）: Context管理の不整合（低すぎる`contextTokens`とreserve不足の時期）
- 第三原因（K）: セッション削除/リセット多発による継続性低下
- 補足: モデル変更（Gemini化）は**主障害発生後の時系列**であり、2/27〜3/1性能低下の一次原因ではない

## 7. 改善アクション（優先順）

1. Gateway単一起動の強制
   - 起動前に `openclaw gateway stop` を必須化
   - PID/port lockチェック失敗時は再起動ループせず即停止
2. コンテキスト安全域の固定
   - `contextTokens >= 160000`
   - `compaction.reserveTokensFloor >= 40000`（運用実績から50000推奨）
3. 失敗時リトライ制御
   - `rate_limit`, `UNAVAILABLE`, `timeout` は指数バックオフ + 最大試行回数を明示制限
4. セッション保全
   - `.deleted/.reset` を自動大量発行しない
   - 長セッションは定期サマリ圧縮してから継続
5. 監視
   - 5分窓で `Gateway already running` と `Context overflow` のしきい値アラート

## 8. 追加メモ

- バックアップ `/Volumes/My Passport/oc-backup` は、ログファイル（例: `gateway.err.20260301.log`）が現行と一致するものあり。
- 現行 `openclaw.json` はバックアップ時点と差分あり（主にモデル/クールダウン/検索周り設定）。
