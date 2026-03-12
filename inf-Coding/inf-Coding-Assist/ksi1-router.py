#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')

from katala_samurai.katala_quantum_03a import Katala_Quantum_03a, KQ03a
from katala_samurai.inf_bridge import (
    run_inf_bridge,
    make_ephemeral_audit_file,
    append_ephemeral_audit,
    cleanup_ephemeral_audit,
    make_ephemeral_goal_history_file,
    append_goal_event,
    cleanup_goal_history,
    purge_stale_ephemeral_audit,
    purge_stale_goal_history,
)
from katala_samurai.inf_coding_adapter import emit_router_event
from katala_samurai.inf_brain_layer import run_inf_brain_layer
from katala_samurai.inf_brain_layer_policy import sanitize_inf_brain_output, validate_inf_brain_output
from katala_samurai.kq_input_layer import build_kq_input_packet

try:
    from katala_samurai.kq_symbolic_bridge import (
        eval_symbolic,
        solve_smt_optional,
        solve_sat_lite,
        solve_math_logic_unified,
    )
    _HAS_KQ_FORMAL = True
except Exception:
    _HAS_KQ_FORMAL = False

RISK_PATTERNS = [
    r"\brm\b", r"--force", r"\bdel\b", r"\bdrop\b", r"\btruncate\b",
    r"\bpush\b", r"\brebase\b", r"\breset\b", r"\bcherry-pick\b",
    r"\bcurl\b", r"\bwget\b", r"\bssh\b", r"\bscp\b",
]

SAFE_FAST_PATTERNS = [
    r"^git status(\s|$)",
    r"^git diff(\s|$)",
    r"^git log(\s|$)",
    r"^ls(\s|$)",
    r"^pwd$",
    r"^cat(\s|$)",
    r"^grep(\s|$)",
    r"^find(\s|$)",
    r"^python3 -m py_compile(\s|$)",
    r"^npm run -s (test|build)(\s|$)",
]

STRICT_ONLY_PATTERNS = [
    r"^git (push|rebase|reset|cherry-pick|tag|branch -D)(\s|$)",
    r"^docker(\s|$)",
    r"^kubectl(\s|$)",
]

UPSTREAM_MUTATION_PATTERNS = [
    r"\bgit\s+(commit|push|rebase|reset|cherry-pick|merge|apply)\b",
    r"\b(cat|tee|sed|perl|python3?)\b.*(>|>>|write|save|dump)",
    r"\bmv\b", r"\bcp\b", r"\brm\b", r"\btruncate\b",
]

UPSTREAM_PROTECTED_HINTS = [
    "inf-coding",
    "inf_bridge.py",
    "inf-bridge",
    "kq_",
    "kq/",
    "kq ",
]

KATALA_THOUGHT_PREFIX = "[Katala思考済]"


def _approval_skip_enabled() -> bool:
    v = os.getenv("INF_SKIP_APPROVALS", "1").strip().lower()
    return v in {"1", "true", "yes", "on"}



def _matches(patterns: list[str], command: str) -> bool:
    return any(re.search(p, command, re.IGNORECASE) for p in patterns)


def _requires_upstream_mutation_approval(command: str) -> bool:
    c = (command or "").lower()
    mutating = _matches(UPSTREAM_MUTATION_PATTERNS, c)
    touches_upstream = any(h in c for h in UPSTREAM_PROTECTED_HINTS)
    return bool(mutating and touches_upstream)


def _has_upstream_mutation_approval() -> bool:
    if _approval_skip_enabled():
        return True
    approved = os.getenv("INF_UPSTREAM_MUTATION_APPROVED", "0").strip().lower() in {"1", "true", "yes", "on"}
    note = os.getenv("INF_UPSTREAM_MUTATION_NOTE", "").strip()
    return bool(approved and note)


def ensure_katala_thought_prefix(text: str | None) -> str:
    s = (text or "").strip()
    if not s:
        return KATALA_THOUGHT_PREFIX
    if s.startswith(KATALA_THOUGHT_PREFIX):
        return s
    return f"{KATALA_THOUGHT_PREFIX} {s}"


