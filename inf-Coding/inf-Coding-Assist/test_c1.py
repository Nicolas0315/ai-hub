import numpy as np
import math
def log_sphere_volume_coeff(d):
    vgamma = np.vectorize(math.lgamma)
    return (d / 2.0) * np.log(np.pi) - vgamma(d / 2.0 + 1.0)
n = 3.0
vol_n = np.exp(log_sphere_volume_coeff(n))
vol_n_eps = np.exp(log_sphere_volume_coeff(n + 0.0001))
vol_prime_over_vol = (vol_n_eps - vol_n) / 0.0001 / vol_n
alpha = 2.0 / (n * vol_prime_over_vol)
print("Exact alpha for c1=2:", alpha)
