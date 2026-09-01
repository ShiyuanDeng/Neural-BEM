"""Kernel-differenced Muller quadrature, hosted on IBIM's own boundary object.

This answers one narrow question: can the trick that makes ``nystrom_ref``
spectrally accurate -- difference the exterior/interior kernels *before* any
quadrature, instead of assembling two separately-approximated operators and
subtracting them -- be hosted against the same ``points``/``normals``/
``quadrature_weights`` data shape that ``ImplicitBoundarySamples2D`` (IBIM's
own boundary representation) already produces, rather than against an
explicit parameterized curve?

Circle only, and only under exact uniform-arclength sampling
(``perfect_circle_boundary_samples``). It is not a generalisation of
``nystrom_ref`` to implicit boundaries -- it is a scoped experiment that
proves out the kernel-differencing half of the idea while borrowing the
other half (an analytic circle parameterization, needed only for the
diagonal self-term limit) from knowing the answer in advance. See
``docs/legacy/ibim_error_mitigation_literature_codex.md`` Phase E and
``docs/validation_change_log.md`` for why the diagonal limit is the piece
that still needs work before this generalizes to a real (irregular,
SDF-derived) narrow-band boundary: Kress' log-singular correction assumes an
equidistant arc-length parametrization, which a projected/compressed IBIM
cloud does not have, and the diagonal limit here is obtained by evaluating
the *known* circle parameterization off-node -- something a general implicit
boundary cannot do without its own corrected (Izzo/Runborg/Tsai-style)
quadrature.

Provenance
----------
The kernel formulas, the Kress log-quadrature weights, and the
Richardson-extrapolated diagonal limit are copied and adapted from
``solvers/nystrom_ref/nystrom_tmz.py`` rather than imported from it, on
purpose: this module and ``nystrom_ref`` play different roles (this one is
being tested for whether it can be *hosted inside the production boundary
representation*; ``nystrom_ref`` is the trusted oracle used to cross-check
it), and keeping them independent means a bug in one cannot silently become
a bug in the other's judgement.

Formulation
-----------
Muller, matching ``ibim_tmz_system.py`` and ``nystrom_ref``. With ``n`` the
outward normal of the interior region, ``u`` the Dirichlet trace and ``q``
the Neumann trace,

    [ I - dD      dS     ] [u]   [u_inc]
    [   -dT     I + dK'  ] [q] = [q_inc]

where ``d`` denotes exterior-minus-interior, formed at the kernel level (see
``_difference_kernels``): every block is bounded except the hypersingular
one, which is only logarithmically singular, so one Kress log-quadrature
rule handles the whole system and no finite trace offset is needed anywhere.

Scope: forward only, circle only, perfect sampling only. Not differentiable
and not intended to be -- this is a diagnostic, not a production path.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import hankel1, jv

TWO_PI = 2.0 * np.pi

__all__ = ["KernelDiffSolution", "solve_transmission_on_circle"]

_BLOCKS = ("single", "double", "adjoint", "hyper")


# ----------------------------------------------------------------- kernels --


def _difference_kernels(
    r: np.ndarray,
    rdotnx: np.ndarray,
    rdotny: np.ndarray,
    nxny: np.ndarray,
    k_ext: complex,
    k_int: complex,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """The four Muller difference kernels and their ``ln r`` coefficients.

    Identical construction to ``nystrom_ref``'s: the coefficient of ``ln r``
    in ``H_n^(1)(k r)`` is ``i (2/pi) J_n(k r)``, so replacing every Hankel
    function with the corresponding Bessel function and the prefactor
    ``i/4`` with ``-1/(2 pi)`` gives that coefficient directly.
    """

    z_ext, z_int = k_ext * r, k_int * r
    inv_r = 1.0 / r

    d_h1 = k_ext * hankel1(1, z_ext) - k_int * hankel1(1, z_int)
    d_h2 = k_ext**2 * hankel1(2, z_ext) - k_int**2 * hankel1(2, z_int)
    kernels = {
        "single": 0.25j * (hankel1(0, z_ext) - hankel1(0, z_int)),
        "double": 0.25j * d_h1 * rdotny * inv_r,
        "adjoint": -0.25j * d_h1 * rdotnx * inv_r,
        "hyper": 0.25j * (nxny * d_h1 * inv_r - rdotnx * rdotny * inv_r**2 * d_h2),
    }
    del d_h1, d_h2

    d_j1 = k_ext * jv(1, z_ext) - k_int * jv(1, z_int)
    d_j2 = k_ext**2 * jv(2, z_ext) - k_int**2 * jv(2, z_int)
    scale = -1.0 / (2.0 * np.pi)
    log_coefficients = {
        "single": scale * (jv(0, z_ext) - jv(0, z_int)),
        "double": scale * d_j1 * rdotny * inv_r,
        "adjoint": -scale * d_j1 * rdotnx * inv_r,
        "hyper": scale * (nxny * d_j1 * inv_r - rdotnx * rdotny * inv_r**2 * d_j2),
    }
    return kernels, log_coefficients


def _pair_geometry(
    targets: np.ndarray,
    target_normals: np.ndarray,
    sources: np.ndarray,
    source_normals: np.ndarray,
    outer: bool,
) -> tuple[np.ndarray, ...]:
    """Displacement invariants, either as an outer product or elementwise."""

    if outer:
        displacement = targets[:, None, :] - sources[None, :, :]
        rdotnx = np.einsum("mnd,md->mn", displacement, target_normals)
        rdotny = np.einsum("mnd,nd->mn", displacement, source_normals)
        nxny = target_normals @ source_normals.T
    else:
        displacement = targets - sources
        rdotnx = np.einsum("nd,nd->n", displacement, target_normals)
        rdotny = np.einsum("nd,nd->n", displacement, source_normals)
        nxny = np.einsum("nd,nd->n", target_normals, source_normals)
    r = np.linalg.norm(displacement, axis=-1)
    return r, rdotnx, rdotny, nxny


def _normals_and_speeds(tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Outward unit normal for a counter-clockwise parameterization."""

    speeds = np.linalg.norm(tangents, axis=-1)
    normals = np.stack((tangents[..., 1], -tangents[..., 0]), axis=-1) / speeds[..., None]
    return normals, speeds


