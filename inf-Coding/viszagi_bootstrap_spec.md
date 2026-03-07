# ViszAGI Bootstrap Spec

更新: 2026-03-07 JST

## 目的

Pythonベースで、Discord上で動く **ViszAGI** の最初の設計を定義する。

この段階では以下だけを固定する:

1. Discord bot として会話を受ける
2. AgentClaw/OpenClaw のコードは再利用せず、**車輪の再発明で独立実装**する
3. `Visz-Coding` へは **単一の絶対接続点** だけを持つ
4. `Visz-Coding` 側を汚染しない
5. `inf-Coding` より先の実装は人間が引き継げるよう、MDで境界を明示する

---

## 結論

できる。
ただし「今のエニグマみたいにする」は、最初から全部ではなく、**段階的に再実装**するのが正しい。

最初の到達目標はこれ:

- Discordでメッセージ受信
- 許可された条件でのみ反応
- メッセージを正規化
- **汚染されない接続点** を通して `Visz-Coding` に処理委譲
- 戻り値をDiscordへ返す
- ログ/設定/人格を分離

---

## 実装方針

### 原則

- OpenClaw/AgentClawのコードはコピペしない
- 役割だけ借りる
- Pythonで最小構成から組む
- Visz-Coding との接続面は **1ファイル / 1関数 / 1プロトコル** に固定する
- それ以外の層は Visz-Coding を直接 import しない

### 重要思想

**ViszAGI 本体** と **Visz-Coding 実行面** を直接混ぜない。

そのため、接続は次の1点に限定する。

---

## 絶対接続点

### 接続名

`visz_coding_bridge.py`

### 配置想定

```text
ViszAGI/
  app/
    discord_bot.py
    router.py
    policy.py
    memory.py
    persona.py
    config.py
    models.py
  bridges/
    visz_coding_bridge.py
  data/
  logs/
  main.py
```

### 役割

`bridges/visz_coding_bridge.py` だけが、外部の `Visz-Coding` と通信してよい。

他のファイルは **絶対に Visz-Coding の内部を知らない**。

### ルール

- `app/*` は `Visz-Coding` のコードを import しない
- `app/*` は `Visz-Coding` のファイルパスを直参照しない
- `app/*` は subprocess を直接叩かない
- `Visz-Coding` 呼び出しは必ず `bridges/visz_coding_bridge.py` 経由
- 返却値は構造化JSON相当の dict に限定

---

## 推奨接続方式

いちばん汚染が少ないのは **subprocess boundary**。

つまり、ViszAGI は Visz-Coding をライブラリとして抱え込まず、**別プロセス実行**で呼ぶ。

### 理由

- import汚染しない
- 依存関係が混ざりにくい
- 失敗時に境界が明確
- timeout / rc / stdout / stderr を管理しやすい
- 将来 HTTP / queue / RPC に差し替えやすい

---

## 接続プロトコル

### 入力

ViszAGI → Visz-Coding に渡す payload:

```json
{
  "version": "v1",
  "request_id": "uuid",
  "source": "discord",
  "channel_id": "...",
  "user_id": "...",
  "message_text": "...",
  "reply_mode": "channel",
  "persona": "ViszAGI",
  "constraints": {
    "allow_tools": true,
    "allow_files": true,
    "timeout_sec": 120
  }
}
```

### 出力

Visz-Coding → ViszAGI の返却:

```json
{
  "ok": true,
  "reply_text": "返答本文",
  "actions": [],
  "artifacts": [],
  "meta": {
    "latency_ms": 1234,
    "engine": "visz-coding"
  }
}
```

### エラー時

```json
{
  "ok": false,
  "error": {
    "code": "TIMEOUT",
    "message": "execution timed out"
  }
}
```

---

## `visz_coding_bridge.py` の責務

このファイルだけがやること:

1. payload を受け取る
2. JSONへ整形する
3. `Visz-Coding` を subprocess で呼ぶ
4. stdout をJSONとして読む
5. 失敗時は構造化エラーへ変換する
6. 上位層に dict を返す

### 疑似コード

