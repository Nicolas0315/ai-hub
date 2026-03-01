#!/usr/bin/env python3
"""Katala Quantum Emulator — Test Suite"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.katala_quantum.emulator import (
    QuantumCircuit, NeuralQuantumApproximator, QuantumKSVerifier
)
import numpy as np

passed = 0
failed = 0

def test(name, condition, msg=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✓ {name}")
    else:
        failed += 1
        print(f"  ✗ {name} — {msg}")

print("═══ Katala Quantum Emulator Tests ═══\n")

# ── Basic Circuit ──
print("── Basic Gates ──")

# |0⟩ → X → |1⟩
qc = QuantumCircuit(1)
qc.x(0)
r = qc.run(shots=100)
test("X gate flips |0⟩ to |1⟩", abs(r.probabilities[1] - 1.0) < 1e-10,
     f"prob[1]={r.probabilities[1]}")

# |0⟩ → H → equal superposition
qc = QuantumCircuit(1)
qc.h(0)
r = qc.run(shots=1000)
test("H gate creates superposition", abs(r.probabilities[0] - 0.5) < 0.01,
     f"prob[0]={r.probabilities[0]}")

# |0⟩ → H → H → |0⟩ (H is self-inverse)
qc = QuantumCircuit(1)
qc.h(0).h(0)
r = qc.run()
test("H·H = I", abs(r.probabilities[0] - 1.0) < 1e-10)

# Z gate: |0⟩ → Z → |0⟩ (no effect on |0⟩)
qc = QuantumCircuit(1)
qc.z(0)
r = qc.run()
test("Z gate preserves |0⟩", abs(r.probabilities[0] - 1.0) < 1e-10)

# ── Bell State ──
print("\n── Bell State ──")
qc = QuantumCircuit(2)
qc.h(0).cx(0, 1).measure_all()
r = qc.run(shots=10000)
test("Bell |Φ+⟩ prob[00]≈0.5", abs(r.probabilities[0] - 0.5) < 0.01,
     f"got {r.probabilities[0]}")
test("Bell |Φ+⟩ prob[11]≈0.5", abs(r.probabilities[3] - 0.5) < 0.01,
     f"got {r.probabilities[3]}")
test("Bell |Φ+⟩ prob[01]≈0", abs(r.probabilities[1]) < 0.01)
test("Bell |Φ+⟩ prob[10]≈0", abs(r.probabilities[2]) < 0.01)
test("Bell measurements", len(r.measurements) > 0)
test("Bell only 00 and 11", all(k in ('00', '11') for k in r.measurements.keys()),
     f"got keys: {list(r.measurements.keys())}")

# ── GHZ State ──
print("\n── GHZ State ──")
qc = QuantumCircuit(3)
qc.h(0).cx(0, 1).cx(0, 2).measure_all()
r = qc.run(shots=10000)
test("GHZ prob[000]≈0.5", abs(r.probabilities[0] - 0.5) < 0.02)
test("GHZ prob[111]≈0.5", abs(r.probabilities[7] - 0.5) < 0.02)
test("GHZ middle states≈0", all(r.probabilities[i] < 0.01 for i in range(1, 7)))

# ── Parametric Gates ──
print("\n── Parametric Gates ──")
qc = QuantumCircuit(1)
qc.rx(0, np.pi)  # Rx(π) = X gate (up to global phase)
r = qc.run()
test("Rx(π) ≈ X gate", abs(r.probabilities[1] - 1.0) < 1e-8,
     f"prob[1]={r.probabilities[1]}")

qc = QuantumCircuit(1)
qc.ry(0, np.pi)  # Ry(π) flips |0⟩ to |1⟩
r = qc.run()
test("Ry(π) flips", abs(r.probabilities[1] - 1.0) < 1e-8)

# ── SWAP ──
print("\n── SWAP Gate ──")
qc = QuantumCircuit(2)
qc.x(0)  # |10⟩
qc.swap(0, 1)  # → |01⟩
r = qc.run()
test("SWAP |10⟩→|01⟩", abs(r.probabilities[1] - 1.0) < 1e-10,
     f"probs={r.probabilities}")

# ── Toffoli ──
print("\n── Toffoli (CCX) Gate ──")
qc = QuantumCircuit(3)
qc.x(0).x(1)  # |110⟩
qc.ccx(0, 1, 2)  # → |111⟩
r = qc.run()
test("Toffoli |110⟩→|111⟩", abs(r.probabilities[7] - 1.0) < 1e-10,
     f"prob[111]={r.probabilities[7]}")

qc = QuantumCircuit(3)
qc.x(0)  # |100⟩ — only one control is 1
qc.ccx(0, 1, 2)  # → |100⟩ (no flip)
r = qc.run()
test("Toffoli |100⟩ unchanged", abs(r.probabilities[4] - 1.0) < 1e-10)

# ── Larger Circuit ──
print("\n── Scalability ──")
for n in [5, 10, 15]:
    qc = QuantumCircuit(n)
    for i in range(n):
        qc.h(i)
    qc.measure_all()
    r = qc.run(shots=1000)
    expected = 1.0 / (2**n)
    max_dev = max(abs(p - expected) for p in r.probabilities)
    test(f"{n}-qubit H⊗{n} uniform", max_dev < 0.01,
         f"max_dev={max_dev:.4f}")
    test(f"{n}-qubit memory", r.memory_bytes == 2**n * 16,
         f"got {r.memory_bytes}")

# ── KS Verification ──
print("\n── KS Verification ──")
verifier = QuantumKSVerifier()

# Bell state verification
qc = QuantumCircuit(2)
qc.h(0).cx(0, 1)
r = qc.run()
v = verifier.verify(qc, r)
test("KS Bell verdict VERIFIED", v["verdict"] == "VERIFIED", f"got {v['verdict']}")
test("KS Bell confidence > 0.9", v["confidence"] > 0.9)
test("KS unitarity check", any(c["name"] == "unitarity" and c["passed"] for c in v["checks"]))
test("KS prob conservation", any(c["name"] == "probability_conservation" and c["passed"] for c in v["checks"]))
test("KS Bell pattern detected", any(c.get("pattern", "").startswith("Bell") for c in v["checks"]),
     f"checks: {[c.get('pattern') for c in v['checks'] if 'pattern' in c]}")

# GHZ verification
qc = QuantumCircuit(3)
qc.h(0).cx(0, 1).cx(0, 2)
r = qc.run()
v = verifier.verify(qc, r)
test("KS GHZ pattern detected", any(c.get("pattern", "").startswith("GHZ") for c in v["checks"]))

# Equal superposition verification
qc = QuantumCircuit(4)
for i in range(4):
    qc.h(i)
r = qc.run()
v = verifier.verify(qc, r, expected_properties={"equal_superposition": True})
test("KS superposition verified", v["verdict"] == "VERIFIED")

# Translation loss
test("KS has translation_loss", "translation_loss" in v)
tl = v["translation_loss"]
test("KS R_struct in [0,1]", 0 <= tl["R_struct"] <= 1)
test("KS total_loss >= 0", tl["total_loss"] >= 0)

# ── Neural Approximation ──
print("\n── Neural Approximation ──")
nn = NeuralQuantumApproximator(n_qubits=3, hidden_size=64)

# Collect training data
for _ in range(50):
    qc = QuantumCircuit(3)
    # Random circuit
    for _ in range(np.random.randint(1, 8)):
        gate = np.random.choice(['h', 'x', 'cx'])
        if gate == 'h':
            qc.h(np.random.randint(3))
        elif gate == 'x':
            qc.x(np.random.randint(3))
        elif gate == 'cx':
            q1, q2 = np.random.choice(3, 2, replace=False)
            qc.cx(q1, q2)
    r = qc.run()
    nn.collect_training_data(qc, r)

test("collected training data", len(nn.training_pairs) == 50)

# Train
result = nn.train(epochs=50, lr=0.001)
test("training completed", "final_loss" in result)
test("loss decreased", result.get("improvement", 0) > 0,
     f"improvement={result.get('improvement', 0):.4f}")

# Predict on known circuit (Bell state)
qc = QuantumCircuit(3)
qc.h(0).cx(0, 1)
pred = nn.predict(qc)
test("NN prediction sums to 1", abs(pred.sum() - 1.0) < 0.01,
     f"sum={pred.sum()}")
test("NN prediction non-negative", np.all(pred >= -0.01))

# ── Circuit Info ──
print("\n── Circuit Utilities ──")
qc = QuantumCircuit(3)
qc.h(0).cx(0, 1).cx(0, 2).measure_all()
test("circuit str", "QuantumCircuit" in str(qc))
test("circuit depth", qc.depth == 3, f"got {qc.depth}")
test("circuit gate count", len(qc.gates) == 3)

# ── Edge Cases ──
print("\n── Edge Cases ──")
qc = QuantumCircuit(1)
r = qc.run()
test("empty circuit = |0⟩", abs(r.probabilities[0] - 1.0) < 1e-10)

try:
    qc = QuantumCircuit(31)
    test("31 qubits rejected", False, "should have raised ValueError")
except ValueError:
    test("31 qubits rejected", True)

# ── Summary ──
print(f"\n{'═' * 40}")
print(f"  Results: {passed} passed, {failed} failed")
print(f"  {'ALL PASSED ✓' if failed == 0 else 'SOME FAILED ✗'}")
print(f"{'═' * 40}")

sys.exit(0 if failed == 0 else 1)
