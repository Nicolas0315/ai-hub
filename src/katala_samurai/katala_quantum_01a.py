"""
Katala_Quantum_01a (KQ01a)
[Kataka_Quantum][KQ]シリーズを使用

KSi1次世代機: 量子エミュ主導の制御探索モデル。
- 指定がなければ本モデルを優先使用
- 制御探索を量子エミュレーション経路で実行
"""
from __future__ import annotations

from typing import Any

from .inf_coding_adapter import emit_bridge_output

try:
    from katala_quantum.emulator import QuantumCircuit
    _HAS_QEMU = True
except Exception:
    _HAS_QEMU = False


class Katala_Quantum_01a:
    SYSTEM_NAME: str = "Katala_Quantum"
    SYSTEM_MODEL: str = "Katala_Quantum_01a"
    ALIAS: str = "KQ01a"
    SERIES: str = "[Katala_Quantum][KQ]シリーズを使用"

    def bridge_status(self) -> dict[str, Any]:
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "series": self.SERIES,
            "quantum_control_only": True,
            "quantum_emulator_available": _HAS_QEMU,
        }

    def _quantum_route_probe(self, text: str) -> dict[str, Any]:
        """量子エミュ経由でfast/strict傾向を推定する。"""
        t = text.lower()
        if not _HAS_QEMU:
            # fail-openではなく保守的
            score = 0.5
            return {"score": score, "mode": "quantum-fallback", "detail": "emulator-unavailable"}

        n_qubits = 2
        qc = QuantumCircuit(n_qubits)
        qc.h(0)
        qc.h(1)

        risky_tokens = ["rm", "--force", "push", "rebase", "reset", "drop", "kubectl", "docker"]
        safe_tokens = ["status", "diff", "log", "ls", "grep", "find", "py_compile", "test", "build"]

        risk_hits = sum(1 for k in risky_tokens if k in t)
        safe_hits = sum(1 for k in safe_tokens if k in t)

        # 回路変調: risky多いと位相を傾ける
        qc.ry(0, min(1.2, 0.2 + risk_hits * 0.2))
        qc.rx(1, max(0.1, 0.8 - safe_hits * 0.1))
        qc.cx(0, 1)
        qc.measure_all()
        r = qc.run(shots=256)

        # strict寄り確率: '11' + '10' を高リスク側とみなす
        m = r.measurements or {}
        strict_mass = (m.get("11", 0) + m.get("10", 0)) / max(1, sum(m.values()))
        score = 1.0 - strict_mass
        return {
            "score": round(max(0.0, min(1.0, score)), 3),
            "mode": "quantum-emulated-control",
            "detail": {
                "risk_hits": risk_hits,
                "safe_hits": safe_hits,
                "strict_mass": round(strict_mass, 3),
                "shots": 256,
            },
        }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        text = claim.text if hasattr(claim, "text") else str(claim)
        probe = self._quantum_route_probe(text)
        conf = float(probe["score"])
        verdict = "LEAN_SUPPORT" if conf >= 0.66 else ("UNCERTAIN" if conf >= 0.45 else "LEAN_REJECT")
        route = "fast" if conf >= 0.66 else "strict"

        result = {
            "verdict": verdict,
            "confidence": round(conf, 3),
            "final_score": round(conf, 3),
            "solvers_passed": "quantum-control/1",
            "mode": probe["mode"],
            "route": route,
            "quantum_probe": probe["detail"],
            "series": self.SERIES,
        }

        emit_bridge_output(self.SYSTEM_MODEL, {
            "alias": self.ALIAS,
            "bridge_status": self.bridge_status(),
            "verdict": result["verdict"],
            "final_score": result["final_score"],
            "confidence": result["confidence"],
            "mode": result["mode"],
            "route": result["route"],
            "series": self.SERIES,
        })
        return result


KQ01a = Katala_Quantum_01a

__all__ = ["Katala_Quantum_01a", "KQ01a"]
