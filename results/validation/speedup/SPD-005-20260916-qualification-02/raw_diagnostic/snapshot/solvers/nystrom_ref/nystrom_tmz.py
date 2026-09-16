"""Standalone Nystrom reference solver for the 2D TMz transmission problem.

This is an *oracle*, not a production solver. It exists to answer one question:
how accurate should this boundary integral equation be on a smooth shape when
geometry and quadrature are not the limiting factors?

Independence
------------
It deliberately shares nothing with ``gpr_bem_ref`` / ``gpr_bem_mod`` except the
*definition of the problem*: the material model, ``EPS0``/``MU0``, and the
``0.25j * H_0^(1)(k r)`` line-source normalisation. Every piece of numerics --
geometry, kernels, quadrature, assembly, evaluation -- is written from scratch
here. An oracle that imports the machinery it judges shares its bugs.

Formulation
-----------
Muller, matching ``ibim_tmz_system.py``. With ``n`` the outward normal of the
interior region, ``u`` the (continuous) Dirichlet trace and ``q`` the
(continuous) Neumann trace, adding the exterior and interior Calderon equations
gives

    [ I - dD      dS     ] [u]   [u_inc]
    [   -dT     I + dK'  ] [q] = [q_inc]

where ``d`` denotes exterior-minus-interior.  ``I`` survives on the diagonal,
which is what makes the system second kind.

Why this is easy to make spectrally accurate
--------------------------------------------
For TMz with non-magnetic media both traces are continuous, so the Muller blocks
are *pure* differences with no material weighting.  Taking those differences
analytically, at the kernel level, kills the leading singularity of every block,
because the leading term is k-independent in each case:

    dS   = (i/4)[H0(ke r) - H0(ki r)]           ln r cancels  -> BOUNDED
    dD   = (i/4)[ke H1(ke r) - ki H1(ki r)] (r.ny)/r
                                                 1/r cancels   -> BOUNDED
    dK'  = same with (r.nx)/r and a sign         1/r cancels   -> BOUNDED
    dT                                           1/r^2 cancels -> O(ln r)

So the hypersingular block is the only one with any singularity left, and it is
merely logarithmic.  **No hypersingular quadrature is needed anywhere**: one
Kress/Kussmaul-Martensen log rule handles the whole system.  This is variant (D)
of ``ibim_error_mitigation_literature_codex.md`` section 4b.4.

The differences must be formed *symbolically*, never by subtracting two
assembled operators -- subtracting two O(1/r^2) matrices is exactly the
cancellation that section 4.3 warns about.

Quadrature
----------
Every kernel is split as

    M(t,tau) = M1(t,tau) log(4 sin^2((t-tau)/2)) + M2(t,tau)

with ``M1`` and ``M2`` smooth.  ``M1`` is known in closed form: the coefficient
of ``ln r`` in ``H_n^(1)(k r)`` is ``i (2/pi) J_n(k r)``, so ``M1`` is the same
expression as the kernel with every Hankel function replaced by the
corresponding Bessel function, times ``-1/(4 pi)``.  ``M2`` follows by
subtraction off the diagonal; on the diagonal it is recovered by a Richardson
limit in the parameter (see ``_diagonal_limits``).  Kress' trigonometric weights
integrate the log term; the plain periodic trapezoid handles the rest.

Scope: forward only.  No SDF, no adjoint, no inverse, no batching over
frequency.  Not differentiable and not intended to be.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.special import hankel1, jv

TWO_PI = 2.0 * np.pi

Parameterization = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]

__all__ = [
    "Curve",
    "NystromSolution",
    "build_curve",
    "circle_parameterization",
    "ellipse_parameterization",
    "star_parameterization",
    "solve_transmission",
]


# ---------------------------------------------------------------- geometry --


@dataclass(frozen=True)
class Curve:
    """A smooth closed curve sampled at uniformly spaced parameter values.

    ``parameterization`` is retained so the curve can be evaluated off-node,
    which the diagonal quadrature limits need.
    """

    name: str
    parameterization: Parameterization
    t: np.ndarray
    points: np.ndarray
    tangents: np.ndarray
    normals: np.ndarray
    speeds: np.ndarray

    @property
    def num_nodes(self) -> int:
        return int(self.t.size)

    @property
    def perimeter(self) -> float:
        return float(self.speeds.sum() * TWO_PI / self.num_nodes)


def _normals_and_speeds(tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Outward unit normal for a counter-clockwise parameterization."""

    speeds = np.linalg.norm(tangents, axis=-1)
    normals = np.stack((tangents[..., 1], -tangents[..., 0]), axis=-1) / speeds[..., None]
    return normals, speeds


