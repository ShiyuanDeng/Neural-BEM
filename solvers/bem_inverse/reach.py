"""ON-001 sampled reach proxy and physical harmonic-direction clipping.

Sampling provides an upper estimate of reach, never a certified lower bound.
Projected curves must still pass the ordinary complete-map validity checks.
"""
from time import perf_counter
import numpy as np


def harmonic_bound(coefficients):
    a = np.asarray(coefficients, float)
    if a.ndim != 1 or len(a) % 2 != 1 or not np.isfinite(a).all():
        raise ValueError("Finite real normal harmonics required")
    m = len(a)//2
    return float(abs(a[0])+np.hypot(a[1:m+1], a[m+1:]).sum())


def sampled_reach(curve, count):
    z, dz, ddz = (curve.values(count, j) for j in range(3))
    speed = np.abs(dz)
    if np.any(speed <= 0):
        return None
    normal = -1j*dz/speed
    curvature = np.abs(np.imag(np.conj(dz)*ddz))/speed**3
    radius = np.inf if not np.max(curvature) else 1/np.max(curvature)
    scale = max(float(np.max(abs(z-z.mean()))), np.finfo(float).tiny)
    # Near-diagonal cancellation is replaced by the analytic local curvature limit.
    threshold = 64*np.finfo(float).eps*scale**2
    for begin in range(0, count, 128):
        delta = z[None, :]-z[begin:begin+128, None]
        squared = abs(delta)**2
        component = abs(np.real(delta*np.conj(normal[begin:begin+128, None])))
        valid = (squared > threshold) & (component > 0)
        quotient = np.full(squared.shape, np.inf)
        np.divide(squared, 2*component, out=quotient, where=valid)
        radius = min(radius, float(quotient.min()))
    return float(radius) if np.isfinite(radius) and radius > 0 else None


def estimate_reach(curve):
    started = perf_counter()
    samples = {n: sampled_reach(curve, n) for n in (1024, 2048)}
    finite = [v for v in samples.values() if v is not None]
    if len(finite) == 2 and abs(finite[0]-finite[1])/min(finite) > .1:
        samples[4096] = sampled_reach(curve, 4096)
        finite = [v for v in samples.values() if v is not None]
    return dict(radius=min(finite) if finite else None, samples=samples,
                seconds=perf_counter()-started, cancellation_factor_eps=64,
                interpretation="sampled upper proxy, not a certified lower bound")


def clip_direction(coefficients, curve, length_unit_m, fraction, cache):
    key = curve.coefficients.tobytes()
    fresh = key not in cache
    if fresh:
        # A stage retains only its current accepted-curve proxy.
        cache.clear()
        cache[key] = estimate_reach(curve)
    receipt = cache[key]
    radius = receipt["radius"]
    bound = harmonic_bound(coefficients)
    alpha = min(1., fraction*length_unit_m*radius/bound) if radius is not None and bound > 0 else 1.
    return np.asarray(coefficients)*alpha, dict(reach_alpha=alpha, reach_bound_m=bound,
        reach_radius_m=None if radius is None else radius*length_unit_m,
        reach_samples=receipt["samples"], reach_seconds=receipt["seconds"] if fresh else 0.,
        reach_proxy_unavailable=radius is None, reach_fraction=fraction)
