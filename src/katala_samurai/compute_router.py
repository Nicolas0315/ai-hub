"""
Compute Router — Intelligent CPU/GPU workload distribution.

Routes computations to the most efficient hardware:
  - GPU (MPS/CUDA): batch matrix ops, bootstrap sampling, similarity computation
  - CPU: regex/pattern matching, graph ops, string processing, external API
  - Multiprocess: independent solver execution

Hardware detection: auto-detects MPS (Apple Silicon), CUDA (NVIDIA), or CPU-only.

Design: Youta Hilono, 2026-02-28
"""

import os
import time
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from functools import lru_cache

# ── Hardware Detection ──

_DEVICE = None
_TORCH_AVAILABLE = False
_NP_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
    if torch.backends.mps.is_available():
        _DEVICE = "mps"
    elif torch.cuda.is_available():
        _DEVICE = "cuda"
    else:
        _DEVICE = "cpu"
except ImportError:
    _DEVICE = "cpu"

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    pass


def get_device() -> str:
    return _DEVICE


def device_info() -> Dict[str, Any]:
    info = {
        "device": _DEVICE,
        "torch": _TORCH_AVAILABLE,
        "numpy": _NP_AVAILABLE,
        "cpu_count": os.cpu_count() or 1,
    }
    if _TORCH_AVAILABLE:
        import torch
        if _DEVICE == "mps":
            info["gpu"] = "Apple Silicon (MPS)"
        elif _DEVICE == "cuda":
            info["gpu"] = torch.cuda.get_device_name(0)
            info["gpu_memory"] = f"{torch.cuda.get_device_properties(0).total_mem / 1e9:.1f}GB"
    return info


# ── GPU-Accelerated Operations ──

def gpu_bootstrap_confidence(layer_scores: List[float], n_samples: int = 500,
                              sample_ratio: float = 0.7) -> Dict[str, float]:
    """Bootstrap confidence estimation on GPU (MPS/CUDA).
    
    ~10-50x faster than CPU for large sample counts.
    """
    # Smart routing: GPU only worth it for large batches (MPS init overhead)
    if not _TORCH_AVAILABLE or not layer_scores or (len(layer_scores) * n_samples < 5000):
        return _cpu_bootstrap(layer_scores, n_samples, sample_ratio)
    
    import torch
    device = torch.device(_DEVICE)
    
    try:
        scores = torch.tensor(layer_scores, dtype=torch.float32, device=device)
        n = len(layer_scores)
        k = max(1, int(n * sample_ratio))
        
        # Generate all bootstrap indices at once on GPU
        indices = torch.randint(0, n, (n_samples, k), device=device)
        
        # Gather and compute means in parallel
        samples = scores[indices]
        means = samples.mean(dim=1)
        
        mean_val = means.mean().item()
        std_val = means.std().item()
        sorted_means = means.sort().values
        ci_low = sorted_means[int(n_samples * 0.025)].item()
        ci_high = sorted_means[int(n_samples * 0.975)].item()
        
        return {
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "ci_low": round(ci_low, 4),
            "ci_high": round(ci_high, 4),
            "device": _DEVICE,
        }
    except Exception:
        return _cpu_bootstrap(layer_scores, n_samples, sample_ratio)


def _cpu_bootstrap(scores, n_samples, ratio):
    import random, math
    if not scores: return {"mean": 0.5, "std": 0.25, "ci_low": 0.25, "ci_high": 0.75, "device": "cpu"}
    n = len(scores); k = max(1, int(n * ratio))
    means = [sum(random.choices(scores, k=k))/k for _ in range(n_samples)]
    mean_v = sum(means)/len(means)
    var = sum((x-mean_v)**2 for x in means)/len(means)
    s = sorted(means)
    return {"mean": round(mean_v,4), "std": round(math.sqrt(var),4),
            "ci_low": round(s[int(n_samples*0.025)],4), "ci_high": round(s[int(n_samples*0.975)],4), "device": "cpu"}


