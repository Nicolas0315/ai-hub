import numpy as np
import math

def log_sphere_volume_coeff(d):
    vgamma = np.vectorize(math.lgamma)
    return (d / 2.0) * np.log(np.pi) - vgamma(d / 2.0 + 1.0)

def get_omega(r, M, alpha=3.02, n=3.0):
    phi = -M / r
    d_r = n * np.exp(phi)
    return np.exp(log_sphere_volume_coeff(d_r) - log_sphere_volume_coeff(n))

def simulate_shapiro():
    print("[Katala思考済] Shapiro Delay Simulation in Dimensional Gradient Field")
    
    M = 1.0 # Source mass
    impact_parameter = 10.0 # Closest approach
    L = 100.0 # Source/Receiver distance from M
    
    # Path from -L to L along x-axis, with y = impact_parameter
    x = np.linspace(-L, L, 2000)
    y = impact_parameter
    r = np.sqrt(x**2 + y**2)
    
    # Katala parameters
    alpha = 3.02 # From previous derivation
    
    # Standard GR delay (approximate)
    # dt = 1/v - 1 = 1/(1-2M/r) - 1 approx 2M/r
    delay_std = np.trapezoid(2.0 * M / r, x)
    
    # Katala delay
    # v = sqrt(A/B). Assume B = 1/A.
    # A = omega(r)^beta. With beta calculated to match GR in weak field.
    # In derive_schwarzschild_dimensional.py, g00 = -exp(alpha * sigma)
    # So A = exp(alpha * sigma) = omega(r)^alpha
    beta = alpha
    v_katala = get_omega(r, M, alpha=alpha)**beta
    delay_katala = np.trapezoid(1.0 / v_katala - 1.0, x)
    
    print(f"Impact Parameter: {impact_parameter}")
    print(f"Distance L:       {L}")
    print(f"Standard GR Delay (dt): {delay_std:.10f}")
    print(f"Katala Model Delay (dt): {delay_katala:.10f}")
    print(f"Deviation:             {((delay_katala / delay_std) - 1) * 100:.4f}%")
    
    # Save results
    import json
    results = {
        "impact_parameter": impact_parameter,
        "L": L,
        "delay_std": delay_std,
        "delay_katala": delay_katala,
        "deviation_percent": ((delay_katala / delay_std) - 1) * 100
    }
    with open("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/data/shapiro_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to JSON.")

if __name__ == "__main__":
    simulate_shapiro()
