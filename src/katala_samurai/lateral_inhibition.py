"""
Lateral Inhibition — Sharpen solver signals by suppressing contradictions.

When a high-confidence solver fires, suppress contradicting low-confidence solvers.
Like retinal ganglion cells: center-surround → sharper signal.

Kandel Ch.21: lateral inhibition enhances contrast in sensory processing.

Design: Youta Hilono, 2026-02-28
"""

from typing import Dict, Any, List, Tuple


def inhibit(solver_results: List[Dict[str, Any]], threshold: float = 0.7) -> List[Dict[str, Any]]:
    """Apply lateral inhibition to solver results.
    
    High-confidence solvers suppress contradicting neighbors.
    Returns modified solver results with adjusted weights.
    """
    if not solver_results:
        return solver_results
    
    # Sort by confidence (strongest signals first)
    indexed = [(i, r) for i, r in enumerate(solver_results)]
    indexed.sort(key=lambda x: x[1].get("confidence", 0.5), reverse=True)
    
    # Inhibition map: track suppression applied to each solver
    suppression = [0.0] * len(solver_results)
    
    for rank, (i, result) in enumerate(indexed):
        conf = result.get("confidence", 0.5)
        verdict = result.get("verdict", result.get("result", ""))
        
        if conf < threshold:
            continue  # Only strong signals inhibit
        
        # Suppress contradicting solvers
        for j, other in enumerate(solver_results):
            if j == i:
                continue
            
            other_conf = other.get("confidence", 0.5)
            other_verdict = other.get("verdict", other.get("result", ""))
            
            # Contradiction detection
            contradicts = _is_contradiction(verdict, conf, other_verdict, other_conf)
            
            if contradicts and other_conf < conf:
                # Inhibition strength proportional to confidence difference
                inhibition_strength = (conf - other_conf) * 0.5
                suppression[j] += inhibition_strength
    
    # Apply suppression
    result_copy = []
    for i, r in enumerate(solver_results):
        modified = dict(r)
        if suppression[i] > 0:
            old_conf = modified.get("confidence", 0.5)
            new_conf = max(0.1, old_conf - suppression[i])
            modified["confidence"] = round(new_conf, 4)
            modified["_inhibited_by"] = round(suppression[i], 4)
            modified["_original_confidence"] = old_conf
        result_copy.append(modified)
    
    return result_copy


def _is_contradiction(v1: str, c1: float, v2: str, c2: float) -> bool:
    """Detect if two solver outputs contradict each other."""
    # Directional contradiction: one says high, other says low
    if c1 > 0.65 and c2 < 0.35:
        return True
    if c1 < 0.35 and c2 > 0.65:
        return True
    
    # Verdict contradiction
    pos = {"VERIFIED", "TRUE", "PASS", "CONSISTENT", "MATCH"}
    neg = {"UNVERIFIED", "FALSE", "FAIL", "INCONSISTENT", "MISMATCH"}
    
    v1_pos = any(p in str(v1).upper() for p in pos)
    v1_neg = any(n in str(v1).upper() for n in neg)
    v2_pos = any(p in str(v2).upper() for p in pos)
    v2_neg = any(n in str(v2).upper() for n in neg)
    
    if (v1_pos and v2_neg) or (v1_neg and v2_pos):
        return True
    
    return False


def compute_sharpness(solver_results: List[Dict]) -> Dict[str, Any]:
    """Measure signal sharpness (post-inhibition vs pre-inhibition)."""
    if not solver_results:
        return {"sharpness": 0, "inhibited_count": 0}
    
    confs = [r.get("confidence", 0.5) for r in solver_results]
    inhibited = [r for r in solver_results if "_inhibited_by" in r]
    
    # Sharpness = variance of confidences (higher = sharper signal)
    mean = sum(confs) / len(confs)
    variance = sum((c - mean)**2 for c in confs) / len(confs)
    
    return {
        "sharpness": round(variance, 4),
        "inhibited_count": len(inhibited),
        "total_suppression": round(sum(r.get("_inhibited_by", 0) for r in solver_results), 4),
        "signal_clarity": "SHARP" if variance > 0.04 else "MODERATE" if variance > 0.01 else "DIFFUSE",
    }
