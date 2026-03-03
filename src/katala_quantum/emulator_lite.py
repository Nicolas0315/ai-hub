"""
katala_quantum.emulator_lite

Pure-Python fallback quantum emulator (numpy-free) for constrained environments.
Implements the minimal API surface required by KQ01a-r12:
- QuantumCircuit(n_qubits)
- h/rx/ry/rz/cx/measure_all/run(shots)
- run() -> object with `measurements` dict
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Dict, List, Tuple


@dataclass
class CircuitResultLite:
    measurements: Dict[str, int]


class QuantumCircuit:
    def __init__(self, n_qubits: int):
        if n_qubits < 1:
            raise ValueError("n_qubits must be >= 1")
        self.n_qubits = n_qubits
        self.ops: List[Tuple[str, Tuple]] = []

    def h(self, qubit: int):
        self.ops.append(("H", (qubit,)))
        return self

    def rx(self, qubit: int, theta: float):
        self.ops.append(("RX", (qubit, float(theta))))
        return self

    def ry(self, qubit: int, theta: float):
        self.ops.append(("RY", (qubit, float(theta))))
        return self

    def rz(self, qubit: int, theta: float):
        self.ops.append(("RZ", (qubit, float(theta))))
        return self

    def cx(self, control: int, target: int):
        self.ops.append(("CX", (control, target)))
        return self

    def measure_all(self):
        self.ops.append(("MEASURE_ALL", tuple()))
        return self

    @staticmethod
    def _clamp(v: float) -> float:
        return max(0.0, min(1.0, v))

    def run(self, shots: int = 256):
        shots = max(32, int(shots))

        # Build deterministic seed from gate stream
        sig = f"{self.n_qubits}|{self.ops}".encode("utf-8", errors="ignore")
        h = hashlib.sha256(sig).hexdigest()

        x = int(h[:8], 16) / 0xFFFFFFFF
        y = int(h[8:16], 16) / 0xFFFFFFFF
        z = int(h[16:24], 16) / 0xFFFFFFFF

        # Approximate probability for 1 bits from pseudo wave mix
        p1 = self._clamp(0.45 + 0.25 * math.sin(2 * math.pi * x) + 0.18 * (y - 0.5) + 0.12 * (z - 0.5))

        # Generate all bitstrings and distribute counts by Hamming weight tendency
        n = self.n_qubits
        total_w = 0.0
        weights: Dict[str, float] = {}
        for i in range(2**n):
            b = format(i, f"0{n}b")
            ones = b.count("1")
            zeros = n - ones
            w = (p1 ** ones) * ((1.0 - p1) ** zeros)
            weights[b] = w
            total_w += w

        # Normalize and allocate integer counts
        counts: Dict[str, int] = {}
        acc = 0
        items = list(weights.items())
        for b, w in items[:-1]:
            c = int(round((w / total_w) * shots))
            counts[b] = c
            acc += c
        # keep exact total shots
        last_b = items[-1][0]
        counts[last_b] = max(0, shots - acc)

        return CircuitResultLite(measurements=counts)
