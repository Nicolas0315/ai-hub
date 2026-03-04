from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class ContextBindingResult:
    verdict: str  # pass|caution (no hard reject policy)
    purpose_score: float
    identity_conflict: bool
    temporal_tag: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict,
            "purpose_score": self.purpose_score,
            "identity_conflict": self.identity_conflict,
            "temporal_tag": self.temporal_tag,
            "reason": self.reason,
        }


def _temporal_tag(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["tomorrow", "next", "予定", "明日", "来週"]):
        return "future"
    if any(k in t for k in ["yesterday", "last", "前", "昨日", "先週"]):
        return "past"
    if any(k in t for k in ["now", "today", "今", "現在", "本日"]):
        return "present"
    return "atemporal"


def _purpose_score(text: str) -> float:
    t = text.lower().strip()
    if len(t) < 3:
        return 0.1
    if re.fullmatch(r"(hi|hello|test|ping|ん|ほい|@+)", t):
        return 0.1
    if len(t) < 10:
        return 0.35
    return 0.72


def _identity_conflict(text: str) -> tuple[bool, str]:
    # KQ/inf-Coding context: reject explicit safety/rule disabling attempts
    patterns = [
        r"(?i)(ignore|無視).{0,20}(rules|ルール|安全)",
        r"(?i)(bypass|回避).{0,20}(safety|guard|order)",
    ]
    for p in patterns:
        if re.search(p, text):
            return True, "identity_conflict_pattern"
    return False, "ok"


def bind_input(text: str) -> ContextBindingResult:
    ps = _purpose_score(text)
    temporal = _temporal_tag(text)
    conflict, reason = _identity_conflict(text)

    if conflict:
        return ContextBindingResult("caution", ps, True, temporal, reason)
    if ps < 0.2:
        return ContextBindingResult("caution", ps, False, temporal, "low_purpose_score")
    return ContextBindingResult("pass", ps, False, temporal, "bound")


def build_inf_bridge_payload(command: str) -> dict[str, Any]:
    ts = time.time()
    clean = " ".join((command or "").split())
    binding = bind_input(clean)
    normalized = clean

    return {
        "bridge": "inf-bridge",
        "version": "v2",
        "timestamp": ts,
        "input": {
            "raw": command,
            "normalized": normalized,
            "length": len(normalized),
            "source_trust": "untrusted",
        },
        "context_binding": binding.to_dict(),
        "trace": {
            "layer": "inf-coding->inf-bridge->kq",
            "normalized": True,
            "routed": "pending",
        },
        "kq_payload": {
            "text": normalized,
            "meta": {
                "temporal_tag": binding.temporal_tag,
                "purpose_score": binding.purpose_score,
                "source_trust": "untrusted",
            },
        },
    }


def plan_step(payload: dict[str, Any]) -> dict[str, Any]:
    text = ((payload.get("kq_payload") or {}).get("text") or "").strip()
    risky = bool(re.search(r"\b(rm|drop|truncate|reset|rebase|push)\b", text, re.I))
    return {
        "kind": "plan",
        "route_hint": "strict" if risky else "fast",
        "risk_level": "high" if risky else "normal",
        "trusted": False,
    }


def make_ephemeral_audit_file() -> str:
    root = os.getenv(
        "INF_BRIDGE_AUDIT_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-audit",
    )
    os.makedirs(root, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="inf-bridge-", suffix=".ndjson", dir=root)
    os.close(fd)
    return path


def append_ephemeral_audit(path: str, event: dict[str, Any]) -> None:
    rec = {"ts": time.time(), **event}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cleanup_ephemeral_audit(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass
