#!/usr/bin/env python3
"""Query Mesh Pipeline (1 -> 3 -> 2 -> 5 -> 6 -> 7 -> 8)

Implements:
1) Query Decomposer
3) DOI/ID Normalizer
2) Multi-Source Fetcher (parallel adapters)
5) Parallel Paper Reader
6) Reasoning Mesh Executor
7) Formal Claim Router
8) Evidence Scorer

Design notes:
- Stateless by default (no file cache)
- Per-run ephemeral memory is cleared in finally blocks
"""

from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re
import time
from dataclasses import dataclass
from html import unescape
from typing import Any
from urllib.parse import quote

import requests

import sys
from pathlib import Path

ROOT = Path('/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/src')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from katala_samurai.kq_symbolic_bridge import (
    eval_ltl_lite,
    eval_symbolic,
    solve_ctl_lite,
    solve_hol_lite,
    solve_sat_lite,
    solve_smt_optional,
)

TIMEOUT = 12
UA = "KQ-inf-QueryMesh/1.0"


@dataclass
class DecomposedQuery:
    original: str
    search_terms: list[str]
    refutation_terms: list[str]
    temporal_terms: list[str]
    generated_queries: list[str]


@dataclass
class ResourceGovernor:
    cpu_budget: float = float(os.getenv("KQ_CPU_BUDGET", "0.40"))
    gpu_budget: float = float(os.getenv("KQ_GPU_BUDGET", "0.40"))

    def snapshot(self) -> dict[str, Any]:
        try:
            load1 = os.getloadavg()[0]
        except Exception:
            load1 = 0.0
        cpu_cnt = max(1, (os.cpu_count() or 1))
        cpu_ratio = min(1.0, max(0.0, load1 / float(cpu_cnt)))
        # GPU ratio is optional; if unavailable we keep 0 and mark unknown
        gpu_ratio = 0.0
        gpu_known = False
        try:
            import subprocess
            p = subprocess.run([
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ], capture_output=True, text=True, check=False)
            if p.returncode == 0 and (p.stdout or "").strip():
                vals = [float(x.strip()) for x in (p.stdout or "").splitlines() if x.strip()]
                if vals:
                    gpu_ratio = min(1.0, max(0.0, max(vals) / 100.0))
                    gpu_known = True
        except Exception:
            pass
        return {
            "cpu_ratio": round(cpu_ratio, 4),
            "gpu_ratio": round(gpu_ratio, 4),
            "gpu_known": gpu_known,
            "cpu_ok": cpu_ratio <= self.cpu_budget,
            "gpu_ok": (gpu_ratio <= self.gpu_budget) if gpu_known else True,
            "cpu_budget": self.cpu_budget,
            "gpu_budget": self.gpu_budget,
        }


class TaskScheduler:
    def __init__(self, governor: ResourceGovernor):
        self.governor = governor

    def choose_lane(self, task_kind: str, priority: str = "normal") -> dict[str, Any]:
        snap = self.governor.snapshot()
        heavy = task_kind in {"ocr", "embedding", "nn-rank", "pdf-deep-read"}
        lane = "cpu"
        degrade = False
        if heavy and snap.get("gpu_ok"):
            lane = "gpu"
        if not snap.get("cpu_ok") or not snap.get("gpu_ok"):
            degrade = True
        if priority == "high":
            degrade = False
        return {"lane": lane, "degrade": degrade, "resource": snap}


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


class ParallelPaperReader:
    def __init__(self, timeout: int = TIMEOUT):
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": UA})

    @staticmethod
    def _strip_html(html: str) -> str:
        x = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html or "")
        x = re.sub(r"(?s)<[^>]+>", " ", x)
        x = unescape(x)
        x = re.sub(r"\s+", " ", x).strip()
        return x

    def _read_one(self, item: dict[str, Any]) -> dict[str, Any]:
        url = str(item.get("url") or "").strip()
        out = dict(item)
        out["read_status"] = "unread"
        out["text"] = ""
        if not url:
            return out
        try:
            r = self._session.get(url, timeout=self.timeout)
            ctype = (r.headers.get("content-type") or "").lower()
            if r.status_code != 200:
                out["read_status"] = f"http_{r.status_code}"
                return out
            if "text/html" in ctype or "xml" in ctype:
                txt = self._strip_html(r.text)
            else:
                # keep conservative for non-html payloads
                txt = (r.text or "")[:20000]
            out["text"] = txt[:8000]
            out["read_status"] = "ok" if out["text"] else "empty"
            return out
        except Exception:
            out["read_status"] = "error"
            return out

    def read_parallel(self, items: list[dict[str, Any]], max_workers: int = 16) -> dict[str, Any]:
        out_items: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=min(max_workers, max(4, len(items) or 4))) as ex:
            futs = [ex.submit(self._read_one, it) for it in items]
            for fu in cf.as_completed(futs):
                try:
                    out_items.append(fu.result())
                except Exception:
                    pass
        ok_n = sum(1 for x in out_items if x.get("read_status") == "ok")
        return {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "ok_count": ok_n,
            "total": len(out_items),
            "items": out_items,
        }


class ReasoningMeshExecutor:
    CLAIM_PAT = re.compile(r"(therefore|thus|show|demonstrate|prove|implies|suggests|indicates|結論|示す|証明|示唆|if|then|all|exists|forall|si|entonces|se|logo|si\s+ent[aã]o|si\s+alors|wenn|dann|если|то|اذا|فإن|यदि|तो|如果|那么|ถ้า|แล้ว|jika|maka|toki|la|se\s+tiam|quando|allora|siempre|sempre|wenn|dann|если|то|اذا|فان|यदि|तो|如果|那么|ถ้า|แล้ว|jika|maka|kad|onda|at|kai)", re.I)

    @staticmethod
    def _normalize_claim_text(s: str) -> dict[str, Any]:
        t = (s or "").strip()
        low = t.lower()
        notes = []

        rep = {
            " ならば ": " -> ", " implies ": " -> ", " iff ": " <-> ",
            " かつ ": " and ", " または ": " or ", " もしくは ": " or ",
            " si ": " if ", " entonces ": " then ", " y ": " and ", " o ": " or ",  # es
            " se ": " if ", " então ": " then ", " e ": " and ", " ou ": " or ",  # pt
            " alors ": " then ", " et ": " and ",  # fr
            " wenn ": " if ", " dann ": " then ", " und ": " and ", " oder ": " or ",  # de
            " если ": " if ", " то ": " then ", " и ": " and ", " или ": " or ",  # ru
            " اذا ": " if ", " فإن ": " then ", " و ": " and ", " أو ": " or ",  # ar
            " यदि ": " if ", " और ": " and ", " या ": " or ",  # hi
            " 如果 ": " if ", " 那么 ": " then ", " 且 ": " and ", " 或 ": " or ",  # zh
            " ถ้า ": " if ", " แล้ว ": " then ", " และ ": " and ", " หรือ ": " or ",  # th
            " jika ": " if ", " maka ": " then ", " dan ": " and ", " atau ": " or ",  # id
            " toki ": " if ", " la ": " then ", " en ": " and ", " anu ": " or ",  # toki pona
            " se ": " if ", " tiam ": " then ", " kaj ": " and ", " aŭ ": " or ",  # eo
            " igitur ": " then ", " ergo ": " then ", " aut ": " or ",  # latin
            " εἰ ": " if ", " καί ": " and ", " ἤ ": " or ",  # ancient greek
            " sace ": " if ", " ca ": " and ", " vā ": " or ",  # pali
            " ܐܢ ": " if ", " ܗܝܕܝܢ ": " then ",  # classical syriac
            " ije ": " if ", " ian ": " and ", " a ": " or ",  # interlingua/ido lite
            " xu ": " if ", " gi'e ": " and ", " ja ": " or ",  # lojban-lite
            " chugh ": " if ", " vaj ": " then ", " je ": " and ", " pagh ": " or ",  # klingon-lite
            " aiya ": " if ", " ar ": " and ", " hya ": " or ",  # quenya/sindarin-lite
            " mae ": " if ", " san ": " then ", " vos ": " or ",  # dothraki/valyrian-lite
            " tsnì ": " and ", " fu ": " or ",  # na'vi-lite
        }
        for a, b in rep.items():
            if a in low:
                low = low.replace(a, b)
                notes.append(f"replace:{a.strip()}->{b.strip()}")

        # multilingual quantifier keywords to canonical tokens
        low = re.sub(r"\b(todos?|todas|todo|toute?s?|alle|all|alles|semua|모든|tutti|wszystkie|всі|tüm|όλοι|mọi|semua|lahat|sarva|omnis|omnes|sabba|πᾶς|𓂋)\b", "forall", low)
        low = re.sub(r"\b(existe|existen|existem|il\s+existe|gibt\s+es|ada|ある|存在|существует|يوجد|है|有|esiste|istnieje|існує|vardır|υπάρχει|tồn tại|existit|atthi|ἐστίν|umiiral?)\b", "exists", low)

        m_forall = re.search(r"forall\s+([a-zA-Z_]\w*)\s+(in|en|em|dans|в|في|में|在|ใน|di)\s*(\[[^\]]+\]|\([^\)]+\))\s*,?\s*(.+)", low)
        if m_forall:
            v, _, dom, body = m_forall.group(1), m_forall.group(2), m_forall.group(3), m_forall.group(4)
            low = f"forall {v} in {dom}. {body}"
            notes.append("template:forall-multi")

        m_exists = re.search(r"exists\s+([a-zA-Z_]\w*)\s+(in|en|em|dans|в|في|में|在|ใน|di)\s*(\[[^\]]+\]|\([^\)]+\))\s*,?\s*(.+)", low)
        if m_exists:
            v, _, dom, body = m_exists.group(1), m_exists.group(2), m_exists.group(3), m_exists.group(4)
            low = f"exists {v} in {dom}. {body}"
            notes.append("template:exists-multi")

        if " if " in low and " then " in low and "->" not in low:
            try:
                a = low.split(" if ", 1)[1].split(" then ", 1)[0].strip()
                b = low.split(" then ", 1)[1].strip()
                low = f"({a}) -> ({b})"
                notes.append("template:if-then")
            except Exception:
                pass

        return {"normalized": low.strip(), "notes": notes}

    def extract_claims(self, text: str) -> list[dict[str, Any]]:
        sents = [s.strip() for s in re.split(r"[。.!?\n]+", text or "") if s.strip()]
        claims = []
        for s in sents:
            if self.CLAIM_PAT.search(s) or len(s.split()) >= 10:
                n = self._normalize_claim_text(s[:300])
                claims.append({"raw": s[:300], "normalized": n["normalized"], "notes": n["notes"]})
        return claims[:12]

    def run_parallel(self, items: list[dict[str, Any]], max_workers: int = 12) -> dict[str, Any]:
        def _one(it: dict[str, Any]) -> dict[str, Any]:
            txt = str(it.get("text") or "")
            claims = self.extract_claims(txt)
            return {
                "canonical_id": it.get("canonical_id"),
                "title": it.get("title"),
                "claims": claims,
                "claim_count": len(claims),
            }

        rows: list[dict[str, Any]] = []
        t0 = time.perf_counter()
        with cf.ThreadPoolExecutor(max_workers=min(max_workers, max(4, len(items) or 4))) as ex:
            futs = [ex.submit(_one, it) for it in items]
            for fu in cf.as_completed(futs):
                try:
                    rows.append(fu.result())
                except Exception:
                    pass

        total_claims = sum(int(x.get("claim_count") or 0) for x in rows)
        return {
            "elapsed_ms": round((time.perf_counter() - t0) * 1000.0, 3),
            "papers": len(rows),
            "total_claims": total_claims,
            "rows": rows,
        }


