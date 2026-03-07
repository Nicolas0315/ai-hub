import numpy as np
from l2_link_verification import xi_map, inter_dimensional_scaling

def run_tests():
    print("[Katala思考済] Xi Link Automated Test Suite")
    print("-" * 40)

    # 1. Base Case: 3.0 -> 2.0
    d1, d2 = 3.0, 2.0
    sigma = inter_dimensional_scaling(d1, d2)
    factor = np.exp(sigma)
    print(f"Test 1 (3D -> 2D): factor = {factor:.6f} (Expected: 0.750000)")
    assert np.allclose(factor, 0.75), "3D->2D factor mismatch"

    # 2. Identity Case: 3.0 -> 3.0
    d1, d2 = 3.0, 3.0
    sigma = inter_dimensional_scaling(d1, d2)
    factor = np.exp(sigma)
    print(f"Test 2 (Identity): factor = {factor:.6f} (Expected: 1.000000)")
    assert np.allclose(factor, 1.0), "Identity factor mismatch"

    # 3. Non-integer Case: 3.0 -> 2.58 (Sierpinski/Fractal-like)
    d1, d2 = 3.0, 2.58
    sigma = inter_dimensional_scaling(d1, d2)
    factor = np.exp(sigma)
    print(f"Test 3 (3D -> 2.58D): factor = {factor:.6f}")

    # 4. Continuity Test (Small delta)
    d1 = 3.0
    d2 = 3.0001
    sigma = inter_dimensional_scaling(d1, d2)
    factor = np.exp(sigma)
    print(f"Test 4 (Continuity): d=3.0001 factor = {factor:.8f}")
    assert np.allclose(factor, 1.0, atol=1e-3), "Continuity failed"

    # 5. Reverse Link Stability: Xi(d1->d2) * Xi(d2->d1) = 1
    d1, d2 = 3.0, 2.58
    f1 = np.exp(inter_dimensional_scaling(d1, d2))
    f2 = np.exp(inter_dimensional_scaling(d2, d1))
    product = f1 * f2
    print(f"Test 5 (Reversibility): product = {product:.10f} (Expected: 1.000000)")
    assert np.allclose(product, 1.0), "Reversibility failed"

    print("-" * 40)
    print("All tests passed successfully.")

if __name__ == "__main__":
    run_tests()
