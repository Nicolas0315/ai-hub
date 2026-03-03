"""
Katala_Quantum_02a (KQ02a)

KQ02a extends KQ01a with KS47 solver-coverage parity pack.
Goal: provide KS47-equivalent axis coverage inside KQ pipeline,
then fuse with quantumized scoring path.
"""
from __future__ import annotations

from typing import Any

from .katala_quantum_01a import Katala_Quantum_01a

try:
    from .ks47_deep_research import KS47
    _HAS_KS47 = True
except Exception:
    _HAS_KS47 = False

try:
    from .ks47_quantum_full import KS47QuantumFull
    _HAS_KS47Q = True
except Exception:
    _HAS_KS47Q = False


class Katala_Quantum_02a(Katala_Quantum_01a):
    SYSTEM_MODEL: str = "Katala_Quantum_02a"
    ALIAS: str = "KQ02a"

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "ks47_solver_parity": _HAS_KS47,
            "ks47_quantum_pack": _HAS_KS47Q,
        })
        return s

    def _ks47_parity_pack(self, text: str) -> dict[str, Any]:
        if not _HAS_KS47:
            return {"available": False, "error": "KS47 unavailable"}

        k = KS47()
        r = k.verify(query=text, report=text).to_dict()
        solver_results = {
            "query_coverage": r["query_coverage"]["score"],
            "search_depth": r["search_depth"]["score"],
            "synthesis_quality": r["synthesis_quality"]["score"],
            "citation_verify": r["citation_verify"]["score"],
            "orchestration": r["orchestration"]["score"],
        }
        return {
            "available": True,
            "overall_score": float(r.get("overall_score", 0.0)),
            "grade": r.get("grade"),
            "solver_results": solver_results,
        }

    def _ks47_quantum_pack(self, text: str) -> dict[str, Any]:
        if not _HAS_KS47Q:
            return {"available": False, "error": "KS47QuantumFull unavailable"}
        try:
            r = KS47QuantumFull().verify(query=text, report=text)
            return {"available": True, **r}
        except Exception as e:
            return {"available": False, "error": str(e)}

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

        ks47p = self._ks47_parity_pack(text)
        ks47q = self._ks47_quantum_pack(text)

        # fuse parity signal into KQ final score (moderate weight to preserve KQ identity)
        kq_score = float(r.get("final_score", r.get("confidence", 0.5)) or 0.5)
        ks_score = float(ks47p.get("overall_score", 0.0)) if ks47p.get("available") else 0.0
        ksq_score = float(ks47q.get("overall_score", 0.0)) if ks47q.get("available") else 0.0

        fused = self._clamp(kq_score * 0.62 + ks_score * 0.23 + ksq_score * 0.15)
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

        r["kq_revision"] = "02a-r2"
        r["model"] = self.SYSTEM_MODEL
        r["alias"] = self.ALIAS
        r["ks47_parity_pack"] = ks47p
        r["ks47_quantum_pack"] = ks47q
        r["solver_coverage_parity"] = {
            "target": [
                "query_coverage",
                "search_depth",
                "synthesis_quality",
                "citation_verify",
                "orchestration",
            ],
            "covered": list((ks47p.get("solver_results") or {}).keys()) if ks47p.get("available") else [],
            "status": "full" if ks47p.get("available") else "partial",
        }

        return r


KQ02a = Katala_Quantum_02a

__all__ = ["Katala_Quantum_02a", "KQ02a"]
