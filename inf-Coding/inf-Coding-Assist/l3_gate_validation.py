from __future__ import annotations
import sys
import os

# Add ViszBot/core to path
sys.path.append(os.path.abspath("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/ViszBot"))

from core.l3_recovery_gate import L3RecoveryGate

def validate_l3_gate():
    gate = L3RecoveryGate(tolerance=0.01)
    print("[Katala思考済] L3 Recovery Gate Live Validation")
    
    test_cases = [
        {
            "name": "Case A: Precise Integer (Safe)",
            "text": "The dimension is d=3.0, following Euclidean recovery.",
            "expected": True
        },
        {
            "name": "Case B: Near Integer (No Keyword - Warning Expected)",
            "text": "The dimension is d=3.0001.",
            "expected": False
        },
        {
            "name": "Case C: Near Integer (With Keyword - Safe)",
            "text": "The dimension is d=2.999, which allows for Euclidean recovery.",
            "expected": True
        },
        {
            "name": "Case D: Fractal Dimension (Safe)",
            "text": "The dimension is d=2.58.",
            "expected": True
        },
        {
            "name": "Case E: Multiple dimensions (One invalid)",
            "text": "We start at d=2.58 and move to d=3.0001.",
            "expected": False
        },
        {
            "name": "Case F: Japanese Keywords (Safe)",
            "text": "次元は d=3.0001 ですが、ユークリッド幾何学へ回収されます。",
            "expected": True
        }
    ]
    
    passed = 0
    for case in test_cases:
        res = gate.verify_text(case["text"])
        is_passed = res["l3_compliant"] == case["expected"]
        status = "PASSED" if is_passed else "FAILED"
        print(f"[{status}] {case['name']}")
        if not is_passed:
            print(f"  Result: {res}")
        else:
            passed += 1
            
    print(f"\nSummary: {passed}/{len(test_cases)} cases passed.")
    
    if passed == len(test_cases):
        print("L3 Gate Validation: SUCCESS")
    else:
        print("L3 Gate Validation: FAILURE")

if __name__ == "__main__":
    validate_l3_gate()
