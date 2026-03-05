"""
Katala_Quantum_02a (KQ02a)

Independent KQ line (KS47 dependency detached).
Adds literature-driven fusion weight tuning based on:
- number of peer-reviewed refs retrieved
- how many references are readable as PDF content
"""
from __future__ import annotations

import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from .katala_quantum_01a import Katala_Quantum_01a

try:
    from .paper_reference import _query_openalex  # KS paper search core
    _HAS_KS_PAPER_SEARCH = True
except Exception:
    _HAS_KS_PAPER_SEARCH = False

from .kq_pdf_reader import extract_pdf_text_kq

try:
    from . import kq_symbolic_bridge as _kq_sym
    _HAS_KQ_SYMBOLIC = True
except Exception:
    _HAS_KQ_SYMBOLIC = False

try:
    from .peer_review_reach import check_reachability, normalize_item, trace_html_fulltext
    _HAS_PEER_REACH = True
except Exception:
    _HAS_PEER_REACH = False


class Katala_Quantum_02a(Katala_Quantum_01a):
    SYSTEM_MODEL: str = "Katala_Quantum_02a"
    ALIAS: str = "KQ02a"

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "ks47_dependency": False,
            "literature_weight_tuning": True,
            "ks_paper_search_applied": _HAS_KS_PAPER_SEARCH,
            "kq_pdf_reader_applied": True,
            "peer_db_scope": ["jstor", "springer", "web_of_science"],
            "peer_db_framework": _HAS_PEER_REACH,
        })
        return s

    @staticmethod
    def _is_pdf_readable(url: str, timeout: float = 2.0) -> bool:
        if not url:
            return False
        u = url.lower()
        if u.endswith(".pdf"):
            return True
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Katala-Quantum/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                ct = (r.headers.get("Content-Type") or "").lower()
                if "pdf" in ct:
                    return True
                # lightweight sniff
                b = r.read(8)
                return b.startswith(b"%PDF-")
        except Exception:
            return False

    def _augment_refs_with_ks_search(self, text: str, refs: dict[str, Any], target_total: int = 80) -> dict[str, Any]:
        """Apply KS paper search system (OpenAlex core) to expand references."""
        if not _HAS_KS_PAPER_SEARCH:
            return refs

        items = list((refs or {}).get("items") or [])
        seen = {(it.get("doi") or "", it.get("title") or "") for it in items if isinstance(it, dict)}

        terms = [w for w in re.findall(r"[A-Za-z]{4,}", text)[:10]]
        queries = []
        if terms:
            queries.append(" ".join(terms[:4]))
            queries.append(" ".join(terms[:3] + ["systematic review"]))
            queries.append(" ".join(terms[:3] + ["empirical study"]))
        else:
            queries = ["verification architecture", "scientific reasoning model", "quantum control systems"]

        for q in queries:
            if len(items) >= target_total:
                break
            try:
                res = _query_openalex(q, per_page=25, timeout=10)
            except Exception:
                continue
            for work in res:
                if len(items) >= target_total:
                    break
                title = (work.get("title") or "").strip()
                doi_raw = (work.get("doi") or "").strip()
                doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""
                key = (doi, title)
                if not title or key in seen:
                    continue
                seen.add(key)
                year = work.get("publication_year")
                items.append({
                    "source": "ks-openalex",
                    "title": title,
                    "doi": doi,
                    "year": year,
                    "journal": "",
                    "url": work.get("id") or (f"https://doi.org/{doi}" if doi else None),
                })

        out = dict(refs or {})
        out["items"] = items
        out.setdefault("providers", [])
        if "ks-openalex" not in out["providers"]:
            out["providers"].append("ks-openalex")
        out["source"] = str(out.get("source", "")) + "+ks-openalex"
        return out

    @staticmethod
    def _extract_pdf_text_lite(raw: bytes) -> str:
        """Reverse-engineered lightweight PDF text extraction (no external deps)."""
        # Very rough PDF text pull: extract (...) strings and decode escaped chars.
        try:
            s = raw.decode("latin-1", errors="ignore")
        except Exception:
            return ""
        chunks = re.findall(r"\(([^\)]{1,300})\)", s)
        text = " ".join(chunks)
        text = text.replace("\\n", " ").replace("\\r", " ").replace("\\t", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text[:4000]

    @staticmethod
    def _extract_html_text_lite(raw: bytes) -> str:
        try:
            s = raw.decode("utf-8", errors="ignore")
        except Exception:
            try:
                s = raw.decode("latin-1", errors="ignore")
            except Exception:
                return ""
        s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
        s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
        s = re.sub(r"<[^>]+>", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s[:4000]

    def _resolve_pdf_candidate(self, url: str, doi: str = "") -> str:
        """Try to reach a paper PDF from landing pages via lightweight web exploration."""
        candidates = []
        if url:
            candidates.append(url)
        if doi:
            d = doi.replace("https://doi.org/", "").strip()
            if d:
                candidates.append(f"https://doi.org/{d}")

        seen = set()
        for c in candidates:
            if not c or c in seen:
                continue
            seen.add(c)
            try:
                req = urllib.request.Request(c, headers={"User-Agent": "Katala-Quantum/1.0"})
                with urllib.request.urlopen(req, timeout=4.0) as r:
                    final_url = (r.geturl() or c)
                    ct = (r.headers.get("Content-Type") or "").lower()
                    raw = r.read(250000)
                if "pdf" in ct or final_url.lower().endswith(".pdf") or raw.startswith(b"%PDF-"):
                    return final_url

                html = raw.decode("utf-8", errors="ignore")
                links = re.findall(r"href=[\"']([^\"']+)[\"']", html, flags=re.I)
                for lk in links:
                    lk2 = urllib.parse.urljoin(final_url, lk)
                    ll = lk2.lower()
                    if any(k in ll for k in [".pdf", "/pdf", "download", "fulltext", "articlepdf", "viewpdf"]):
                        return lk2
            except Exception:
                continue

        return url

    def _paper_stats(self, refs: dict[str, Any]) -> dict[str, Any]:
        items = (refs or {}).get("items") or []
        total = len(items)
        pdf_readable = 0

        # try as many as possible but cap for latency
        for it in items[:50]:
            if not isinstance(it, dict):
                continue
            url = (it.get("url") or "")
            doi = (it.get("doi") or "")
            probe_url = self._resolve_pdf_candidate(url, doi)
            if self._is_pdf_readable(probe_url):
                pdf_readable += 1

        ratio = (pdf_readable / total) if total else 0.0
        return {
            "refs_count": total,
            "pdf_readable_count": pdf_readable,
            "pdf_readable_ratio": round(ratio, 3),
        }

    def _literature_read_sweep(self, refs: dict[str, Any], pdf_target: int = 40, text_target: int = 40) -> dict[str, Any]:
        items = (refs or {}).get("items") or []
        pdf_ok = 0
        text_ok = 0
        pdf_titles = []
        text_titles = []
        errors = 0
        reason_counts: dict[str, int] = {}
        host_failures: dict[str, int] = {}
        batch_summaries = []
        pdf_method_counts: dict[str, int] = {}

        batch_size = 10
        max_retries = 2

        def _reason_from_exc(exc: Exception) -> str:
            e = str(exc).lower()
            if "timed out" in e:
                return "timeout"
            if "http error 401" in e or "http error 403" in e:
                return "auth_blocked"
            if "http error 429" in e:
                return "rate_limited"
            if "http error" in e:
                return "http_error"
            if "name or service not known" in e or "temporary failure" in e:
                return "dns_error"
            return "network_error"

        for bstart in range(0, len(items), batch_size):
            if pdf_ok >= pdf_target and text_ok >= text_target:
                break

            chunk = items[bstart:bstart + batch_size]
            b_ok = 0
            b_err = 0
            b_reasons: dict[str, int] = {}

            for it in chunk:
                if pdf_ok >= pdf_target and text_ok >= text_target:
                    break
                if not isinstance(it, dict):
                    continue
                url = (it.get("url") or "").strip()
                doi = (it.get("doi") or "").strip()
                title = (it.get("title") or "").strip()[:120]
                if not url and not doi:
                    continue
                resolved_url = self._resolve_pdf_candidate(url, doi)

                from urllib.parse import urlparse
                host = (urlparse(resolved_url).netloc or "unknown").lower()

                success = False
                last_reason = "unknown"
                for attempt in range(max_retries + 1):
                    try:
                        req = urllib.request.Request(resolved_url, headers={"User-Agent": "Katala-Quantum/1.0"})
                        with urllib.request.urlopen(req, timeout=3.0 + attempt) as r:
                            raw = r.read(200000)
                            ct = (r.headers.get("Content-Type") or "").lower()

                        is_pdf = ("pdf" in ct) or resolved_url.lower().endswith(".pdf") or raw.startswith(b"%PDF-")
                        if is_pdf and pdf_ok < pdf_target:
                            kres = extract_pdf_text_kq(raw)
                            txt = (kres.get("text") or "")
                            method = str(kres.get("method", "unknown"))
                            if len((txt or "").strip()) < 120:
                                txt = self._extract_pdf_text_lite(raw)
                                method = "lite"
                            if len((txt or "").strip()) >= 120:
                                pdf_ok += 1
                                pdf_titles.append(title or url)
                                pdf_method_counts[method] = pdf_method_counts.get(method, 0) + 1
                                success = True
                                break
                            last_reason = "thin_pdf_content"
                        elif (not is_pdf) and text_ok < text_target:
                            txt = self._extract_html_text_lite(raw)
                            if len(txt) >= 120:
                                text_ok += 1
                                text_titles.append(title or url)
                                success = True
                                break
                            last_reason = "thin_html_content"
                        else:
                            success = True
                            break
                    except Exception as e:
                        last_reason = _reason_from_exc(e)
                        if attempt < max_retries:
                            time.sleep(0.15 * (attempt + 1))

                if success:
                    b_ok += 1
                else:
                    errors += 1
                    b_err += 1
                    reason_counts[last_reason] = reason_counts.get(last_reason, 0) + 1
                    b_reasons[last_reason] = b_reasons.get(last_reason, 0) + 1
                    host_failures[host] = host_failures.get(host, 0) + 1

            batch_summaries.append({
                "batch": len(batch_summaries) + 1,
                "size": len(chunk),
                "ok": b_ok,
                "errors": b_err,
                "reasons": b_reasons,
            })

        # runtime-only local counters are not persisted outside output payload
        return {
            "pdf_target": pdf_target,
            "text_target": text_target,
            "pdf_read_count": pdf_ok,
            "text_read_count": text_ok,
            "pdf_target_met": pdf_ok >= pdf_target,
            "text_target_met": text_ok >= text_target,
            "pdf_titles_sample": pdf_titles[:10],
            "text_titles_sample": text_titles[:10],
            "errors": errors,
            "batch_summaries": batch_summaries,
            "reason_counts": reason_counts,
            "host_failures": host_failures,
            "kq_pdf_reader": {
                "enabled": True,
                "method_counts": pdf_method_counts,
            },
        }

    def _html_first_pipeline(self, refs: dict[str, Any], limit: int = 20) -> dict[str, Any]:
        if not _HAS_PEER_REACH:
            return {
                "enabled": False,
                "reason": "peer_review_reach_unavailable",
                "reachability": {},
                "html_hits": [],
            }

        reach = check_reachability()
        items = (refs or {}).get("items") or []
        html_hits = []
        scanned = 0

        for it in items:
            if scanned >= limit:
                break
            if not isinstance(it, dict):
                continue
            n = normalize_item(it)
            t = trace_html_fulltext(n.get("url", ""), n.get("doi", ""))
            scanned += 1
            if t.get("ok"):
                html_hits.append({
                    "title": n.get("title"),
                    "doi": n.get("doi"),
                    "final_url": t.get("final_url"),
                    "text_len": t.get("text_len"),
                    "text_preview": t.get("text_preview"),
                    "source": n.get("source"),
                })

        return {
            "enabled": True,
            "reachability": reach,
            "scanned": scanned,
            "html_hit_count": len(html_hits),
            "html_hits": html_hits[:10],
        }

    @staticmethod
    def _math_logic_priority(text: str) -> dict[str, Any]:
        t = (text or "").lower()
        hits = {
            "symbolic_formula": bool(re.search(r"(vars\s*:|formula\s*:|\bforall\b|\bexists\b|\bmu\b|\bnu\b)", t)),
            "equational_claim": bool(re.search(r"(==|!=|<=|>=|\bx\b\s*\*\s*\bx\b|\bproof\b|\btheorem\b)", t)),
            "logic_keywords": bool(re.search(r"(logic|論理|数学|数理|model\s*check|smt|sat|ctl|ltl)", t)),
        }
        score = sum(1 for v in hits.values() if v) / 3.0
        return {
            "enabled": True,
            "signals": hits,
            "priority_score": round(score, 3),
            "priority": "high" if score >= 0.67 else ("medium" if score >= 0.34 else "normal"),
        }

    @staticmethod
    def _search_result_scrutiny(refs: dict[str, Any], html_pipeline: dict[str, Any]) -> dict[str, Any]:
        items = (refs or {}).get("items") or []
        total = len(items)
        doi_count = 0
        journal_count = 0
        title_seen = set()
        dup = 0
        trusted_domains = {"doi.org", "arxiv.org", "nature.com", "science.org", "springer.com", "wiley.com", "sciencedirect.com", "jstor.org"}
        trusted_hits = 0

        for it in items:
            if not isinstance(it, dict):
                continue
            title = (it.get("title") or "").strip().lower()
            if title:
                if title in title_seen:
                    dup += 1
                title_seen.add(title)
            if (it.get("doi") or "").strip():
                doi_count += 1
            if (it.get("journal") or "").strip():
                journal_count += 1
            u = (it.get("url") or "").lower()
            if any(d in u for d in trusted_domains):
                trusted_hits += 1

        doi_ratio = (doi_count / total) if total else 0.0
        journal_ratio = (journal_count / total) if total else 0.0
        dup_ratio = (dup / total) if total else 0.0
        trusted_ratio = (trusted_hits / total) if total else 0.0
        html_hits = float((html_pipeline or {}).get("html_hit_count", 0) or 0)

        scrutiny_score = max(0.0, min(1.0, (doi_ratio * 0.35) + (journal_ratio * 0.25) + (trusted_ratio * 0.25) + min(0.15, html_hits * 0.01) - (dup_ratio * 0.2)))
        return {
            "refs_total": total,
            "doi_ratio": round(doi_ratio, 3),
            "journal_ratio": round(journal_ratio, 3),
            "trusted_domain_ratio": round(trusted_ratio, 3),
            "duplicate_ratio": round(dup_ratio, 3),
            "html_hit_count": int(html_hits),
            "scrutiny_score": round(scrutiny_score, 3),
        }

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if not isinstance(r, dict):
            return r

        text = ""
        if args:
            c = args[0]
            text = c.text if hasattr(c, "text") else str(c)
        elif "claim" in kwargs:
            c = kwargs.get("claim")
            text = c.text if hasattr(c, "text") else str(c)

        refs = r.get("external_peer_review_refs") or {}
        refs = self._augment_refs_with_ks_search(text, refs, target_total=80)
        html_pipeline = self._html_first_pipeline(refs, limit=24)
        p = self._paper_stats(refs)
        sweep = self._literature_read_sweep(refs, pdf_target=40, text_target=40)

        # Re-tune fusion weights using literature quality + actual readability sweep
        kq_score = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
        ref_bonus = min(0.08, p["refs_count"] * 0.004)
        pdf_bonus = min(0.10, p["pdf_readable_ratio"] * 0.10)
        html_bonus = min(0.08, float(html_pipeline.get("html_hit_count", 0)) * 0.003)
        sweep_bonus = min(0.12, (sweep["pdf_read_count"] + sweep["text_read_count"]) * 0.002)

        # Priority dimensions: math/logical reasoning and peer-reviewed scrutiny
        logic_priority = self._math_logic_priority(text)
        scrutiny = self._search_result_scrutiny(refs, html_pipeline)
        logic_bonus = min(0.10, float(logic_priority.get("priority_score", 0.0)) * 0.10)
        scrutiny_bonus = min(0.12, float(scrutiny.get("scrutiny_score", 0.0)) * 0.12)

        # baseline 0.78, literature+logic scrutiny contributes up to +0.34
        fused = self._clamp(kq_score * 0.78 + (0.5 + ref_bonus + pdf_bonus + sweep_bonus + html_bonus + logic_bonus + scrutiny_bonus) * 0.22)

        r["final_score"] = fused
        r["confidence"] = fused

        if fused >= 0.82:
            r["verdict"] = "SUPPORT"
        elif fused >= 0.66:
            r["verdict"] = "LEAN_SUPPORT"
        elif fused >= 0.45:
            r["verdict"] = "UNCERTAIN"
        else:
            r["verdict"] = "LEAN_REJECT"

        r["kq_revision"] = "02a-r9"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        connected_coverage = [
            "query_coverage",
            "search_depth",
            "synthesis_quality",
            "citation_verify",
            "orchestration",
            "symbolic_sat_lite",
            "symbolic_smt_lite",
            "symbolic_temporal_ltl_ctl_mu",
            "symbolic_hol_zfc_lite",
        ] if _HAS_KQ_SYMBOLIC else [
            "query_coverage",
            "search_depth",
            "synthesis_quality",
            "citation_verify",
            "orchestration",
        ]
        r["ks47_parity_pack"] = {
            "available": True,
            "status": "connected",
            "mode": "kq-native-parity",
        }
        r["ks47_quantum_pack"] = {
            "available": _HAS_KQ_SYMBOLIC,
            "status": "connected" if _HAS_KQ_SYMBOLIC else "partial",
            "mode": "kq-symbolic-bridge" if _HAS_KQ_SYMBOLIC else "kq-core-only",
        }
        r["solver_coverage_parity"] = {
            "target": [
                "query_coverage",
                "search_depth",
                "synthesis_quality",
                "citation_verify",
                "orchestration",
                "symbolic_sat_lite",
                "symbolic_smt_lite",
                "symbolic_temporal_ltl_ctl_mu",
                "symbolic_hol_zfc_lite",
            ],
            "covered": connected_coverage,
            "status": "connected" if _HAS_KQ_SYMBOLIC else "partial",
        }
        r["paper_stats"] = p
        r["paper_read_sweep"] = sweep
        r["html_first_pipeline"] = html_pipeline
        r["math_logic_priority"] = logic_priority
        r["search_result_scrutiny"] = scrutiny
        r["new_issues"] = [
            "Landing pages now explored for PDF links, but paywalled hosts still block full text",
            "Some DOI redirects require JavaScript/session cookies and cannot be resolved via lightweight fetch",
            "KS pdf_reader path can fail when pdfplumber/pytesseract unavailable",
            "40-PDF target may still require provider-level OA filters and multi-hop retries",
        ]
        r["fusion_weights"] = {
            "kq_base_weight": 0.78,
            "literature_weight": 0.22,
            "ref_bonus": round(ref_bonus, 3),
            "pdf_bonus": round(pdf_bonus, 3),
            "sweep_bonus": round(sweep_bonus, 3),
            "html_bonus": round(html_bonus, 3),
            "logic_bonus": round(logic_bonus, 3),
            "scrutiny_bonus": round(scrutiny_bonus, 3),
        }

        return r


KQ02a = Katala_Quantum_02a

__all__ = ["Katala_Quantum_02a", "KQ02a"]
