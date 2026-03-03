"""
Katala_Quantum_02a (KQ02a)

Independent KQ line (KS47 dependency detached).
Adds literature-driven fusion weight tuning based on:
- number of peer-reviewed refs retrieved
- how many references are readable as PDF content
"""
from __future__ import annotations

import re
import urllib.request
from typing import Any

from .katala_quantum_01a import Katala_Quantum_01a


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

    def _paper_stats(self, refs: dict[str, Any]) -> dict[str, Any]:
        items = (refs or {}).get("items") or []
        total = len(items)
        pdf_readable = 0

        # try as many as possible but cap for latency
        for it in items[:50]:
            url = (it.get("url") or "") if isinstance(it, dict) else ""
            if self._is_pdf_readable(url):
                pdf_readable += 1

        ratio = (pdf_readable / total) if total else 0.0
        return {
            "refs_count": total,
            "pdf_readable_count": pdf_readable,
            "pdf_readable_ratio": round(ratio, 3),
        }

    def _literature_read_sweep(self, refs: dict[str, Any], pdf_target: int = 30, text_target: int = 30) -> dict[str, Any]:
        items = (refs or {}).get("items") or []
        pdf_ok = 0
        text_ok = 0
        pdf_titles = []
        text_titles = []
        errors = 0

        for it in items:
            if pdf_ok >= pdf_target and text_ok >= text_target:
                break
            if not isinstance(it, dict):
                continue
            url = (it.get("url") or "").strip()
            title = (it.get("title") or "").strip()[:120]
            if not url:
                continue
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Katala-Quantum/1.0"})
                with urllib.request.urlopen(req, timeout=3.0) as r:
                    raw = r.read(200000)
                    ct = (r.headers.get("Content-Type") or "").lower()

                is_pdf = ("pdf" in ct) or url.lower().endswith(".pdf") or raw.startswith(b"%PDF-")
                if is_pdf and pdf_ok < pdf_target:
                    txt = self._extract_pdf_text_lite(raw)
                    if len(txt) >= 120:
                        pdf_ok += 1
                        pdf_titles.append(title or url)
                elif (not is_pdf) and text_ok < text_target:
                    txt = self._extract_html_text_lite(raw)
                    if len(txt) >= 120:
                        text_ok += 1
                        text_titles.append(title or url)
            except Exception:
                errors += 1

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
        }

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if not isinstance(r, dict):
            return r

        refs = r.get("external_peer_review_refs") or {}
        p = self._paper_stats(refs)
        sweep = self._literature_read_sweep(refs, pdf_target=30, text_target=30)

        # Re-tune fusion weights using literature quality + actual readability sweep
        kq_score = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
        ref_bonus = min(0.08, p["refs_count"] * 0.004)
        pdf_bonus = min(0.10, p["pdf_readable_ratio"] * 0.10)
        sweep_bonus = min(0.12, (sweep["pdf_read_count"] + sweep["text_read_count"]) * 0.002)

        # baseline 0.82, literature/readability contributes up to +0.30
        fused = self._clamp(kq_score * 0.82 + (0.5 + ref_bonus + pdf_bonus + sweep_bonus) * 0.18)

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

        r["kq_revision"] = "02a-r5"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        r["ks47_parity_pack"] = {"available": False, "status": "detached"}
        r["ks47_quantum_pack"] = {"available": False, "status": "detached"}
        r["solver_coverage_parity"] = {
            "target": [
                "query_coverage",
                "search_depth",
                "synthesis_quality",
                "citation_verify",
                "orchestration",
            ],
            "covered": [],
            "status": "detached",
        }
        r["paper_stats"] = p
        r["paper_read_sweep"] = sweep
        r["fusion_weights"] = {
            "kq_base_weight": 0.82,
            "literature_weight": 0.18,
            "ref_bonus": round(ref_bonus, 3),
            "pdf_bonus": round(pdf_bonus, 3),
            "sweep_bonus": round(sweep_bonus, 3),
        }

        return r


KQ02a = Katala_Quantum_02a

__all__ = ["Katala_Quantum_02a", "KQ02a"]
