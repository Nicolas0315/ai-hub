"""
Katala_Quantum_01a (KQ01a)
[Katala_Quantum][KQ]シリーズを使用

KSi1次世代機: 量子エミュ主導の制御探索モデル。
- 指定がなければ本モデルを優先使用
- 制御探索を量子エミュレーション経路で実行
- KS実測重み（KS29/S28）を取り込んだ推論強化版
"""
from __future__ import annotations

import os
from typing import Any

from .inf_coding_adapter import emit_bridge_output

try:
    from katala_quantum.emulator import QuantumCircuit
    _HAS_QEMU = True
except Exception:
    _HAS_QEMU = False

# KS29/S28 実測由来重み（ks29.py から採用）
S28_WEIGHT_A_DATA_HASH: float = 0.35
S28_WEIGHT_B_REPRODUCIBILITY: float = 0.25
S28_WEIGHT_C_CONSENSUS: float = 0.25
S28_WEIGHT_D_DETERMINISM: float = 0.15

KS29_KS27_WEIGHT: float = 0.75
KS29_S28_WEIGHT: float = 0.25


class Katala_Quantum_01a:
    SYSTEM_NAME: str = "Katala_Quantum"
    SYSTEM_MODEL: str = "Katala_Quantum_01a"
    ALIAS: str = "KQ01a"
    SERIES: str = "[Katala_Quantum][KQ]シリーズを使用"
    GPU_BUDGET_TARGET: float = 0.20

    def bridge_status(self) -> dict[str, Any]:
        gpu_budget = float(os.getenv("KQ_GPU_BUDGET", str(self.GPU_BUDGET_TARGET)))
        return {
            "system": self.SYSTEM_NAME,
            "model": self.SYSTEM_MODEL,
            "alias": self.ALIAS,
            "series": self.SERIES,
            "quantum_control_only": True,
            "quantum_emulator_available": _HAS_QEMU,
            "ks_weighted_reasoning": True,
            "adaptive_quantum_probe": True,
            "gpu_budget_target": max(0.05, min(0.95, gpu_budget)),
        }

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    def _quantum_route_probe(self, text: str) -> dict[str, Any]:
        """量子エミュ経由でfast/strict傾向を推定する（適応ショット/適応量子ビット）。"""
        t = text.lower()
        gpu_budget = max(0.05, min(0.95, float(os.getenv("KQ_GPU_BUDGET", str(self.GPU_BUDGET_TARGET)))))

        risky_tokens = ["rm", "--force", "push", "rebase", "reset", "drop", "kubectl", "docker"]
        safe_tokens = ["status", "diff", "log", "ls", "grep", "find", "py_compile", "test", "build"]
        risk_hits = sum(1 for k in risky_tokens if k in t)
        safe_hits = sum(1 for k in safe_tokens if k in t)

        complexity = len(t.split()) + risk_hits * 3
        # budget 20% 付近を基準に、探索負荷を制御
        shots = int(max(128, min(1024, 128 + complexity * 6 + gpu_budget * 320)))
        n_qubits = 3 if (complexity > 24 or risk_hits >= 2) else 2

        if not _HAS_QEMU:
            score = self._clamp(0.5 + safe_hits * 0.02 - risk_hits * 0.04)
            return {
                "score": score,
                "mode": "quantum-fallback",
                "detail": {
                    "reason": "emulator-unavailable",
                    "risk_hits": risk_hits,
                    "safe_hits": safe_hits,
                    "shots": shots,
                    "n_qubits": n_qubits,
                    "gpu_budget": gpu_budget,
                },
            }

        qc = QuantumCircuit(n_qubits)
        qc.h(0)
        qc.h(1)
        if n_qubits == 3:
            qc.h(2)

        qc.ry(0, min(1.2, 0.2 + risk_hits * 0.2))
        qc.rx(1, max(0.1, 0.8 - safe_hits * 0.1))
        qc.cx(0, 1)
        if n_qubits == 3:
            qc.rz(2, min(1.3, 0.3 + complexity * 0.01))
            qc.cx(1, 2)
        qc.measure_all()
        r = qc.run(shots=shots)

        m = r.measurements or {}
        strict_keys = [k for k in m.keys() if k.endswith("1") or k.startswith("1")]
        strict_mass = sum(m.get(k, 0) for k in strict_keys) / max(1, sum(m.values()))
        score = 1.0 - strict_mass
        return {
            "score": round(self._clamp(score), 3),
            "mode": "quantum-emulated-control",
            "detail": {
                "risk_hits": risk_hits,
                "safe_hits": safe_hits,
                "strict_mass": round(strict_mass, 3),
                "shots": shots,
                "n_qubits": n_qubits,
                "gpu_budget": gpu_budget,
                "complexity": complexity,
            },
        }

    def _s28_style_components(self, text: str, q_score: float) -> dict[str, float]:
        """KS29 S28構造をKQに移植した軽量推論コンポーネント。"""
        t = text.lower()

        # A: data-hash相当（入力仕様の明確さ）
        has_structured_meta = any(k in t for k in ["hash", "sha", "evidence", "source", "metadata"])
        a = 1.0 if has_structured_meta else 0.6

        # B: reproducibility相当（量子探索の再現度 proxy）
        b = self._clamp(0.55 + (q_score - 0.5) * 0.9)

        # C: consensus相当（命令の整合/矛盾少なさ）
        conflict_markers = ["but", "however", "except", "ただし", "一方で"]
        c = 0.7 if any(k in t for k in conflict_markers) else 0.88

        # D: determinism相当（決定性が必要か）
        deterministic_markers = ["must", "必ず", "固定", "deterministic", "再現"]
        d = 0.9 if any(k in t for k in deterministic_markers) else 0.78

        return {
            "a_data_hash_like": round(a, 3),
            "b_reproducibility_like": round(b, 3),
            "c_consensus_like": round(c, 3),
            "d_determinism_like": round(d, 3),
        }

    def _enhanced_reasoning_score(self, text: str, q_probe: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        q_score = float(q_probe.get("score", 0.5))
        comps = self._s28_style_components(text, q_score)

        s28_score = (
            comps["a_data_hash_like"] * S28_WEIGHT_A_DATA_HASH
            + comps["b_reproducibility_like"] * S28_WEIGHT_B_REPRODUCIBILITY
            + comps["c_consensus_like"] * S28_WEIGHT_C_CONSENSUS
            + comps["d_determinism_like"] * S28_WEIGHT_D_DETERMINISM
        )

        # KS29 final-score構造を準用: quantum-path(=ks27相当) + s28相当
        final = q_score * KS29_KS27_WEIGHT + s28_score * KS29_S28_WEIGHT
        final = self._clamp(final)

        return round(final, 3), {
            "q_score": round(q_score, 3),
            "s28_like_score": round(s28_score, 3),
            "weights": {
                "ks29_ks27_weight": KS29_KS27_WEIGHT,
                "ks29_s28_weight": KS29_S28_WEIGHT,
                "s28_a": S28_WEIGHT_A_DATA_HASH,
                "s28_b": S28_WEIGHT_B_REPRODUCIBILITY,
                "s28_c": S28_WEIGHT_C_CONSENSUS,
                "s28_d": S28_WEIGHT_D_DETERMINISM,
            },
            "components": comps,
        }

    def verify(self, claim, store=None, skip_s28=True, **kwargs):
        text = claim.text if hasattr(claim, "text") else str(claim)
        probe = self._quantum_route_probe(text)

        enhanced_score, reason = self._enhanced_reasoning_score(text, probe)

        verdict = "SUPPORT" if enhanced_score >= 0.82 else ("LEAN_SUPPORT" if enhanced_score >= 0.66 else ("UNCERTAIN" if enhanced_score >= 0.45 else "LEAN_REJECT"))
        route = "fast" if enhanced_score >= 0.66 else "strict"

        result = {
            "verdict": verdict,
            "confidence": enhanced_score,
            "final_score": enhanced_score,
            "solvers_passed": "quantum-control+ks-weighted/2",
            "mode": probe["mode"],
            "route": route,
            "quantum_probe": probe["detail"],
            "quantum_features": {
                "route_confidence": enhanced_score,
                "probe_mode": probe["mode"],
                "probe_detail": probe["detail"],
            },
            "reasoning": reason,
            "series": self.SERIES,
            "kq_revision": "01a-r1",
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
            "reasoning": reason,
        })
        return result


KQ01a = Katala_Quantum_01a

__all__ = ["Katala_Quantum_01a", "KQ01a"]