def circle_parameterization(center: tuple[float, float], radius: float) -> Parameterization:
    origin = np.asarray(center, dtype=float)

    def parameterization(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        t = np.asarray(t, dtype=float)
        points = origin + radius * np.stack((np.cos(t), np.sin(t)), axis=-1)
        tangents = radius * np.stack((-np.sin(t), np.cos(t)), axis=-1)
        return points, tangents

    return parameterization


def ellipse_parameterization(
    center: tuple[float, float], semi_major: float, semi_minor: float
) -> Parameterization:
    origin = np.asarray(center, dtype=float)

    def parameterization(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        t = np.asarray(t, dtype=float)
        points = origin + np.stack((semi_major * np.cos(t), semi_minor * np.sin(t)), axis=-1)
        tangents = np.stack((-semi_major * np.sin(t), semi_minor * np.cos(t)), axis=-1)
        return points, tangents

    return parameterization


def star_parameterization(
    center: tuple[float, float], mean_radius: float, amplitude: float, lobes: int
) -> Parameterization:
    """``r(t) = mean_radius * (1 + amplitude cos(lobes t))``.

    Keep ``amplitude`` modest.  Uniform ``t`` gives strongly non-uniform
    arclength spacing as the amplitude grows, which makes "N nodes" stop being
    comparable with the IBIM's roughly arclength-uniform samples.
    """

    origin = np.asarray(center, dtype=float)

    def parameterization(t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        t = np.asarray(t, dtype=float)
        radius = mean_radius * (1.0 + amplitude * np.cos(lobes * t))
        radius_prime = -mean_radius * amplitude * lobes * np.sin(lobes * t)
        cos_t, sin_t = np.cos(t), np.sin(t)
        points = origin + radius[..., None] * np.stack((cos_t, sin_t), axis=-1)
        tangents = radius_prime[..., None] * np.stack((cos_t, sin_t), axis=-1) + radius[
            ..., None
        ] * np.stack((-sin_t, cos_t), axis=-1)
        return points, tangents

    return parameterization


def build_curve(parameterization: Parameterization, num_nodes: int, name: str = "curve") -> Curve:
    if num_nodes % 2 != 0:
        raise ValueError("Kress' log rule needs an even number of nodes")
    t = TWO_PI * np.arange(num_nodes, dtype=float) / num_nodes
    points, tangents = parameterization(t)
    normals, speeds = _normals_and_speeds(tangents)
    return Curve(name, parameterization, t, points, tangents, normals, speeds)


# ----------------------------------------------------------------- kernels --

_BLOCKS = ("single", "double", "adjoint", "hyper")


def _difference_kernels(
    r: np.ndarray,
    rdotnx: np.ndarray,
    rdotny: np.ndarray,
    nxny: np.ndarray,
    k_ext: complex,
    k_int: complex,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """The four Muller difference kernels and their ``ln r`` coefficients.

    ``r`` is the displacement magnitude, ``rdotnx``/``rdotny`` are
    ``(x - y) . n_x`` and ``(x - y) . n_y``, ``nxny`` is ``n_x . n_y``.

    The second return value is the coefficient of ``ln r``, obtained by
    replacing every ``H_n^(1)`` with ``J_n`` and the prefactor ``i/4`` with
    ``-1/(2 pi)``, since the coefficient of ``ln r`` in ``H_n^(1)(k r)`` is
    ``i (2/pi) J_n(k r)``.
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
    curve: Curve, k_ext: complex, k_int: complex, epsilon: float
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Diagonal values of ``M1`` and ``M2`` by a Richardson limit in ``t``.

    Both are continuous across ``tau = t``, so they are recovered by evaluating
    slightly off-diagonal and extrapolating.  Nothing is differenced and nothing
    is divided by ``epsilon``, so this is a limit of a continuous function, not
    a finite-difference derivative: shrinking ``epsilon`` costs accuracy only
    through the cancellation inside ``M2 = M - M1 log(...)``, never through
    amplification.  Two-sided averaging removes the linear term and the
    Richardson step removes most of the ``epsilon^2 log epsilon`` term.
    """

    def evaluate(step: float) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
        first: dict[str, np.ndarray] = {key: 0.0 for key in _BLOCKS}
        second: dict[str, np.ndarray] = {key: 0.0 for key in _BLOCKS}
        log_value = np.log(4.0 * np.sin(0.5 * step) ** 2)
        for sign in (1.0, -1.0):
            points, tangents = curve.parameterization(curve.t + sign * step)
            normals, speeds = _normals_and_speeds(tangents)
            geometry = _pair_geometry(curve.points, curve.normals, points, normals, outer=False)
            kernels, log_coefficients = _difference_kernels(*geometry, k_ext, k_int)
            for key in _BLOCKS:
                m1 = 0.5 * log_coefficients[key] * speeds
                m2 = kernels[key] * speeds - m1 * log_value
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
    curve: Curve, k_ext: complex, k_int: complex, epsilon: float
) -> dict[str, np.ndarray]:
    """Discretised Muller difference operators, one dense matrix per block."""

    num_nodes = curve.num_nodes
    step = TWO_PI / num_nodes

    safe_radius = np.ones((num_nodes, num_nodes))
    geometry = _pair_geometry(curve.points, curve.normals, curve.points, curve.normals, outer=True)
    radius = np.where(np.eye(num_nodes, dtype=bool), safe_radius, geometry[0])
    kernels, log_coefficients = _difference_kernels(radius, *geometry[1:], k_ext, k_int)

    separation = curve.t[:, None] - curve.t[None, :]
    with np.errstate(divide="ignore"):
        log_factor = np.log(4.0 * np.sin(0.5 * separation) ** 2)
    np.fill_diagonal(log_factor, 0.0)

    index = np.arange(num_nodes)
    kress = _kress_log_weights(num_nodes)[(index[:, None] - index[None, :]) % num_nodes]
    diagonal_first, diagonal_second = _diagonal_limits(curve, k_ext, k_int, epsilon)

    matrices: dict[str, np.ndarray] = {}
    for key in _BLOCKS:
        first = 0.5 * log_coefficients[key] * curve.speeds[None, :]
        second = kernels[key] * curve.speeds[None, :] - first * log_factor
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
    receivers: np.ndarray, curve: Curve, trace: np.ndarray, normal_trace: np.ndarray, k_ext: complex
) -> np.ndarray:
    """``u_sc(x) = (D_e u - S_e q)(x)`` for ``x`` in the exterior.

    The incident part drops out: ``D_e u_inc - S_e q_inc`` vanishes outside the
    scatterer because ``u_inc`` is a regular solution inside it.  Receivers are
    far from the boundary, so the plain periodic trapezoid is spectral here.
    """

    displacement = receivers[:, None, :] - curve.points[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    projection = np.einsum("mnd,nd->mn", displacement, curve.normals) / distance
    green = 0.25j * hankel1(0, k_ext * distance)
    green_normal = 0.25j * k_ext * hankel1(1, k_ext * distance) * projection
    weights = curve.speeds * (TWO_PI / curve.num_nodes)
    return (green_normal * trace[None, :] - green * normal_trace[None, :]) @ weights


@dataclass
class NystromSolution:
    curve: Curve
    k_exterior: complex
    k_interior: complex
    scattered: np.ndarray
    dirichlet_trace: np.ndarray
    neumann_trace: np.ndarray
    condition_number: float
    relative_residual: float
    incident_consistency: float


def solve_transmission(
    curve: Curve,
    sources: np.ndarray,
    receivers: np.ndarray,
    k_exterior: complex,
    k_interior: complex,
    *,
    strength: float = 1.0,
    epsilon: float = 1.0e-3,
    condition_number: bool = False,
) -> NystromSolution:
    """Solve the Muller system and evaluate the scattered field at receivers.

    ``scattered`` comes back shaped ``(num_sources, num_receivers)``.
    """

    sources = np.atleast_2d(np.asarray(sources, dtype=float))
    receivers = np.atleast_2d(np.asarray(receivers, dtype=float))
    num_nodes = curve.num_nodes

    blocks = _operator_matrices(curve, k_exterior, k_interior, epsilon)
    identity = np.eye(num_nodes, dtype=complex)
    system = np.block(
        [
            [identity - blocks["double"], blocks["single"]],
            [-blocks["hyper"], identity + blocks["adjoint"]],
        ]
    )

    right_hand_side = np.empty((2 * num_nodes, sources.shape[0]), dtype=complex)
    for column, source in enumerate(sources):
        trace, normal_trace = _incident_traces(
            curve.points, curve.normals, source, k_exterior, strength
        )
        right_hand_side[:num_nodes, column] = trace
        right_hand_side[num_nodes:, column] = normal_trace

    solution = np.linalg.solve(system, right_hand_side)
    residual = np.linalg.norm(system @ solution - right_hand_side) / np.linalg.norm(right_hand_side)

    dirichlet = solution[:num_nodes, :]
    neumann = solution[num_nodes:, :]
    scattered = np.empty((sources.shape[0], receivers.shape[0]), dtype=complex)
    consistency = 0.0
    for column, source in enumerate(sources):
        scattered[column] = _exterior_representation(
            receivers, curve, dirichlet[:, column], neumann[:, column], k_exterior
        )
        # D_e u_inc - S_e q_inc must vanish outside the scatterer.  This is a
        # convention check: it fails loudly if a normal points the wrong way or
        # a jump-relation sign is wrong, and it costs one extra evaluation.
        trace, normal_trace = _incident_traces(
            curve.points, curve.normals, source, k_exterior, strength
        )
        leak = _exterior_representation(receivers, curve, trace, normal_trace, k_exterior)
        consistency = max(
            consistency, float(np.max(np.abs(leak)) / max(np.max(np.abs(scattered[column])), 1e-300))
        )

    return NystromSolution(
        curve=curve,
        k_exterior=k_exterior,
        k_interior=k_interior,
        scattered=scattered,
        dirichlet_trace=dirichlet,
        neumann_trace=neumann,
        condition_number=float(np.linalg.cond(system)) if condition_number else float("nan"),
        relative_residual=float(residual),
        incident_consistency=consistency,
    )
