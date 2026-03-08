from __future__ import annotations

import json
import os
import sys
from typing import Any

SRC_ROOT = "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src"
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from katala_quantum.emulator_lite import QuantumCircuit
from katala_samurai.iut_core_subset_v1 import evaluate_iut_core_subset_v1
from katala_samurai.iut_formal_dictionary import normalize_iut_terms
from katala_samurai.iut_lemma_catalog import build_iut_lemma_catalog_v1, infer_catalog_dependencies
from katala_samurai.kq_symbolic_bridge import solve_math_logic_unified

try:
    from katala_samurai.htn_planner import HTNPlanner
    from katala_samurai.adaptive_planner import AdaptivePlanner
except Exception:
    HTNPlanner = None  # type: ignore[assignment]
    AdaptivePlanner = None  # type: ignore[assignment]

try:
    from katala_samurai.adversarial_verifier import run_adversarial_verification
except Exception:
    run_adversarial_verification = None  # type: ignore[assignment]

try:
    from katala_samurai.causal_verifier import run_causal_verification
except Exception:
    run_causal_verification = None  # type: ignore[assignment]

KQ3_STRICT_INVARIANT_THRESHOLD = 0.72
KS_APPROVAL_CONFIDENCE = 0.70
KCS_APPROVAL_CONSENSUS = 0.55
KQ_ALWAYS_ON = True

FORMAL_MARKERS = (
    "theorem", "proof", "lemma", "formal", "forall", "exists", "axiom",
    "定理", "証明", "補題", "形式", "公理", "iut", "lean", "coq", "isabelle",
)

CI_JOB_FILES = (
    ("deep-grammar-regression", "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/kq_deep_grammar_regression.py"),
    ("logic-math-benchmark", "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/kq_logic_math_benchmark.py"),
    ("iut-subset-check", "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/iut_subset_scaffold.py"),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _extract_unified(formal_probe: dict[str, Any] | None, command: str) -> dict[str, Any]:
    if isinstance(formal_probe, dict):
        unified = formal_probe.get("unified")
        if isinstance(unified, dict):
            return unified
    try:
        return solve_math_logic_unified(command)
    except Exception as exc:
        return {
            "ok": False,
            "proof_status": "unavailable",
            "solver": "math-logic-unified",
            "error": str(exc),
        }


def _extract_solver_result(unified: dict[str, Any], solver_name: str) -> dict[str, Any]:
    primary = unified.get("primary") or {}
    if isinstance(primary, dict) and primary.get("solver") == solver_name:
        return primary
    for row in unified.get("results") or []:
        if isinstance(row, dict) and row.get("solver") == solver_name:
            return row
    return {}


def _build_quantum_runtime_profile(command: str) -> dict[str, Any]:
    text = (command or "").strip()
    q = QuantumCircuit(3)
    q.h(0)
    q.rz(1, min(1.8, 0.2 + (len(text) % 9) * 0.15))
    if any(marker in text.lower() for marker in ("proof", "theorem", "lemma", "forall", "exists")):
        q.cx(0, 2)
    else:
        q.rx(2, 0.35 + (len(text.split()) % 5) * 0.1)
    measurements = q.measure_all().run(shots=96).measurements
    dominant_state, dominant_hits = max(measurements.items(), key=lambda item: item[1])
    return {
        "profile": "16GB-aware-runtime-profile",
        "budget_default": 0.60,
        "cpu_gpu_split": "CPU/GPU budget default 0.60",
        "quantum_hint_state": dominant_state,
        "quantum_hint_ratio": round(dominant_hits / 96.0, 4),
        "measurement_top3": [
            {"state": state, "hits": hits}
            for state, hits in sorted(measurements.items(), key=lambda item: item[1], reverse=True)[:3]
        ],
    }


def _derive_solver_weights(unified: dict[str, Any]) -> dict[str, float]:
    coverage = unified.get("coverage") or {}
    passed = set(coverage.get("passed") or [])
    failed = set(coverage.get("failed") or [])
    weights: dict[str, float] = {}
    for solver in sorted(passed | failed):
        weights[solver] = round(1.18 if solver in passed else 0.86, 4)
    return weights


def _top_weights(weights: dict[str, float], limit: int = 6) -> list[dict[str, Any]]:
    return [
        {"solver": name, "weight": weight}
        for name, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True)[:limit]
    ]


