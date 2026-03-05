#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import json
import os
import re
import shutil
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

BASE = "https://api.openalex.org/works"
CACHE_DIR = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/.tmp-openalex-cache")
CACHE_TTL_SEC = 3600  # runtime-use only; cache is purged at end of each run

RECENT_FROM, RECENT_TO = "2022-01-01", "2026-12-31"
OLD_FROM, OLD_TO = "1973-01-01", "1977-12-31"

GROUPS = {
    "neuro_recent": {
        "search": "neuroscience brain neural",
        "from": RECENT_FROM,
        "to": RECENT_TO,
        "concept": "",
    },
    "neuro_old": {
        "search": "neuroscience brain neural",
        "from": OLD_FROM,
        "to": OLD_TO,
        "concept": "",
    },
    "ai_recent": {
        "search": "artificial intelligence machine learning deep learning",
        "from": RECENT_FROM,
        "to": RECENT_TO,
        "concept": "C154945302",  # artificial intelligence
    },
    "ai_old": {
        "search": "artificial intelligence computer science pattern recognition",
        "from": OLD_FROM,
        "to": OLD_TO,
        "concept": "",
        "allow_no_abstract": True,
    },
}

STOP = {
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were", "using",
    "study", "analysis", "model", "models", "method", "methods", "research", "journal", "vol",
}


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def purge_cache() -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for p in CACHE_DIR.glob("*.json"):
        try:
            if now - p.stat().st_mtime > CACHE_TTL_SEC:
                p.unlink()
        except Exception:
            pass


def purge_cache_all() -> None:
    """Strict policy: remove all runtime cache artifacts after response."""
    try:
        shutil.rmtree(CACHE_DIR, ignore_errors=True)
    except Exception:
        pass


def fetch_json(url: str) -> dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ck = CACHE_DIR / f"{_cache_key(url)}.json"
    if ck.exists():
        try:
            if time.time() - ck.stat().st_mtime <= CACHE_TTL_SEC:
                return json.loads(ck.read_text(encoding="utf-8"))
        except Exception:
            pass

    with urllib.request.urlopen(url, timeout=45) as r:
        data = json.loads(r.read().decode("utf-8", errors="ignore"))
    ck.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def inv_to_text(inv: dict[str, list[int]] | None) -> str:
    if not inv:
        return ""
    pos = []
    for w, idxs in inv.items():
        for i in idxs:
            pos.append((i, w))
    pos.sort()
    return " ".join(w for _, w in pos)


def parse_page(group: str, page: int, per_page: int = 50) -> list[dict[str, Any]]:
    g = GROUPS[group]
    has_abs = '' if g.get('allow_no_abstract') else ',has_abstract:true'
    base_filt = f"from_publication_date:{g['from']},to_publication_date:{g['to']},type:article{has_abs}"
    filt = base_filt if not g.get('concept') else (base_filt + f",concepts.id:{g['concept']}")
    params = {
        "search": g["search"],
        "filter": filt,
        "sort": "cited_by_count:desc",
        "per-page": per_page,
        "page": page,
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    out = []
    for it in data.get("results", []):
        out.append(
            {
                "id": it.get("id"),
                "title": it.get("title"),
                "year": it.get("publication_year"),
                "cites": it.get("cited_by_count", 0),
                "journal": (((it.get("primary_location") or {}).get("source") or {}).get("display_name")),
                "abstract": inv_to_text(it.get("abstract_inverted_index")),
            }
        )
    return out


def collect_group(group: str, target: int = 40) -> list[dict[str, Any]]:
    pages = list(range(1, 9))  # bulk + page-parallel
    items: list[dict[str, Any]] = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(parse_page, group, p) for p in pages]
        for fu in cf.as_completed(futs):
            try:
                items.extend(fu.result())
            except Exception:
                pass

    # dedupe
    by_id = {}
    for it in items:
        if it.get("id") and it["id"] not in by_id:
            by_id[it["id"]] = it
    uniq = list(by_id.values())

    # quality strengthening
    cleaned = []
    for it in uniq:
        txt = (it.get("title") or "") + " " + (it.get("abstract") or "")
        toks = re.findall(r"[A-Za-z][A-Za-z\-]{2,}", txt)
        if len(toks) < 20:
            continue
        cleaned.append(it)

    cleaned.sort(key=lambda x: x.get("cites", 0), reverse=True)

    if len(cleaned) < target:
        # fallback sweep (sequential pages) to fill target
        p = 9
        seen_ids = {x.get('id') for x in cleaned if x.get('id')}
        while len(cleaned) < target and p <= 20:
            for it in parse_page(group, p):
                if it.get('id') in seen_ids:
                    continue
                seen_ids.add(it.get('id'))
                cleaned.append(it)
                if len(cleaned) >= target:
                    break
            p += 1

    return cleaned[:target]


def summarize(items: list[dict[str, Any]]) -> dict[str, Any]:
    years = [x["year"] for x in items if x.get("year")]
    journals = Counter([x.get("journal") for x in items if x.get("journal")])
    terms = Counter()
    for x in items:
        txt = f"{x.get('title','')} {x.get('abstract','')}".lower()
        for t in re.findall(r"[a-z][a-z\-]{2,}", txt):
            if t in STOP:
                continue
            terms[t] += 1
    return {
        "n": len(items),
        "year_range": [min(years) if years else None, max(years) if years else None],
        "top_journals": journals.most_common(8),
        "top_terms": terms.most_common(20),
        "examples": [
            {
                "title": x.get("title"),
                "year": x.get("year"),
                "journal": x.get("journal"),
                "cites": x.get("cites", 0),
            }
            for x in items[:5]
        ],
    }


def compare(new: list[tuple[str, int]], old: list[tuple[str, int]]) -> dict[str, list[str]]:
    a = {k for k, _ in new[:20]}
    b = {k for k, _ in old[:20]}
    return {"emerging": sorted(list(a - b)), "declining": sorted(list(b - a))}


def main():
    t0 = time.time()
    purge_cache()

    try:
        # fixed windows only in-run; not persisted in output
        with cf.ThreadPoolExecutor(max_workers=4) as ex:
            fut = {k: ex.submit(collect_group, k, 40) for k in GROUPS.keys()}
            groups = {k: v.result() for k, v in fut.items()}

        sm = {k: summarize(v) for k, v in groups.items()}
        comp = {
            "neuro": compare(sm["neuro_recent"]["top_terms"], sm["neuro_old"]["top_terms"]),
            "ai": compare(sm["ai_recent"]["top_terms"], sm["ai_old"]["top_terms"]),
        }

        out = {
            "meta": {
                "schema": "openalex-fast-precision-v1",
                "cache_ttl_sec": CACHE_TTL_SEC,
                "mode": "bulk+page-parallel+batch-summary",
                "elapsed_sec": round(time.time() - t0, 3),
            },
            "summaries": sm,
            "comparisons": comp,
        }

        out_path = Path("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-run/openalex_fast_precision_summary.json")
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out_path))
    finally:
        # strict policy: runtime cache does not remain after response
        purge_cache_all()


if __name__ == "__main__":
    main()