class FormalClaimRouter:
    LOGIC_PAT = re.compile(r"(forall|exists|\bSAT\b|\bSMT\b|\bCTL\b|\bLTL\b|\bmu\b|\bnu\b|->|<->|\band\b|\bor\b|=|<=|>=|ならば|すべて|存在|si|entonces|y|o|se|ent[aã]o|e|ou|si\s+alors|et|ou|wenn|dann|und|oder|если|то|и|или|اذا|فإن|و|أو|यदि|तो|और|या|如果|那么|且|或|ถ้า|แล้ว|และ|หรือ|jika|maka|dan|atau|toki|la|en|aŭ|se\s+tiam|kaj|aux|ergo|igitur|aut|εἰ|καί|ἤ|sace|vā|ܐܢ|lojban|la\s+o\w+|interlingua|ido|klingon|tlh|quenya|sindarin|dothraki|valyrian|na['’]vi)", re.I)

    @staticmethod
    def _normalize_claim(claim: str) -> dict[str, Any]:
        c = (claim or "").strip()
        low = c.lower()
        notes: list[str] = []

        rep = {
            " ならば ": " -> ", " implies ": " -> ", " iff ": " <-> ",
            " かつ ": " and ", " または ": " or ", " もしくは ": " or ", " ではない": " not ",
            " si ": " if ", " entonces ": " then ", " y ": " and ", " o ": " or ",
            " se ": " if ", " então ": " then ", " e ": " and ", " ou ": " or ",
            " alors ": " then ", " et ": " and ",
            " wenn ": " if ", " dann ": " then ", " und ": " and ", " oder ": " or ",
            " если ": " if ", " то ": " then ", " и ": " and ", " или ": " or ",
            " اذا ": " if ", " فإن ": " then ", " و ": " and ", " أو ": " or ",
            " यदि ": " if ", " और ": " and ", " या ": " or ",
            " 如果 ": " if ", " 那么 ": " then ", " 且 ": " and ", " 或 ": " or ",
            " ถ้า ": " if ", " แล้ว ": " then ", " และ ": " and ", " หรือ ": " or ",
            " jika ": " if ", " maka ": " then ", " dan ": " and ", " atau ": " or ",
            " toki ": " if ", " la ": " then ", " en ": " and ", " anu ": " or ",
            " tiam ": " then ", " kaj ": " and ", " aŭ ": " or ",
            " quando ": " if ", " allora ": " then ", " sempre ": " forall ",  # it extra
            " gdy ": " if ", " wtedy ": " then ", " i ": " and ", " lub ": " or ",  # pl
            " якщо ": " if ", " тоді ": " then ", " та ": " and ", " або ": " or ",  # uk
            " eğer ": " if ", " ise ": " then ", " ve ": " and ", " veya ": " or ",  # tr
            " αν ": " if ", " τότε ": " then ", " και ": " and ", " ή ": " or ",  # el
            " nếu ": " if ", " thì ": " then ", " và ": " and ", " hoặc ": " or ",  # vi
            " kalau ": " if ", " maka ": " then ",  # ms
            " kung ": " if ", " kung gayon ": " then ", " at ": " and ", " o ": " or ",  # tl
            " igitur ": " then ", " ergo ": " then ", " aut ": " or ",  # latin
            " εἰ ": " if ", " καί ": " and ", " ἤ ": " or ",  # ancient greek
            " sace ": " if ", " ca ": " and ", " vā ": " or ",  # pali
            " ܐܢ ": " if ", " ܗܝܕܝܢ ": " then ",  # classical syriac
            " ije ": " if ", " ian ": " and ", " a ": " or ",  # interlingua/ido lite
            " xu ": " if ", " gi'e ": " and ", " ja ": " or ",  # lojban-lite
            " chugh ": " if ", " vaj ": " then ", " je ": " and ", " pagh ": " or ",  # klingon-lite
            " aiya ": " if ", " ar ": " and ", " hya ": " or ",  # quenya/sindarin-lite
            " mae ": " if ", " san ": " then ", " vos ": " or ",  # dothraki/valyrian-lite
            " tsnì ": " and ", " fu ": " or ",  # na'vi-lite
            " 𒆠 ": " in ", " 𒌋 ": " and ",  # sumerian markers (best-effort)
        }
        for a, b in rep.items():
            if a in low:
                low = low.replace(a, b)
                notes.append(f"replace:{a.strip()}->{b.strip()}")

        low = re.sub(r"\b(todos?|todas|todo|toute?s?|alle|all|alles|semua|모든|tutti|wszystkie|всі|tüm|όλοι|mọi|semua|lahat|sarva|omnis|omnes|sabba|πᾶς|𓂋)\b", "forall", low)
        low = re.sub(r"\b(existe|existen|existem|il\s+existe|gibt\s+es|ada|ある|存在|существует|يوجد|है|有|esiste|istnieje|існує|vardır|υπάρχει|tồn tại|existit|atthi|ἐστίν|umiiral?)\b", "exists", low)

        m_forall = re.search(r"forall\s+([a-zA-Z_]\w*)\s+(in|en|em|dans|в|في|में|在|ใน|di)\s*(\[[^\]]+\]|\([^\)]+\))\s*,?\s*(.+)", low)
        if m_forall:
            v, _, dom, body = m_forall.group(1), m_forall.group(2), m_forall.group(3), m_forall.group(4)
            low = f"forall {v} in {dom}. {body}"
            notes.append("template:forall-multi")

        m_exists = re.search(r"exists\s+([a-zA-Z_]\w*)\s+(in|en|em|dans|в|في|में|在|ใน|di)\s*(\[[^\]]+\]|\([^\)]+\))\s*,?\s*(.+)", low)
        if m_exists:
            v, _, dom, body = m_exists.group(1), m_exists.group(2), m_exists.group(3), m_exists.group(4)
            low = f"exists {v} in {dom}. {body}"
            notes.append("template:exists-multi")

        if " if " in low and " then " in low and "->" not in low:
            try:
                a = low.split(" if ", 1)[1].split(" then ", 1)[0].strip()
                b = low.split(" then ", 1)[1].strip()
                low = f"({a}) -> ({b})"
                notes.append("template:if-then")
            except Exception:
                pass

        return {"normalized": low.strip(), "notes": notes}

    @staticmethod
    def _formalize_for_solver(norm: str) -> dict[str, Any]:
        s = (norm or "").strip()
        low = s.lower()
        notes: list[str] = []

        # lexical math normalization
        swaps = {
            ' greater than or equal to ': ' >= ',
            ' less than or equal to ': ' <= ',
            ' greater than ': ' > ',
            ' less than ': ' < ',
            ' equals ': ' == ',
            ' equal to ': ' == ',
        }
        for a, b in swaps.items():
            if a in low:
                low = low.replace(a, b)
                notes.append(f'lex:{a.strip()}->{b.strip()}')

        # If quantifier with a simple predicate body, route to HOL directly
        if low.startswith('forall ') or low.startswith('exists '):
            return {'kind_hint': 'hol', 'expr': low, 'notes': notes}

        # Build SMT-lite when explicit variable-domain exists and math body found
        m_dom = re.search(r'([a-zA-Z_]\w*)\s+in\s*(\[[^\]]+\]|\([^\)]+\))', low)
        m_cmp = re.findall(r'([a-zA-Z_]\w*)\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)', low)
        if m_dom and m_cmp:
            v, dom = m_dom.group(1), m_dom.group(2)
            body_atoms = [f"{a} {op} {b}" for a, op, b in m_cmp if a == v]
            if body_atoms:
                expr = f"vars: {v} in {dom}; formula: and(" + ", ".join(body_atoms) + ")"
                notes.append('shape:smt-lite')
                return {'kind_hint': 'smt', 'expr': expr, 'notes': notes}

        # If boolean implication-like, force SAT skeleton
        if '->' in low or (' and ' in low) or (' or ' in low) or low.startswith('not '):
            notes.append('shape:sat-lite')
            return {'kind_hint': 'sat', 'expr': low, 'notes': notes}

        return {'kind_hint': 'symbolic', 'expr': low, 'notes': notes}

    @staticmethod
    def _try_solver(kind: str, expr: str) -> dict[str, Any]:
        if kind == 'ctl':
            return solve_ctl_lite(expr)
        if kind == 'ltl':
            return eval_ltl_lite(expr)
        if kind == 'hol':
            return solve_hol_lite(expr)
        if kind == 'smt':
            return solve_smt_optional(expr)
        if kind == 'sat':
            return solve_sat_lite(expr)
        return eval_symbolic(expr)

    def _candidate_forms(self, normalized: str, kind_hint: str | None = None) -> list[tuple[str, str]]:
        low = (normalized or '').strip().lower()
        cands: list[tuple[str, str]] = []

        # explicit temporal with missing trace -> attach conservative boolean trace
        if any(x in f" {low} " for x in [" g ", " f ", " x ", " u ", " r ", " w ", " s ", " t "]) and "@" not in low:
            cands.append(('ltl', f"{low} @ ['p','p','p']"))

        if 'forall' in low or 'exists' in low or 'lambda' in low:
            cands.append(('hol', low))

        # SMT shaping fallback from comparison-rich claims
        cmp_hits = re.findall(r'([a-zA-Z_]\w*)\s*(==|!=|<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)', low)
        dom_hit = re.search(r'([a-zA-Z_]\w*)\s+in\s*(\[[^\]]+\]|\([^\)]+\))', low)
        if dom_hit and cmp_hits:
            v, dom = dom_hit.group(1), dom_hit.group(2)
            atoms = [f"{a} {op} {b}" for a, op, b in cmp_hits if a == v]
            if atoms:
                cands.append(('smt', f"vars: {v} in {dom}; formula: and(" + ", ".join(atoms) + ")"))

        if 'vars:' in low or 'formula:' in low or kind_hint == 'smt':
            cands.append(('smt', low))
        if ' and ' in low or ' or ' in low or 'not ' in low or '->' in low or kind_hint == 'sat':
            cands.append(('sat', low))

        # baseline symbolic always last
        cands.append(('symbolic', low))

        # dedupe preserve order
        out: list[tuple[str, str]] = []
        seen = set()
        for k, e in cands:
            key = (k, e)
            if key not in seen:
                seen.add(key)
                out.append((k, e))
        return out

    def _route_one(self, claim: str) -> dict[str, Any]:
        c = (claim or "").strip()
        n = self._normalize_claim(c)
        norm = n["normalized"]
        fz = self._formalize_for_solver(norm)
        norm2 = str(fz.get('expr') or norm)
        merged_notes = (n["notes"] or []) + (fz.get("notes") or [])

        best = None
        for kind, expr in self._candidate_forms(norm2, kind_hint=str(fz.get('kind_hint') or '').strip().lower() or None):
            r = self._try_solver(kind, expr)
            cand = {"claim": c, "normalized_claim": expr, "normalization_notes": merged_notes, "kind": kind, "formal": r}
            if best is None:
                best = cand
            if bool((r or {}).get('ok')):
                return cand

        return best or {"claim": c, "normalized_claim": norm2, "normalization_notes": merged_notes, "kind": "symbolic", "formal": {"ok": False, "proof_status": "failed", "error": "no-candidate"}}

    def route_parallel(self, rows: list[dict[str, Any]], max_workers: int = 16) -> dict[str, Any]:
        claims = []
        for row in rows:
            for c in (row.get("claims") or []):
                if isinstance(c, dict):
                    raw = str(c.get("raw") or "")
                    norm = str(c.get("normalized") or raw)
                else:
                    raw = str(c)
                    norm = raw
                if self.LOGIC_PAT.search(norm) or self.LOGIC_PAT.search(raw):
                    claims.append(norm)
        claims = claims[:200]

        routed = []
        with cf.ThreadPoolExecutor(max_workers=min(max_workers, max(4, len(claims) or 4))) as ex:
            futs = [ex.submit(self._route_one, c) for c in claims]
            for fu in cf.as_completed(futs):
                try:
                    routed.append(fu.result())
                except Exception:
                    pass

        ok_n = sum(1 for x in routed if bool((x.get("formal") or {}).get("ok")))
        return {"total": len(routed), "ok": ok_n, "items": routed}


