"""Exact (Mie) paired data for any disk, and the dense localization landscape it makes affordable.

For a homogeneous disk of radius R centred at z0, with a unit line source
(i/4) H0(k|x - y|) at y and a receiver at x, both outside the disk,

    u_s(x) = sum_n c_n(k, R) H_n(k rho_s) H_n(k rho_r) exp(i n (phi_r - phi_s)),
    c_n = (i/4) [ (2i / (pi R)) J_n(k_i R) / D_n - J_n(k R) ] / H_n(k R),
    D_n = k J_n(k_i R) H_n'(k R) - k_i J_n'(k_i R) H_n(k R),

with (rho, phi) polar coordinates about z0. The Hankel products depend on the
centre only and c_n on the radius only, so a (centre x radius) grid costs one
matrix product per frequency. This is MA-001's `circle.scattered` (checked
against the Kress solver to 4e-14 in MA-002's `mie_check.json`), reorganized
for many circles at once. SC-050's localization objective is reproduced
exactly: 0.5 * mean over frequencies of (||pred - obs|| / ||obs||)^2.
"""
import numpy as np
from scipy.special import hankel1, h1vp, jv, jvp


def radial_coefficients(k, contrast, radii, orders):
    """c_n(k, R): shape (radii, orders)."""
    R = np.asarray(radii, float)[:, None]
    n = np.asarray(orders)[None, :]
    ki = k * np.sqrt(contrast)
    with np.errstate(all='ignore'):
        D = k * jv(n, ki * R) * h1vp(n, k * R) - ki * jvp(n, ki * R) * hankel1(n, k * R)
        c = 0.25j * ((2j / (np.pi * R)) * jv(n, ki * R) / D - jv(n, k * R)) / hankel1(n, k * R)
    return np.where(np.isfinite(c), c, 0)


def geometric_products(k, centers, sources, receivers, orders):
    """H_n(k rho_s) H_n(k rho_r) exp(i n (phi_r - phi_s)): shape (centers, pairs, orders)."""
    zs = sources[:, 0] + 1j * sources[:, 1]
    zr = receivers[:, 0] + 1j * receivers[:, 1]
    c = np.asarray(centers)[:, None]
    ds, dr = zs[None, :] - c, zr[None, :] - c
    n = np.asarray(orders)[None, None, :]
    phase = np.exp(1j * n * (np.angle(dr) - np.angle(ds))[..., None])
    return hankel1(n, k * np.abs(ds)[..., None]) * hankel1(n, k * np.abs(dr)[..., None]) * phase


def paired_data(k, contrast, centers, radii, sources, receivers, cutoff):
    """Scattered paired data for every (centre, radius): shape (centers, radii, pairs)."""
    orders = np.arange(-cutoff, cutoff + 1)
    P = geometric_products(k, centers, sources, receivers, orders)            # (C, pairs, n)
    C = radial_coefficients(k, contrast, radii, orders)                        # (R, n)
    return np.einsum('cpn,rn->crp', P, C)


def landscape(observations, contrast, centers, radii, *, cutoff=None):
    """SC-050's localization loss on a (centre x radius) grid, from exact Mie data.

    `observations` are the package observations (wavenumber, acquisition with
    sources/receivers/strength, scattered data). Circles that would contain a
    source or receiver are returned as inf, as SC-050 refuses them.
    """
    centers = np.asarray(centers, complex)
    radii = np.asarray(radii, float)
    total = np.zeros((len(centers), len(radii)))
    for o in observations:
        acq = o.acquisition
        cut = cutoff or int(np.ceil(o.wavenumber * np.sqrt(max(contrast, 1)) * radii.max() + 30))
        pred = paired_data(o.wavenumber, contrast, centers, radii, acq.sources, acq.receivers, cut) * acq.strength
        obs = np.asarray(o.scattered)
        total += (np.linalg.norm(pred - obs[None, None, :], axis=2) / np.linalg.norm(obs)) ** 2
    loss = 0.5 * total / len(observations)
    points = np.concatenate([o.acquisition.sources for o in observations] +
                            [o.acquisition.receivers for o in observations])
    zp = points[:, 0] + 1j * points[:, 1]
    clearance = np.min(np.abs(zp[None, :] - centers[:, None]), axis=1)[:, None] - radii[None, :]
    return np.where(clearance > 1e-9, loss, np.inf)
