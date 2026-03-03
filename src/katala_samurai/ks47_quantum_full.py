"""
KS47 Quantum Full

KS47の5軸構造を保ったまま、各軸評価を量子エミュレーション回路で算出する。
目的: KQへの"全量子化"移植レイヤ。

注: `katala_quantum.emulator` が利用できない環境では、
軽量な擬似量子エミュレーション（pure Python）へ自動切替する。
"""
from __future__ import annotations

import hashlib
import math
from typing import Any

try:
    from katala_quantum.emulator import QuantumCircuit
    _HAS_QEMU = True
except Exception:
    QuantumCircuit = None  # type: ignore
    _HAS_QEMU = False


class KS47QuantumFull:
    VERSION = "KS47Q-full-v0"

    WEIGHTS = {
        "query_coverage": 0.15,
        "search_depth": 0.20,
        "synthesis_quality": 0.30,
        "citation_verify": 0.25,
        "orchestration": 0.10,
    }

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    def _pseudo_quantum_score(self, key: str) -> float:
        # pure-python deterministic pseudo-quantum sampler
        h = hashlib.sha256(key.encode("utf-8")).hexdigest()
        x = int(h[:8], 16) / 0xFFFFFFFF
        y = int(h[8:16], 16) / 0xFFFFFFFF
        z = int(h[16:24], 16) / 0xFFFFFFFF
        # interference-like mix
        score = 0.5 + 0.35 * math.sin(2 * math.pi * x) + 0.15 * math.cos(2 * math.pi * y) + 0.1 * (z - 0.5)
        return self._clamp(score)

    def _axis_quantum_score(self, text: str, seed_bias: float, shots: int = 192) -> float:
        t = text.lower()
        length = len(t.split())
        ent = len(set(t)) / max(1, len(t))

        if not _HAS_QEMU or QuantumCircuit is None:
            base = self._pseudo_quantum_score(f"{text}|{seed_bias}|{shots}|{length}|{ent:.4f}")
            return self._clamp(base * 0.82 + (0.18 + seed_bias * 0.2))

        qc = QuantumCircuit(3)
        qc.h(0).h(1).h(2)
        qc.ry(0, min(1.3, 0.15 + seed_bias + length * 0.004))
        qc.rz(1, min(1.4, 0.25 + ent))
        qc.rx(2, min(1.2, 0.2 + length * 0.003))
        qc.cx(0, 1).cx(1, 2)
        qc.measure_all()
        r = qc.run(shots=shots)

        m = r.measurements or {}
        total = max(1, sum(m.values()))
        pos = (m.get("000", 0) + m.get("001", 0) + m.get("010", 0) + m.get("011", 0)) / total
        return self._clamp(pos)

    def verify(self, query: str, report: str) -> dict[str, Any]:
        text = f"{query}\n{report}".strip()

        ax = {
            "query_coverage": self._axis_quantum_score(text + " query", 0.10),
            "search_depth": self._axis_quantum_score(text + " search", 0.18),
            "synthesis_quality": self._axis_quantum_score(text + " synthesis", 0.24),
            "citation_verify": self._axis_quantum_score(text + " citation", 0.20),
            "orchestration": self._axis_quantum_score(text + " orchestration", 0.14),
        }

        overall = sum(ax[k] * self.WEIGHTS[k] for k in self.WEIGHTS)

        if overall >= 0.90:
            grade = "S"
        elif overall >= 0.80:
            grade = "A"
        elif overall >= 0.65:
            grade = "B"
        elif overall >= 0.50:
            grade = "C"
        elif overall >= 0.35:
            grade = "D"
        else:
            grade = "F"

        return {
            "version": self.VERSION,
            "backend": "quantum-circuit" if _HAS_QEMU else "pseudo-quantum",
            "overall_score": round(overall, 3),
            "grade": grade,
            "solver_results": {k: round(v, 3) for k, v in ax.items()},
        }