def _build_formal_probe_section(
    command: str,
    input_packet: dict[str, Any] | None,
    bridge_result: dict[str, Any] | None,
    formal_probe: dict[str, Any] | None,
) -> dict[str, Any]:
    unified = _extract_unified(formal_probe, command)
    coverage = unified.get("coverage") or {}
    invariants = unified.get("inter_universal_invariants") or {}
    smt = _extract_solver_result(unified, "smt")
    hol = _extract_solver_result(unified, "hol")
    primary = unified.get("primary") or {}

    return {
        "solve_math_logic_unified": unified,
        "coverage_report": {
            "total_solvers": coverage.get("total_solvers"),
            "passed_solvers": coverage.get("passed_solvers"),
            "pass_ratio": coverage.get("pass_ratio"),
            "passed": coverage.get("passed") or [],
            "failed": coverage.get("failed") or [],
        },
        "inter_universal_invariants": invariants,
        "solver_families": {
            "primary_solver": primary.get("solver"),
            "passed": coverage.get("passed") or [],
            "failed": coverage.get("failed") or [],
        },
        "smt_strategy_search": ((smt.get("result") or {}).get("proof_trace") or {}).get("strategy_search") or {
            "enabled": False,
            "reason": "smt-strategy-search-unavailable",
        },
        "hol_strategy_unification": ((hol.get("result") or {}).get("proof_trace") or {}).get("strategy_unification") or {
            "enabled": False,
            "reason": "hol-strategy-unification-unavailable",
        },
        "input_route": {
            "path": ["inf-coding", "inf-bridge", "kq", "inf-bridge", "kq", "katala"],
            "kq3_mode": (unified.get("kq3_mode") or {}).get("public_mode"),
            "input_packet_layer": ((input_packet or {}).get("classifications") or {}).get("layer_class"),
            "bridge_trust": (((bridge_result or {}).get("input") or {}).get("source_trust") or "untrusted"),
            "quantum_runtime_profile": _build_quantum_runtime_profile(command),
        },
    }


def _build_kq3_control(
    input_packet: dict[str, Any] | None,
    bridge_result: dict[str, Any] | None,
    formal_section: dict[str, Any],
) -> dict[str, Any]:
    unified = formal_section.get("solve_math_logic_unified") or {}
    invariants = formal_section.get("inter_universal_invariants") or {}
    coverage = formal_section.get("coverage_report") or {}
    base_mode = unified.get("kq3_mode") or {}
    proof_status = str(unified.get("proof_status", "")).lower()
    truth_invariant = (invariants.get("truth_invariant") or {})
    counterexample_invariant = (invariants.get("counterexample_invariant") or {})
    invariant_score = _safe_float(invariants.get("invariant_preservation_score"), 0.0)
    truth_conflict = bool(truth_invariant.get("conflict"))
    counterexample_inconsistent = not bool(counterexample_invariant.get("consistent", True))
    identity_conflict = bool(((bridge_result or {}).get("context_binding") or {}).get("identity_conflict"))
    strict_triggers = {
        "invariant_score_lt_0_72": invariant_score < KQ3_STRICT_INVARIANT_THRESHOLD,
        "truth_conflict": truth_conflict,
        "counterexample_inconsistency": counterexample_inconsistent,
        "identity_conflict": identity_conflict,
        "proof_status_requires_strict": proof_status in {"failed", "inconclusive", "undecidable", "unavailable"},
    }
    strict_activated = any(strict_triggers.values())
    return {
        "public_mode": base_mode.get("public_mode") or "balanced+strict",
        "stage": "strict" if strict_activated else (base_mode.get("stage") or "balanced"),
        "strict_activated": strict_activated,
        "strict_triggers": strict_triggers,
        "constraint_class": ((input_packet or {}).get("classifications") or {}).get("constraint_class") or {},
        "coverage_pass_ratio": coverage.get("pass_ratio"),
        "invariant_preservation_score": invariant_score,
    }


