"""Quadrature-by-expansion (QBX) evaluation of the near-diagonal Muller kernel band.

Klockner, Barnett, Greengard, O'Neil, *Quadrature by expansion: A new method
for the evaluation of layer potentials*, J. Comput. Phys. 252 (2013),
332-349. See ``ibim_tmz_forward.py``'s module docstring for why this exists,
and for why the exact diagonal is deliberately *not* handled here.

Construction
------------
Graf's addition theorem for the 2D Helmholtz fundamental solution, about an
expansion center ``c``, for ``|x - c| < |y - c|``::

    H_0^(1)(k|x-y|) = sum_n J_n(k|x-c|) H_n^(1)(k|y-c|) exp(i n (theta_x - theta_y))

with ``theta_x = arg(x - c)``, ``theta_y = arg(y - c)``. Truncated at
``+-expansion_order``, this gives a *regular* (entire, no singularity
anywhere) function of the target ``x`` -- so once its coefficients are built
from the source side, it can be evaluated, and analytically differentiated,
at any target point strictly inside the disk of convergence. The
single-layer kernel is this expansion directly; the other three Muller
blocks come from differentiating it -- once on the source (``y``) side,
before evaluating (folded into the coefficients below), and once on the
target (``x``) side, after evaluating (analytic, since the target-side
expansion is smooth everywhere it's evaluated) -- rather than by deriving
four separate addition-theorem identities by hand.

Placing ``c`` off the curve by a *signed* offset ``r`` along the normal and
evaluating from both signs recovers the boundary (principal-value) operator
value directly via the Plemelj jump relations: for any density,
``(exterior-side one-sided limit + interior-side one-sided limit) / 2``
equals the principal-value operator regardless of which physical side is
which, since the jump term cancels in the average either way. That holds at
the kernel level too (linearity), so the same averaging is applied to the
raw kernel values before ever introducing a density -- this is what
``_qbx_pv_row`` does, and it is *not* a no-op for D/K' (their jump does not
cancel without it), only for S/T (already continuous, so the average is a
free numerical consistency check rather than a needed correction).

Radius sizing -- smaller than neighbour spacing, not larger
-------------------------------------------------------------
The natural first guess (this module's first draft, before it was measured)
is to make the expansion radius ``r`` a few times *larger* than the local
node spacing ``h``, on the reasoning that the coefficient sum needs several
nodes to "see". That is backwards for this discretisation, and measured
(not just argued) to fail: for a fixed source node at arc-distance ``s`` from
the target, ``|y-c|/|x-c| - 1 ~ s^2 / (2 r^2)`` (small-``s`` expansion, valid
while ``r`` stays below the local radius of curvature). *Increasing* ``r``
at fixed ``s`` therefore pushes that ratio *closer* to 1 -- the boundary of
Graf's addition theorem's convergence -- not further from it, and the
truncated series' error scales like ``(1/ratio)^order``. Tried at
``r ~ 3h`` (a "few times the spacing", the obvious first guess): the nearest
neighbour sits at ratio ~1.06, and even ``order=40`` does not converge (~1
correct digit). Tried instead at ``r ~ 0.5h`` (*smaller* than the spacing):
the nearest neighbour already sits at ratio ~2.2, and ``order=20`` converges
to 6+ digits, matching the closed-form ``_difference_kernels`` result on
well-separated pairs to the same precision. ``radius_spacing_factor`` below
reflects this measurement, not the naive guess.

This is also *why* the exact diagonal is out of scope here regardless of how
``r`` is chosen: for the source node coincident with the target, ``s = 0``
identically, so the ratio is exactly 1 for *any* ``r`` -- there is no radius
that fixes it. See ``ibim_tmz_forward.py``'s module docstring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
from scipy.special import hankel1, jv

from .ibim_tmz_forward import _local_frames, _local_radius, _sdf_curvature

__all__ = ["QbxSettings", "apply_qbx_band_correction"]

_BLOCKS = ("single", "double", "adjoint", "hyper")


@dataclass
class QbxSettings:
    """Numerical parameters of the expansion -- not physical trace offsets.

    ``expansion_order``: the ``n`` truncation of the cylindrical-harmonic sum;
    accuracy is spectral in this (Bessel/Hankel series decay), so a handful
    of extra terms buys many more digits, at linear extra cost per node. 20
    gives 6+ digit agreement with the closed-form kernel at the nearest
    included neighbour under the radius sizing below (measured, see module
    docstring); kept above that for margin.

    ``radius_spacing_factor``: the expansion offset at node i is
    ``min(radius_spacing_factor * local_spacing_i, radius_curvature_factor *
    local_radius_of_curvature_i)``. Deliberately *below* 1 -- see module
    docstring for why a larger radius makes the nearest neighbour's Graf
    series converge *worse*, not better, in this (Nystrom, not
    panel-quadrature) discretisation.

    ``radius_curvature_factor``: upper bound keeping the expansion center
    inside the curve's local disk of convergence (Graf's theorem needs
    ``r`` below the local radius of curvature; see the addition-theorem
    validity discussion this module's docstring references).

    ``band_factor``: a target node's matrix row is QBX-corrected for every
    *other* source within ``band_factor * r_i`` of it (Euclidean distance,
    excluding the node itself); this should be generous enough that QBX and
    the untouched plain-quadrature entries agree in the transition zone,
    since both approximate the same true kernel there.
    """

    expansion_order: int = 20
    radius_spacing_factor: float = 0.5
    radius_curvature_factor: float = 0.2
    band_factor: float = 8.0


def _qbx_side_row(
    x_i: np.ndarray,
    n_i: np.ndarray,
    y_band: np.ndarray,
    n_y_band: np.ndarray,
    k: complex,
    r_i: float,
    side: float,
    order: int,
) -> dict[str, np.ndarray]:
    """One-sided QBX kernel row (all four Muller blocks) for one wavenumber.

    ``side`` is +1 or -1: the expansion center is ``x_i + side * r_i * n_i``.
    Returns, for each block, an array over ``y_band`` -- the *unweighted*
    kernel value ``K(x_i, y_j)``, built by truncating Graf's addition theorem
    at ``+-order`` (see module docstring for the derivation of each block
    from the ``G`` and ``d G/d n_y`` expansions). Callers must exclude
    ``y_j == x_i`` from ``y_band`` -- see module docstring.
    """

    center = x_i + side * r_i * n_i
    disp = y_band - center[None, :]
    rho = np.linalg.norm(disp, axis=1)
    theta = np.arctan2(disp[:, 1], disp[:, 0])

    orders = np.arange(-order, order + 1, dtype=float)
    n_col = orders[:, None]  # (2p+1, 1)
    z = (k * rho)[None, :]  # (1, B)

    hankel_n = hankel1(n_col, z)
    hankel_deriv = 0.5 * (hankel1(n_col - 1.0, z) - hankel1(n_col + 1.0, z))
    exp_y = np.exp(-1j * n_col * theta[None, :])
    psi = hankel_n * exp_y  # (2p+1, B): H_n(k rho) exp(-i n theta_y)

    rho_hat = np.stack((np.cos(theta), np.sin(theta)), axis=1)  # (B, 2)
    theta_hat = np.stack((-np.sin(theta), np.cos(theta)), axis=1)  # (B, 2)

    dpsi_drho = k * hankel_deriv * exp_y  # (2p+1, B)
    dpsi_dtheta_over_rho = (-1j * n_col / rho[None, :]) * psi  # (2p+1, B)
    grad_y = dpsi_drho[:, :, None] * rho_hat[None, :, :] + dpsi_dtheta_over_rho[:, :, None] * theta_hat[None, :, :]
    dpsi_dny = np.einsum("nbd,bd->nb", grad_y, n_y_band)  # (2p+1, B): d/dn_y [H_n(k rho) exp(-i n theta_y)]

    # Target side: x_i sits at the *known* offset from the center, so its
    # polar coordinates about `center` are exact, not a nearest-neighbour
    # estimate -- rho_x = r_i, theta_x = arg(x_i - center) = arg(-side * n_i).
    theta_x = float(np.arctan2(-side * n_i[1], -side * n_i[0]))
    rho_x = float(r_i)
    zx = k * rho_x

    bessel_n = jv(orders, zx)
    bessel_deriv = 0.5 * (jv(orders - 1.0, zx) - jv(orders + 1.0, zx))
    exp_x = np.exp(1j * orders * theta_x)
    phi_x = bessel_n * exp_x  # (2p+1,): J_n(k rho_x) exp(i n theta_x)

    dphi_x_drho = k * bessel_deriv * exp_x
    dphi_x_dtheta_over_rho = (1j * orders / rho_x) * phi_x
    rho_hat_x = np.array([np.cos(theta_x), np.sin(theta_x)])
    theta_hat_x = np.array([-np.sin(theta_x), np.cos(theta_x)])
    grad_x = dphi_x_drho[:, None] * rho_hat_x[None, :] + dphi_x_dtheta_over_rho[:, None] * theta_hat_x[None, :]
    dphi_x_dnx = grad_x @ n_i  # (2p+1,): d/dn_x [J_n(k rho_x) exp(i n theta_x)]

    prefactor = 0.25j
    return {
        "single": prefactor * np.einsum("n,nb->b", phi_x, psi),
        "double": prefactor * np.einsum("n,nb->b", phi_x, dpsi_dny),
        "adjoint": prefactor * np.einsum("n,nb->b", dphi_x_dnx, psi),
        "hyper": prefactor * np.einsum("n,nb->b", dphi_x_dnx, dpsi_dny),
    }


def _qbx_pv_row(
    x_i: np.ndarray,
    n_i: np.ndarray,
    y_band: np.ndarray,
    n_y_band: np.ndarray,
    k: complex,
    r_i: float,
    order: int,
) -> dict[str, np.ndarray]:
    """Principal-value kernel row for one wavenumber: average of both one-sided limits."""

    plus = _qbx_side_row(x_i, n_i, y_band, n_y_band, k, r_i, +1.0, order)
    minus = _qbx_side_row(x_i, n_i, y_band, n_y_band, k, r_i, -1.0, order)
    return {key: 0.5 * (plus[key] + minus[key]) for key in _BLOCKS}


def _qbx_diff_row(
    x_i: np.ndarray,
    n_i: np.ndarray,
    y_band: np.ndarray,
    n_y_band: np.ndarray,
    k_ext: complex,
    k_int: complex,
    r_i: float,
    order: int,
) -> dict[str, np.ndarray]:
    """Exterior-minus-interior principal-value row, matching ``_difference_kernels``'s sign convention."""

    exterior = _qbx_pv_row(x_i, n_i, y_band, n_y_band, k_ext, r_i, order)
    interior = _qbx_pv_row(x_i, n_i, y_band, n_y_band, k_int, r_i, order)
    return {key: exterior[key] - interior[key] for key in _BLOCKS}


