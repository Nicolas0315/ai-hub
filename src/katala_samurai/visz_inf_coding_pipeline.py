from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .inf_bridge import run_inf_bridge

WORKSPACE_ROOT = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala")
INF_CODING_ROOT = WORKSPACE_ROOT / "inf-Coding"
TMP_ROOT = INF_CODING_ROOT / "inf-Coding-run" / ".tmp-visz-bridge"

ALLOWED_SURFACES = {"discord"}
ALLOWED_INTENTS = {"chat", "execute", "analyze", "route", "reject", "hold"}

MENTION_RE = re.compile(r"<@!?\d+>")
EXECUTE_PATTERNS = [
    r"\b(run|execute|implement|fix|build|create|patch|write code)\b",
    r"\b(実装|実行|修正|作って|書いて|進めて)\b",
]
ANALYZE_PATTERNS = [
    r"\b(analyze|review|inspect|explain|summarize|diagnose)\b",
    r"\b(解析|分析|確認|読んで|調べて|説明)\b",
]
ROUTE_PATTERNS = [
    r"\b(route|forward|handoff|delegate)\b",
    r"\b(ルート|振り分け|転送|委譲)\b",
]
REJECT_PATTERNS = [
    r"(?i)(ignore|bypass|disable).{0,24}(guard|safety|rule|approval)",
    r"(安全|ルール|承認).{0,12}(無視|回避|解除)",
]


class PhaseFailCloseError(RuntimeError):
    def __init__(self, code: str, message: str, *, audit: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.audit = audit or {}

    def to_error_payload(self) -> dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message": self.message,
            },
            "audit": self.audit,
        }


@dataclass
class DiscordEnvelope:
    message_id: str
    channel_id: str
    guild_id: str | None
    author_id: str
    content: str
    timestamp: str
    attachments: list[dict[str, Any]] = field(default_factory=list)
    reply_to_id: str | None = None
    author: dict[str, Any] = field(default_factory=dict)
    surface: str = "discord"
    message_type: str = "plain"


@dataclass
class InfCodingRequest:
    request_id: str
    source_surface: str
    must_enter_via_inf_coding: bool
    direct_downstream_forbidden: bool
    ephemeral: bool
    content: str
    workspace_root: str
    channel_id: str
    author_id: str
    message_id: str
    timestamp: str
    guild_id: str | None = None
    reply_to_id: str | None = None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    author: dict[str, Any] = field(default_factory=dict)
    temp_dir: str | None = None


@dataclass
class PipelineResult:
    ok: bool
    request: dict[str, Any] | None = None
    normalized_packet: dict[str, Any] | None = None
    engine_packet: dict[str, Any] | None = None
    reply: dict[str, Any] | None = None
    cleanup: dict[str, Any] | None = None
    audit: dict[str, Any] | None = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _short_reason(code: str) -> str:
    mapping = {
        "ENTRY_VIOLATION": "inf-Coding 経由の要求だけ受け付けます。",
        "INVALID_PACKET": "要求パケットが不正です。",
        "EMPTY_CONTENT": "空メッセージは処理できません。",
        "WORKSPACE_VIOLATION": "workspace 境界違反です。",
        "CLEANUP_RESERVATION_FAILED": "一時実行領域を確保できませんでした。",
        "DOWNSTREAM_FORBIDDEN": "直呼び要求は拒否しました。",
    }
    return mapping.get(code, "要求を安全側で拒否しました。")


def extract_discord_envelope(event: dict[str, Any]) -> DiscordEnvelope:
    content = str(event.get("content") or "")
    refs = event.get("message_reference") or {}
    author = event.get("author") or {}
    attachments = event.get("attachments") or []
    reply_to_id = event.get("reply_to_id") or refs.get("message_id")

    message_type = "plain"
    if reply_to_id:
        message_type = "reply"
    elif MENTION_RE.search(content):
        message_type = "mention"

    return DiscordEnvelope(
        message_id=str(event.get("id") or event.get("message_id") or ""),
        channel_id=str(event.get("channel_id") or ""),
        guild_id=str(event.get("guild_id")) if event.get("guild_id") is not None else None,
        author_id=str(author.get("id") or event.get("author_id") or ""),
        content=content,
        timestamp=str(event.get("timestamp") or ""),
        attachments=[_normalize_attachment(a) for a in attachments],
        reply_to_id=str(reply_to_id) if reply_to_id is not None else None,
        author={
            "id": str(author.get("id") or event.get("author_id") or ""),
            "username": author.get("username") or author.get("name"),
            "display_name": author.get("global_name") or author.get("display_name"),
            "bot": bool(author.get("bot", False)),
        },
        surface="discord",
        message_type=message_type,
    )


