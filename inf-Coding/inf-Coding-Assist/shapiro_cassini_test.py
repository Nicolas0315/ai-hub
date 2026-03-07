import numpy as np
import math

def log_sphere_volume_coeff(d):
    vgamma = np.vectorize(math.lgamma)
    return (d / 2.0) * np.log(np.pi) - vgamma(d / 2.0 + 1.0)

def get_omega(r, M, alpha=3.02, n=3.0):
    phi = -M / r
    d_r = n * np.exp(alpha * phi)
    return np.exp(log_sphere_volume_coeff(d_r) - log_sphere_volume_coeff(n))

def simulate_cassini():
    M = 1.0
    impact_parameter = 500000.0  # Approx Solar radius in terms of solar mass M
    L = 100000000.0  # Distance to Earth / Cassini
    
    # We need a log-spaced grid near the sun
    x1 = np.logspace(np.log10(impact_parameter), np.log10(L), 10000)
    x = np.concatenate((-x1[::-1], x1))
    
    y = impact_parameter
    r = np.sqrt(x**2 + y**2)
    
    alpha = 3.02
    
    # Standard GR
    delay_std = np.trapezoid(2.0 * M / r, x)
    
    # Katala
    phi = -M / r
    d_r = 3.0 * np.exp(phi) # wait, in shapiro_delay_simulation it was n * exp(phi), but the script said d_r = n * np.exp(phi). Let's use the exact formulation from before.
    omega = np.exp(log_sphere_volume_coeff(d_r) - log_sphere_volume_coeff(3.0))
    v_katala = omega**alpha
    delay_katala = np.trapezoid(1.0 / v_katala - 1.0, x)
    
    print(f"Impact Parameter: {impact_parameter}")
    print(f"GR Delay: {delay_std}")
    print(f"Katala Delay: {delay_katala}")
    print(f"Deviation: {((delay_katala/delay_std)-1)*100:.8f}%")

if __name__ == "__main__":
    simulate_cassini()
