"""
Katala_Quantum_02a (KQ02a)

Successor wrapper for KQ01a-r13 lineage.
Keeps internal engine compatibility while exposing new model id.
"""
from __future__ import annotations

from .katala_quantum_01a import Katala_Quantum_01a


class Katala_Quantum_02a(Katala_Quantum_01a):
    SYSTEM_MODEL: str = "Katala_Quantum_02a"
    ALIAS: str = "KQ02a"

    def bridge_status(self) -> dict:
        s = super().bridge_status()
        s.update({
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
        })
        return s

    def verify(self, *args, **kwargs):
        r = super().verify(*args, **kwargs)
        if isinstance(r, dict):
            r["kq_revision"] = "02a-r1"
            r["model"] = self.SYSTEM_MODEL
            r["alias"] = self.ALIAS
        return r


KQ02a = Katala_Quantum_02a

__all__ = ["Katala_Quantum_02a", "KQ02a"]
