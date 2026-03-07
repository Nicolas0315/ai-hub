import numpy as np
import math

def log_sphere_volume_coeff(d):
    vgamma = np.vectorize(math.lgamma)
    return (d / 2.0) * np.log(np.pi) - vgamma(d / 2.0 + 1.0)

def simulate_cassini():
    M = 1.0
    impact_parameter = 500000.0
    L = 100000000.0
    x1 = np.logspace(np.log10(impact_parameter), np.log10(L), 10000)
    x = np.concatenate((-x1[::-1], x1))
    y = impact_parameter
    r = np.sqrt(x**2 + y**2)
    
    alpha = 3.019557107213268
    
    delay_std = np.trapezoid(2.0 * M / r, x)
    
    phi = -M / r
    d_r = 3.0 * np.exp(phi)
    omega = np.exp(log_sphere_volume_coeff(d_r) - log_sphere_volume_coeff(3.0))
    v_katala = omega**alpha
    delay_katala = np.trapezoid(1.0 / v_katala - 1.0, x)
    
    print(f"Deviation: {((delay_katala/delay_std)-1)*100:.10f}%")

if __name__ == "__main__":
    simulate_cassini()
