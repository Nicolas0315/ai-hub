"""Benchmark: Python KS42 vs Rust ks42_core"""
import time
import sys
import random

sys.path.insert(0, "src")

# ── Python implementation ──
from katala_samurai.ks42 import (
    LossVector as PyLossVector,
    _classify_loss_pattern as py_classify,
    _compute_tension as py_tension,
    _find_donors as py_find_donors,
    _detect_conflicts as py_detect_conflicts,
    _explore_voids as py_explore_voids,
    AXES,
)

# ── Rust implementation ──
import ks42_core as rust

# ── Generate test data ──
random.seed(42)
N = 10_000

test_scores = [[random.random() for _ in range(5)] for _ in range(N)]

py_vectors = [PyLossVector(*s) for s in test_scores]
rust_vectors = [rust.RustLossVector(*s) for s in test_scores]

# Corpus for donor search
corpus_py = [
    {"name": f"mod_{i}", "loss_vector": dict(zip(AXES, test_scores[i]))}
    for i in range(min(100, N))
]
corpus_rust = [
    (f"mod_{i}", test_scores[i])
    for i in range(min(100, N))
]

# Tension test data
a_vals = [random.random() for _ in range(200)]
b_vals = [random.random() for _ in range(200)]

print(f"Benchmarking {N} vectors...\n")

# ── 1. LossVector operations ──
print("═══ LossVector Operations ═══")

# Magnitude
t0 = time.perf_counter()
for v in py_vectors:
    v.magnitude()
py_mag = time.perf_counter() - t0

t0 = time.perf_counter()
for v in rust_vectors:
    v.magnitude()
rust_mag = time.perf_counter() - t0

print(f"  magnitude():   Python {py_mag*1000:.1f}ms  |  Rust {rust_mag*1000:.1f}ms  |  {py_mag/rust_mag:.0f}x faster")

# Mean
t0 = time.perf_counter()
for v in py_vectors:
    v.mean()
py_mean = time.perf_counter() - t0

t0 = time.perf_counter()
for v in rust_vectors:
    v.mean()
rust_mean = time.perf_counter() - t0

print(f"  mean():        Python {py_mean*1000:.1f}ms  |  Rust {rust_mean*1000:.1f}ms  |  {py_mean/rust_mean:.0f}x faster")

# Dominant loss axis
t0 = time.perf_counter()
for v in py_vectors:
    v.dominant_loss_axis()
py_dom = time.perf_counter() - t0

t0 = time.perf_counter()
for v in rust_vectors:
    v.dominant_loss_axis()
rust_dom = time.perf_counter() - t0

print(f"  dominant():    Python {py_dom*1000:.1f}ms  |  Rust {rust_dom*1000:.1f}ms  |  {py_dom/rust_dom:.0f}x faster")

# Void dimensions
t0 = time.perf_counter()
for v in py_vectors:
    v.void_dimensions()
py_void = time.perf_counter() - t0

t0 = time.perf_counter()
for v in rust_vectors:
    v.void_dimensions()
rust_void = time.perf_counter() - t0

print(f"  void_dims():   Python {py_void*1000:.1f}ms  |  Rust {rust_void*1000:.1f}ms  |  {py_void/rust_void:.0f}x faster")

# Distance
t0 = time.perf_counter()
for i in range(0, min(N, 1000), 2):
    py_vectors[i].distance_to(py_vectors[i+1])
py_dist = time.perf_counter() - t0

t0 = time.perf_counter()
for i in range(0, min(N, 1000), 2):
    rust_vectors[i].distance_to(rust_vectors[i+1])
rust_dist = time.perf_counter() - t0

print(f"  distance():    Python {py_dist*1000:.1f}ms  |  Rust {rust_dist*1000:.1f}ms  |  {py_dist/rust_dist:.0f}x faster")

# ── 2. Pattern Classification ──
print("\n═══ Pattern Classification ═══")

t0 = time.perf_counter()
for v in py_vectors:
    py_classify(v)
py_class = time.perf_counter() - t0

t0 = time.perf_counter()
for v in rust_vectors:
    rust.classify_loss_pattern(v)