```python
from dataclasses import dataclass
import json
import subprocess

@dataclass
class BridgeResult:
    ok: bool
    reply_text: str | None
    error_code: str | None
    error_message: str | None
    raw: dict | None


def call_visz_coding(payload: dict) -> BridgeResult:
    proc = subprocess.run(
        ["python", "<VISZ-CODING-ENTRYPOINT>"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=120,
    )

    if proc.returncode != 0:
        return BridgeResult(
            ok=False,
            reply_text=None,
            error_code="NONZERO_EXIT",
            error_message=proc.stderr.strip() or f"rc={proc.returncode}",
            raw=None,
        )

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        return BridgeResult(
            ok=False,
            reply_text=None,
            error_code="BAD_JSON",
            error_message=str(e),
            raw=None,
        )

    if not data.get("ok"):
        err = data.get("error") or {}
        return BridgeResult(
            ok=False,
            reply_text=None,
            error_code=err.get("code", "UNKNOWN"),
            error_message=err.get("message", "unknown error"),
            raw=data,
        )

    return BridgeResult(
        ok=True,
        reply_text=data.get("reply_text", ""),
        error_code=None,
        error_message=None,
        raw=data,
    )
```

---

## ViszAGI 側の最小レイヤ構成

### 1. `main.py`
起動点。

### 2. `app/config.py`
- Discord token
- allowed guild/channel/user
- bridge command
- timeout
- logging level

### 3. `app/discord_bot.py`
- Discord接続
- mention/reply/DM 条件判定
- inbound event 受付

### 4. `app/router.py`
- Discord event を内部 request に正規化
- bridge 呼び出し
- reply 組み立て

### 5. `app/policy.py`
- 誰に反応するか
- どのチャンネルで反応するか
- 最大文字数
- 添付可否
- 危険操作の抑制

### 6. `app/persona.py`
- 名前: ViszAGI
- 口調
- system prompt 相当の固定人格

### 7. `bridges/visz_coding_bridge.py`
- 唯一の接続点

---

## 汚染防止ルール

### 絶対にやらない

- ViszAGI から Visz-Coding の内部モジュールを import する
- Visz-Coding の config を共有する
- 同じ venv を無理に共有する
- 同じ working directory に雑多な生成物を吐く
- Discord bot 層から直接コード実行を始める

### やる

- プロセス境界を作る
- JSON入出力だけ共有する
- タイムアウトを設ける
- 作業ディレクトリを分離する
- ログを分離する

---

## 最初の実装順

### Phase 1: Bot shell
- Discord bot ログイン
- mention で反応
- 固定文を返す

### Phase 2: Bridge shell
- `visz_coding_bridge.py` を実装
- ダミーJSONを返すローカルコマンドと接続

### Phase 3: Real handoff
- `Visz-Coding` の entrypoint を決定
- payload schema を固定
- エラー処理を追加

### Phase 4: Enigma-like behavior
- persona
- channel policy
- attachments
- logs
- memory
- command gating

### Phase 5: Hardening
- allowlist
- fail-close
- audit log
- artifact path control

---

## いま人間が決めるべき1点

`<VISZ-CODING-ENTRYPOINT>` を何にするか。

候補:

1. Python script
```bash
python /absolute/path/to/visz-coding-entry.py
```

2. shell wrapper
```bash
/absolute/path/to/visz-coding-run.sh
```

3. HTTP endpoint
```text
POST http://127.0.0.1:PORT/invoke
```

**おすすめは 1 か 2。**
最初はローカル subprocess がいちばん壊れにくい。

---

## 推奨仕様（今回の暫定決定）

ViszAGI は、当面こうする:

- 実装言語: Python
- Discord ライブラリ: `discord.py`
- 接続方式: subprocess
- 唯一の接続点: `bridges/visz_coding_bridge.py`
- Visz-Coding entrypoint: **絶対パスで1個だけ指定**
- 通信形式: stdin JSON / stdout JSON
- 失敗時: fail-closed で「内部処理に失敗した」とだけ返す

---

## 受け渡し用ひとこと

人間は `inf-Coding` の先で、以下だけ作ればよい。

1. `ViszAGI/bridges/visz_coding_bridge.py`
2. `Visz-Coding` の entrypoint 1個
3. stdin JSON → stdout JSON の往復仕様

ここさえ守れば、ViszAGI 本体は汚れずに増築できる。

---

## 最短の一文要約

**ViszAGI は Python 製 Discord bot として独立実装し、Visz-Coding へは `bridges/visz_coding_bridge.py` の subprocess JSON 境界だけで接続する。**
