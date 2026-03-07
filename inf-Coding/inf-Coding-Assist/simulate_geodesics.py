import numpy as np
import math

def sphere_volume_coeff(d):
    """Vol(d) = pi^(d/2) / Gamma(d/2 + 1)"""
    if d <= 0: return 0
    return np.pi**(d/2.0) / math.gamma(d/2.0 + 1.0)

def get_dimension(r, M, n=3.0, alpha=1.0):
    """D(r) = n * exp(alpha * Phi/c^2), Phi = -M/r"""
    # Using G=c=1
    phi = -M / r
    return n * np.exp(alpha * phi)

def get_omega(r, M, n=3.0, alpha=1.0):
    """omega(r) = Vol(D(r)) / Vol(n)"""
    d_r = get_dimension(r, M, n, alpha)
    return sphere_volume_coeff(d_r) / sphere_volume_coeff(n)

def simulate_ray(impact_parameter, M, steps=1000, dt=0.1, alpha=1.0, beta=2.0, gamma_param=2.0):
    """
    Simulates a light ray in the dimensional gradient field.
    A(r) = omega(r)^beta
    B(r) = omega(r)^-gamma_param (Using -gamma to match 1/A behavior)
    """
    # Initial position (x, y) - coming from far left
    x = -20.0
    y = impact_parameter
    
    trajectory = [[x, y]]
    
    # Velocity (vx, vy)
    vx = 1.0
    vy = 0.0
    
    for _ in range(steps):
        r = np.sqrt(x**2 + y**2)
        if r < 2.1 * M: # Close to horizon
            break
            
        omega = get_omega(r, M, alpha=alpha)
        # Effective refractive index/potential
        # In GR, n_eff = 1 + 2M/r
        # Here we use the gradient of omega
        
        # Simple Newtonian-like deflection for simulation
        # a = - grad(potential)
        # Here potential ~ log(omega)
        
        # d_omega/dr
        eps = 1e-4
        omega_plus = get_omega(r + eps, M, alpha=alpha)
        d_omega_dr = (omega_plus - omega) / eps
        
        # Acceleration magnitude (simplified)
        force = beta * d_omega_dr / omega
        
        ax = force * (x / r)
        ay = force * (y / r)
        
        vx += ax * dt
        vy += ay * dt
        
        # Keep speed constant (light)
        speed = np.sqrt(vx**2 + vy**2)
        vx /= speed
        vy /= speed
        
        x += vx * dt
        y += vy * dt
        
        trajectory.append([x, y])
        if x > 20.0: break
        
    return np.array(trajectory)

if __name__ == "__main__":
    M = 1.0
    alphas = [0.5, 1.0, 2.0]
    impact_b = 5.0
    
    results = []
    for a in alphas:
        traj = simulate_ray(impact_b, M, alpha=a)
        final_angle = np.arctan2(traj[-1, 1], traj[-1, 0])
        results.append({
            "alpha": a,
            "deflection_angle": final_angle,
            "final_y": traj[-1, 1]
        })
        print(f"Alpha={a}: Final Angle={final_angle:.6f}")
    
    import json
    with open("/mnt/c/Users/ogosh/Documents/NICOLAS/Katala/inf-Coding/inf-Coding-Assist/data/geodesic_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("[Katala思考済] Geodesic simulation completed. Results saved to JSON.")
