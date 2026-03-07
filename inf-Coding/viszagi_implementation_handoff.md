# ViszAGI Implementation Handoff

更新: 2026-03-07 JST

## 目的

あなたがこのままコピペして、すぐ実装に入れるようにする。

今回は **設計の説明を減らして、実装に必要なコード断片をそのまま渡す**。

前提:
- Python ベース
- Discord bot
- `Visz-Coding` とは **絶対に1接続点だけ** 持つ
- その接続点は `bridges/visz_coding_bridge.py`
- `ViszAGI` 本体は `Visz-Coding` を import しない
- 通信は `stdin JSON -> stdout JSON`

---

# ディレクトリ構成

```text
ViszAGI/
  main.py
  requirements.txt
  .env
  app/
    __init__.py
    config.py
    models.py
    policy.py
    router.py
    discord_bot.py
  bridges/
    __init__.py
    visz_coding_bridge.py
```

---

# requirements.txt

```txt
discord.py==2.5.2
python-dotenv==1.0.1
```

---

# .env

```env
DISCORD_TOKEN=YOUR_DISCORD_BOT_TOKEN
VISZ_ALLOWED_CHANNEL_IDS=1476438544309551104
VISZ_ALLOWED_USER_IDS=
VISZ_TRIGGER_MODE=mention_or_reply
VISZ_BRIDGE_COMMAND=python /ABSOLUTE/PATH/TO/visz_coding_entry.py
VISZ_BRIDGE_TIMEOUT_SEC=120
VISZ_BOT_NAME=ViszAGI
```

※ `VISZ_BRIDGE_COMMAND` は **絶対パス** にすること。

---

# main.py

```python
from app.discord_bot import run_bot

if __name__ == "__main__":
    run_bot()
```

---

# app/config.py

```python
from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _split_csv_int(value: str) -> set[int]:
    value = (value or "").strip()
    if not value:
        return set()
    return {int(x.strip()) for x in value.split(",") if x.strip()}


@dataclass(frozen=True)
class Settings:
    discord_token: str
    allowed_channel_ids: set[int]
    allowed_user_ids: set[int]
    trigger_mode: str
    bridge_command: list[str]
    bridge_timeout_sec: int
    bot_name: str


settings = Settings(
    discord_token=os.environ["DISCORD_TOKEN"],
    allowed_channel_ids=_split_csv_int(os.getenv("VISZ_ALLOWED_CHANNEL_IDS", "")),
    allowed_user_ids=_split_csv_int(os.getenv("VISZ_ALLOWED_USER_IDS", "")),
    trigger_mode=os.getenv("VISZ_TRIGGER_MODE", "mention_or_reply"),
    bridge_command=shlex.split(os.environ["VISZ_BRIDGE_COMMAND"]),
    bridge_timeout_sec=int(os.getenv("VISZ_BRIDGE_TIMEOUT_SEC", "120")),
    bot_name=os.getenv("VISZ_BOT_NAME", "ViszAGI"),
)
```

---

# app/models.py

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InboundRequest:
    request_id: str
    source: str
    channel_id: str
    user_id: str
    username: str
    message_text: str
    reply_mode: str = "channel"
    persona: str = "ViszAGI"
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class BridgeResponse:
    ok: bool
    reply_text: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] | None = None
```

---

# app/policy.py

```python
from __future__ import annotations

import discord
from app.config import settings


def is_allowed_channel(message: discord.Message) -> bool:
    if not settings.allowed_channel_ids:
        return True
    return message.channel.id in settings.allowed_channel_ids


def is_allowed_user(message: discord.Message) -> bool:
    if not settings.allowed_user_ids:
        return True
    return message.author.id in settings.allowed_user_ids


def should_respond(message: discord.Message, bot_user: discord.ClientUser | None) -> bool:
    if message.author.bot:
        return False

    if not is_allowed_channel(message):
        return False

    if not is_allowed_user(message):
        return False

    mode = settings.trigger_mode

    if mode == "always":
        return True

    if bot_user is None:
        return False

    if mode == "mention":
        return bot_user in message.mentions

    if mode == "reply":
        if not message.reference or not message.reference.resolved:
            return False
        ref = message.reference.resolved
        return getattr(ref, "author", None) and ref.author.id == bot_user.id

    if mode == "mention_or_reply":
        mentioned = bot_user in message.mentions
        replied = False
        if message.reference and message.reference.resolved:
            ref = message.reference.resolved
            replied = getattr(ref, "author", None) and ref.author.id == bot_user.id
        return bool(mentioned or replied)

    return False
```

---

# bridges/visz_coding_bridge.py

```python
from __future__ import annotations

