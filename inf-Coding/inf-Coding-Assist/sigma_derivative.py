import numpy as np
from math import lgamma

def sphere_volume_coeff(d):
    return (d / 2.0) * np.log(np.pi) - lgamma(d / 2.0 + 1.0)

def sigma(d1, d2):
    return sphere_volume_coeff(d2) - sphere_volume_coeff(d1)

if __name__ == "__main__":
    d = 3.0
    eps = 1e-6
    d_prime = (sigma(d, d + eps) - sigma(d, d)) / eps
    print(f"d/dD sigma(3, D) at D=3: {d_prime}")
