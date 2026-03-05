from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass(frozen=True)
class IUTLemmaCatalogEntry:
    lemma_id: str
    paper: str
    section: str
    title: str
    premise: str
    conclusion: str
    dependency_ids: tuple[str, ...] = ()


def build_iut_lemma_catalog_v1() -> list[IUTLemmaCatalogEntry]:
    """IUT I-IV lemma catalog scaffold (ID/premise/conclusion/dependency).

    Note: this is a structured cataloging layer for incremental formalization,
    not a claim of full theorem-prover-level transcription.
    """
    return [
        IUTLemmaCatalogEntry("I-L1-001", "IUT I", "§1", "Base theater coherence", "Given base layered object", "Object remains self-consistent"),
        IUTLemmaCatalogEntry("I-L1-002", "IUT I", "§1", "Local arithmetic consistency", "Given local arithmetic map", "Monotone local consistency", ("I-L1-001",)),
        IUTLemmaCatalogEntry("II-L2-001", "IUT II", "§2", "Evaluation stability", "Given theater + local map", "Bounded evaluation transfer", ("I-L1-002",)),
        IUTLemmaCatalogEntry("II-L2-002", "IUT II", "§2", "Morphism composition sanity", "Given composable local morphisms", "Composition preserves consistency", ("I-L1-002",)),
        IUTLemmaCatalogEntry("III-L3-001", "IUT III", "§3", "Theta-link correspondence", "Given inter-theater map", "Bridge preserves selected invariants", ("II-L2-001", "II-L2-002")),
        IUTLemmaCatalogEntry("III-L3-002", "IUT III", "§3", "Canonical split compatibility", "Given canonical splitting frame", "Split compatible across correspondence", ("III-L3-001",)),
        IUTLemmaCatalogEntry("IV-L4-001", "IUT IV", "§4", "Invariant transfer", "Given established correspondences", "Invariants transfer to target theater", ("III-L3-001", "III-L3-002")),
        IUTLemmaCatalogEntry("IV-L4-002", "IUT IV", "§4", "Global synthesis check", "Given transferred invariants", "Global consistency constraints satisfy", ("IV-L4-001",)),
    ]


def catalog_index(catalog: list[IUTLemmaCatalogEntry]) -> dict[str, IUTLemmaCatalogEntry]:
    return {c.lemma_id: c for c in catalog}


def infer_catalog_dependencies(text: str, catalog: list[IUTLemmaCatalogEntry] | None = None) -> dict[str, Any]:
    cat = catalog or build_iut_lemma_catalog_v1()
    ids = [c.lemma_id for c in cat]
    hits = [lid for lid in ids if re.search(re.escape(lid), text or "", flags=re.I)]
    by_id = catalog_index(cat)
    deps: set[str] = set()
    for h in hits:
        deps.update(by_id[h].dependency_ids)
    return {
        "hits": hits,
        "required_dependencies": sorted(list(deps)),
        "catalog_size": len(cat),
    }
