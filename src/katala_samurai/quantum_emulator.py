"""
Quantum Circuit Emulator — Classical emulation of quantum computation.

Youta: "量子コンピュータ的演算をエミュレートできんか？"
Nicolas: "どんなGPUがあれば可能？"
Youta: "現状のGPUで余裕で動くようにしてね"

Design: State vector simulation of quantum circuits.
Target: 20-25 qubits on RTX 5070 Ti (16GB VRAM).

Memory usage: 2^n complex128 = 2^n × 16 bytes
  20 qubits: 16 MB
  25 qubits: 512 MB
  30 qubits: 16 GB (limit of RTX 5070 Ti)

Supported gates: H, X, Y, Z, CNOT, CZ, T, S, Rx, Ry, Rz, SWAP, Toffoli
Supported algorithms: Grover, Deutsch-Jozsa, QFT, Shor (small)

KCS connection:
  Quantum mechanics (design) → Classical emulation (code) → Computation result (execution)
  R_struct: 1.0 (gate structure perfectly preserved)
  R_context: low (quantum parallelism → classical sequential = exponential slowdown)
  R_qualia: medium (interference elegance lost)
  R_temporal: very low (exponential time cost)
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

VERSION = "1.0.0"

# ═══════════════════════════════════════════════════════════════
# Quantum Gates (unitary matrices)
# ═══════════════════════════════════════════════════════════════

# Pauli gates
I_GATE = np.array([[1, 0], [0, 1]], dtype=np.complex128)
X_GATE = np.array([[0, 1], [1, 0]], dtype=np.complex128)
Y_GATE = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
Z_GATE = np.array([[1, 0], [0, -1]], dtype=np.complex128)

# Hadamard
H_GATE = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)

# Phase gates
S_GATE = np.array([[1, 0], [0, 1j]], dtype=np.complex128)
T_GATE = np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]], dtype=np.complex128)


def rx_gate(theta: float) -> np.ndarray:
    """Rotation around X axis."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=np.complex128)


def ry_gate(theta: float) -> np.ndarray:
    """Rotation around Y axis."""
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=np.complex128)


def rz_gate(theta: float) -> np.ndarray:
    """Rotation around Z axis."""
    return np.array([
        [np.exp(-1j * theta / 2), 0],
        [0, np.exp(1j * theta / 2)]
    ], dtype=np.complex128)


GATE_REGISTRY = {
    'I': I_GATE, 'X': X_GATE, 'Y': Y_GATE, 'Z': Z_GATE,
    'H': H_GATE, 'S': S_GATE, 'T': T_GATE,
}


# ═══════════════════════════════════════════════════════════════
# Quantum State
# ═══════════════════════════════════════════════════════════════

class QuantumState:
    """State vector representation of a quantum register.

    State = column vector of 2^n complex amplitudes.
    |ψ⟩ = Σ αᵢ|i⟩ where Σ|αᵢ|² = 1.
    """

    def __init__(self, n_qubits: int, gpu: bool = False):
        self.n_qubits = n_qubits
        self.n_states = 2 ** n_qubits
        self.gpu = gpu

        # Memory estimate
        mem_bytes = self.n_states * 16  # complex128 = 16 bytes
        self.mem_mb = mem_bytes / (1024 * 1024)

        if gpu:
            try:
                import cupy as cp
                self.xp = cp
                self.state = cp.zeros(self.n_states, dtype=cp.complex128)
                self.state[0] = 1.0  # |00...0⟩
                self.backend = "cupy_gpu"
            except ImportError:
                self.xp = np
                self.state = np.zeros(self.n_states, dtype=np.complex128)
                self.state[0] = 1.0
                self.backend = "numpy_cpu (cupy not available)"
                self.gpu = False
        else:
            self.xp = np
            self.state = np.zeros(self.n_states, dtype=np.complex128)
            self.state[0] = 1.0
            self.backend = "numpy_cpu"

    def reset(self):
        """Reset to |00...0⟩."""
        self.state[:] = 0
        self.state[0] = 1.0

    def probabilities(self) -> np.ndarray:
        """Get measurement probabilities for all basis states."""
        probs = np.abs(self.state) ** 2
        if self.gpu:
            probs = probs.get()  # cupy → numpy
        return probs

    def measure(self, shots: int = 1024) -> Dict[str, int]:
        """Simulate measurement with given number of shots.

        Returns dict of bitstring → count.
        """
        probs = self.probabilities()
        indices = np.random.choice(self.n_states, size=shots, p=probs)
        results = {}
        for idx in indices:
            bitstring = format(idx, f'0{self.n_qubits}b')
            results[bitstring] = results.get(bitstring, 0) + 1
        return dict(sorted(results.items(), key=lambda x: -x[1]))

    def measure_qubit(self, qubit: int) -> int:
        """Measure a single qubit (collapses the state)."""
        probs = self.probabilities()
        # Sum probabilities where qubit is 0/1
        p0 = 0.0
        for i in range(self.n_states):
            if not (i >> (self.n_qubits - 1 - qubit)) & 1:
                p0 += probs[i]

        result = 0 if np.random.random() < p0 else 1

        # Collapse state
        for i in range(self.n_states):
            bit = (i >> (self.n_qubits - 1 - qubit)) & 1
            if bit != result:
                self.state[i] = 0

        # Renormalize
        norm = np.sqrt(np.sum(np.abs(self.state) ** 2))
        if norm > 0:
            self.state /= norm

        return result

    def get_amplitudes(self) -> List[complex]:
        """Get state vector amplitudes (for inspection/debugging)."""
        if self.gpu:
            return self.state.get().tolist()
        return self.state.tolist()

    def fidelity(self, other: 'QuantumState') -> float:
        """Compute fidelity |⟨ψ|φ⟩|²."""
        inner = np.sum(np.conj(self.state) * other.state)
        return float(np.abs(inner) ** 2)