def _circle_point_and_tangent(t: np.ndarray, center: np.ndarray, radius: float) -> tuple[np.ndarray, np.ndarray]:
    points = center[None, :] + radius * np.stack((np.cos(t), np.sin(t)), axis=-1)
    tangents = radius * np.stack((-np.sin(t), np.cos(t)), axis=-1)
    return points, tangents


# -------------------------------------------------------------- quadrature --


def _kress_log_weights(num_nodes: int) -> np.ndarray:
    """Kress' weights for ``int f(tau) log(4 sin^2((t-tau)/2)) dtau``.

    Returned as a length-``N`` vector indexed by ``(i - j) mod N``; the full
    matrix is that vector read circulantly.
    """

    half = num_nodes // 2
    offsets = TWO_PI * np.arange(num_nodes, dtype=float) / num_nodes
    orders = np.arange(1, half, dtype=float)
    series = (np.cos(np.outer(offsets, orders)) / orders).sum(axis=1)
    return -(TWO_PI / half) * series - (np.pi / half**2) * np.cos(half * offsets)


def _diagonal_limits(
    points: np.ndarray,
    normals: np.ndarray,
    t: np.ndarray,
    center: np.ndarray,
    radius: float,
    k_ext: complex,
    k_int: complex,
    epsilon: float,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Diagonal values of ``M1`` and ``M2`` by a Richardson limit in ``t``.

    The only place this module needs more than discrete node data: the
    off-node samples ``t +- step`` come from the *known* circle
    parameterization, not from the discrete boundary. A general implicit
    boundary has no such off-node access without its own corrected
    quadrature -- see the module docstring.
    """

    def evaluate(step: float) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        first: dict[str, np.ndarray] = {key: 0.0 for key in _BLOCKS}
        second: dict[str, np.ndarray] = {key: 0.0 for key in _BLOCKS}
        log_value = np.log(4.0 * np.sin(0.5 * step) ** 2)
        for sign in (1.0, -1.0):
            off_points, off_tangents = _circle_point_and_tangent(t + sign * step, center, radius)
            off_normals, off_speeds = _normals_and_speeds(off_tangents)
            geometry = _pair_geometry(points, normals, off_points, off_normals, outer=False)
            kernels, log_coefficients = _difference_kernels(*geometry, k_ext, k_int)
            for key in _BLOCKS:
                m1 = 0.5 * log_coefficients[key] * off_speeds
                m2 = kernels[key] * off_speeds - m1 * log_value
                first[key] = first[key] + 0.5 * m1
                second[key] = second[key] + 0.5 * m2
        return first, second

    near_first, near_second = evaluate(epsilon)
    far_first, far_second = evaluate(2.0 * epsilon)
    richardson = lambda near, far: (4.0 * near - far) / 3.0  # noqa: E731
    return (
        {key: richardson(near_first[key], far_first[key]) for key in _BLOCKS},
        {key: richardson(near_second[key], far_second[key]) for key in _BLOCKS},
    )


def _operator_matrices(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    t: np.ndarray,
    center: np.ndarray,
    radius: float,
    k_ext: complex,
    k_int: complex,
    epsilon: float,
) -> dict[str, np.ndarray]:
    """Discretised Muller difference operators, one dense matrix per block.

    ``weights`` is the per-node arc-length measure IBIM already computes
    (``quadrature_weights``); ``weights / step`` recovers the parametric
    speed Kress' log-weight formula needs, since ``step`` is exact and known
    here (equidistant angles, checked by the caller).
    """

    num_nodes = points.shape[0]
    step = TWO_PI / num_nodes
    speeds = weights / step

    safe_radius = np.ones((num_nodes, num_nodes))
    geometry = _pair_geometry(points, normals, points, normals, outer=True)
    radius_matrix = np.where(np.eye(num_nodes, dtype=bool), safe_radius, geometry[0])
    kernels, log_coefficients = _difference_kernels(radius_matrix, *geometry[1:], k_ext, k_int)

    separation = t[:, None] - t[None, :]
    with np.errstate(divide="ignore"):
        log_factor = np.log(4.0 * np.sin(0.5 * separation) ** 2)
    np.fill_diagonal(log_factor, 0.0)

    index = np.arange(num_nodes)
    kress = _kress_log_weights(num_nodes)[(index[:, None] - index[None, :]) % num_nodes]
    diagonal_first, diagonal_second = _diagonal_limits(points, normals, t, center, radius, k_ext, k_int, epsilon)

    matrices: dict[str, np.ndarray] = {}
    for key in _BLOCKS:
        first = 0.5 * log_coefficients[key] * speeds[None, :]
        second = kernels[key] * speeds[None, :] - first * log_factor
        np.fill_diagonal(first, diagonal_first[key])
        np.fill_diagonal(second, diagonal_second[key])
        matrices[key] = kress * first + step * second
    return matrices


# ------------------------------------------------------------- the physics --


def _incident_traces(
    points: np.ndarray, normals: np.ndarray, source: np.ndarray, k_ext: complex, strength: float
) -> tuple[np.ndarray, np.ndarray]:
    """Line source at ``source``: ``u_inc = strength * (i/4) H_0^(1)(k R)``."""

    displacement = points - source[None, :]
    distance = np.linalg.norm(displacement, axis=1)
    projection = np.einsum("nd,nd->n", displacement, normals) / distance
    trace = strength * 0.25j * hankel1(0, k_ext * distance)
    normal_trace = -strength * 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    return trace, normal_trace


def _exterior_representation(
    receivers: np.ndarray,
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    trace: np.ndarray,
    normal_trace: np.ndarray,
    k_ext: complex,
) -> np.ndarray:
    """``u_sc(x) = (D_e u - S_e q)(x)`` for ``x`` in the exterior.

    Receivers are far from the boundary, so the plain weighted sum is
    accurate here -- no kernel-differencing or log-correction needed, same
    as ``nystrom_ref``.
    """

    displacement = receivers[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    return (green_normal * trace[None, :] - green * normal_trace[None, :]) @ weights


@dataclass
class KernelDiffSolution:
    scattered: np.ndarray
    dirichlet_trace: np.ndarray
    neumann_trace: np.ndarray
    condition_number: float
    relative_residual: float


def solve_transmission_on_circle(
    boundary_points: np.ndarray,
    boundary_normals: np.ndarray,
    boundary_weights: np.ndarray,
    center: tuple[float, float],
    radius: float,
    sources: np.ndarray,
    receivers: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    *,
    strength: float = 1.0,
    epsilon: float = 1.0e-3,
    condition_number: bool = False,
) -> KernelDiffSolution:
    """Solve the kernel-differenced Muller system and evaluate at receivers.

    ``boundary_points``/``boundary_normals``/``boundary_weights`` are exactly
    the fields ``ImplicitBoundarySamples2D`` carries -- typically read off a
    ``perfect_circle_boundary_samples()`` result. They are checked (not just
    assumed) to be equidistant-angle circle nodes in increasing order, since
    that layout is what the Kress log-quadrature and the diagonal limit both
    rely on; anything else raises rather than silently producing a wrong
    answer.

    ``scattered`` comes back shaped ``(num_sources, num_receivers)``, same
    convention as ``nystrom_ref.solve_transmission``.
    """

    points = np.asarray(boundary_points, dtype=float)
    normals = np.asarray(boundary_normals, dtype=float)
    weights = np.asarray(boundary_weights, dtype=float).reshape(-1)
    num_nodes = points.shape[0]
    if num_nodes % 2 != 0:
        raise ValueError("Kress' log rule needs an even number of nodes.")

    center_arr = np.asarray(center, dtype=float)
    t = TWO_PI * np.arange(num_nodes, dtype=float) / num_nodes
    expected_points, _ = _circle_point_and_tangent(t, center_arr, float(radius))
    tolerance = max(1.0e-6 * float(radius), 1.0e-9)
    if not np.allclose(points, expected_points, atol=tolerance, rtol=0.0):
        raise ValueError(
            "boundary_points are not equidistant-angle circle nodes starting at angle 0 "
            "(the perfect_circle_boundary_samples layout this solver relies on). This "
            "solver is circle-only and perfect-sampling-only; it does not generalize to "
            "an irregular or non-circular boundary."
        )

    sources = np.atleast_2d(np.asarray(sources, dtype=float))
    receivers = np.atleast_2d(np.asarray(receivers, dtype=float))

    blocks = _operator_matrices(points, normals, weights, t, center_arr, float(radius), k_exterior, k_interior, epsilon)
    identity = np.eye(num_nodes, dtype=complex)
    system = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )

    right_hand_side = np.empty((2 * num_nodes, sources.shape[0]), dtype=complex)
    for column, source in enumerate(sources):
        trace, normal_trace = _incident_traces(points, normals, source, k_exterior, strength)
        right_hand_side[:num_nodes, column] = trace
        right_hand_side[num_nodes:, column] = normal_trace

    solution = np.linalg.solve(system, right_hand_side)
    residual = np.linalg.norm(system @ solution - right_hand_side) / np.linalg.norm(right_hand_side)

    dirichlet = solution[:num_nodes, :]
    neumann = solution[num_nodes:, :]
    scattered = np.empty((sources.shape[0], receivers.shape[0]), dtype=complex)
    for column in range(sources.shape[0]):
        scattered[column] = _exterior_representation(
            receivers, points, normals, weights, dirichlet[:, column], neumann[:, column], k_exterior
        )

    return KernelDiffSolution(
        scattered=scattered,
        dirichlet_trace=dirichlet,
        neumann_trace=neumann,
        condition_number=float(np.linalg.cond(system)) if condition_number else float("nan"),
        relative_residual=float(residual),
    )
