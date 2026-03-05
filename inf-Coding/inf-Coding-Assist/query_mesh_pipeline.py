#!/usr/bin/env python3
"""Query Mesh Pipeline (1 -> 3 -> 2)

Implements:
1) Query Decomposer
3) DOI/ID Normalizer
2) Multi-Source Fetcher (parallel adapters)

Design notes:
- Stateless by default (no file cache)
- Per-run ephemeral memory is cleared in finally blocks
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import requests

TIMEOUT = 12
UA = "KQ-inf-QueryMesh/1.0"


@dataclass
class DecomposedQuery:
    original: str
    search_terms: list[str]
    refutation_terms: list[str]
    temporal_terms: list[str]
    generated_queries: list[str]


class QueryDecomposer:
    REFUTE_LEX = {
        "counterexample",
        "limitation",
        "failure",
        "bias",
        "reproducibility",
        "反証",
        "限界",
        "再現性",
        "バイアス",
    }

    TEMPORAL_PAT = re.compile(r"\b(19\d{2}|20\d{2}|latest|recent|today|yesterday|past|future)\b", re.I)

    def decompose(self, text: str) -> DecomposedQuery:
        t = (text or "").strip()
        low = t.lower()
        # rough term extraction: words with letters/number and JP blocks
        raw_terms = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}|[一-龥ぁ-んァ-ヴー]{2,}", t)
        uniq = []
        seen = set()
        for x in raw_terms:
            k = x.lower()
            if k not in seen:
                seen.add(k)
                uniq.append(x)

        temporal = []
        for m in self.TEMPORAL_PAT.findall(low):
            if m not in temporal:
                temporal.append(m)

        refute = [x for x in uniq if x.lower() in self.REFUTE_LEX]
        base = uniq[:8] if uniq else [t]

        generated = []
        if base:
            generated.append(" ".join(base))
            generated.append(" ".join(base + ["peer reviewed", "doi"]))
            generated.append(" ".join(base + ["systematic review"]))
            generated.append(" ".join(base + ["counterexample", "limitation"]))
        if temporal:
            generated.append(" ".join(base + temporal))

        # dedupe preserve order
        g2 = []
        s2 = set()
        for g in generated:
            gg = g.strip()
            if gg and gg not in s2:
                s2.add(gg)
                g2.append(gg)

        return DecomposedQuery(
            original=t,
            search_terms=base,
            refutation_terms=refute,
            temporal_terms=temporal,
            generated_queries=g2,
        )


class DoiIdNormalizer:
    DOI_PAT = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)

    @staticmethod
    def normalize_doi(doi: str | None) -> str | None:
        if not doi:
            return None
        d = doi.strip()
        d = d.replace("https://doi.org/", "").replace("http://doi.org/", "")
        m = DoiIdNormalizer.DOI_PAT.search(d)
        if not m:
            return None
        return m.group(0).lower()

    def normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        doi = self.normalize_doi(item.get("doi") or item.get("DOI"))
        out = dict(item)
        out["doi_normalized"] = doi

        # provider-specific ids
        pmid = str(item.get("pmid") or "").strip()
        if pmid:
            out["pmid_normalized"] = pmid
        arxiv = str(item.get("arxiv_id") or item.get("arxiv") or "").strip()
        if arxiv:
            out["arxiv_normalized"] = arxiv.lower().replace("arxiv:", "")

        # canonical key for merge
        out["canonical_id"] = doi or out.get("pmid_normalized") or out.get("arxiv_normalized") or (out.get("url") or "")
        return out

    def merge_dedup(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for it in items:
            n = self.normalize_item(it)
            key = str(n.get("canonical_id") or "").strip()
            if not key:
                continue
            if key not in merged:
                merged[key] = n
            else:
                cur = merged[key]
                # fill missing fields
                for k, v in n.items():
                    if (cur.get(k) in (None, "", [])) and v not in (None, "", []):
                        cur[k] = v
                # union sources
                s = set(cur.get("sources") or []) | set(n.get("sources") or [])
                cur["sources"] = sorted(list(s))
        return list(merged.values())


class MultiSourceFetcher:
    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})

    def _get_json(self, url: str) -> dict[str, Any] | None:
        try:
            r = self._session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            return None

    def fetch_openalex(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        url = f"https://api.openalex.org/works?search={quote(q)}&per-page={max(1,min(limit,25))}"
        j = self._get_json(url) or {}
        out = []
        for w in (j.get("results") or [])[:limit]:
            out.append(
                {
                    "title": w.get("display_name"),
                    "doi": w.get("doi"),
                    "url": w.get("primary_location", {}).get("landing_page_url") or w.get("id"),
                    "year": w.get("publication_year"),
                    "sources": ["openalex"],
                }
            )
        return out

    def fetch_crossref(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        url = f"https://api.crossref.org/works?query={quote(q)}&rows={max(1,min(limit,25))}"
        j = self._get_json(url) or {}
        out = []
        for w in ((j.get("message") or {}).get("items") or [])[:limit]:
            ttl = (w.get("title") or [None])[0]
            out.append(
                {
                    "title": ttl,
                    "doi": w.get("DOI"),
                    "url": (w.get("URL") or ""),
                    "year": (((w.get("issued") or {}).get("date-parts") or [[None]])[0][0]),
                    "sources": ["crossref"],
                }
            )
        return out

    def fetch_arxiv(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        url = f"http://export.arxiv.org/api/query?search_query=all:{quote(q)}&start=0&max_results={max(1,min(limit,25))}"
        try:
            r = self._session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return []
            xml = r.text
        except Exception:
            return []

        entries = re.findall(r"<entry>(.*?)</entry>", xml, re.S)
        out = []
        for e in entries[:limit]:
            title_m = re.search(r"<title>(.*?)</title>", e, re.S)
            id_m = re.search(r"<id>(.*?)</id>", e, re.S)
            doi_m = re.search(r"<arxiv:doi[^>]*>(.*?)</arxiv:doi>", e, re.S)
            out.append(
                {
                    "title": (title_m.group(1).strip() if title_m else None),
                    "doi": (doi_m.group(1).strip() if doi_m else None),
                    "arxiv_id": (id_m.group(1).strip().split("/")[-1] if id_m else None),
                    "url": (id_m.group(1).strip() if id_m else None),
                    "sources": ["arxiv"],
                }
            )
        return out

    def fetch_pubmed(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        # eSearch -> IDs, then summary
        es = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax={max(1,min(limit,25))}&term={quote(q)}"
        j = self._get_json(es) or {}
        ids = ((j.get("esearchresult") or {}).get("idlist") or [])[:limit]
        if not ids:
            return []
        sm = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={','.join(ids)}"
        s = self._get_json(sm) or {}
        out = []
        for pid in ids:
            row = (s.get("result") or {}).get(pid) or {}
            out.append(
                {
                    "title": row.get("title"),
                    "pmid": pid,
                    "year": row.get("pubdate"),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    "sources": ["pubmed"],
                }
            )
        return out

    def fetch_semantic_scholar(self, q: str, limit: int = 10) -> list[dict[str, Any]]:
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(q)}&limit={max(1,min(limit,25))}&fields=title,year,externalIds,url"
        j = self._get_json(url) or {}
        out = []
        for p in (j.get("data") or [])[:limit]:
            ext = p.get("externalIds") or {}
            out.append(
                {
                    "title": p.get("title"),
                    "doi": ext.get("DOI"),
                    "arxiv_id": ext.get("ArXiv"),
                    "year": p.get("year"),
                    "url": p.get("url"),
                    "sources": ["semantic_scholar"],
                }
            )
        return out

    def fetch_all(self, queries: list[str], per_source_limit: int = 8) -> dict[str, Any]:
        jobs = []
        for q in queries:
            qq = q.strip()
            if not qq:
                continue
            jobs.extend(
                [
                    ("openalex", qq, self.fetch_openalex),
                    ("crossref", qq, self.fetch_crossref),
                    ("pubmed", qq, self.fetch_pubmed),
                    ("arxiv", qq, self.fetch_arxiv),
                    ("semantic_scholar", qq, self.fetch_semantic_scholar),
                ]
            )

        raw_items: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=min(24, max(6, len(jobs)))) as ex:
            futs = [ex.submit(fn, q, per_source_limit) for _, q, fn in jobs]
            for fu in cf.as_completed(futs):
                try:
                    raw_items.extend(fu.result() or [])
                except Exception:
                    pass

        return {
            "raw_count": len(raw_items),
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "items": raw_items,
        }


def run_pipeline(query: str, per_source_limit: int = 8) -> dict[str, Any]:
    decomposer = QueryDecomposer()
    normalizer = DoiIdNormalizer()
    fetcher = MultiSourceFetcher()

    # ephemeral run memory
    raw_items: list[dict[str, Any]] = []
    try:
        dq = decomposer.decompose(query)
        fetched = fetcher.fetch_all(dq.generated_queries, per_source_limit=per_source_limit)
        raw_items = fetched.get("items") or []
        merged = normalizer.merge_dedup(raw_items)

        return {
            "pipeline": "query-mesh-v1",
            "step1_query_decomposer": {
                "search_terms": dq.search_terms,
                "refutation_terms": dq.refutation_terms,
                "temporal_terms": dq.temporal_terms,
                "generated_queries": dq.generated_queries,
            },
            "step3_doi_id_normalizer": {
                "raw_count": len(raw_items),
                "dedup_count": len(merged),
            },
            "step2_multi_source_fetcher": {
                "raw_count": fetched.get("raw_count", 0),
                "elapsed_ms": fetched.get("elapsed_ms", 0.0),
                "sources": ["openalex", "crossref", "pubmed", "arxiv", "semantic_scholar"],
            },
            "items": merged[:200],
        }
    finally:
        # strict no-residual policy for this run
        raw_items.clear()


def main() -> int:
    if len(__import__("sys").argv) < 2:
        print("Usage: query_mesh_pipeline.py <query> [per_source_limit]", file=__import__("sys").stderr)
        return 64
    q = __import__("sys").argv[1]
    lim = int(__import__("sys").argv[2]) if len(__import__("sys").argv) >= 3 else 8
    out = run_pipeline(q, per_source_limit=lim)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