def _build_chain_result(command: str, plan: Any) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [{"text": f"goal {command}", "connector_type": "condition"}]
    dependency_edges: list[dict[str, Any]] = []
    ordered = list(getattr(plan, "execution_order", []) or [])
    tasks = getattr(plan, "tasks", {}) or {}
    for task_id in ordered[:6]:
        task = tasks.get(task_id)
        if not task:
            continue
        steps.append({"text": getattr(task, "name", task_id), "connector_type": "condition"})
        idx = len(steps) - 1
        dependency_edges.append({"from": max(0, idx - 1), "to": idx, "relation": "condition"})
    if len(steps) >= 3:
        dependency_edges.append({"from": 0, "to": len(steps) - 1, "relation": "conclusion"})
    return {"steps": steps, "dependency_edges": dependency_edges}


def _build_planner_vs_verifier(
    command: str,
    formal_section: dict[str, Any],
    kq3_control: dict[str, Any],
) -> dict[str, Any]:
    try:
        if HTNPlanner is None or AdaptivePlanner is None:
            raise RuntimeError("planner modules unavailable")
        htn_plan = HTNPlanner().plan(command)
        adaptive_plan = AdaptivePlanner().create_plan(command)
        chain_result = _build_chain_result(command, adaptive_plan)
        layer_results = {
            "formal_probe": {
                "verdict": "PASS" if bool((formal_section.get("solve_math_logic_unified") or {}).get("ok")) else "FAIL",
                "confidence": _safe_float((formal_section.get("solve_math_logic_unified") or {}).get("confidence"), 0.5),
            },
            "kq3_control": {
                "verdict": "STRICT" if kq3_control.get("strict_activated") else "BALANCED",
                "confidence": 0.85 if not kq3_control.get("strict_activated") else 0.52,
            },
        }
        if run_adversarial_verification is None:
            raise RuntimeError("adversarial verifier unavailable")
        adversarial = run_adversarial_verification(command, layer_results=layer_results)
        causal = run_causal_verification(chain_result) if run_causal_verification is not None else {
            "causal_verdict": "UNAVAILABLE",
            "causal_confidence": 0.0,
            "detail": "causal verifier unavailable",
        }
        plan_total = max(1, int(getattr(htn_plan, "total_tasks", 0) or 1))
        planner_score = min(1.0, 0.45 + min(plan_total, 8) * 0.06 + min(getattr(htn_plan, "max_depth", 0), 4) * 0.04)
        verifier_score = 0.55
        if adversarial.get("verdict") == "ADVERSARIAL_PASS":
            verifier_score += 0.20
        elif adversarial.get("verdict") == "ADVERSARIAL_FAIL":
            verifier_score -= 0.20
        verifier_score += _safe_float(causal.get("causal_confidence"), 0.5) * 0.20 - 0.10
        verifier_score = max(0.0, min(1.0, verifier_score))
        disagreement = round(abs(planner_score - verifier_score), 4)
        consensus_score = round(max(0.0, 1.0 - disagreement), 4)
        return {
            "planner": {
                "engine": "HTNPlanner+AdaptivePlanner",
                "candidate_count": plan_total,
                "max_depth": getattr(htn_plan, "max_depth", 0),
                "execution_order": list(getattr(htn_plan, "execution_order", []) or []),
                "novelty_score": round(planner_score, 4),
            },
            "verifier": {
                "adversarial": adversarial,
                "causal": causal,
                "machine_checked": causal.get("causal_verdict"),
                "human_support": adversarial.get("verdict"),
                "confidence": round(verifier_score, 4),
            },
            "dependent_eval": True,
            "disagreement": disagreement,
            "consensus_score": consensus_score,
            "plan_chain": chain_result,
        }
    except Exception as exc:
        return {
            "planner": {
                "engine": "HTNPlanner+AdaptivePlanner",
                "candidate_count": 0,
                "max_depth": 0,
                "execution_order": [],
                "novelty_score": 0.0,
            },
            "verifier": {
                "adversarial": {"verdict": "UNAVAILABLE", "error": str(exc)},
                "causal": {"causal_verdict": "UNAVAILABLE", "error": str(exc)},
                "machine_checked": "UNAVAILABLE",
                "human_support": "UNAVAILABLE",
                "confidence": 0.0,
            },
            "dependent_eval": False,
            "disagreement": 1.0,
            "consensus_score": 0.0,
            "plan_chain": {"steps": [], "dependency_edges": []},
        }


