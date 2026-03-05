from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import dataclass
from typing import Any

PATTERN_DETECTORS: dict[str, list[str]] = {
    "destructive_ops": [r"\brm\b", r"\bdrop\b", r"\btruncate\b", r"\breset\b"],
    "history_ops": [r"\brebase\b", r"\bcherry-pick\b", r"\bpush\b", r"\btag\b"],
    "network_ops": [r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b"],
    "safe_read_ops": [r"^git status(\s|$)", r"^git diff(\s|$)", r"^ls(\s|$)", r"^cat(\s|$)"],
}


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


def detect_patterns(text: str) -> dict[str, Any]:
    low = (text or "").strip()
    hits: dict[str, list[str]] = {}
    for group, pats in PATTERN_DETECTORS.items():
        matched = [p for p in pats if re.search(p, low, re.I)]
        if matched:
            hits[group] = matched

    risk_score = 0.0
    if "destructive_ops" in hits:
        risk_score += 0.55
    if "history_ops" in hits:
        risk_score += 0.40
    if "network_ops" in hits:
        risk_score += 0.20
    if "safe_read_ops" in hits and len(hits) == 1:
        risk_score = max(0.0, risk_score - 0.25)

    return {
        "groups": list(hits.keys()),
        "matches": hits,
        "risk_score": round(min(1.0, risk_score), 3),
    }


def plan_step(payload: dict[str, Any]) -> dict[str, Any]:
    text = ((payload.get("kq_payload") or {}).get("text") or "").strip()
    pat = detect_patterns(text)
    risk_score = float(pat.get("risk_score", 0.0))
    return {
        "kind": "plan",
        "route_hint": "strict" if risk_score >= 0.35 else "fast",
        "risk_level": "high" if risk_score >= 0.6 else ("medium" if risk_score >= 0.35 else "normal"),
        "trusted": False,
        "pattern_detection": pat,
    }


def external_signals(payload: dict[str, Any]) -> dict[str, Any]:
    txt = ((payload.get("kq_payload") or {}).get("text") or "").lower()
    signal_hits = {
        "deadline_signal": any(k in txt for k in ["today", "今日", "urgent", "至急", "締切"]),
        "research_signal": any(k in txt for k in ["paper", "doi", "査読", "論文"]),
        "security_signal": any(k in txt for k in ["security", "権限", "token", "鍵", "安全"]),
    }
    strength = sum(1 for v in signal_hits.values() if v)
    goal_hint = "stability"
    if signal_hits["security_signal"]:
        goal_hint = "risk-reduction"
    elif signal_hits["research_signal"]:
        goal_hint = "evidence-strengthening"
    elif signal_hits["deadline_signal"]:
        goal_hint = "delivery-priority"
    return {
        "strength": strength,
        "signals": signal_hits,
        "goal_hint": goal_hint,
    }


def adversarial_pretest(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    txt = ((payload.get("kq_payload") or {}).get("text") or "")
    contradictory = bool(re.search(r"(?i)(always|絶対).*(except|ただし|but)", txt))
    injection_like = bool(re.search(r"(?i)(ignore previous|system prompt|bypass)", txt))
    pat_risk = float(((plan.get("pattern_detection") or {}).get("risk_score", 0.0) or 0.0))
    risk = min(1.0, pat_risk + (0.25 if contradictory else 0.0) + (0.35 if injection_like else 0.0))
    return {
        "enabled": True,
        "contradictory_claim": contradictory,
        "injection_like": injection_like,
        "risk_score": round(risk, 3),
        "route_hint": "strict" if risk >= 0.35 else plan.get("route_hint", "fast"),
    }


def hardware_batch_telemetry() -> dict[str, Any]:
    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1, load5, load15 = 0.0, 0.0, 0.0
    cpu_budget = float(os.getenv("KQ_CPU_BUDGET", "0.40"))
    gpu_budget = float(os.getenv("KQ_GPU_BUDGET", "0.40"))
    mode = "batch" if load1 > max(1.0, os.cpu_count() * cpu_budget * 0.8) else "interactive"
    return {
        "cpu_load": {"1m": round(load1, 3), "5m": round(load5, 3), "15m": round(load15, 3)},
        "budget": {"cpu": cpu_budget, "gpu": gpu_budget},
        "batch_mode": mode,
    }


def route_ab_evaluation(payload: dict[str, Any], plan: dict[str, Any], adv: dict[str, Any], hw: dict[str, Any]) -> dict[str, Any]:
    txt = ((payload.get("kq_payload") or {}).get("text") or "")
    length_factor = min(1.0, len(txt) / 900.0)
    adv_risk = float((adv or {}).get("risk_score", 0.0) or 0.0)
    pat_risk = float(((plan.get("pattern_detection") or {}).get("risk_score", 0.0) or 0.0))
    cpu_load = float(((hw.get("cpu_load") or {}).get("1m", 0.0) or 0.0))

    strict_safety = max(0.0, min(1.0, 0.58 + adv_risk * 0.30 + pat_risk * 0.25))
    fast_speed = max(0.0, min(1.0, 0.62 + (1.0 - length_factor) * 0.18 - min(0.25, cpu_load * 0.02)))
    fast_safety = max(0.0, min(1.0, 0.72 - adv_risk * 0.35 - pat_risk * 0.22))

    strict_utility = strict_safety * 0.72 + (1.0 - min(1.0, length_factor * 0.7)) * 0.28
    fast_utility = fast_safety * 0.55 + fast_speed * 0.45

    recommended = "strict" if strict_utility >= fast_utility else "fast"
    return {
        "enabled": True,
        "candidate_metrics": {
            "strict": {"safety": round(strict_safety, 4), "utility": round(strict_utility, 4)},
            "fast": {"safety": round(fast_safety, 4), "speed": round(fast_speed, 4), "utility": round(fast_utility, 4)},
        },
        "recommended": recommended,
        "selected": plan.get("route_hint", recommended),
        "divergence": round(abs(strict_utility - fast_utility), 4),
    }


def build_meta_visualization(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    c = payload.get("context_binding") or {}
    pd = plan.get("pattern_detection") or {}
    return {
        "summary": {
            "verdict": c.get("verdict"),
            "purpose_score": c.get("purpose_score"),
            "temporal_tag": c.get("temporal_tag"),
            "route_hint": plan.get("route_hint"),
            "risk_level": plan.get("risk_level"),
            "risk_score": pd.get("risk_score", 0.0),
            "pattern_groups": pd.get("groups", []),
            "source_trust": ((payload.get("input") or {}).get("source_trust") or "untrusted"),
        },
        "flow": [
            "collect:input",
            "normalize:command",
            "bind:context",
            "detect:patterns",
            "sense:external_signals",
            "pretest:adversarial",
            "observe:hardware_batch",
            "evaluate:route_ab",
            "plan:route_hint+goal_hint",
            "emit:kq_payload",
        ],
    }


def run_inf_bridge(command: str) -> dict[str, Any]:
    payload = build_inf_bridge_payload(command)
    plan = plan_step(payload)
    ext = external_signals(payload)
    adv = adversarial_pretest(payload, plan)
    hw = hardware_batch_telemetry()

    # external signals influence goal hint and may tighten route
    payload["external_signals"] = ext
    payload["adversarial_pretest"] = adv
    payload["hardware_batch_telemetry"] = hw

    plan["goal_hint"] = ext.get("goal_hint")
    plan["route_hint"] = adv.get("route_hint", plan.get("route_hint"))
    ab_eval = route_ab_evaluation(payload, plan, adv, hw)
    payload["route_ab_evaluation"] = ab_eval
    if ab_eval.get("recommended") == "strict":
        plan["route_hint"] = "strict"
    payload["plan"] = plan

    payload["goal_loop_state"] = {
        "phase": "goal_set",
        "current_goal": ext.get("goal_hint"),
        "next_goal": "pending_result_reflection",
    }

    payload["meta_visualization"] = build_meta_visualization(payload, plan)
    return payload


def purge_stale_goal_history(max_age_sec: float = 1800.0) -> dict[str, Any]:
    root = os.getenv(
        "INF_BRIDGE_GOAL_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-goal-history",
    )
    os.makedirs(root, exist_ok=True)
    now = time.time()
    removed = 0
    kept = 0
    for name in os.listdir(root):
        if not name.startswith("goal-history-") or not name.endswith(".jsonl"):
            continue
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
            if age >= max_age_sec:
                os.unlink(path)
                removed += 1
            else:
                kept += 1
        except Exception:
            kept += 1
    return {"root": root, "removed": removed, "kept": kept, "max_age_sec": max_age_sec}


def purge_stale_ephemeral_audit(max_age_sec: float = 1800.0) -> dict[str, Any]:
    root = os.getenv(
        "INF_BRIDGE_AUDIT_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-audit",
    )
    os.makedirs(root, exist_ok=True)
    now = time.time()
    removed = 0
    kept = 0
    for name in os.listdir(root):
        if not name.startswith("inf-bridge-") or not name.endswith(".ndjson"):
            continue
        path = os.path.join(root, name)
        try:
            age = now - os.path.getmtime(path)
            if age >= max_age_sec:
                os.unlink(path)
                removed += 1
            else:
                kept += 1
        except Exception:
            kept += 1
    return {"root": root, "removed": removed, "kept": kept, "max_age_sec": max_age_sec}


def make_ephemeral_goal_history_file() -> str:
    root = os.getenv(
        "INF_BRIDGE_GOAL_DIR",
        "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-goal-history",
    )
    os.makedirs(root, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix="goal-history-", suffix=".jsonl", dir=root)
    os.close(fd)
    return path


def append_goal_event(path: str, event: dict[str, Any]) -> None:
    rec = {"ts": time.time(), **event}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cleanup_goal_history(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


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
