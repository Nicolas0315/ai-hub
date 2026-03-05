"""
Katala_Quantum_03a (KQ03a)

Version uplift wrapper for the current strongest KQ lane.
Behavior inherits KQ02b while exposing explicit KQ03a system identity.
"""

from __future__ import annotations

from .katala_quantum_02b import Katala_Quantum_02b


class Katala_Quantum_03a(Katala_Quantum_02b):
    SYSTEM_MODEL: str = "Katala_Quantum_03a"
    ALIAS: str = "KQ03a"


KQ03a = Katala_Quantum_03a

__all__ = ["Katala_Quantum_03a", "KQ03a"]