def _select_model(command: str):
    """KL-only policy: treat the default route as Katala_Labyrinth_001.

    Internal compatibility keeps the current KQ03a implementation alive until the
    lower layers are fully renamed.
    """
    kq_only = os.getenv("KQ_ONLY", "1").strip().lower()
    if kq_only in {"1", "true", "yes", "on"}:
        return KQ03a()

    # compatibility path (when KQ_ONLY=0): allow explicit KS47 only
    requested = os.getenv("KSI_MODEL", "").strip().lower()
    c = command.lower()
    if requested in {"ks47"} or "ks47" in c:
        return "KS47"
    return KQ03a()


def _formal_probe(command: str, bridge: dict | None = None) -> dict:
    """Run formal probe so inf-Bridge routes with heuristic+formal evidence."""
    if not _HAS_KQ_FORMAL:
        return {"enabled": False, "reason": "kq_formal_bridge_unavailable"}

    s = (command or "").strip()
    low = s.lower()

    # Standard operation: run unified math+logic coverage first.
    unified = solve_math_logic_unified(s)
    if isinstance(unified, dict):
        unified.setdefault('kq_access_gate', {
            'granted': True,
            'source': 'kq',
            'path': 'inf-coding->inf-bridge->kl->inf-brain',
        })
        if isinstance(bridge, dict):
            kref = bridge.get('katala_grand_unification_reference')
            if isinstance(kref, dict):
                unified['katala_grand_unification_reference'] = kref
            actl = bridge.get('observation_assimilation_control')
            if isinstance(actl, dict):
                unified['observation_assimilation_control'] = actl
    inf_brain_raw = run_inf_brain_layer(s, unified)
    inf_brain = sanitize_inf_brain_output(inf_brain_raw)
    inf_brain_validation = validate_inf_brain_output(inf_brain)

    # Keep explicit kind for routing compatibility.
    if any(k in low for k in ["vars:", "formula:", " in [", "==", ">=", "<="]):
        r = solve_smt_optional(s)
        return {"enabled": True, "kind": "smt", "result": r, "unified": unified, "inf_brain": inf_brain, "inf_brain_validation": inf_brain_validation}
    if any(k in low for k in ["cnf:", "clause:", "sat(", "unsat", " or ", " and "]):
        r = solve_sat_lite(s)
        return {"enabled": True, "kind": "sat", "result": r, "unified": unified, "inf_brain": inf_brain, "inf_brain_validation": inf_brain_validation}

    primary = ((unified.get("primary") or {}).get("result") if isinstance(unified, dict) else None)
    if isinstance(primary, dict):
        return {
            "enabled": True,
            "kind": ((unified.get("primary") or {}).get("solver") or "unified"),
            "result": primary,
            "unified": unified,
            "inf_brain": inf_brain,
            "inf_brain_validation": inf_brain_validation,
        }

    r = eval_symbolic(s)
    return {"enabled": True, "kind": "symbolic", "result": r, "unified": unified, "inf_brain": inf_brain, "inf_brain_validation": inf_brain_validation}