def apply_qbx_band_correction(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    matrices: dict[str, np.ndarray],
    k_exterior: complex,
    k_interior: complex,
    settings: QbxSettings | None = None,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Overwrite the near-diagonal band (excluding the diagonal itself) of
    each block, in place, with QBX rows.

    ``matrices`` must already hold the plain differenced-kernel entries
    everywhere, diagonal included (the diagonal is read by nothing here and
    left exactly as the caller set it -- see
    ``ibim_tmz_forward.build_kdiff_operator_blocks``, which fills it from
    ``_diagonal_terms`` first). Returns the same dict and, for visibility,
    each node's band size (how many *other* source columns were
    QBX-corrected).
    """

    settings = settings or QbxSettings()
    num_nodes = points.shape[0]

    frames = _local_frames(points, normals, weights)
    curvature = _sdf_curvature(points, sdf_fn) if sdf_fn is not None else frames["curvature"]
    curvature_radius = _local_radius(curvature)
    expansion_radius = np.minimum(
        settings.radius_spacing_factor * frames["step_scale"],
        settings.radius_curvature_factor * curvature_radius,
    )
    expansion_radius = np.maximum(expansion_radius, 1.0e-12)

    displacement = points[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=-1)
    band_mask = distance < (settings.band_factor * expansion_radius)[:, None]
    np.fill_diagonal(band_mask, False)  # the exact diagonal is never QBX-corrected -- see module docstring

    band_sizes = np.empty(num_nodes, dtype=int)
    for i in range(num_nodes):
        band_j = np.nonzero(band_mask[i])[0]
        band_sizes[i] = band_j.size
        if band_j.size == 0:
            continue
        row = _qbx_diff_row(
            points[i],
            normals[i],
            points[band_j],
            normals[band_j],
            k_exterior,
            k_interior,
            float(expansion_radius[i]),
            settings.expansion_order,
        )
        for key in _BLOCKS:
            matrices[key][i, band_j] = row[key] * weights[band_j]

    return matrices, band_sizes