def create_inf_coding_request(event: dict[str, Any]) -> InfCodingRequest:
    env = extract_discord_envelope(event)
    intake_route = event.get("intake_route") or {}
    request = InfCodingRequest(
        request_id=f"discord-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}",
        source_surface="discord",
        must_enter_via_inf_coding=True,
        direct_downstream_forbidden=True,
        ephemeral=True,
        content=env.content,
        workspace_root=str(WORKSPACE_ROOT),
        channel_id=env.channel_id,
        author_id=env.author_id,
        message_id=env.message_id,
        timestamp=env.timestamp,
        guild_id=env.guild_id,
        reply_to_id=env.reply_to_id,
        attachments=env.attachments,
        author={**env.author, "intake_route": intake_route},
    )
    validate_request(request)
    request.temp_dir = reserve_ephemeral_tempdir(request.request_id)
    return request


def validate_request(request: InfCodingRequest) -> None:
    if request.source_surface not in ALLOWED_SURFACES:
        raise PhaseFailCloseError("INVALID_PACKET", "unsupported source surface")
    if not request.must_enter_via_inf_coding:
        raise PhaseFailCloseError("ENTRY_VIOLATION", _short_reason("ENTRY_VIOLATION"))
    if not request.direct_downstream_forbidden:
        raise PhaseFailCloseError("DOWNSTREAM_FORBIDDEN", _short_reason("DOWNSTREAM_FORBIDDEN"))
    if not request.ephemeral:
        raise PhaseFailCloseError("INVALID_PACKET", "ephemeral execution is mandatory")
    if not request.message_id or not request.channel_id or not request.author_id:
        raise PhaseFailCloseError("INVALID_PACKET", _short_reason("INVALID_PACKET"))
    if not isinstance(request.attachments, list):
        raise PhaseFailCloseError("INVALID_PACKET", "attachments must be a list")
    if not str(request.content or "").strip():
        raise PhaseFailCloseError("EMPTY_CONTENT", _short_reason("EMPTY_CONTENT"))
    ws = Path(request.workspace_root).resolve()
    if ws != WORKSPACE_ROOT.resolve():
        raise PhaseFailCloseError("WORKSPACE_VIOLATION", _short_reason("WORKSPACE_VIOLATION"))


def reserve_ephemeral_tempdir(request_id: str) -> str:
    try:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        return tempfile.mkdtemp(prefix=f"{request_id}-", dir=str(TMP_ROOT))
    except Exception as exc:
        raise PhaseFailCloseError(
            "CLEANUP_RESERVATION_FAILED",
            _short_reason("CLEANUP_RESERVATION_FAILED"),
            audit={"detail": str(exc)},
        ) from exc


def cleanup_ephemeral_tempdir(path: str | None) -> dict[str, Any]:
    if not path:
        return {"requested": False, "removed": False}
    target = Path(path)
    existed = target.exists()
    try:
        shutil.rmtree(target, ignore_errors=False)
        removed = not target.exists()
    except FileNotFoundError:
        removed = True
    except Exception as exc:
        return {"requested": True, "removed": False, "warning": str(exc), "path": path}
    return {"requested": True, "removed": removed, "existed": existed, "path": path}


def normalize_discord_request(request: InfCodingRequest) -> dict[str, Any]:
    cleaned = MENTION_RE.sub(" ", request.content)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    normalized_attachments = [_normalize_attachment(a) for a in request.attachments]
    normalized = {
        "content": {
            "raw": request.content,
            "clean": cleaned,
            "reply_context": _reply_context(request),
            "markdown_normalized": cleaned,
        },
        "speaker": {
            "surface": request.source_surface,
            "author_id": request.author_id,
            "username": request.author.get("username"),
            "display_name": request.author.get("display_name"),
            "bot": bool(request.author.get("bot", False)),
        },
        "context": {
            "surface": request.source_surface,
            "channel_id": request.channel_id,
            "guild_id": request.guild_id,
            "message_id": request.message_id,
            "reply_to_id": request.reply_to_id,
            "timestamp": request.timestamp,
            "attachments": normalized_attachments,
            "message_type": detect_message_type(request),
        },
    }
    return normalized


def classify_intent(normalized_packet: dict[str, Any]) -> str:
    text = ((normalized_packet.get("content") or {}).get("clean") or "").strip()
    if not text:
        return "reject"
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, text):
            return "reject"
    for pattern in ROUTE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "route"
    for pattern in EXECUTE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "execute"
    for pattern in ANALYZE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return "analyze"
    if len(text) <= 2:
        return "hold"
    return "chat"


