"""Sampling utilities with explicit acquisition and discrepancy contracts."""
from dataclasses import dataclass

import numpy as np
from scipy import ndimage
from scipy.optimize import brentq


def tikhonov_sampling(matrix, probes, relative_discrepancy=1e-3):
    """Solve N g_z = phi_z by SVD and a right-hand-side Morozov tolerance.

    N must contain the measured FULL receiver-by-source matrix at ONE
    frequency. A vector of paired observations cannot determine N. The
    caller supplies quadrature weighting in N and phi when appropriate.
    This numerical discrepancy tolerance is NOT an estimated operator noise
    level. Unattainable tolerances are reported, not silently relaxed.
    """
    a, b = np.asarray(matrix, complex), np.asarray(probes, complex)
    if a.ndim != 2 or min(a.shape) < 2:
        raise ValueError("LSM requires a full receiver-by-source matrix, not paired data.")
    if b.ndim != 2 or b.shape[0] != a.shape[0]:
        raise ValueError("Probes must have one receiver row per matrix row.")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Sampling inputs must be finite.")
    if not 0 < relative_discrepancy < 1:
        raise ValueError("Discrepancy must lie in (0,1).")
    u, s, _ = np.linalg.svd(a, full_matrices=False)
    if s[0] == 0:
        raise ValueError("Zero scattering matrix has no sampling information.")
    projection = u.conj().T @ b
    norms2 = np.sum(abs(b)**2, axis=0)
    if np.any(norms2 == 0):
        raise ValueError("Sampling probes must be nonzero.")
    outside = np.maximum(norms2 - np.sum(abs(projection)**2, axis=0), 0)
    power = (s / s[0])**2
    floor = 1e-30
    indicator, parameters, attained, residuals = [], [], [], []
    for j, norm2 in enumerate(norms2):
        target = relative_discrepancy**2 * norm2

        def residual2(log_alpha):
            alpha = np.exp(log_alpha)
            return outside[j] + np.sum(abs(projection[:, j])**2 * (alpha / (power + alpha))**2)

        low, high = np.log(floor), np.log(1e12)
        feasible = residual2(low) <= target <= residual2(high)
        alpha = np.exp(brentq(lambda x: residual2(x) - target, low, high)) if feasible else floor
        gnorm = np.linalg.norm(s / (s**2 + alpha * s[0]**2) * projection[:, j])
        # An unattainable probe must not masquerade as an arbitrarily bright
        # inclusion when its minimum-norm coefficient vector is near zero.
        indicator.append(1 / max(gnorm, np.finfo(float).tiny) if feasible else np.nan)
        parameters.append(alpha * s[0]**2)
        attained.append(feasible)
        residuals.append(np.sqrt(residual2(np.log(alpha)) / norm2))
    return dict(indicator=np.asarray(indicator), alpha=np.asarray(parameters),
                discrepancy_attained=np.asarray(attained), relative_residual=np.asarray(residuals),
                singular_values=s)


@dataclass(frozen=True)
class CircleSeed:
    center: tuple
    radius: float


def threshold_circles(points, values, *, center=(.5, .5), inspection_radius=.2,
                      threshold=.6, minimum_pixels=4, minimum_radius=.008,
                      maximum_radius=.065, maximum_components=6):
    """Data-only negative-TD superlevel sets, area-equivalent circle seeds.

    The fixed threshold and radius limits are shared by all scenes; no target
    count or shape is available. Positive derivatives produce no seeds.
    Overlapping area-equivalent circles are shrunk symmetrically.
    """
    points, values = np.asarray(points), np.asarray(values)
    if points.shape != (*values.shape, 2) or values.ndim != 2:
        raise ValueError("Expected a Cartesian image grid and scalar values.")
    if not 0 < threshold <= 1:
        raise ValueError("Threshold must be in (0,1].")
    domain = np.linalg.norm(points - center, axis=-1) <= inspection_radius
    score = np.where(domain & np.isfinite(values), np.maximum(-values, 0), 0)
    if score.max() == 0:
        return (), np.zeros(values.shape, bool)
    mask = score >= threshold * score.max()
    labels, count = ndimage.label(mask)
    pixel_area = abs(np.linalg.det(np.stack((points[0, 1] - points[0, 0],
                                             points[1, 0] - points[0, 0]))))
    components = []
    for label in range(1, count + 1):
        region = labels == label
        if np.count_nonzero(region) < minimum_pixels:
            continue
        c = np.average(points[region], axis=0, weights=score[region])
        r = np.clip(np.sqrt(np.count_nonzero(region) * pixel_area / np.pi),
                    minimum_radius, maximum_radius)
        r = min(r, inspection_radius - np.linalg.norm(c - center) - 1e-5)
        if r >= minimum_radius:
            components.append([c, float(r), float(np.sum(score[region]))])
    components.sort(key=lambda item: -item[2])
    components = components[:maximum_components]
    for i, first in enumerate(components):
        for second in components[i+1:]:
            distance = np.linalg.norm(first[0] - second[0])
            factor = min(1., .9 * distance / (first[1] + second[1]))
            first[1] *= factor
            second[1] *= factor
    return tuple(CircleSeed(tuple(c), r) for c, r, _ in components if r >= minimum_radius), mask