def decide_route(command: str, input_packet: dict | None = None) -> tuple[str, dict]:
    pre_kq_command = ((input_packet or {}).get("normalized_input") if isinstance(input_packet, dict) else None) or command
    bridge = run_inf_bridge(pre_kq_command)
    bridge_plan = bridge.get("plan") or {}
    normalized_command = (bridge.get("input") or {}).get("normalized") or command
    cbind = (bridge.get("context_binding") or {})
    formal = _formal_probe(normalized_command, bridge)

    # inf-Bridge caution gate (before KQ, no hard reject policy)
    if cbind.get("verdict") in {"caution"}:
        route = "strict"
        detail = {
            "route": route,
            "reason": f"inf_bridge_{cbind.get('verdict')}",
            "confidence": 0.25,
            "risky_pattern": True,
            "strict_only_pattern": True,
            "safe_fast_pattern": False,
            "verdict": cbind.get("verdict", "UNKNOWN").upper(),
            "mode": "inf-bridge-pre-gate",
            "model": "inf-bridge",
            "alias": "inf-bridge",
            "series": "[inf-Bridge]",
            "inf_bridge": bridge,
            "formal_probe": formal,
        }
        emit_router_event(detail["model"], {
            "alias": detail["alias"],
            "command": normalized_command,
            **detail,
        })
        return route, detail

    model = _select_model(normalized_command)
    claim = (
        "Route this command for efficiency+safety in inf-Coding.\n"
        f"command: {normalized_command}\n"
        "Use fast-path for low-risk local read/build checks; strict-path for destructive/network/history-rewriting ops."
        f"\ninf_bridge_meta: temporal={cbind.get('temporal_tag')} purpose={cbind.get('purpose_score')}"
    )

    if model == "KS47":
        bridge = subprocess.run(
            [
                "python3",
                "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/ks-bridge.py",
                "--model", "KS47",
                "--query", claim,
                "--report", command,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if bridge.returncode != 0:
            raise RuntimeError(f"KS47 bridge failed: {bridge.stderr.strip()}")
        result = json.loads((bridge.stdout or "{}").strip())
        model_status = {
            "model": "KS47",
            "alias": "KS47",
            "series": "[KS] explicit-only",
        }
    else:
        result = model.verify(claim, fast=True)
        model_status = model.bridge_status() if hasattr(model, 'bridge_status') else {}

    verdict = result.get('verdict') if isinstance(result, dict) else 'UNKNOWN'
    mode = result.get('mode') if isinstance(result, dict) else 'unknown'
    conf = float(result.get('confidence', 0.5)) if isinstance(result, dict) else 0.5

    risky = _matches(RISK_PATTERNS, normalized_command)
    strict_only = _matches(STRICT_ONLY_PATTERNS, normalized_command)
    safe_fast = _matches(SAFE_FAST_PATTERNS, normalized_command)

    # Model suggested route has priority when provided
    model_route = result.get('route') if isinstance(result, dict) else None

    bridge_hint = bridge_plan.get('route_hint')

    if model_route in {'fast', 'strict'}:
        route = model_route
        reason = 'model_quantum_route' if 'quantum' in str(mode) else 'model_route'
    elif strict_only:
        route = 'strict'
        reason = 'strict_only_pattern'
    elif risky:
        if safe_fast and conf >= 0.85 and verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'risky_but_high_conf_safe_fast'
        else:
            route = 'strict'
            reason = 'risky_pattern'
    elif safe_fast:
        if conf >= 0.5 or verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'safe_fast_pattern'
        else:
            route = 'strict'
            reason = 'safe_fast_low_conf'
    else:
        if conf >= 0.72 and verdict in {'SUPPORT', 'LEAN_SUPPORT'}:
            route = 'fast'
            reason = 'generic_high_conf'
        else:
            route = 'strict'
            reason = 'generic_default_strict'

    # Formal probe can tighten route when logical checks fail/inconclusive on risky operators
    f_res = ((formal.get('result') or {}) if isinstance(formal, dict) else {})
    f_ok = bool(f_res.get('ok')) if isinstance(f_res, dict) else False
    f_status = str(f_res.get('proof_status', '')) if isinstance(f_res, dict) else ''
    if formal.get('enabled') and (not f_ok or f_status in {'failed', 'inconclusive', 'undecidable'}):
        if route != 'strict':
            route = 'strict'
            reason = 'formal_probe_requires_strict'

    inf_brain_validation = (formal.get('inf_brain_validation') or {}) if isinstance(formal, dict) else {}
    if inf_brain_validation and not bool(inf_brain_validation.get('ok', True)):
        route = 'strict'
        reason = 'inf_brain_schema_violation'

    # inf-Bridge plan hint has final safety priority
    if bridge_hint == 'strict' and route != 'strict':
        route = 'strict'
        reason = 'inf_bridge_plan_strict'

    detail = {
        'route': route,
        'reason': reason,
        'inf_coding_passed': True,
        'kq_input_layer': input_packet,
        'confidence': conf,
        'risky_pattern': risky,
        'strict_only_pattern': strict_only,
        'safe_fast_pattern': safe_fast,
        'verdict': verdict,
        'mode': mode,
        'model': model_status.get('model', type(model).__name__),
        'alias': model_status.get('alias', 'unknown'),
        'series': model_status.get('series'),
        'inf_bridge': bridge,
        'formal_probe': formal,
        'route_ab_evaluation': (bridge.get('route_ab_evaluation') if isinstance(bridge, dict) else None),
    }
    emit_router_event(detail['model'], {
        'alias': detail['alias'],
        'command': normalized_command,
        **detail,
    })
    return route, detail


def _is_under(path: str, roots: list[str]) -> bool:
    rp = os.path.realpath(path)
    for r in roots:
        rr = os.path.realpath(r)
        if rp == rr or rp.startswith(rr + os.sep):
            return True
    return False


def _post_response_cleanup() -> None:
    """
    KQ-and-before strict cache hygiene:
    - remove cache artifacts after each completed run
    - never auto-delete inf-Brain persistent area unless user explicitly asks
    """
    inf_root = '/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding'

    # Protected persistent zones (inf-Brain/inf-Memory side)
    protected_roots = [
        os.path.join(inf_root, 'inf-memory-store'),
    ]

    # Targeted cache dirs
    cleanup_targets = [
        os.path.join(inf_root, 'inf-Coding-cache'),
        os.path.join(inf_root, 'inf-Coding-run', '.tmp-openalex-cache'),
        os.path.join(inf_root, '.pytest_cache'),
        os.path.join(inf_root, '.mypy_cache'),
        os.path.join(inf_root, '.ruff_cache'),
        os.path.join(inf_root, '.cache'),
    ]

    for t in cleanup_targets:
        try:
            if os.path.isdir(t) and not _is_under(t, protected_roots):
                shutil.rmtree(t, ignore_errors=True)
        except Exception:
            pass

    # Recursive __pycache__ cleanup across KQ-before workspace trees
    scan_roots = [
        os.path.join('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala', 'src'),
        os.path.join(inf_root, 'inf-Coding-Assist'),
        os.path.join(inf_root, 'inf-Coding-run'),
        os.path.join(inf_root, 'katala-writable', 'src'),
    ]
    for root in scan_roots:
        if not os.path.isdir(root):
            continue
        for cur, dirs, _files in os.walk(root, topdown=True):
            # never descend into protected inf-Brain persistent roots
            dirs[:] = [d for d in dirs if not _is_under(os.path.join(cur, d), protected_roots)]
            for d in list(dirs):
                if d == '__pycache__':
                    p = os.path.join(cur, d)
                    try:
                        if not _is_under(p, protected_roots):
                            shutil.rmtree(p, ignore_errors=True)
                    except Exception:
                        pass


def _kq_mandatory_gate_enabled() -> bool:
    v = os.getenv("KQ_MANDATORY_GATE", "1").strip().lower()
    return v in {"1", "true", "yes", "on"}


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: ksi1-router.py <command...>', file=sys.stderr)
        return 64

    # proactive stale cleanup from prior abnormal terminations
    purge_stale_ephemeral_audit(max_age_sec=600.0)
    purge_stale_goal_history(max_age_sec=600.0)

    audit_path = make_ephemeral_audit_file()
    goal_history_path = make_ephemeral_goal_history_file()
    try:
        command = ' '.join(sys.argv[1:])
        input_packet = build_kq_input_packet(command).to_dict()
        append_ephemeral_audit(audit_path, {"event": "start", "command": command, "kq_input_layer": input_packet})
        append_goal_event(goal_history_path, {"event": "goal_set", "goal": command, "kq_input_layer": input_packet})

        if _kq_mandatory_gate_enabled() and not input_packet:
            blocked = {
                'blocked': True,
                'reason': 'kq_mandatory_gate_missing_input_packet',
            }
            print(json.dumps(blocked, ensure_ascii=False))
            append_ephemeral_audit(audit_path, {"event": "blocked", **blocked})
            append_goal_event(goal_history_path, {"event": "goal_blocked", **blocked})
            return 74

        route, detail = decide_route(command, input_packet=input_packet)
        if input_packet.get('violations'):
            if _kq_mandatory_gate_enabled():
                blocked = {
                    'blocked': True,
                    'reason': 'kq_mandatory_gate_input_violation',
                    'violations': input_packet.get('violations') or [],
                }
                print(json.dumps(blocked, ensure_ascii=False))
                append_ephemeral_audit(audit_path, {"event": "blocked", **blocked})
                append_goal_event(goal_history_path, {"event": "goal_blocked", **blocked})
                return 74
            route = 'strict'
            detail['route'] = 'strict'
            detail['reason'] = 'kq_input_layer_violation'

        print(json.dumps({'command': command, **detail}, ensure_ascii=False))
        append_ephemeral_audit(audit_path, {
            "event": "routed",
            "route": route,
            "reason": detail.get('reason'),
            "model": detail.get('model'),
            "verdict": detail.get('verdict'),
        })
        append_goal_event(goal_history_path, {
            "event": "goal_route",
            "route": route,
            "reason": detail.get('reason'),
            "model": detail.get('model'),
        })

        env = os.environ.copy()
        env['KSI1_ROUTE'] = route
        env['KSI_MODEL_ACTIVE'] = detail.get('model', '')
        env['INF_BRIDGE_TRUST'] = (((detail.get('inf_bridge') or {}).get('input') or {}).get('source_trust') or 'untrusted')
        env['INF_CODING_PASSED'] = '1'
        env['INF_SKIP_APPROVALS'] = '1' if _approval_skip_enabled() else '0'
        if route == 'strict' and (detail.get('model') or '').upper() != 'KS47':
            env['INF_CODING_DISPLAY_PREFIX'] = KATALA_THOUGHT_PREFIX
            env['KL_PASSED'] = '1'
        else:
            env.pop('INF_CODING_DISPLAY_PREFIX', None)
            env['KL_PASSED'] = '0'
        env['KQ_MANDATORY_GATE_ACTIVE'] = '1' if _kq_mandatory_gate_enabled() else '0'
        env['KQ_INPUT_PACKET_JSON'] = json.dumps(input_packet, ensure_ascii=False)

        if _requires_upstream_mutation_approval(command) and not _has_upstream_mutation_approval():
            blocked = {
                'blocked': True,
                'reason': 'upstream_mutation_requires_user_confirmation',
                'required_env': {
                    'INF_UPSTREAM_MUTATION_APPROVED': '1',
                    'INF_UPSTREAM_MUTATION_NOTE': '<user-confirmation-text>',
                },
            }
            print(json.dumps(blocked, ensure_ascii=False))
            append_ephemeral_audit(audit_path, {"event": "blocked", **blocked})
            append_goal_event(goal_history_path, {"event": "goal_blocked", **blocked})
            return 73

        rc = subprocess.call(sys.argv[1:], cwd='/mnt/c/Users/ogosh/Documents/NICOLAS/Katala', env=env)
        append_ephemeral_audit(audit_path, {"event": "completed", "rc": rc})
        append_goal_event(goal_history_path, {"event": "goal_complete", "rc": rc})
        return rc
    finally:
        # cache-only audit/history: always remove at task completion
        cleanup_ephemeral_audit(audit_path)
        cleanup_goal_history(goal_history_path)
        # strict zero-residual policy: purge any stale audit/history artifacts immediately
        purge_stale_ephemeral_audit(max_age_sec=0.0)
        purge_stale_goal_history(max_age_sec=0.0)
        _post_response_cleanup()


if __name__ == '__main__':
    raise SystemExit(main())
