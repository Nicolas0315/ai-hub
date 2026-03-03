"""
Katala_Quantum_02a (KQ02a)

Independent KQ line (KS47 dependency detached).
Adds literature-driven fusion weight tuning based on:
- number of peer-reviewed refs retrieved
- how many references are readable as PDF content
"""
from __future__ import annotations

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

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if not isinstance(r, dict):
            return r

        refs = r.get("external_peer_review_refs") or {}
        p = self._paper_stats(refs)

        # Re-tune fusion weights using literature quality
        # More refs + higher PDF readability => stronger confidence retention
        kq_score = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
        ref_bonus = min(0.08, p["refs_count"] * 0.004)
        pdf_bonus = min(0.10, p["pdf_readable_ratio"] * 0.10)

        # baseline 0.86, literature quality contributes up to +0.18
        fused = self._clamp(kq_score * 0.86 + (0.5 + ref_bonus + pdf_bonus) * 0.14)

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

        r["kq_revision"] = "02a-r4"
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
        r["fusion_weights"] = {
            "kq_base_weight": 0.86,
            "literature_weight": 0.14,
            "ref_bonus": round(ref_bonus, 3),
            "pdf_bonus": round(pdf_bonus, 3),
        }

        return r


KQ02a = Katala_Quantum_02a

__all__ = ["Katala_Quantum_02a", "KQ02a"]
