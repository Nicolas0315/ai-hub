"""
Rust Bridge — Transparent fallback wrapper for ks_accel.

If ks_accel (Rust) is available, use it. Otherwise fall back to Python.
All KS modules should import from here instead of directly.

Design: Youta Hilono, 2026-02-28
"""

import json
from typing import Dict, Any, List, Optional

try:
    import ks_accel as _rust
    RUST_AVAILABLE = True
except ImportError:
    _rust = None
    RUST_AVAILABLE = False


# ── Claim Classification ──

def classify_claim(text: str) -> Dict[str, float]:
    if RUST_AVAILABLE:
        return _rust.classify_claim(text)
    # Python fallback (import lazily)
    from .metacognitive_planner import _classify_type
    return _classify_type(text)


# ── Bootstrap Confidence ──

def bootstrap_confidence(scores: list, n_samples: int = 500,
                         sample_ratio: float = 0.7) -> Dict[str, float]:
    if RUST_AVAILABLE:
        return _rust.bootstrap_confidence(scores, n_samples, sample_ratio)
    import random, math
    if not scores:
        return {"mean": 0.5, "std": 0.25, "ci_low": 0.25, "ci_high": 0.75}
    k = max(1, int(len(scores) * sample_ratio))
    means = [sum(random.choices(scores, k=k)) / k for _ in range(n_samples)]
    mean = sum(means) / len(means)
    std = math.sqrt(sum((x - mean)**2 for x in means) / len(means))
    means.sort()
    return {
        "mean": round(mean, 4), "std": round(std, 4),
        "ci_low": round(means[int(n_samples * 0.025)], 4),
        "ci_high": round(means[int(n_samples * 0.975)], 4),
    }


# ── Lateral Inhibition ──

def lateral_inhibit(confidences: list, threshold: float = 0.7) -> list:
    if RUST_AVAILABLE:
        return _rust.lateral_inhibit(confidences, threshold)
    # Python fallback
    n = len(confidences)
    if n < 2:
        return confidences
    suppression = [0.0] * n
    for i in range(n):
        if confidences[i] < threshold:
            continue
        for j in range(n):
            if j == i:
                continue
            if (confidences[i] > 0.65 and confidences[j] < 0.35) or \
               (confidences[i] < 0.35 and confidences[j] > 0.65):
                if confidences[j] < confidences[i]:
                    suppression[j] += (confidences[i] - confidences[j]) * 0.5
    return [round(max(0.1, c - s), 4) for c, s in zip(confidences, suppression)]


# ── Feature Extraction ──

def extract_features(text: str) -> Dict[str, Any]:
    if RUST_AVAILABLE:
        return _rust.extract_features(text)
    words = set(text.lower().split())
    return {
        "word_count": len(words), "char_count": len(text),
        "has_numbers": any(c.isdigit() for c in text),
        "has_negation": bool(words & {"not","never","no","neither","without","none"}),
        "has_causal": bool(words & {"cause","causes","caused","because","effect","leads","results"}),
        "has_statistical": bool(words & {"significant","correlation","sample","regression"}),
        "has_definition": bool(words & {"defined","means","refers","definition","known"}),
        "sentence_count": max(1, text.count('.') + text.count('!') + text.count('?')),
    }


# ── Coherence Check ──