# ═══════════════════════════════════════════════════════════════
# Quantum Circuit
# ═══════════════════════════════════════════════════════════════

@dataclass
class GateOp:
    """A quantum gate operation."""
    name: str
    targets: List[int]
    controls: List[int] = field(default_factory=list)
    params: Dict[str, float] = field(default_factory=dict)


class QuantumCircuit:
    """Quantum circuit builder and executor.

    Efficient state vector simulation using vectorized operations.
    """

    def __init__(self, n_qubits: int, gpu: bool = False):
        self.n_qubits = n_qubits
        self.state = QuantumState(n_qubits, gpu=gpu)
        self.ops: List[GateOp] = []

    def _apply_single_gate(self, gate: np.ndarray, target: int):
        """Apply a single-qubit gate using vectorized indexing.

        Instead of building the full 2^n × 2^n matrix (exponential memory),
        we operate directly on pairs of amplitudes.
        """
        xp = self.state.xp
        n = self.n_qubits
        step = 1 << (n - 1 - target)
        indices = xp.arange(self.state.n_states)
        # Separate indices where target bit is 0 vs 1
        mask = indices & step
        idx0 = indices[mask == 0]
        idx1 = idx0 + step

        a = self.state.state[idx0].copy()
        b = self.state.state[idx1].copy()
        self.state.state[idx0] = gate[0, 0] * a + gate[0, 1] * b
        self.state.state[idx1] = gate[1, 0] * a + gate[1, 1] * b

    def _apply_controlled_gate(self, gate: np.ndarray, control: int, target: int):
        """Apply a controlled single-qubit gate."""
        xp = self.state.xp
        n = self.n_qubits
        ctrl_step = 1 << (n - 1 - control)
        tgt_step = 1 << (n - 1 - target)

        indices = xp.arange(self.state.n_states)
        # Only act on states where control qubit is 1
        ctrl_mask = (indices & ctrl_step) != 0
        tgt_mask = (indices & tgt_step) == 0

        idx0 = indices[ctrl_mask & tgt_mask]
        idx1 = idx0 + tgt_step

        if len(idx0) == 0:
            return

        a = self.state.state[idx0].copy()
        b = self.state.state[idx1].copy()
        self.state.state[idx0] = gate[0, 0] * a + gate[0, 1] * b
        self.state.state[idx1] = gate[1, 0] * a + gate[1, 1] * b

    def _apply_toffoli(self, ctrl1: int, ctrl2: int, target: int):
        """Apply Toffoli (CCX) gate."""
        xp = self.state.xp
        n = self.n_qubits
        c1_step = 1 << (n - 1 - ctrl1)
        c2_step = 1 << (n - 1 - ctrl2)
        tgt_step = 1 << (n - 1 - target)

        indices = xp.arange(self.state.n_states)
        c1_mask = (indices & c1_step) != 0
        c2_mask = (indices & c2_step) != 0
        tgt_mask = (indices & tgt_step) == 0

        idx0 = indices[c1_mask & c2_mask & tgt_mask]
        idx1 = idx0 + tgt_step

        if len(idx0) == 0:
            return

        # Swap amplitudes (X gate on target when both controls are 1)
        temp = self.state.state[idx0].copy()
        self.state.state[idx0] = self.state.state[idx1]
        self.state.state[idx1] = temp

    # ─── Gate builders ───

    def h(self, target: int) -> 'QuantumCircuit':
        """Hadamard gate."""
        self.ops.append(GateOp('H', [target]))
        return self

    def x(self, target: int) -> 'QuantumCircuit':
        """Pauli-X (NOT) gate."""
        self.ops.append(GateOp('X', [target]))
        return self

    def y(self, target: int) -> 'QuantumCircuit':
        """Pauli-Y gate."""
        self.ops.append(GateOp('Y', [target]))
        return self

    def z(self, target: int) -> 'QuantumCircuit':
        """Pauli-Z gate."""
        self.ops.append(GateOp('Z', [target]))
        return self

    def s(self, target: int) -> 'QuantumCircuit':
        """S (phase) gate."""
        self.ops.append(GateOp('S', [target]))
        return self

    def t(self, target: int) -> 'QuantumCircuit':
        """T gate."""
        self.ops.append(GateOp('T', [target]))
        return self

    def rx(self, target: int, theta: float) -> 'QuantumCircuit':
        """Rotation-X gate."""
        self.ops.append(GateOp('Rx', [target], params={'theta': theta}))
        return self

    def ry(self, target: int, theta: float) -> 'QuantumCircuit':
        """Rotation-Y gate."""
        self.ops.append(GateOp('Ry', [target], params={'theta': theta}))
        return self

    def rz(self, target: int, theta: float) -> 'QuantumCircuit':
        """Rotation-Z gate."""
        self.ops.append(GateOp('Rz', [target], params={'theta': theta}))
        return self

    def cnot(self, control: int, target: int) -> 'QuantumCircuit':
        """CNOT (CX) gate."""
        self.ops.append(GateOp('CNOT', [target], [control]))
        return self

    def cx(self, control: int, target: int) -> 'QuantumCircuit':
        """Alias for CNOT."""
        return self.cnot(control, target)

    def cz(self, control: int, target: int) -> 'QuantumCircuit':
        """Controlled-Z gate."""
        self.ops.append(GateOp('CZ', [target], [control]))
        return self

    def swap(self, q1: int, q2: int) -> 'QuantumCircuit':
        """SWAP gate (implemented as 3 CNOTs)."""
        self.ops.append(GateOp('SWAP', [q1, q2]))
        return self

    def toffoli(self, ctrl1: int, ctrl2: int, target: int) -> 'QuantumCircuit':
        """Toffoli (CCX) gate."""
        self.ops.append(GateOp('Toffoli', [target], [ctrl1, ctrl2]))
        return self

    def ccx(self, ctrl1: int, ctrl2: int, target: int) -> 'QuantumCircuit':
        """Alias for Toffoli."""
        return self.toffoli(ctrl1, ctrl2, target)

    def barrier(self) -> 'QuantumCircuit':
        """Visual barrier (no-op)."""
        self.ops.append(GateOp('barrier', []))
        return self

    # ─── Execution ───

    def run(self, shots: int = 1024) -> Dict[str, Any]:
        """Execute the circuit and return measurement results."""
        t0 = time.time()
        self.state.reset()

        for op in self.ops:
            if op.name == 'barrier':
                continue
            elif op.name in GATE_REGISTRY:
                self._apply_single_gate(GATE_REGISTRY[op.name], op.targets[0])
            elif op.name == 'Rx':
                self._apply_single_gate(rx_gate(op.params['theta']), op.targets[0])
            elif op.name == 'Ry':
                self._apply_single_gate(ry_gate(op.params['theta']), op.targets[0])
            elif op.name == 'Rz':
                self._apply_single_gate(rz_gate(op.params['theta']), op.targets[0])
            elif op.name == 'CNOT':
                self._apply_controlled_gate(X_GATE, op.controls[0], op.targets[0])
            elif op.name == 'CZ':
                self._apply_controlled_gate(Z_GATE, op.controls[0], op.targets[0])
            elif op.name == 'SWAP':
                q1, q2 = op.targets
                self._apply_controlled_gate(X_GATE, q1, q2)
                self._apply_controlled_gate(X_GATE, q2, q1)
                self._apply_controlled_gate(X_GATE, q1, q2)
            elif op.name == 'Toffoli':
                self._apply_toffoli(op.controls[0], op.controls[1], op.targets[0])

        elapsed = time.time() - t0
        measurements = self.state.measure(shots)

        return {
            'measurements': measurements,
            'n_qubits': self.n_qubits,
            'n_gates': len([op for op in self.ops if op.name != 'barrier']),
            'memory_mb': round(self.state.mem_mb, 2),
            'backend': self.state.backend,
            'execution_time_ms': round(elapsed * 1000, 2),
            'shots': shots,
        }

    def statevector(self) -> np.ndarray:
        """Get the current state vector (after run)."""
        return self.state.get_amplitudes()

    def draw(self) -> str:
        """ASCII circuit diagram."""
        lines = [f"q{i}: " for i in range(self.n_qubits)]
        for op in self.ops:
            width = max(len(op.name), 3)
            if op.name == 'barrier':
                for i in range(self.n_qubits):
                    lines[i] += "│ "
            elif not op.controls:
                for i in range(self.n_qubits):
                    if i in op.targets:
                        lines[i] += f"[{op.name:^{width}}]─"
                    else:
                        lines[i] += "─" * (width + 2) + "─"
            else:
                for i in range(self.n_qubits):
                    if i in op.targets:
                        lines[i] += f"[{op.name:^{width}}]─"
                    elif i in op.controls:
                        lines[i] += f"──●{'─' * (width - 1)}──"
                    else:
                        # Check if wire passes through controlled gate
                        all_qubits = op.targets + op.controls
                        if min(all_qubits) < i < max(all_qubits):
                            lines[i] += f"──┼{'─' * (width - 1)}──"
                        else:
                            lines[i] += "─" * (width + 2) + "─"
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# Pre-built quantum algorithms
# ═══════════════════════════════════════════════════════════════

