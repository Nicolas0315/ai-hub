from __future__ import annotations

from typing import Any

TRUSTED_PEER_REVIEW_SOURCES = {"openalex", "crossref", "pubmed"}


def _collect_peer_review_items(unified: dict[str, Any] | None) -> list[dict[str, Any]]:
    u = unified or {}
    refs = (u.get("external_peer_review_refs") or {}) if isinstance(u, dict) else {}
    items = refs.get("items") or []
    out: list[dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        src = str(it.get("source", "")).lower().strip()
        if src not in TRUSTED_PEER_REVIEW_SOURCES:
            continue
        out.append({
            "source": src,
            "title": it.get("title"),
            "doi": it.get("doi"),
            "year": it.get("year"),
            "authors": it.get("authors"),
            "url": it.get("url"),
        })
    return out


def run_inf_memory_layer(prompt: str, unified: dict[str, Any] | None = None) -> dict[str, Any]:
    papers = _collect_peer_review_items(unified)
    return {
        "enabled": True,
        "schema_version": "inf-memory-v1",
        "layer": "inf-memory",
        "goal": "peer_review_memory_only",
        "input": {
            "prompt": (prompt or "")[:400],
        },
        "peer_review_memory": {
            "policy": "peer-reviewed-only",
            "trusted_sources": sorted(list(TRUSTED_PEER_REVIEW_SOURCES)),
            "storage_strategy": {
                "logic_layer": "code",
                "raw_data_layer": "binary",
                "trace_layer": "metadata-json",
                "hash_algorithm": "sha256",
                "binary_store_root": "/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-memory-store",
            },
            "count": len(papers),
            "papers": papers,
        },
        "status": {
            "writeback_forbidden": True,
        },
    }