class EvidenceScorer:
    TRUSTED = {"openalex", "crossref", "pubmed"}

    @staticmethod
    def _citation_trust_score(p: dict[str, Any]) -> float:
        # citation count aliases across providers
        c = p.get("cited_by_count")
        if c is None:
            c = p.get("citation_count")
        if c is None:
            c = p.get("cites")
        try:
            c = max(0.0, float(c or 0.0))
        except Exception:
            c = 0.0

        year = p.get("year") or p.get("publication_year")
        try:
            year = int(year)
        except Exception:
            year = None

        # age normalization: avoid penalizing recent papers too hard
        age_norm = 1.0
        if year is not None:
            age = max(0, 2026 - int(year))
            age_norm = min(1.0, 0.35 + age / 10.0)

        # saturating citation transform (rough log-like)
        cite_sat = min(1.0, (c / 50.0) ** 0.5) if c > 0 else 0.0
        return round(max(0.0, min(1.0, 0.7 * cite_sat + 0.3 * age_norm)), 4)

    def score(self, papers: list[dict[str, Any]], routed: list[dict[str, Any]]) -> dict[str, Any]:
        paper_map = {str(p.get("canonical_id") or p.get("url") or p.get("title") or i): p for i, p in enumerate(papers)}
        # per-paper quality
        scores = []
        for k, p in paper_map.items():
            src = set(p.get("sources") or [])
            peer = 1.0 if (src & self.TRUSTED) else 0.5
            doi = 1.0 if p.get("doi_normalized") else 0.4
            read = 1.0 if p.get("read_status") == "ok" else 0.3
            citation_trust = self._citation_trust_score(p)
            s = min(1.0, peer * 0.3 + doi * 0.25 + read * 0.2 + citation_trust * 0.25)
            scores.append({
                "canonical_id": k,
                "paper_score": round(s, 4),
                "citation_trust_score": citation_trust,
            })

        # formal claim evidence
        formal_ok = sum(1 for it in routed if bool((it.get("formal") or {}).get("ok")))
        formal_total = len(routed)
        formal_ratio = (formal_ok / formal_total) if formal_total else 0.0

        global_score = min(1.0, (sum(x["paper_score"] for x in scores) / max(1, len(scores))) * 0.7 + formal_ratio * 0.3)
        return {
            "papers": scores[:200],
            "formal_total": formal_total,
            "formal_ok": formal_ok,
            "formal_ok_ratio": round(formal_ratio, 4),
            "global_evidence_score": round(global_score, 4),
        }