def build_engine_packet(request: InfCodingRequest, normalized_packet: dict[str, Any], intent: str) -> dict[str, Any]:
    if intent not in ALLOWED_INTENTS:
        raise PhaseFailCloseError("INVALID_PACKET", "unsupported intent")
    history = []
    reply_to_id = normalized_packet["context"].get("reply_to_id")
    if reply_to_id:
        history.append({"kind": "reply_to", "message_id": reply_to_id})
    packet = {
        "schema": "engine_packet.v1",
        "request_id": request.request_id,
        "task_type": intent,
        "input_text": normalized_packet["content"]["clean"],
        "context": normalized_packet["context"],
        "artifacts": normalized_packet["context"]["attachments"],
        "history": history,
        "cleanup_policy": {
            "ephemeral": True,
            "temp_dir": request.temp_dir,
            "cleanup_on": ["success", "failure", "timeout", "kill", "interrupt"],
            "owner": "inf-Coding",
        },
        "constraints": {
            "must_enter_via_inf_coding": True,
            "direct_downstream_forbidden": True,
            "workspace_root": request.workspace_root,
        },
        "evidence": {
            "source_surface": request.source_surface,
            "message_id": request.message_id,
            "author_id": request.author_id,
            "intake_route": request.author.get("intake_route"),
        },
    }
    return packet


def build_reply_payload(engine_packet: dict[str, Any], bridge_payload: dict[str, Any]) -> dict[str, Any]:
    summary = (bridge_payload.get("meta_visualization") or {}).get("summary") or {}
    task_type = engine_packet.get("task_type")
    input_text = engine_packet.get("input_text") or ""
    reply_text = f"[{task_type}] {input_text}"
    if summary:
        reply_text = (
            f"[{task_type}] {input_text}\n"
            f"verdict={summary.get('verdict')} risk={summary.get('risk_level')}"
        )
    return {
        "surface": "discord",
        "channel_id": engine_packet["context"].get("channel_id"),
        "reply_to_id": engine_packet["context"].get("message_id"),
        "thread_reply_to": engine_packet["context"].get("reply_to_id"),
        "message": reply_text,
    }


def process_discord_event(event: dict[str, Any]) -> dict[str, Any]:
    request: InfCodingRequest | None = None
    result: dict[str, Any] | None = None
    try:
        request = create_inf_coding_request(event)
        normalized_packet = normalize_discord_request(request)
        intent = classify_intent(normalized_packet)
        if intent == "reject":
            raise PhaseFailCloseError("DOWNSTREAM_FORBIDDEN", _short_reason("DOWNSTREAM_FORBIDDEN"))
        if intent == "hold":
            result = PipelineResult(
                ok=True,
                request=asdict(request),
                normalized_packet=normalized_packet,
                engine_packet=build_engine_packet(request, normalized_packet, intent),
                reply={
                    "surface": "discord",
                    "channel_id": request.channel_id,
                    "reply_to_id": request.message_id,
                    "message": "要件が薄いので保留にした。もう少し具体化してくれ。",
                },
                cleanup=None,
                audit={"status": "held", "request_id": request.request_id},
            ).to_dict()
            return result

        engine_packet = build_engine_packet(request, normalized_packet, intent)
        bridge_payload = run_inf_bridge(engine_packet["input_text"])
        reply = build_reply_payload(engine_packet, bridge_payload)
        result = PipelineResult(
            ok=True,
            request=asdict(request),
            normalized_packet=normalized_packet,
            engine_packet=engine_packet,
            reply=reply,
            cleanup=None,
            audit={
                "status": "ok",
                "request_id": request.request_id,
                "intent": intent,
                "kept_meta_only": True,
            },
        ).to_dict()
        return result
    except PhaseFailCloseError as exc:
        audit = {
            "status": "rejected",
            "request_id": request.request_id if request else None,
            "error_code": exc.code,
            "error_summary": exc.message,
            **exc.audit,
        }
        result = PipelineResult(
            ok=False,
            request=asdict(request) if request else None,
            cleanup=None,
            audit=audit,
            error={"code": exc.code, "message": exc.message},
            reply={
                "surface": "discord",
                "channel_id": request.channel_id if request else str(event.get("channel_id") or ""),
                "reply_to_id": request.message_id if request else str(event.get("id") or event.get("message_id") or ""),
                "message": _short_reason(exc.code),
            },
        ).to_dict()
        return result
    finally:
        cleanup_report = cleanup_ephemeral_tempdir(request.temp_dir if request else None)
        if result is not None:
            result["cleanup"] = cleanup_report


def _normalize_attachment(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(attachment.get("id") or ""),
        "filename": attachment.get("filename"),
        "content_type": attachment.get("content_type"),
        "size": attachment.get("size"),
        "url": attachment.get("url"),
    }


def _reply_context(request: InfCodingRequest) -> dict[str, Any]:
    return {
        "reply_to_id": request.reply_to_id,
        "has_reply": bool(request.reply_to_id),
    }


def detect_message_type(request: InfCodingRequest) -> str:
    if request.reply_to_id:
        return "reply"
    if MENTION_RE.search(request.content):
        return "mention"
    return "plain"


def process_discord_event_json(raw_json: str) -> str:
    try:
        event = json.loads(raw_json)
    except Exception as exc:
        return json.dumps(
            PhaseFailCloseError("INVALID_PACKET", f"invalid JSON: {exc}").to_error_payload(),
            ensure_ascii=False,
        )
    return json.dumps(process_discord_event(event), ensure_ascii=False)