def _build_complementary_five_loops(
    command: str,
    formal_section: dict[str, Any],
    planner_vs_verifier: dict[str, Any],
    iut_payload: dict[str, Any],
    external_cross: dict[str, Any],
) -> dict[str, Any]:
    unified = formal_section.get("solve_math_logic_unified") or {}
    coverage = formal_section.get("coverage_report") or {}
    invariants = formal_section.get("inter_universal_invariants") or {}
    quantum_runtime = formal_section.get("input_route", {}).get("quantum_runtime_profile") or {}
    planner = planner_vs_verifier.get("planner") or {}
    verifier = planner_vs_verifier.get("verifier") or {}
    verifier_causal = verifier.get("causal") or {}
    solver_weights = _derive_solver_weights(unified)
    tokens = max(1, len((command or "").split()))
    base_score = _safe_float(invariants.get("invariant_preservation_score"), 0.0)
    active_solver_count = int(coverage.get("total_solvers") or len(solver_weights) or 0)
    existing = (unified.get("complementary_parallel_loops") or {}).get("trace") or []

    loop1_weights = dict(solver_weights)
    if "symbolic" in loop1_weights:
        loop1_weights["symbolic"] = round(loop1_weights["symbolic"] + 0.12, 4)
    loop1 = {
        "loop": 1,
        "name": "main-language",
        "purpose": "lang-sensitive solver activation",
        "status": "completed",
        "input_signal": {
            "token_count": tokens,
            "layer_class": formal_section.get("input_route", {}).get("input_packet_layer"),
            "bridge_trust": formal_section.get("input_route", {}).get("bridge_trust"),
        },
        "invariant_preservation_score": round(base_score, 4),
        "active_solver_count": active_solver_count,
        "top_weights": _top_weights(loop1_weights),
        "source_trace": existing[0] if len(existing) >= 1 else {},
    }

    loop2_weights = dict(loop1_weights)
    if "smt" in loop2_weights:
        loop2_weights["smt"] = round(loop2_weights["smt"] + 0.10, 4)
    if "hol" in loop2_weights:
        loop2_weights["hol"] = round(loop2_weights["hol"] + 0.08, 4)
    loop2 = {
        "loop": 2,
        "name": "main-paradigm",
        "purpose": "planner-informed paradigm rebalance",
        "status": "completed",
        "input_signal": {
            "candidate_count": planner.get("candidate_count"),
            "plan_depth": planner.get("max_depth"),
            "novelty_score": planner.get("novelty_score"),
        },
        "invariant_preservation_score": round(min(1.0, base_score + 0.02), 4),
        "active_solver_count": active_solver_count,
        "top_weights": _top_weights(loop2_weights),
        "source_trace": existing[1] if len(existing) >= 2 else {},
    }

    loop3_weights = dict(loop2_weights)
    if quantum_runtime.get("quantum_hint_ratio", 0.0) >= 0.2:
        loop3_weights["predicate"] = round(loop3_weights.get("predicate", 0.92) + 0.07, 4)
        loop3_weights["modal"] = round(loop3_weights.get("modal", 0.90) + 0.07, 4)
    loop3 = {
        "loop": 3,
        "name": "main-creative",
        "purpose": "quantum-runtime creative exploration",
        "status": "completed",
        "input_signal": quantum_runtime,
        "invariant_preservation_score": round(min(1.0, base_score + 0.03), 4),
        "active_solver_count": active_solver_count,
        "top_weights": _top_weights(loop3_weights),
        "source_trace": existing[2] if len(existing) >= 3 else {},
    }

    validation_score = round(_safe_float(planner_vs_verifier.get("consensus_score"), 0.0), 4)
    loop4 = {
        "loop": 4,
        "name": "validation",
        "purpose": "planner+verifier+cross validation",
        "status": "completed",
        "input_signal": {
            "consensus_score": validation_score,
            "machine_checked": verifier.get("machine_checked"),
            "human_support": verifier.get("human_support"),
            "causal_verdict": verifier_causal.get("causal_verdict"),
            "external_cross_enabled": external_cross.get("enabled"),
        },
        "validation_result": {
            "passed": validation_score >= KCS_APPROVAL_CONSENSUS,
            "disagreement": planner_vs_verifier.get("disagreement"),
            "cross_consistent_rows": external_cross.get("cross_consistent_rows"),
        },
        "top_weights": _top_weights(loop3_weights),
    }

    integrated_weights = dict(loop3_weights)
    if iut_payload.get("enabled"):
        integrated_weights["uf"] = round(integrated_weights.get("uf", 1.0) + 0.08, 4)
        integrated_weights["array"] = round(integrated_weights.get("array", 1.0) + 0.06, 4)
    integration_strength = round(
        min(
            1.0,
            (
                loop1["invariant_preservation_score"]
                + loop2["invariant_preservation_score"]
                + loop3["invariant_preservation_score"]
                + validation_score
            ) / 4.0,
        ),
        4,
    )
    loop5 = {
        "loop": 5,
        "name": "integration",
        "purpose": "domain-aware weight optimization",
        "status": "completed",
        "input_signal": {
            "iut_enabled": iut_payload.get("enabled"),
            "iut_pass_ratio": iut_payload.get("pass_ratio"),
            "integration_strength": integration_strength,
        },
        "weight_optimization": {
            "strategy": "domain-aware",
            "integrated_weights": _top_weights(integrated_weights, limit=8),
            "stability_score": integration_strength,
        },
    }

    loop_rows: list[dict[str, Any]] = [loop1, loop2, loop3, loop4, loop5]
    return {
        "enabled": True,
        "loop_count": 5,
        "completed_loops": 5,
        "always_on": KQ_ALWAYS_ON,
        "loops": loop_rows,
    }