def check_coherence(confidences: list) -> Dict[str, float]:
    if RUST_AVAILABLE:
        return _rust.check_coherence(confidences)
    n = len(confidences)
    if n < 2:
        return {"coherence": 1.0, "conflicts": 0.0}
    conflicts = support = 0
    for i in range(n):
        for j in range(i+1, n):
            if (confidences[i] > 0.65 and confidences[j] < 0.35) or \
               (confidences[i] < 0.35 and confidences[j] > 0.65):
                conflicts += 1
            elif abs(confidences[i] - confidences[j]) < 0.2:
                support += 1
    coh = max(0, 1.0 - conflicts / max(n*(n-1)//2, 1) * 2)
    return {"coherence": round(coh, 4), "conflicts": float(conflicts),
            "support_pairs": float(support),
            "modifier": round(-0.1 * (1 - coh), 4) if coh < 0.5 else 0.0}


# ── Reason Space ──

def reason_space_analyze(solvers: list, reasons: list,
                         confidences: list, verdicts: list) -> Dict[str, Any]:
    if RUST_AVAILABLE:
        raw = _rust.reason_space_analyze(solvers, reasons, confidences, verdicts)
        # Parse JSON strings back to Python objects
        result = {}
        for k, v in raw.items():
            if k in ("conflicts", "isolated_solvers"):
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, TypeError):
                    result[k] = v
            elif k in ("coherence", "confidence_modifier"):
                result[k] = float(v)
            elif k in ("conflict_count", "support_pairs"):
                result[k] = int(v)
            else:
                result[k] = v
        return result
    # Python fallback: import ReasonSpace
    from .reason_space import ReasonSpace
    rs = ReasonSpace()
    for s, r, c, v in zip(solvers, reasons, confidences, verdicts):
        rs.register(s, r, c, v)
    return rs.analyze_coherence()


# ── Neuromodulation ──

def neuromodulate(claim_type: str, difficulty: str,
                  prediction_error: float, novelty: float = 0.5) -> Dict[str, Any]:
    if RUST_AVAILABLE:
        raw = _rust.neuromodulate(claim_type, difficulty, prediction_error, novelty)
        mode_val = raw.pop("mode", 0.0)
        raw["mode"] = "VIGILANT" if mode_val > 0 else ("RELAXED" if mode_val < 0 else "NORMAL")
        return raw
    from .neuromodulation import Neuromodulator
    nm = Neuromodulator()
    params = nm.modulate(claim_type, difficulty, prediction_error, novelty)
    params["mode"] = nm.get_state()["mode"]
    return params


def neuro_apply_confidence(raw_confidence: float, caution: float) -> float:
    if RUST_AVAILABLE:
        return _rust.neuro_apply_confidence(raw_confidence, caution)
    if caution > 1.0:
        return round(max(0, min(1, raw_confidence + (0.5 - raw_confidence) * (caution - 1.0) * 0.3)), 4)
    return raw_confidence


# ── Predictive Coding ──

def predictive_error(predicted_conf: float, actual_conf: float,
                     predicted_verdict: str, actual_verdict: str,
                     range_low: float, range_high: float,
                     precision: float = 1.0, surprise_threshold: float = 0.15) -> Dict[str, Any]:
    if RUST_AVAILABLE:
        raw = _rust.predictive_error(predicted_conf, actual_conf,
                                     predicted_verdict, actual_verdict,
                                     range_low, range_high, precision, surprise_threshold)
        raw["surprising"] = bool(raw["surprising"])
        raw["verdict_match"] = bool(raw["verdict_match"])
        raw["in_range"] = bool(raw["in_range"])
        depth_map = {0.0: "MINIMAL", 1.0: "PARTIAL", 2.0: "FULL"}
        raw["meta_depth"] = depth_map.get(raw["meta_depth"], "PARTIAL")
        return raw
    from .predictive_coding import PredictiveEngine
    pe = PredictiveEngine(surprise_threshold)
    pred = {"predicted_confidence": predicted_conf, "predicted_verdict": predicted_verdict,
            "predicted_range": [range_low, range_high], "precision": precision}
    return pe.compute_error(pred, actual_conf, actual_verdict)


# ── Solver Cache ──

def cache_get(namespace: str, query: str, ttl: float = 3600.0) -> Optional[Any]:
    if RUST_AVAILABLE:
        raw = _rust.cache_get(namespace, query, ttl)
        if raw is not None:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return raw
        return None
    return None  # No Python fallback for cache (use SolverCache directly)


def cache_put(namespace: str, query: str, value: Any, max_size: int = 1000):
    if RUST_AVAILABLE:
        _rust.cache_put(namespace, query, json.dumps(value), max_size)


def cache_stats() -> Dict[str, float]:
    if RUST_AVAILABLE:
        return _rust.cache_stats()
    return {"size": 0, "hits": 0, "misses": 0, "hit_rate": 0.0}


def cache_clear():
    if RUST_AVAILABLE:
        _rust.cache_clear()


def status() -> Dict[str, Any]:
    return {
        "rust_available": RUST_AVAILABLE,
        "functions": 14 if RUST_AVAILABLE else 0,
        "backend": "ks_accel (Rust/PyO3/Rayon)" if RUST_AVAILABLE else "Python fallback",
    }