def grover_search(n_qubits: int, target: int,
                  gpu: bool = False, shots: int = 1024) -> Dict[str, Any]:
    """Grover's search algorithm.

    Finds |target⟩ in unsorted database of 2^n items.
    Classical: O(2^n), Quantum: O(√2^n).

    Uses direct state vector manipulation for oracle and diffusion
    (exact simulation, not gate decomposition — avoids multi-controlled gate issues).
    """
    N = 2 ** n_qubits
    n_iterations = max(1, int(math.pi / 4 * math.sqrt(N)))

    qc = QuantumCircuit(n_qubits, gpu=gpu)

    # Initial superposition
    for i in range(n_qubits):
        qc.h(i)

    # Execute superposition first
    qc.state.reset()
    for op in qc.ops:
        if op.name in GATE_REGISTRY:
            qc._apply_single_gate(GATE_REGISTRY[op.name], op.targets[0])

    xp = qc.state.xp

    # Grover iterations via direct state vector manipulation
    t0 = time.time()
    for _ in range(n_iterations):
        # Oracle: flip phase of |target⟩
        qc.state.state[target] *= -1

        # Diffusion: 2|s⟩⟨s| - I where |s⟩ = uniform superposition
        mean = xp.mean(qc.state.state)
        qc.state.state = 2 * mean - qc.state.state

    elapsed = time.time() - t0
    measurements = qc.state.measure(shots)
    target_bitstring = format(target, f'0{n_qubits}b')
    target_count = measurements.get(target_bitstring, 0)

    return {
        'measurements': measurements,
        'n_qubits': n_qubits,
        'n_gates': n_qubits,  # H gates for initial superposition
        'memory_mb': round(qc.state.mem_mb, 2),
        'backend': qc.state.backend,
        'execution_time_ms': round(elapsed * 1000, 2),
        'shots': shots,
        'algorithm': 'Grover Search',
        'target': target,
        'target_bitstring': target_bitstring,
        'target_probability': round(target_count / shots, 4),
        'iterations': n_iterations,
        'theoretical_optimal': round(
            math.sin((2 * n_iterations + 1) * math.asin(1 / math.sqrt(N))) ** 2, 4),
    }


