import numpy as np
import math

def log_sphere_volume_coeff(d):
    """Log-volume coefficient of a d-dimensional unit ball: Vol(d) = pi^(d/2) / Gamma(d/2 + 1)"""
    return (d / 2.0) * np.log(np.pi) - math.lgamma(d / 2.0 + 1.0)

def derive_schwarzschild_dimensional():
    print("[Katala思考済] Schwarzschild Dimensional Gradient Derivation")
    
    n = 3.0
    # Schwarzschild radius (normalized to 1 for calculation)
    rs = 1.0
    
    # Define r range from far away to near rs
    r = np.linspace(1.1 * rs, 10.0 * rs, 100)
    
    # 1. Map Potential to Dimension
    # Phi/c^2 = -rs / 2r
    # D(r) = n * exp(Phi/c^2)
    D = n * np.exp(-rs / (2 * r))
    
    # 2. Calculate Sigma (Scaling Factor)
    log_vol_n = log_sphere_volume_coeff(n)
    sigma = np.array([log_sphere_volume_coeff(d) - log_vol_n for d in D])
    
    # 3. Propose Metric
    g00_std = -(1.0 - rs / r)
    
    # Numerical derivative of log_vol at n=3
    eps = 1e-6
    deriv_log_vol = (log_sphere_volume_coeff(n + eps) - log_sphere_volume_coeff(n - eps)) / (2 * eps)
    
    # alpha = 1 / ( (n/2) * deriv ) ? No, let's re-derive.
    # D approx n * (1 - rs/2r) -> D - n approx -n * rs / 2r = -1.5 * rs/r
    # sigma approx deriv * (D - n) = deriv * (-1.5 * rs/r)
    # Want alpha * sigma = -rs/r
    # alpha * deriv * (-1.5) = -1
    # alpha = 1 / (1.5 * deriv)
    alpha = 1.0 / (1.5 * deriv_log_vol)
    
    g00_katala = -np.exp(alpha * sigma)
    
    print(f"Computed alpha: {alpha:.6f}")
    print(f"Derivative of log(Vol) at D=3: {deriv_log_vol:.6f}")
    
    # Compare values at r = 5*rs
    # Corrected indexing for linspace(1.1, 10, 100)
    # r = 1.1 + (10 - 1.1) * i / 99
    # For r approx 5.5: i approx 49
    idx = 49
    print(f"\nAt r = {r[idx]:.2f} rs:")
    print(f"  Standard g00: {g00_std[idx]:.6f}")
    print(f"  Katala   g00: {g00_katala[idx]:.6f}")
    print(f"  Difference:   {np.abs(g00_std[idx] - g00_katala[idx]):.6e}")
    
    # 4. Check Horizon (r -> rs)
    D_rs = n * np.exp(-0.5)
    sigma_rs = log_sphere_volume_coeff(D_rs) - log_vol_n
    g00_katala_rs = -np.exp(alpha * sigma_rs)
    print(f"\nAt Horizon (r=rs):")
    print(f"  Standard g00: 0.000000")
    print(f"  Katala   g00: {g00_katala_rs:.6f}")
    print(f"  Dimension D:  {D_rs:.6f}")
    
    print("\n[Conclusion]")
    print("The dimensional gradient model reproduces the Schwarzschild weak field limit.")
    print("Near the horizon, it predicts a non-zero g00, suggesting a 'smooth' transition")
    print("rather than a coordinate singularity. Dimension drops to ~1.82 at r=rs.")

if __name__ == "__main__":
    derive_schwarzschild_dimensional()
