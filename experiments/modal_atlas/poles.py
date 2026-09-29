"""Scattering poles of the nodal Müller/Kress system by Beyn's contour-integral method.

The transmission system T(k) = A(k, k sqrt(contrast)) is analytic in the right
half k-plane. Its eigenvalues (scattering resonances) inside a closed contour
are those of the small matrix built from the moments

    A_j = (1 / 2 pi i) \\oint k^j T(k)^{-1} V dk,  j = 0, 1,

with a random probe block V (W.-J. Beyn, Linear Algebra Appl. 436 (2012)
3839-3863, Integral method 1). Circles are discretized by the trapezoid rule.
Each returned pole is polished by Newton's method on det T, with
dk = -1 / tr(T^{-1} T'), and qualified by the smallest singular value of T at
the pole relative to its largest.
"""
from dataclasses import dataclass

import numpy as np
from scipy.linalg import lu_factor, lu_solve

from gpr_bem_kress.execution import execution
from gpr_bem_kress.system import build_muller_system


def system(curve_nodes, k, contrast):
    with execution(kernels='reference', device='cpu'):
        return np.asarray(build_muller_system(curve_nodes, k, k * np.sqrt(contrast)).system_matrix)


@dataclass
class Pole:
    k: complex
    smallest_singular: float   # sigma_min / sigma_max of T(k)
    newton_steps: int
    right: np.ndarray          # null vector (traces [u; du/dn] at the nodes)
    left: np.ndarray

    @property
    def quality(self):
        return self.k.real / (-2 * self.k.imag)


def beyn(curve_nodes, contrast, center, radius, *, probes=24, points=64, rank_tol=1e-9, seed=0):
    """Eigenvalue estimates of T inside the circle |k - center| < radius."""
    n = 2 * curve_nodes.num_nodes
    V = np.random.default_rng(seed).normal(size=(n, probes)) + 1j * np.random.default_rng(seed + 1).normal(
        size=(n, probes))
    A0 = np.zeros((n, probes), complex)
    A1 = np.zeros((n, probes), complex)
    for j in range(points):
        phase = np.exp(2j * np.pi * j / points)
        z = center + radius * phase
        X = lu_solve(lu_factor(system(curve_nodes, z, contrast)), V)
        weight = radius * phase / points          # dz / (2 pi i) under the trapezoid rule
        A0 += weight * X
        A1 += weight * z * X
    U, s, Wh = np.linalg.svd(A0, full_matrices=False)
    keep = s > rank_tol * max(s[0], 1e-300)
    if not keep.any():
        return np.array([], complex), s
    if keep.all():
        raise RuntimeError('Probe block saturated: increase probes for this contour; singular values '
                           + np.array2string(s / s[0], precision=1))
    U, s, W = U[:, keep], s[keep], Wh[keep].conj().T
    B = U.conj().T @ A1 @ W / s
    values = np.linalg.eigvals(B)
    return values[np.abs(values - center) < radius], s


def polish(curve_nodes, contrast, k, *, steps=30, h=1e-6, tol=1e-13):
    """Newton on det T; returns the pole, its null vectors and sigma_min/sigma_max."""
    used = 0
    for used in range(1, steps + 1):
        T = system(curve_nodes, k, contrast)
        dT = (system(curve_nodes, k + h, contrast) - system(curve_nodes, k - h, contrast)) / (2 * h)
        factors = lu_factor(T)
        step = -1.0 / np.trace(lu_solve(factors, dT))
        k = k + step
        if abs(step) < tol * max(1.0, abs(k)):
            break
    T = system(curve_nodes, k, contrast)
    U, s, Wh = np.linalg.svd(T)
    return Pole(k=complex(k), smallest_singular=float(s[-1] / s[0]), newton_steps=used,
                right=Wh[-1].conj(), left=U[:, -1].conj())


def poles_in_band(curve_nodes, contrast, low, high, *, depth=0.25, probes=24, points=64, polish_poles=True):
    """Poles with low <= Re k <= high and -depth <= Im k < 0, from overlapping circles on the real axis."""
    radius = depth
    centers = np.arange(low, high + radius, radius)       # circles overlap by half a radius on each side
    found = []
    for center in centers:
        values, _ = beyn(curve_nodes, contrast, complex(center, 0.0), radius, probes=probes, points=points)
        for value in values:
            if not (low <= value.real <= high and -depth <= value.imag < 1e-9):
                continue
            if all(abs(value - f) > 1e-6 * max(1, abs(value)) for f in found):
                found.append(value)
    if not polish_poles:
        return sorted(found, key=lambda z: z.real)
    out = []
    for value in found:
        pole = polish(curve_nodes, contrast, value)
        if all(abs(pole.k - p.k) > 1e-8 * abs(pole.k) for p in out):
            out.append(pole)
    return sorted(out, key=lambda p: p.k.real)


def smallest_singular(curve_nodes, contrast, k):
    s = np.linalg.svd(system(curve_nodes, k, contrast), compute_uv=False)
    return float(s[-1] / s[0])


def near_axis_poles(curve_nodes, contrast, low, high, *, spacing=0.01, max_quality=None):
    """High-Q poles from dips of sigma_min(T) on a real grid, polished by complex Newton.

    A pole k* = a - i g produces a dip near a of width about g, so the grid
    resolves poles with g >~ spacing; much sharper poles couple to exterior data
    only within a few linewidths of a (their residue scales like g).
    """
    grid = np.arange(low, high + spacing / 2, spacing)
    sigma = np.array([smallest_singular(curve_nodes, contrast, k) for k in grid])
    minima = [i for i in range(1, len(grid) - 1) if sigma[i] < sigma[i - 1] and sigma[i] <= sigma[i + 1]]
    out = []
    for i in minima:
        pole = polish(curve_nodes, contrast, complex(grid[i], -spacing))
        if not (low - spacing <= pole.k.real <= high + spacing and pole.k.imag < 0):
            continue
        if all(abs(pole.k - p.k) > 1e-7 * abs(pole.k) for p in out):
            out.append(pole)
    return sorted(out, key=lambda p: p.k.real), grid, sigma