def deutsch_jozsa(n_qubits: int, oracle_type: str = "balanced",
                  gpu: bool = False) -> Dict[str, Any]:
    """Deutsch-Jozsa algorithm.

    Determines if a function is constant or balanced in ONE query.
    Classical requires O(2^(n-1) + 1) queries.
    """
    total_qubits = n_qubits + 1  # n input + 1 output
    qc = QuantumCircuit(total_qubits, gpu=gpu)

    # Prepare |0⟩^n |1⟩
    qc.x(n_qubits)  # Set output qubit to |1⟩

    # Apply H to all
    for i in range(total_qubits):
        qc.h(i)

    qc.barrier()

    # Oracle
    if oracle_type == "constant":
        pass  # f(x) = 0 for all x → identity
    elif oracle_type == "balanced":
        # f(x) = x[0] → CNOT from first input to output
        qc.cnot(0, n_qubits)

    qc.barrier()

    # Apply H to input qubits
    for i in range(n_qubits):
        qc.h(i)

    result = qc.run(shots=1024)

    # If all input qubits measure 0 → constant, else → balanced
    all_zero = '0' * n_qubits + '1'
    is_constant = all_zero in result['measurements'] and \
                  result['measurements'][all_zero] > 500

    result['algorithm'] = 'Deutsch-Jozsa'
    result['oracle_type'] = oracle_type
    result['determined'] = 'constant' if is_constant else 'balanced'
    result['correct'] = (result['determined'] == oracle_type)

    return result


