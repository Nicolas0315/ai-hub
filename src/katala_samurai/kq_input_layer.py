from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


_PHYSICS_TERMS = [
    "重力", "光", "時空", "場", "ブラックホール", "ニュートリノ",
    "gravity", "light", "spacetime", "field", "black hole", "neutrino",
]

_THEORY_TERMS = [
    "大統一理論", "単一モデル", "3層", "第1層", "第2層", "第3層", "連続次元",
    "katala gut", "grand unified theory", "single model", "continuous dimension", "iut",
]

_IMPLEMENTATION_TERMS = [
    "実装", "コード", "台帳", "保存", "source層", "program層", "model層", "inf-bridge", "kq",
    "implement", "code", "ledger", "storage", "source layer", "program layer", "model layer",
]


@dataclass
class KQInputPacket:
    original_input: str
    normalized_input: str
    constraints: dict
    classifications: dict
    violations: list[str]
    kq_prompt: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _has_any(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


def _extract_constraints(text: str) -> dict:
    low = text.lower()
    euclid_only = ("ユークリッド" in text and ("限定" in text or "内部" in text)) or ("euclid" in low and "only" in low)
    forbid_physics = (
        ("物理" in text and ("禁止" in text or "混ぜない" in text))
        or ("重力" in text and "混ぜない" in text)
        or ("forbid physical" in low)
    )
    axioms_only = ("公準" in text and ("のみ" in text or "候補" in text)) or ("axiom" in low and "only" in low)

    return {
        "euclid_only": bool(euclid_only),
        "forbid_physical_entities": bool(forbid_physics),
        "axiom_candidate_only": bool(axioms_only),
    }


def _classify_layer(text: str) -> str:
    if _has_any(text, ["公準", "定理", "証明", "幾何", "ユークリッド", "axiom", "theorem", "proof", "euclid"]):
        return "math"
    if _has_any(text, ["重力", "光", "時空", "量子", "ブラックホール", "gravity", "spacetime", "quantum"]):
        return "physics"
    if _has_any(text, ["実装", "コード", "commit", "push", "edit", "write", "script", "実行"]):
        return "implementation"
    if _has_any(text, ["運用", "監視", "ジョブ", "cron", "workflow", "policy"]):
        return "operations"
    return "meta_policy"


def _classify_mode(text: str) -> str:
    if _has_any(text, ["許可", "実装して", "やって", "go", "start", "実行"]):
        return "execution_approval"
    if _has_any(text, ["確定", "固定", "これで行く", "adopt"]):
        return "fixed_decision"
    if _has_any(text, ["保留", "待って", "pause", "hold"]):
        return "hold"
    if _has_any(text, ["提案", "案", "候補", "should", "recommend"]):
        return "proposal"
    return "question"


def _classify_rigor(text: str) -> str:
    if _has_any(text, ["厳密", "証明", "独立性判定", "形式", "strict", "formal proof", "independence"]):
        return "strict_proof_required"
    if _has_any(text, ["近似", "仮", "ざっくり", "approx", "rough"]):
        return "approximation_allowed"
    return "idea_stage"


def _classify_change_authority(text: str) -> str:
    if _has_any(text, ["削除", "消して", "reset", "drop", "force", "破壊", "destructive"]):
        return "destructive_with_confirmation"
    if _has_any(text, ["保存", "書いて", "編集", "実装", "commit", "push", "append"]):
        return "edit_allowed"
    return "read_only"


def _classify_output_format(text: str) -> str:
    if _has_any(text, ["json", "yaml"]):
        return "json"
    if _has_any(text, ["公準形式", "axiom form", "公理形式"]):
        return "axiom_form"
    if _has_any(text, ["箇条書き", "bullet", "list"]):
        return "bullets"
    if _has_any(text, ["実装", "task", "todo", "script"]):
        return "implementation_task"
    return "bullets"


def _extract_priority(text: str) -> str:
    if _has_any(text, ["最優先", "urgent", "immediately", "今すぐ", "最優先"]):
        return "high"
    if _has_any(text, ["後で", "later", "余裕"]):
        return "low"
    return "normal"


def _build_classifications(normalized: str, constraints: dict) -> dict:
    return {
        "layer_class": _classify_layer(normalized),
        "mode_class": _classify_mode(normalized),
        "constraint_class": {
            "scope_limits": {
                "euclid_only": bool(constraints.get("euclid_only")),
                "axiom_candidate_only": bool(constraints.get("axiom_candidate_only")),
            },
            "prohibitions": {
                "forbid_physical_entities": bool(constraints.get("forbid_physical_entities")),
            },
            "priority": _extract_priority(normalized),
        },
        "rigor_class": _classify_rigor(normalized),
        "change_authority_class": _classify_change_authority(normalized),
        "output_format_class": _classify_output_format(normalized),
    }


def _find_violations(normalized: str, constraints: dict, classifications: dict) -> list[str]:
    violations: list[str] = []
    if constraints.get("forbid_physical_entities"):
        low = normalized.lower()
        hits = [w for w in _PHYSICS_TERMS if w.lower() in low]
        if hits:
            violations.append(f"forbidden_physics_terms_detected:{','.join(sorted(set(hits)))}")

    if constraints.get("euclid_only") and classifications.get("layer_class") == "physics":
        violations.append("euclid_only_but_physics_layer_detected")

    return violations


def build_meaning_boundary(user_input: str) -> dict[str, Any]:
    normalized = _normalize_text(user_input)
    low = normalized.lower()

    theory_axis = _has_any(normalized, _THEORY_TERMS)
    implementation_axis = _has_any(normalized, _IMPLEMENTATION_TERMS)
    physics_axis = _has_any(normalized, _PHYSICS_TERMS)

    primary_goal = "general_dialogue"
    if ("大統一理論" in normalized) or ("grand unified theory" in low) or ("katala" in low and "gut" in low):
        primary_goal = "katala_gut_construction"
    elif theory_axis and implementation_axis:
        primary_goal = "theory_implementation_alignment"
    elif theory_axis:
        primary_goal = "theory_clarification"
    elif implementation_axis:
        primary_goal = "implementation_planning"

    origin_signal = []
    if ("ブラックホール" in normalized) or ("black hole" in low):
        origin_signal.append("bh_causality_gravity_tension")
    if ("連続次元" in normalized) or ("continuous dimension" in low):
        origin_signal.append("continuous_dimension")
    if ("重力" in normalized and "光" in normalized) or ("gravity" in low and "light" in low):
        origin_signal.append("gravity_speed_vs_light")

    conceptual_axis = []
    if theory_axis:
        conceptual_axis.append("theory_axis")
    if implementation_axis:
        conceptual_axis.append("implementation_axis")
    if physics_axis:
        conceptual_axis.append("physics_axis")

    preserve_terms = [term for term in ["大統一理論", "単一モデル", "連続次元", "IUT", "局所極限", "ユークリッド幾何学"] if term in normalized]
    anti_flatten_rules = [
        "do_not_flatten_theory_axis_into_implementation_axis",
        "do_not_reduce_model_to_storage_only",
        "preserve_user_core_terms",
    ]
    if primary_goal == "katala_gut_construction":
        anti_flatten_rules.append("do_not_downgrade_gut_to_bookkeeping")

    return {
        "version": "meaning-boundary-v1",
        "primary_goal": primary_goal,
        "origin_signal": origin_signal,
        "conceptual_axis": conceptual_axis,
        "non_goals": ["mere_bookkeeping"] if primary_goal == "katala_gut_construction" else [],
        "preserve_terms": preserve_terms,
        "anti_flatten_rules": anti_flatten_rules,
        "loop_policy": {
            "fixed_two_pass_required": True,
            "max_boundary_refinement_passes": 1,
        },
    }


def build_kq_input_packet(user_input: str) -> KQInputPacket:
    normalized = _normalize_text(user_input)
    constraints = _extract_constraints(normalized)
    classifications = _build_classifications(normalized, constraints)
    violations = _find_violations(normalized, constraints, classifications)
    meaning_boundary = build_meaning_boundary(user_input)

    kq_prompt = (
        "[KQ_INPUT_LAYER]\n"
        f"normalized_input: {normalized}\n"
        f"constraints: {constraints}\n"
        f"classifications: {classifications}\n"
        f"violations: {violations}\n"
        f"meaning_boundary: {meaning_boundary}\n"
        "instruction: Apply constraints/classifications before any LLM-facing interpretation."
    )

    return KQInputPacket(
        original_input=user_input,
        normalized_input=normalized,
        constraints=constraints,
        classifications=classifications,
        violations=violations,
        kq_prompt=kq_prompt,
    )
