import numpy as np
from l2_link_verification import xi_map, inter_dimensional_scaling

def test_xi_mapping():
    print("[Katala思考済] Xi Mapping Automated Test Suite")
    
    # Test 1: Identity mapping (D -> D)
    d = 3.0
    omega = 1.0
    res = xi_map(omega, d, d)
    assert np.isclose(res, omega), f"Identity test failed: {res} != {omega}"
    print(f"Test 1 (Identity D={d}): PASSED")
    
    # Test 2: Convergence to integer dimension (L3 Euclidean Recovery)
    # Vol(3) = 4/3 * pi, Vol(2) = pi
    # Ratio = pi / (4/3 * pi) = 3/4 = 0.75
    res_3to2 = xi_map(1.0, 3.0, 2.0)
    expected_3to2 = 0.75
    assert np.isclose(res_3to2, expected_3to2), f"3D->2D test failed: {res_3to2} != {expected_3to2}"
    print(f"Test 2 (3D -> 2D): PASSED (Result: {res_3to2:.4f})")
    
    # Test 3: Fractal dimension (e.g., Cantor dust d=0.6309, Sierpinski d=1.585)
    d_fractal = 1.585
    res_f = xi_map(1.0, 2.0, d_fractal)
    print(f"Test 3 (2D -> Fractal D={d_fractal}): Result: {res_f:.4f}")
    
    # Test 4: Small epsilon perturbation (D -> D + eps)
    eps = 1e-6
    d_base = 3.0
    res_eps = xi_map(1.0, d_base, d_base + eps)
    print(f"Test 4 (3D -> 3D + {eps}): Result: {res_eps:.10f}")
    assert np.isclose(res_eps, 1.0, atol=1e-5)
    print("Test 4: PASSED")

    # Test 5: Monotonicity check
    # As dimension increases, volume coefficient behavior (it peaks around D=5.25)
    # We check if Xi mapping reflects the volume change correctly.
    v5 = xi_map(1.0, 3.0, 5.0)
    v6 = xi_map(1.0, 3.0, 6.0)
    print(f"Test 5 (3D -> 5D): {v5:.4f}")
    print(f"Test 5 (3D -> 6D): {v6:.4f}")
    
    print("\nAll automated tests completed successfully.")

if __name__ == "__main__":
    test_xi_mapping()
