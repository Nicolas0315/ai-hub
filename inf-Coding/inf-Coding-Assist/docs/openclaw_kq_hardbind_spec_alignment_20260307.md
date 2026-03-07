# OpenClaw突合仕様書: KL Mandatory Hard-Bind

更新日時: 2026-03-07 JST  
対象: `https://github.com/openclaw/openclaw` の実装系に対する Enigma/KL 強制通過仕様

---

## 1. 目的

通常チャット受信から応答送信まで、**全経路で KL パケットを必須化**し、
`AgentClaw -> inf-Coding -> inf-Bridge -> KL -> inf-Brain` をバイパス不能にする。

---

## 2. 現状整理（差分）

- 完了済み:
  - router/exec 側の fail-close（No.3）
- 未完:
  - chat ingress 側 hard-bind（No.1）

要点: ソース差分はあるが、実行中runtimeへの完全反映が未完了の場合、No.1が残る。

---

## 3. OpenClaw突合ポイント（実装接点）

以下は OpenClaw の auto-reply 入口周辺で実装/検証すべきポイント。

1. `message_received` 相当の受信入口
2. `dispatch-from-config` 相当の返信実行導線
3. `bash-tools.exec` 相当の実行系
4. 診断ログ（processed / queued / blocked）

---

## 4. 必須仕様（MUST）

### 4.1 Ingress Hard-Bind

- 受信時に `KL_INPUT_PACKET_JSON` を生成し、contextへ添付すること
- 当面は互換のため内部実装で `KQ_INPUT_PACKET_JSON` を保持してもよい
- パケット欠落/不正時は **fail-close**（応答生成しない）

### 4.2 Outbound Hard-Bind

- 外部送信直前に `KL_INPUT_PACKET_JSON` を再検証すること
- 当面は互換のため内部実装で `KQ_INPUT_PACKET_JSON` を保持してもよい
- 欠落/不正時は **fail-close**（送信しない）

### 4.3 Exec Path Hard-Bind

- 実行系（shell/tool）に `KL_INPUT_PACKET_JSON` を必ず伝搬すること
- 当面は互換のため内部実装で `KQ_INPUT_PACKET_JSON` を保持してもよい
- 欠落/不正時は `rc=74` で拒否

### 4.4 Evidence Logging

以下の監査項目を必須化:
- `ingress_kq_packet_created`
- `kq_packet_propagated_to_exec`
- `ingress_blocked_reason`
- `outbound_blocked_reason`

---

## 5. 受入基準（Definition of Done）

次を同時達成したら「完全反映」:

1. `no1_chat_ingress_forced = true`
2. `no3_router_external_fail_close = true`
3. KQパケット無しの通常会話入力が fail-close される
4. KQパケット無しの実行系が `rc=74` で拒否される
5. 監査ログで ingress→KQ→Bridge→Model の到達が追跡できる

---

## 6. 運用ルール

- デフォルト: `KQ_MANDATORY_GATE=1`
- 例外運用をする場合も、監査ログに理由を残す
- 一時無効化は緊急時のみ、復旧後に再強制

---

## 7. ロールアウト手順（最短）

1. PRマージ
2. runtimeビルド/再インストール（dist更新）
3. gateway再起動
4. 受入テスト（DoD 1-5）
5. 監査結果を共有

---

## 8. 補足

- 本仕様は「会話入口を含む全経路KQ強制」を目的とする。
- 実行系のみ強制（No.3のみ）では不十分。