def gpu_batch_similarity(vectors_a: List[List[float]], vectors_b: List[List[float]]) -> List[float]:
    """Compute cosine similarities in batch on GPU."""
    if not _TORCH_AVAILABLE or not vectors_a:
        return _cpu_similarity(vectors_a, vectors_b)
    
    import torch
    device = torch.device(_DEVICE)
    
    try:
        a = torch.tensor(vectors_a, dtype=torch.float32, device=device)
        b = torch.tensor(vectors_b, dtype=torch.float32, device=device)
        
        a_norm = a / a.norm(dim=1, keepdim=True).clamp(min=1e-8)
        b_norm = b / b.norm(dim=1, keepdim=True).clamp(min=1e-8)
        
        sims = (a_norm * b_norm).sum(dim=1)
        return [round(s.item(), 4) for s in sims]
    except Exception:
        return _cpu_similarity(vectors_a, vectors_b)


def _cpu_similarity(va, vb):
    import math
    results = []
    for a, b in zip(va, vb):
        dot = sum(x*y for x,y in zip(a,b))
        na = math.sqrt(sum(x*x for x in a)) or 1e-8
        nb = math.sqrt(sum(x*x for x in b)) or 1e-8
        results.append(round(dot/(na*nb), 4))
    return results


def gpu_lateral_inhibition(confidences: List[float], contradictions: List[tuple]) -> List[float]:
    """Apply lateral inhibition on GPU — matrix operation."""
    if not _TORCH_AVAILABLE or not confidences:
        return confidences
    
    import torch
    device = torch.device(_DEVICE)
    
    try:
        n = len(confidences)
        confs = torch.tensor(confidences, dtype=torch.float32, device=device)
        
        # Build inhibition matrix
        inhib = torch.zeros(n, n, device=device)
        for i, j in contradictions:
            if i < n and j < n:
                if confs[i] > confs[j]:
                    inhib[i, j] = (confs[i] - confs[j]) * 0.5
                else:
                    inhib[j, i] = (confs[j] - confs[i]) * 0.5
        
        # Apply: suppression is column sum
        suppression = inhib.sum(dim=0)
        result = (confs - suppression).clamp(min=0.1)
        
        return [round(r.item(), 4) for r in result]
    except Exception:
        return confidences


# ── CPU-Optimized Operations ──

def cpu_regex_batch(patterns: List[str], text: str) -> List[bool]:
    """Batch regex matching — stays on CPU (regex is CPU-bound)."""
    import re
    return [bool(re.search(p, text, re.IGNORECASE)) for p in patterns]


def cpu_graph_analysis(edges: List[tuple], nodes: int) -> Dict[str, Any]:
    """Graph analysis — CPU with networkx (not GPU-suitable)."""
    try:
        import networkx as nx
        G = nx.DiGraph()
        G.add_nodes_from(range(nodes))
        G.add_edges_from(edges)
        return {
            "is_dag": nx.is_directed_acyclic_graph(G),
            "components": nx.number_weakly_connected_components(G),
            "density": round(nx.density(G), 4),
        }
    except Exception:
        return {"error": "networkx_unavailable"}


# ── Parallel Solver Execution ──

def parallel_execute(tasks: List[Callable], max_workers: int = None,
                     use_processes: bool = False) -> List[Any]:
    """Execute tasks in parallel — CPU threads or processes."""
    if max_workers is None:
        max_workers = min(len(tasks), os.cpu_count() or 4)
    
    Pool = ProcessPoolExecutor if use_processes else ThreadPoolExecutor
    
    results = [None] * len(tasks)
    with Pool(max_workers=max_workers) as pool:
        futures = {pool.submit(task): i for i, task in enumerate(tasks)}
        from concurrent.futures import as_completed
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                results[idx] = {"error": str(e)[:100]}
    
    return results


# ── Benchmark ──

def benchmark() -> Dict[str, Any]:
    """Quick benchmark of CPU vs GPU for key operations."""
    import random
    
    scores = [random.random() for _ in range(100)]
    results = {}
    
    # Bootstrap CPU
    t0 = time.time()
    for _ in range(10):
        _cpu_bootstrap(scores, 500, 0.7)
    results["bootstrap_cpu_ms"] = round((time.time() - t0) * 100, 2)
    
    # Bootstrap GPU
    t0 = time.time()
    for _ in range(10):
        gpu_bootstrap_confidence(scores, 500, 0.7)
    results["bootstrap_gpu_ms"] = round((time.time() - t0) * 100, 2)
    
    if results["bootstrap_cpu_ms"] > 0:
        results["speedup"] = round(results["bootstrap_cpu_ms"] / max(results["bootstrap_gpu_ms"], 0.01), 1)
    
    results["device"] = _DEVICE
    
    return results