def run_pipeline(query: str, per_source_limit: int = 8) -> dict[str, Any]:
    decomposer = QueryDecomposer()
    normalizer = DoiIdNormalizer()
    fetcher = MultiSourceFetcher()
    reader = ParallelPaperReader()
    mesh = ReasoningMeshExecutor()
    router = FormalClaimRouter()
    scorer = EvidenceScorer()
    governor = ResourceGovernor()
    scheduler = TaskScheduler(governor)

    # ephemeral run memory
    raw_items: list[dict[str, Any]] = []
    read_items: list[dict[str, Any]] = []
    mesh_rows: list[dict[str, Any]] = []
    routed_items: list[dict[str, Any]] = []
    try:
        dq = decomposer.decompose(query)
        fetched = fetcher.fetch_all(dq.generated_queries, per_source_limit=per_source_limit)
        raw_items = fetched.get("items") or []
        merged = normalizer.merge_dedup(raw_items)

        step5 = reader.read_parallel(merged[:200])
        read_items = step5.get("items") or []

        step6 = mesh.run_parallel(read_items)
        mesh_rows = step6.get("rows") or []

        step7 = router.route_parallel(mesh_rows)
        routed_items = step7.get("items") or []

        step8 = scorer.score(read_items, routed_items)

        sched_fetch = scheduler.choose_lane("network-fetch", priority="high")
        sched_read = scheduler.choose_lane("pdf-deep-read")
        sched_ocr = scheduler.choose_lane("ocr")

        return {
            "pipeline": "query-mesh-v2",
            "resource_governor": governor.snapshot(),
            "task_scheduler": {
                "network_fetch": sched_fetch,
                "paper_read": sched_read,
                "ocr": sched_ocr,
            },
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
            "step5_parallel_paper_reader": {
                "total": step5.get("total", 0),
                "ok_count": step5.get("ok_count", 0),
                "elapsed_ms": step5.get("elapsed_ms", 0.0),
            },
            "step6_reasoning_mesh_executor": {
                "papers": step6.get("papers", 0),
                "total_claims": step6.get("total_claims", 0),
                "elapsed_ms": step6.get("elapsed_ms", 0.0),
            },
            "step7_formal_claim_router": {
                "total": step7.get("total", 0),
                "ok": step7.get("ok", 0),
            },
            "step8_evidence_scorer": step8,
            "items": read_items[:200],
            "claims_routed": routed_items[:200],
        }
    finally:
        # strict no-residual policy for this run
        raw_items.clear()
        read_items.clear()
        mesh_rows.clear()
        routed_items.clear()


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
