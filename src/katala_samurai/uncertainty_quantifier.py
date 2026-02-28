"""
Uncertainty Quantifier — 2nd-order uncertainty estimation.

Instead of just "confidence = 0.6", outputs "confidence = 0.6 ± 0.15"
by bootstrapping layer results and measuring variance.

Target: Uncertainty Recognition 70% → 90%+

Design: Youta Hilono, 2026-02-28
"""

import math
import random
from typing import Dict, Any, List, Optional, Tuple


def _bootstrap_confidence(
    layer_scores: List[float],
    n_samples: int = 100,
    sample_ratio: float = 0.7,
) -> Tuple[float, float, float, float]:
    """Bootstrap estimate of confidence with uncertainty bounds.
    
    Returns: (mean, std, ci_low, ci_high)
    """
    if not layer_scores:
        return 0.5, 0.25, 0.25, 0.75
    
    if len(layer_scores) == 1:
        return layer_scores[0], 0.2, max(0, layer_scores[0]-0.2), min(1, layer_scores[0]+0.2)
    
    n = len(layer_scores)
    k = max(1, int(n * sample_ratio))
    
    bootstrap_means = []
    for _ in range(n_samples):
        sample = random.choices(layer_scores, k=k)
        bootstrap_means.append(sum(sample) / len(sample))
    
    mean = sum(bootstrap_means) / len(bootstrap_means)
    variance = sum((x - mean)**2 for x in bootstrap_means) / len(bootstrap_means)
    std = math.sqrt(variance)
    
    sorted_means = sorted(bootstrap_means)
    ci_low = sorted_means[int(n_samples * 0.025)]
    ci_high = sorted_means[int(n_samples * 0.975)]
    
    return round(mean, 4), round(std, 4), round(ci_low, 4), round(ci_high, 4)


def _agreement_uncertainty(verdicts: List[str]) -> float:
    """Measure uncertainty from verdict disagreement.
    
    Full agreement → low uncertainty. Mixed → high.
    Returns: uncertainty score 0-1.
    """
    if not verdicts:
        return 0.5
    
    from collections import Counter
    counts = Counter(verdicts)
    total = len(verdicts)
    
    # Shannon entropy normalized
    entropy = 0
    for count in counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    
    max_entropy = math.log2(len(counts)) if len(counts) > 1 else 1
    normalized = entropy / max_entropy if max_entropy > 0 else 0
    
    return round(normalized, 4)


def _meta_uncertainty(confidence: float, uncertainty: float) -> float:
    """2nd-order: how uncertain are we about our uncertainty estimate?
    
    Based on how much data we have and how stable the estimate is.
    """
    # With few data points, meta-uncertainty is high
    # This is a simplified heuristic
    if uncertainty < 0.05:
        # Suspiciously certain about uncertainty → meta-uncertainty is moderate
        return 0.3
    elif uncertainty > 0.3:
        # Very uncertain → at least we know we're uncertain (meta is lower)
        return 0.2
    else:
        # Normal range
        return 0.15


def quantify_uncertainty(result: Dict[str, Any]) -> Dict[str, Any]:
    """Full uncertainty quantification for a verification result.
    
    Produces confidence intervals and 2nd-order uncertainty.
    """
    # Collect all confidence signals
    layer_scores = []
    layer_verdicts = []
    
    # Core confidence
    core_conf = result.get("confidence", 0.5)
    layer_scores.append(core_conf)
    
    # L6
    l6 = result.get("L6_statistical", {})
    if l6.get("modifier", 0) != 0:
        layer_scores.append(0.5 + l6["modifier"])
    
    # L7
    l7 = result.get("L7_adversarial", {})
    if l7.get("modifier", 0) != 0:
        layer_scores.append(0.5 + l7["modifier"])
    
    # Deep causal
    deep = result.get("deep_causal", {})
    if deep.get("adjustment", 0) != 0:
        layer_scores.append(0.5 + deep["adjustment"])
    
    # From trace
    for step in result.get("trace", []):
        if "confidence" in step:
            layer_scores.append(step["confidence"])
        if "verdict" in step:
            layer_verdicts.append(step["verdict"])
    
    # Add main verdict
    layer_verdicts.append(result.get("verdict", "UNKNOWN"))
    
    # Bootstrap confidence
    mean, std, ci_low, ci_high = _bootstrap_confidence(layer_scores)
    
    # Agreement uncertainty
    agreement_unc = _agreement_uncertainty(layer_verdicts)
    
    # Combined 1st-order uncertainty
    first_order = round(max(std, agreement_unc * 0.3), 4)
    
    # 2nd-order meta-uncertainty
    second_order = _meta_uncertainty(mean, first_order)
    
    # Calibration check: is stated confidence within bootstrap CI?
    stated_conf = result.get("confidence", 0.5)
    calibrated = ci_low <= stated_conf <= ci_high
    calibration_gap = round(abs(stated_conf - mean), 4)
    
    return {
        "stated_confidence": stated_conf,
        "bootstrap": {
            "mean": mean,
            "std": std,
            "ci_95": [ci_low, ci_high],
            "samples_used": len(layer_scores),
        },
        "uncertainty": {
            "first_order": first_order,
            "second_order": second_order,
            "agreement": agreement_unc,
        },
        "calibration": {
            "within_ci": calibrated,
            "gap": calibration_gap,
            "assessment": (
                "WELL_CALIBRATED" if calibration_gap < 0.05
                else "SLIGHTLY_OFF" if calibration_gap < 0.15
                else "MISCALIBRATED"
            ),
        },
        "display": f"{stated_conf:.2f} ± {first_order:.2f} (meta-unc: {second_order:.2f})",
        "confidence_modifier": round(-0.05 if not calibrated else 0, 4),
    }
