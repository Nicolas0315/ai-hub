from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass(frozen=True)
class IUTFormalConcept:
    key: str
    aliases: tuple[str, ...]
    formal_role: str
    machine_template: str
    note: str


IUT_FORMAL_DICTIONARY: tuple[IUTFormalConcept, ...] = (
    IUTFormalConcept(
        key="hodge_theater",
        aliases=("hodge theater", "hodge-theater", "ホッジ劇場", "ホッジシアター"),
        formal_role="layered_object_space",
        machine_template="theater(T): layered_space(T) and base_coherent(T)",
        note="IUT I base layered framework",
    ),
    IUTFormalConcept(
        key="frobenioid",
        aliases=("frobenioid", "フロベニオイド"),
        formal_role="arithmetic_category",
        machine_template="frobenioid(F): arithmetic_category(F) and local_functorial(F)",
        note="Arithmetic categorical structure",
    ),
    IUTFormalConcept(
        key="log_theta_link",
        aliases=("log-theta", "log theta", "theta link", "log-theta link", "ログシータ"),
        formal_role="inter_layer_morphism",
        machine_template="theta_link(A,B): morphism(A,B) and invariant_preserving(A,B)",
        note="Inter-universal correspondence bridge",
    ),
    IUTFormalConcept(
        key="arakelov_evaluation",
        aliases=("hodge-arakelov", "arakelov", "アラケロフ", "hodge arakelov"),
        formal_role="evaluation_map",
        machine_template="arakelov_eval(E): evaluation_map(E) and bounded_distortion(E)",
        note="Evaluation/magnitude control layer",
    ),
    IUTFormalConcept(
        key="log_volume",
        aliases=("log-volume", "log volume", "ログ体積"),
        formal_role="invariant_measure",
        machine_template="log_volume(V): invariant_measure(V) and transfer_stable(V)",
        note="Invariant transfer/comparison quantity",
    ),
)


def normalize_iut_terms(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    low = t.lower()
    detected: list[str] = []
    replacements: list[dict[str, str]] = []
    normalized = t

    for c in IUT_FORMAL_DICTIONARY:
        hit = None
        for a in c.aliases:
            if a.lower() in low:
                hit = a
                break
        if hit is None:
            continue
        detected.append(c.key)
        normalized = re.sub(re.escape(hit), c.key, normalized, flags=re.I)
        replacements.append({"from": hit, "to": c.key})

    return {
        "input": t,
        "normalized_text": normalized,
        "detected_concepts": detected,
        "replacements": replacements,
        "concept_count": len(detected),
    }


def suggest_iut_interpretation(text: str) -> dict[str, Any]:
    # User policy: run this feature outside KQ only.
    return {
        "enabled": False,
        "reason": "moved-to-external-layer",
        "normalized": normalize_iut_terms(text),
        "suggestions": [],
        "style": "disabled-in-kq",
    }