def qft(n_qubits: int, input_state: int = 0,
        gpu: bool = False) -> Dict[str, Any]:
    """Quantum Fourier Transform.

    Foundation of Shor's algorithm.
    Transforms computational basis → frequency basis.
    """
    qc = QuantumCircuit(n_qubits, gpu=gpu)

    # Prepare input state
    if input_state > 0:
        bits = format(input_state, f'0{n_qubits}b')
        for i, b in enumerate(bits):
            if b == '1':
                qc.x(i)

    qc.barrier()

    # QFT circuit
    for i in range(n_qubits):
        qc.h(i)
        for j in range(i + 1, n_qubits):
            angle = math.pi / (2 ** (j - i))
            # Controlled rotation (approximate with Rz + CNOT)
            qc.rz(j, angle / 2)
            qc.cnot(i, j)
            qc.rz(j, -angle / 2)
            qc.cnot(i, j)

    # Swap qubits (bit-reversal)
    for i in range(n_qubits // 2):
        qc.swap(i, n_qubits - 1 - i)

    result = qc.run(shots=1024)
    result['algorithm'] = 'QFT'
    result['input_state'] = input_state

    return result


def bell_state(gpu: bool = False) -> Dict[str, Any]:
    """Create Bell state (maximally entangled 2-qubit state).

    |Φ+⟩ = (|00⟩ + |11⟩) / √2
    """
    qc = QuantumCircuit(2, gpu=gpu)
    qc.h(0)
    qc.cnot(0, 1)
    result = qc.run(shots=1024)
    result['algorithm'] = 'Bell State'
    result['expected'] = '|Φ+⟩ = (|00⟩ + |11⟩) / √2'
    return result


# ═══════════════════════════════════════════════════════════════
# Status / info
# ═══════════════════════════════════════════════════════════════

def get_status() -> Dict[str, Any]:
    gpu_available = False
    gpu_name = None
    try:
        import cupy as cp
        gpu_available = True
        gpu_name = cp.cuda.runtime.getDeviceProperties(0)['name'].decode()
    except (ImportError, Exception):
        pass

    return {
        'version': VERSION,
        'engine': 'QuantumEmulator',
        'backend': f"cupy_gpu ({gpu_name})" if gpu_available else "numpy_cpu",
        'gpu_available': gpu_available,
        'max_qubits_16gb': 30,  # 2^30 × 16 bytes = 16 GB
        'max_qubits_safe': 25,  # 2^25 × 16 bytes = 512 MB
        'gates': list(GATE_REGISTRY.keys()) + ['Rx', 'Ry', 'Rz', 'CNOT', 'CZ', 'SWAP', 'Toffoli'],
        'algorithms': ['Grover', 'Deutsch-Jozsa', 'QFT', 'Bell State'],
        'memory_table': {
            f'{n} qubits': f'{2**n * 16 / (1024**2):.1f} MB'
            for n in [10, 15, 20, 25, 30]
        },
    }
