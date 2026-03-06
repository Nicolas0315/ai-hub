from __future__ import annotations

import re
from dataclasses import dataclass, asdict


_PHYSICS_TERMS = [
    "重力", "光", "時空", "場", "ブラックホール", "ニュートリノ",
    "gravity", "light", "spacetime", "field", "black hole", "neutrino",
]


@dataclass
class KQInputPacket:
    original_input: str
    normalized_input: str
    constraints: dict
    violations: list[str]
    kq_prompt: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_text(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _extract_constraints(text: str) -> dict:
    low = text.lower()
    euclid_only = ("ユークリッド" in text and ("限定" in text or "内部" in text)) or ("euclid" in low and "only" in low)
    forbid_physics = ("物理" in text and ("禁止" in text or "混ぜない" in text)) or ("forbid physical" in low)
    axioms_only = ("公準" in text and ("のみ" in text or "候補" in text)) or ("axiom" in low and "only" in low)

    return {
        "euclid_only": bool(euclid_only),
        "forbid_physical_entities": bool(forbid_physics),
        "axiom_candidate_only": bool(axioms_only),
    }


def _find_violations(normalized: str, constraints: dict) -> list[str]:
    violations: list[str] = []
    if constraints.get("forbid_physical_entities"):
        low = normalized.lower()
        hits = [w for w in _PHYSICS_TERMS if w.lower() in low]
        if hits:
            violations.append(f"forbidden_physics_terms_detected:{','.join(sorted(set(hits)))}")
    return violations


def build_kq_input_packet(user_input: str) -> KQInputPacket:
    normalized = _normalize_text(user_input)
    constraints = _extract_constraints(normalized)
    violations = _find_violations(normalized, constraints)

    kq_prompt = (
        "[KQ_INPUT_LAYER]\n"
        f"normalized_input: {normalized}\n"
        f"constraints: {constraints}\n"
        f"violations: {violations}\n"
        "instruction: Apply constraints before any LLM-facing interpretation."
    )

    return KQInputPacket(
        original_input=user_input,
        normalized_input=normalized,
        constraints=constraints,
        violations=violations,
        kq_prompt=kq_prompt,
    )