import json
import subprocess
from app.config import settings
from app.models import BridgeResponse, InboundRequest


def call_visz_coding(req: InboundRequest) -> BridgeResponse:
    payload = {
        "version": "v1",
        "request_id": req.request_id,
        "source": req.source,
        "channel_id": req.channel_id,
        "user_id": req.user_id,
        "username": req.username,
        "message_text": req.message_text,
        "reply_mode": req.reply_mode,
        "persona": req.persona,
        "constraints": req.constraints,
    }

    try:
        proc = subprocess.run(
            settings.bridge_command,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=settings.bridge_timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return BridgeResponse(
            ok=False,
            error_code="TIMEOUT",
            error_message="visz-coding bridge timed out",
        )
    except Exception as e:
        return BridgeResponse(
            ok=False,
            error_code="SPAWN_FAILED",
            error_message=str(e),
        )

    if proc.returncode != 0:
        return BridgeResponse(
            ok=False,
            error_code="NONZERO_EXIT",
            error_message=proc.stderr.strip() or f"rc={proc.returncode}",
        )

    try:
        data = json.loads(proc.stdout)
    except Exception as e:
        return BridgeResponse(
            ok=False,
            error_code="BAD_JSON",
            error_message=f"stdout was not valid JSON: {e}",
        )

    if not data.get("ok"):
        err = data.get("error") or {}
        return BridgeResponse(
            ok=False,
            error_code=err.get("code", "UNKNOWN"),
            error_message=err.get("message", "unknown error"),
            raw=data,
        )

    return BridgeResponse(
        ok=True,
        reply_text=data.get("reply_text", ""),
        raw=data,
    )
```

---

# app/router.py

```python
from __future__ import annotations

import uuid
import discord
from app.models import InboundRequest, BridgeResponse
from bridges.visz_coding_bridge import call_visz_coding


def normalize_message(message: discord.Message) -> InboundRequest:
    text = message.content or ""

    return InboundRequest(
        request_id=str(uuid.uuid4()),
        source="discord",
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        username=str(message.author),
        message_text=text,
        reply_mode="channel",
        persona="ViszAGI",
        constraints={
            "allow_tools": True,
            "allow_files": True,
            "timeout_sec": 120,
        },
    )


def handle_message(message: discord.Message) -> BridgeResponse:
    req = normalize_message(message)
    return call_visz_coding(req)
```

---

# app/discord_bot.py

```python
from __future__ import annotations

import discord
from app.config import settings
from app.policy import should_respond
from app.router import handle_message


def run_bot() -> None:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    intents.messages = True

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        print(f"{settings.bot_name} ready as {client.user}")

    @client.event
    async def on_message(message: discord.Message) -> None:
        if not should_respond(message, client.user):
            return

        async with message.channel.typing():
            result = handle_message(message)

        if result.ok and result.reply_text:
            await message.reply(result.reply_text, mention_author=False)
        else:
            await message.reply(
                f"内部処理に失敗した。({result.error_code or 'ERROR'})",
                mention_author=False,
            )

    client.run(settings.discord_token)
```

---

# Visz-Coding 側の最小 entrypoint 例

これは **ViszAGI 側ではなく、Visz-Coding 側に置く想定**。

たとえば `visz_coding_entry.py`:

```python
import json
import sys


def main() -> None:
    raw = sys.stdin.read()
    req = json.loads(raw)

    text = req.get("message_text", "")

    # ここをあとで本物に差し替える
    reply = f"Visz-Coding received: {text}"

    sys.stdout.write(json.dumps({
        "ok": True,
        "reply_text": reply,
        "actions": [],
        "artifacts": [],
        "meta": {"engine": "visz-coding"},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
```

---

# まずやること

## 1.
`ViszAGI/` ディレクトリを作る

## 2.
このMDのコードを対応ファイルに貼る

## 3.
`pip install -r requirements.txt`

## 4.
`.env` の `DISCORD_TOKEN` と `VISZ_BRIDGE_COMMAND` を埋める

## 5.
`python main.py` で起動する

---

# いちばん大事なルール

以下だけ守れば、かなり汚れにくい。

- `ViszAGI` 本体は `Visz-Coding` を import しない
- `Visz-Coding` 呼び出しは `bridges/visz_coding_bridge.py` だけ
- 受け渡しは JSON のみ
- パスは絶対パス
- timeout を必ず入れる

---

# 最短要約

**あなたが今すぐ作るべきなのは、Discord bot 本体 + `bridges/visz_coding_bridge.py` + Visz-Coding entrypoint の3点だけ。**
