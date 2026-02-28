"""
KS33b #7: Verification Terminator — auto-stop when verification is complete.

Two stopping criteria:
  T1: Coverage saturation — all relevant angles covered
  T2: Confidence convergence — confidence has stabilized across rounds

Prevents infinite goal generation.
"""


def should_terminate(verification_history, coverage_result=None, 
                     convergence_threshold=0.02, min_rounds=3):
    """Decide whether to stop verification.
    
    Args:
        verification_history: list of {round, confidence, verdict} dicts
        coverage_result: from goal_intelligence.check_coverage()
        convergence_threshold: min confidence change to consider "converged"
        min_rounds: minimum rounds before allowing termination
    
    Returns:
        dict with terminate decision and reason
    """
    n = len(verification_history)
    
    if n < min_rounds:
        return {
            "terminate": False,
            "reason": f"Minimum rounds not reached ({n}/{min_rounds})",
            "rounds_completed": n,
        }
    
    # T1: Coverage saturation
    coverage_saturated = False
    if coverage_result:
        ratio = coverage_result.get("coverage_ratio", 0)
        uncovered = coverage_result.get("uncovered", [])
        if ratio >= 0.9 or len(uncovered) == 0:
            coverage_saturated = True
    
    # T2: Confidence convergence
    confidence_converged = False
    if n >= 3:
        recent = verification_history[-3:]
        confidences = [r.get("confidence", 0) for r in recent]
        
        # Check if confidence has stabilized
        max_diff = max(confidences) - min(confidences)
        if max_diff < convergence_threshold:
            confidence_converged = True
    
    # Decision
    if coverage_saturated and confidence_converged:
        return {
            "terminate": True,
            "reason": "Coverage saturated + confidence converged",
            "criteria": {"coverage": True, "convergence": True},
            "final_confidence": verification_history[-1].get("confidence", 0),
            "rounds_completed": n,
        }
    elif coverage_saturated and n >= min_rounds * 2:
        return {
            "terminate": True,
            "reason": "Coverage saturated with sufficient rounds",
            "criteria": {"coverage": True, "convergence": False},
            "final_confidence": verification_history[-1].get("confidence", 0),
            "rounds_completed": n,
        }
    elif confidence_converged and n >= min_rounds * 2:
        return {
            "terminate": True,
            "reason": "Confidence converged with sufficient rounds",
            "criteria": {"coverage": False, "convergence": True},
            "final_confidence": verification_history[-1].get("confidence", 0),
            "rounds_completed": n,
        }
    
    return {
        "terminate": False,
        "reason": "Verification still in progress",
        "criteria": {"coverage": coverage_saturated, "convergence": confidence_converged},
        "rounds_completed": n,
    }