rust_class = time.perf_counter() - t0

print(f"  classify():    Python {py_class*1000:.1f}ms  |  Rust {rust_class*1000:.1f}ms  |  {py_class/rust_class:.0f}x faster")

# ── 3. Batch Analysis (Rust only) ──
print("\n═══ Batch Analysis (Rust-only) ═══")

t0 = time.perf_counter()
batch = rust.batch_analyze(test_scores)
rust_batch = time.perf_counter() - t0

# Compare: equivalent Python
t0 = time.perf_counter()
for s in test_scores:
    v = PyLossVector(*s)
    py_classify(v)
    v.magnitude()
    v.dominant_loss_axis()
    v.void_dimensions()
py_batch = time.perf_counter() - t0

print(f"  batch({N}):  Python {py_batch*1000:.1f}ms  |  Rust {rust_batch*1000:.1f}ms  |  {py_batch/rust_batch:.0f}x faster")

# ── 4. Tension ──
print("\n═══ Tension Computation ═══")

TENSION_ITERS = 1000

t0 = time.perf_counter()
for _ in range(TENSION_ITERS):
    py_tension("r_struct", "r_qualia", {"r_struct": a_vals, "r_qualia": b_vals})
py_tens = time.perf_counter() - t0

t0 = time.perf_counter()
for _ in range(TENSION_ITERS):
    rust.compute_tension("r_struct", "r_qualia", a_vals, b_vals)
rust_tens = time.perf_counter() - t0

print(f"  tension():     Python {py_tens*1000:.1f}ms  |  Rust {rust_tens*1000:.1f}ms  |  {py_tens/rust_tens:.0f}x faster")

# ── 5. Distance Matrix ──
print("\n═══ Distance Matrix ═══")

MATRIX_N = 500
mat_scores = test_scores[:MATRIX_N]

t0 = time.perf_counter()
mat_py_vecs = [PyLossVector(*s) for s in mat_scores]
py_matrix = [[0.0]*MATRIX_N for _ in range(MATRIX_N)]
for i in range(MATRIX_N):
    for j in range(i+1, MATRIX_N):
        d = mat_py_vecs[i].distance_to(mat_py_vecs[j])
        py_matrix[i][j] = d
        py_matrix[j][i] = d
py_mat_time = time.perf_counter() - t0

t0 = time.perf_counter()
rust_matrix = rust.distance_matrix(mat_scores)
rust_mat_time = time.perf_counter() - t0

print(f"  matrix({MATRIX_N}²):  Python {py_mat_time*1000:.1f}ms  |  Rust {rust_mat_time*1000:.1f}ms  |  {py_mat_time/rust_mat_time:.0f}x faster")

# ── 6. Correctness Check ──
print("\n═══ Correctness Verification ═══")

errors = 0
for i in range(min(100, N)):
    py_v = py_vectors[i]
    rs_v = rust_vectors[i]
    
    if abs(py_v.magnitude() - rs_v.magnitude()) > 1e-9:
        errors += 1
    if abs(py_v.mean() - rs_v.mean()) > 1e-9:
        errors += 1
    if py_v.dominant_loss_axis() != rs_v.dominant_loss_axis():
        errors += 1
    if py_v.void_dimensions() != rs_v.void_dimensions():
        errors += 1
    
    py_pat = py_classify(py_v)
    rs_pat = rust.classify_loss_pattern(rs_v)
    if py_pat != rs_pat:
        errors += 1

print(f"  Errors: {errors} / 500 checks → {'✅ PASS' if errors == 0 else '❌ FAIL'}")

# ── Summary ──
print("\n═══ Summary ═══")
total_py = py_mag + py_mean + py_dom + py_void + py_class + py_batch + py_tens + py_mat_time
total_rust = rust_mag + rust_mean + rust_dom + rust_void + rust_class + rust_batch + rust_tens + rust_mat_time
print(f"  Total Python: {total_py*1000:.0f}ms")
print(f"  Total Rust:   {total_rust*1000:.0f}ms")
print(f"  Overall:      {total_py/total_rust:.0f}x faster")
