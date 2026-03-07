import numpy as np

def log_sphere_volume_coeff(d):
    from math import lgamma
    return (d / 2.0) * np.log(np.pi) - lgamma(d / 2.0 + 1.0)

def get_katala_metric(r, rs, n=3.0, alpha=3.019507):
    # D(r) = n * exp(-rs/2r)
    D = n * np.exp(-rs / (2.0 * r))
    # sigma = log(Vol(D)) - log(Vol(n))
    sigma = log_sphere_volume_coeff(D) - log_sphere_volume_coeff(n)
    # factor = exp(alpha * sigma)
    factor = np.exp(alpha * sigma)
    
    # Propose a simple scaling: g00 = -factor, grr = 1/factor (to keep some GR flavor)
    # OR g00 = -factor, grr = factor (pure IUT scaling)
    # Let's try both or just one and see.
    # Given Axiom 2: lim D->n, g -> delta.
    # Standard Schwarzschild weak field: g00 = -(1-rs/r), grr = 1+rs/r
    # Our factor in weak field: exp(alpha*sigma) approx 1 - rs/r
    # So g00 = -factor matches GR.
    # And grr = 1/factor approx 1/(1-rs/r) approx 1+rs/r also matches GR!
    
    g00 = -factor
    grr = 1.0 / factor
    return g00, grr

def simulate_light_deflection():
    print("[Katala思考済] Light Geodesic Simulation (Deflection Angle)")
    
    rs = 1.0
    b = 5.0 * rs # Impact parameter
    
    # Equation of motion for light in a central potential (approximate)
    # d^2u/dphi^2 + u = 3/2 * rs * u^2 (Standard GR)
    # For Katala, we use the effective potential from the metric.
    # For a metric ds^2 = A(r) dt^2 + B(r) dr^2 + r^2 dphi^2
    # The orbit equation is: (dr/dphi)^2 = r^4 / (b^2 * B(r)) * (1/(-A(r)) * (b/r)^2 * (-A(inf))? No.)
    # Let's use the conserved quantities:
    # E = -g00 * dt/dlambda
    # L = r^2 * dphi/dlambda
    # For light, ds^2 = 0: 0 = g00 (dt/dl)^2 + grr (dr/dl)^2 + r^2 (dphi/dl)^2
    # 0 = g00 (E/-g00)^2 + grr (dr/dphi * dphi/dl)^2 + r^2 (dphi/dl)^2
    # 0 = E^2 / g00 + grr (dr/dphi * L/r^2)^2 + r^2 (L/r^2)^2
    # (dr/dphi)^2 = (r^4 / (L^2 * grr)) * (-E^2 / g00 - L^2 / r^2)
    # Let b = L/E.
    # (dr/dphi)^2 = (r^4 / grr) * (1 / (b^2 * (-g00)) - 1 / r^2)
    
    def dr_dphi(r, b, rs):
        g00, grr = get_katala_metric(r, rs)
        val = (r**4 / grr) * (1.0 / (b**2 * (-g00)) - 1.0 / r**2)
        return np.sqrt(max(0, val))

    # Numerical integration of dphi = dr / (dr/dphi)
    # From r_min to infinity. r_min is where dr/dphi = 0.
    
    # Find r_min
    r_range = np.linspace(1.5 * rs, 10.0 * rs, 1000)
    vals = [1.0 / (b**2 * (-get_katala_metric(ri, rs)[0])) - 1.0 / ri**2 for ri in r_range]
    r_min = r_range[np.argmin(np.abs(vals))]
    
    print(f"Impact parameter b: {b:.2f} rs")
    print(f"Closest approach r_min: {r_min:.4f} rs")
    
    # Integration
    rs_list = [1.0]
    phi_total = 0
    r_steps = np.logspace(np.log10(r_min), 4, 10000)
    for i in range(len(r_steps)-1):
        r1 = r_steps[i]
        r2 = r_steps[i+1]
        mid_r = (r1 + r2) / 2.0
        deriv = dr_dphi(mid_r, b, rs)
        if deriv > 0:
            phi_total += (r2 - r1) / deriv
            
    deflection_katala = 2 * phi_total - np.pi
    
    # Standard GR deflection: 4GM / (bc^2) = 2rs / b
    deflection_gr = 2.0 * rs / b
    
    print(f"Deflection (Katala): {deflection_katala:.6f} rad")
    print(f"Deflection (GR):     {deflection_gr:.6f} rad")
    print(f"Deviation:           {(deflection_katala - deflection_gr) / deflection_gr * 100:.4f}%")

if __name__ == "__main__":
    simulate_light_deflection()