def _should_run_iut(command: str, input_packet: dict[str, Any] | None) -> bool:
    low = (command or "").lower()
    if any(marker in low for marker in FORMAL_MARKERS):
        return True
    rigor = ((input_packet or {}).get("classifications") or {}).get("rigor_class")
    return rigor == "strict_proof_required"


def _build_iut_and_cross_verification(command: str, input_packet: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_terms = normalize_iut_terms(command)
    lemma_catalog = build_iut_lemma_catalog_v1()
    dependencies = infer_catalog_dependencies(command, lemma_catalog)
    if not _should_run_iut(command, input_packet):
        iut_payload = {
            "enabled": False,
            "reason": "non-formal-command",
            "normalized_terms": normalized_terms,
            "lemma_dependencies": dependencies,
        }
        external = {
            "enabled": False,
            "reason": "iut-core-not-enabled",
        }
        return iut_payload, external

    try:
        iut_result = evaluate_iut_core_subset_v1()
        cross_rows = [
            row.get("external_cross_verification") or {}
            for row in iut_result.get("results") or []
            if isinstance(row, dict) and row.get("external_cross_verification")
        ]
        cross_available = [row for row in cross_rows if row.get("enabled")]
        external_summary = {
            "enabled": bool(cross_rows),
            "available_rows": len(cross_available),
            "cross_consistent_rows": sum(1 for row in cross_available if row.get("cross_consistent", True)),
            "primary_ok_rows": sum(1 for row in cross_available if row.get("primary_ok", True)),
            "results": cross_rows[:6],
        }
        iut_payload = {
            "enabled": True,
            "normalized_terms": normalized_terms,
            "lemma_dependencies": dependencies,
            "subset": iut_result.get("subset"),
            "total": iut_result.get("total"),
            "passed": iut_result.get("passed"),
            "pass_ratio": iut_result.get("pass_ratio"),
            "layers": iut_result.get("layers"),
            "dependency_graph": iut_result.get("dependency_graph"),
            "optimization": iut_result.get("optimization"),
            "results_sample": (iut_result.get("results") or [])[:5],
        }
        return iut_payload, external_summary
    except Exception as exc:
        return (
            {
                "enabled": False,
                "reason": "iut-core-evaluation-failed",
                "error": str(exc),
                "normalized_terms": normalized_terms,
                "lemma_dependencies": dependencies,
            },
            {
                "enabled": False,
                "reason": "iut-core-evaluation-failed",
                "error": str(exc),
            },
        )


def _build_ci_validation() -> dict[str, Any]:
    jobs = []
    for name, path in CI_JOB_FILES:
        jobs.append({
            "name": name,
            "path": path,
            "present": os.path.exists(path),
            "mode": "always-on",
        })
    return {
        "enabled": True,
        "kq_always_on": KQ_ALWAYS_ON,
        "build_gated": all(job["present"] for job in jobs),
        "jobs": jobs,
    }


def _build_observability_outputs(
    formal_section: dict[str, Any],
    kq3_control: dict[str, Any],
    planner_vs_verifier: dict[str, Any],
    external_cross: dict[str, Any],
) -> dict[str, Any]:
    unified = formal_section.get("solve_math_logic_unified") or {}
    primary = unified.get("primary") or {}
    primary_result = primary.get("result") or {}
    invariants = formal_section.get("inter_universal_invariants") or {}
    return {
        "coverage": formal_section.get("coverage_report"),
        "invariants": invariants,
        "invariant_preservation_score": invariants.get("invariant_preservation_score"),
        "proof_trace_machine": primary_result.get("proof_trace"),
        "proof_trace_human": primary_result.get("proof_trace_human"),
        "planner_verifier_consensus": planner_vs_verifier.get("consensus_score"),
        "kq3_mode": kq3_control.get("public_mode"),
        "kq_always_on": KQ_ALWAYS_ON,
        "strict_triggers": kq3_control.get("strict_triggers"),
        "external_cross_summary": external_cross,
    }


def _build_final_artifacts(
    command: str,
    formal_section: dict[str, Any],
    kq3_control: dict[str, Any],
    planner_vs_verifier: dict[str, Any],
    five_loops: dict[str, Any],
    iut_payload: dict[str, Any],
    observability: dict[str, Any],
) -> dict[str, Any]:
    unified = formal_section.get("solve_math_logic_unified") or {}
    primary = unified.get("primary") or {}
    primary_result = primary.get("result") or {}
    dependency_graph = iut_payload.get("dependency_graph") or {}
    return {
        "primary_solver_result": {
            "solver": primary.get("solver"),
            "proof_status": primary.get("proof_status") or unified.get("proof_status"),
            "result": primary_result,
        },
        "coverage_report_per_solver_unit": formal_section.get("coverage_report"),
        "kq3_mode": kq3_control,
        "planner_verifier_consensus": {
            "consensus_score": planner_vs_verifier.get("consensus_score"),
            "disagreement": planner_vs_verifier.get("disagreement"),
        },
        "complementary_loop_deltas": five_loops,
        "iut_subset_evaluation": {
            "dependency_graph": dependency_graph,
            "verification_hooks": [row.get("verification_hooks") for row in iut_payload.get("results_sample") or [] if isinstance(row, dict)],
            "strict_escalation_reasons": [row.get("strict_escalation") for row in iut_payload.get("results_sample") or [] if isinstance(row, dict)],
        },
        "proof_certificate": primary_result.get("proof_certificate"),
        "audit_trace": {
            "command": command,
            "proof_trace_machine": observability.get("proof_trace_machine"),
        },
    }


def _build_mandatory_gate(
    formal_section: dict[str, Any],
    kq3_control: dict[str, Any],
    planner_vs_verifier: dict[str, Any],
    external_cross: dict[str, Any],
) -> dict[str, Any]:
    unified = formal_section.get("solve_math_logic_unified") or {}
    confidence = _safe_float(unified.get("confidence"), 0.5)
    ks_passed = bool(unified.get("ok")) and confidence >= KS_APPROVAL_CONFIDENCE or str(unified.get("proof_status", "")).lower() == "checked"
    consensus_score = _safe_float(planner_vs_verifier.get("consensus_score"), 0.0)
    cross_consistent = (
        not external_cross.get("enabled")
        or external_cross.get("cross_consistent_rows", 0) >= max(1, external_cross.get("available_rows", 0))
    )
    kcs_passed = consensus_score >= KCS_APPROVAL_CONSENSUS and cross_consistent
    approval = "pending-strict-review" if kq3_control.get("strict_activated") else "granted"
    return {
        "required": True,
        "always_on": KQ_ALWAYS_ON,
        "ks_passed": bool(ks_passed),
        "kcs_passed": bool(kcs_passed),
        "approval": approval,
        "passed": bool(ks_passed and kcs_passed),
        "details": {
            "confidence": round(confidence, 4),
            "consensus_score": round(consensus_score, 4),
            "cross_consistent": cross_consistent,
        },
    }


def run_solver_unit_pipeline(
    command: str,
    input_packet: dict[str, Any] | None = None,
    bridge_result: dict[str, Any] | None = None,
    formal_probe: dict[str, Any] | None = None,
) -> dict[str, Any]:
    formal_section = _build_formal_probe_section(command, input_packet, bridge_result, formal_probe)
    kq3_control = _build_kq3_control(input_packet, bridge_result, formal_section)
    planner_vs_verifier = _build_planner_vs_verifier(command, formal_section, kq3_control)
    iut_payload, external_cross = _build_iut_and_cross_verification(command, input_packet)
    five_loops = _build_complementary_five_loops(command, formal_section, planner_vs_verifier, iut_payload, external_cross)
    ci_validation = _build_ci_validation()
    observability = _build_observability_outputs(formal_section, kq3_control, planner_vs_verifier, external_cross)
    final_artifacts = _build_final_artifacts(
        command,
        formal_section,
        kq3_control,
        planner_vs_verifier,
        five_loops,
        iut_payload,
        observability,
    )
    mandatory_gate = _build_mandatory_gate(formal_section, kq3_control, planner_vs_verifier, external_cross)
    bundle = {
        "formal_probe": formal_section,
        "kq3_control": kq3_control,
        "planner_vs_verifier": planner_vs_verifier,
        "complementary_5_loops": five_loops,
        "iut_core_subset_v1": iut_payload,
        "external_cross_verification": external_cross,
        "ci_always_on_validation": ci_validation,
        "observability_outputs": observability,
        "final_artifacts": final_artifacts,
        "mandatory_gate": mandatory_gate,
    }
    bundle["json"] = json.dumps(bundle, ensure_ascii=False)
    return bundle
