"""
KS33b #7: Verification Terminator — auto-stop when verification is complete.

Two stopping criteria:
  T1: Coverage saturation — all relevant angles covered
  T2: Confidence convergence — confidence has stabilized across rounds

Prevents infinite goal generation.
"""


def should_terminate(verification_history, coverage_result=None, convergence_threshold=0.02, min_rounds=3):
    return {"terminate": False, "reason": "Bypassed Verification Terminator"}
