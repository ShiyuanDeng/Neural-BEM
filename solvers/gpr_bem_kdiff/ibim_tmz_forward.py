"""Kernel-differenced Muller operator assembly on the real compressed boundary.

Forked from ``gpr_bem_mod`` -- geometry/SDF files are byte-identical to it
(see ``solvers/README.md``). This file replaces the finite-standoff trace
machinery entirely: no ``offset_distance`` anywhere.

Design, and what is genuinely new here versus ``solvers/kernel_diff_ref/``
--------------------------------------------------------------------------
``kernel_diff_ref`` proved kernel-differenced quadrature works when hosted on
IBIM's own boundary-object shape, but only for a perfectly-sampled circle: its
diagonal self-term samples the *known analytic circle formula* off-node. This
module removes that dependency -- it operates on whatever boundary
``compress_implicit_boundary_band`` actually produces (irregular spacing, any
smooth shape), using only data already in that object: ``points``,
``normals``, ``quadrature_weights``.

Off-diagonal entries are unchanged in spirit from ``kernel_diff_ref``: the
Muller kernels are differenced analytically first (exterior-minus-interior,
see ``_difference_kernels``), then evaluated directly node-to-node with no
offset. S, D, K' are bounded there; T keeps only the leading O(kd)-free
logarithmic singularity, and *this version does not correct that
off-diagonal-but-nearby log behaviour* -- it uses plain quadrature there,
same as everywhere else. That is a known, flagged limitation (see the module
docstring's closing note), not an oversight.

The diagonal (node i against itself) cannot use plain evaluation at all --
even the differenced kernels are singular or indeterminate exactly at r=0.
Getting a value there without inventing new stored fields (no curvature
field survives ``compress_implicit_boundary_band``) or a global arclength
reordering works like this: estimate node i's local curvature from data
already at hand -- the *change in the already-trusted normal field* between
its two nearest neighbours, one on each side (found by projecting onto the
local tangent, not by assuming any global ordering) -- then treat node i as
if it sat on its own local osculating circle, with as many "effective
neighbours" as its own local spacing implies. That local circle is fed
through the exact same Richardson-extrapolated diagonal-limit machinery
``kernel_diff_ref`` already validated (bit-for-bit against
``nystrom_ref``) -- the only change is that the circle is fit per node from
real neighbours instead of being one known global shape.

Known limitation, to be measured, not assumed away: the off-diagonal
log-singular behaviour of T near (but not at) the diagonal has no correction
in this version. If validation against ``nystrom_ref`` on the real compressed
ellipse/star boundary shows a floor from this, that is the next thing to fix
-- see ``docs/ibim_error_mitigation_literature_codex.md`` Phase E/F.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
from scipy.special import hankel1, jv

from .ibim_geometry import ImplicitBoundaryBand2D, ImplicitBoundarySamples2D

TWO_PI = 2.0 * np.pi

__all__ = [
    "KdiffOperatorBlocks",
    "boundary_points_normals_weights",
    "build_kdiff_operator_blocks",
]

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

    Identical construction to ``nystrom_ref``/``kernel_diff_ref``: the
    coefficient of ``ln r`` in ``H_n^(1)(k r)`` is ``i (2/pi) J_n(k r)``, so
    replacing every Hankel function with the corresponding Bessel function
    and the prefactor ``i/4`` with ``-1/(2 pi)`` gives that coefficient
    directly.
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


def _kress_log_self_weight(num_nodes: int) -> float:
    """Kress' self (offset-0) weight for ``int f(tau) log(4 sin^2((t-tau)/2)) dtau``.

    Only the diagonal entry is needed here (see ``_diagonal_terms``), so this
    evaluates just that closed-form term directly -- O(N), not the O(N^2)
    full circulant vector ``kernel_diff_ref``'s version builds, which matters
    because ``num_nodes`` here can run into the thousands for a locally
    near-straight boundary segment.
    """

    half = num_nodes // 2
    harmonic = np.sum(1.0 / np.arange(1, half, dtype=float))
    return -(TWO_PI / half) * harmonic - (np.pi / half**2)


def _normals_and_speeds(tangents: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    speeds = np.linalg.norm(tangents, axis=-1)
    normals = np.stack((tangents[..., 1], -tangents[..., 0]), axis=-1) / speeds[..., None]
    return normals, speeds


# ----------------------------------------------------- local osculating fit --


def _tangent_from_normal(normal: np.ndarray) -> np.ndarray:
    """Unit tangent for a CCW-oriented curve, from its outward unit normal."""

    return np.stack((-normal[..., 1], normal[..., 0]), axis=-1)


def _local_frames(points: np.ndarray, normals: np.ndarray, weights: np.ndarray) -> dict[str, np.ndarray]:
    """Per-node local osculating-circle data, from already-stored neighbours only.

    For each node, finds the nearest already-stored point on each side (by
    projection onto the local tangent, not by any assumed global order),
    estimates signed curvature from how much the *already-trusted* normal
    field turns between those two neighbours over that arc, and derives an
    "effective local node count" -- how many uniformly-spaced nodes a circle
    of that radius would need to match this node's own local spacing. That
    count feeds the Kress self-weight, exactly as it would for a real
    uniformly-sampled circle of that size.
    """

    num_nodes = points.shape[0]
    tangents = _tangent_from_normal(normals)

    displacement = points[:, None, :] - points[None, :, :]
    distance = np.linalg.norm(displacement, axis=-1)
    np.fill_diagonal(distance, np.inf)
    projection = np.einsum("ijd,id->ij", -displacement, tangents)  # (points[j]-points[i]).tangent_i

    plus_index = np.empty(num_nodes, dtype=int)
    minus_index = np.empty(num_nodes, dtype=int)
    for i in range(num_nodes):
        ahead = np.where(projection[i] > 0.0)[0]
        behind = np.where(projection[i] < 0.0)[0]
        plus_index[i] = ahead[np.argmin(distance[i, ahead])] if ahead.size else np.argmin(distance[i])
        minus_index[i] = behind[np.argmin(distance[i, behind])] if behind.size else np.argmin(distance[i])

    dist_plus = distance[np.arange(num_nodes), plus_index]
    dist_minus = distance[np.arange(num_nodes), minus_index]
    arc = dist_plus + dist_minus

    normal_plus = normals[plus_index]
    normal_minus = normals[minus_index]
    cross = normal_minus[:, 0] * normal_plus[:, 1] - normal_minus[:, 1] * normal_plus[:, 0]
    dot = np.einsum("id,id->i", normal_minus, normal_plus)
    turning_angle = np.arctan2(cross, dot)
    curvature = turning_angle / np.maximum(arc, 1.0e-15)

    step_scale = np.minimum(dist_plus, dist_minus)
    return {
        "tangent": tangents,
        "curvature": curvature,
        "step_scale": step_scale,
    }


def _local_radius(curvature: np.ndarray) -> np.ndarray:
    """Local osculating-circle radius, clipped away from the zero-curvature
    (straight-segment) singularity rather than treated as a separate case --
    a circle of radius 1e6 (times whatever the boundary's own length unit
    is; these targets are centimeter-to-decimeter scale) is indistinguishable
    from a straight line at the arc-length scales ``weight`` operates on.
    """

    return np.minimum(1.0 / np.maximum(np.abs(curvature), 1.0e-9), 1.0e6)


def _effective_node_count(radius: np.ndarray, weight: np.ndarray) -> np.ndarray:
    """Local ``N`` such that a uniform circle of ``radius``, sampled at this
    node's own arc-length spacing, would have this many nodes.

    Bounded away from both extremes: a large local radius implies a large
    count, a tight local bend a small one; neither is meaningful past a
    point, and ``_kress_log_weights`` needs an even integer >= 2 to be well
    defined.
    """

    count = np.round(TWO_PI * radius / np.maximum(weight, 1.0e-15))
    count = np.clip(count, 8, 4_000)
    count = count + np.mod(count, 2.0)
    return count.astype(int)


def _sdf_curvature(points: np.ndarray, sdf_fn: Callable[[torch.Tensor], torch.Tensor]) -> np.ndarray:
    """Exact curvature, evaluated directly at ``points``, via autograd through ``sdf_fn``.

    Same construction as ``ibim_geometry._divergence_of_vector_field`` (the
    divergence of the SDF's own unit-normalized gradient field), except this
    is sampled precisely at the compressed boundary nodes instead of being
    averaged over raw band cells during compression -- ``ImplicitBoundarySamples2D``
    carries no curvature field of its own (see module docstring), so there is
    nothing to read off the boundary object; this recomputes it on demand.

    Optional and only used when ``sdf_fn`` is supplied by the caller: the
    neighbour-turning-angle estimate in ``_local_frames`` remains the default
    so this can be adopted incrementally.
    """

    pts = torch.tensor(points, dtype=torch.float32, requires_grad=True)
    sdf_values = sdf_fn(pts).reshape(-1)
    gradients = torch.autograd.grad(
        outputs=sdf_values,
        inputs=pts,
        grad_outputs=torch.ones_like(sdf_values),
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
    grad_norm = torch.linalg.norm(gradients, dim=1, keepdim=True).clamp_min(1.0e-8)
    unit_normals = gradients / grad_norm

    divergence = torch.zeros(pts.shape[0], dtype=torch.float32)
    for axis in range(2):
        component_grad = torch.autograd.grad(
            outputs=unit_normals[:, axis],
            inputs=pts,
            grad_outputs=torch.ones_like(unit_normals[:, axis]),
            create_graph=False,
            retain_graph=True,
            only_inputs=True,
        )[0]
        divergence = divergence + component_grad[:, axis]

    return divergence.detach().cpu().numpy().astype(float)


def _diagonal_terms(
    points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    k_ext: complex,
    k_int: complex,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
) -> dict[str, np.ndarray]:
    """Diagonal entries of the four Muller blocks, one value per node.

    Mirrors ``kernel_diff_ref._diagonal_limits`` + the diagonal assembly in
    ``kernel_diff_ref._operator_matrices`` exactly, except the circle each
    node is sampled against is a local osculating fit (``_local_frames``)
    instead of one shared, known, global circle: node i sits on a circle of
    its own local radius, in its own local (tangent, normal) frame, so the
    same exact circle parameterization ``kernel_diff_ref`` uses applies
    verbatim -- just centered and oriented per node.
    """

    num_nodes = points.shape[0]
    frames = _local_frames(points, normals, weights)
    tangent = frames["tangent"]
    curvature = _sdf_curvature(points, sdf_fn) if sdf_fn is not None else frames["curvature"]
    radius = _local_radius(curvature)
    node_count = _effective_node_count(radius, weights)

    diagonal: dict[str, np.ndarray] = {key: np.empty(num_nodes, dtype=complex) for key in _BLOCKS}

    for i in range(num_nodes):
        n_local = int(node_count[i])
        step = TWO_PI / n_local
        epsilon = 0.25 * step
        r_i = radius[i]

        def local_sample(t: float) -> tuple[np.ndarray, np.ndarray]:
            # Exact circle of radius r_i through points[i] at t=0, tangent
            # tangent[i] there, curving toward -normals[i] -- the same
            # parametric form as a global circle, just in node i's own local
            # frame instead of a shared (center, radius).
            point = points[i] + r_i * (tangent[i] * np.sin(t) - normals[i] * (1.0 - np.cos(t)))
            tan = r_i * (tangent[i] * np.cos(t) - normals[i] * np.sin(t))
            return point, tan

        def evaluate(step_size: float) -> tuple[dict[str, complex], dict[str, complex]]:
            first = {key: 0.0 for key in _BLOCKS}
            second = {key: 0.0 for key in _BLOCKS}
            log_value = np.log(4.0 * np.sin(0.5 * step_size) ** 2)
            for sign in (1.0, -1.0):
                off_point, off_tangent = local_sample(sign * step_size)
                off_normal, off_speed = _normals_and_speeds(off_tangent[None, :])
                displacement = points[i] - off_point
                r = np.linalg.norm(displacement)
                rdotnx = float(np.dot(displacement, normals[i]))
                rdotny = float(np.dot(displacement, off_normal[0]))
                nxny = float(np.dot(normals[i], off_normal[0]))
                kernels, log_coefficients = _difference_kernels(
                    np.array([r]), np.array([rdotnx]), np.array([rdotny]), np.array([nxny]), k_ext, k_int
                )
                for key in _BLOCKS:
                    m1 = 0.5 * log_coefficients[key][0] * off_speed[0]
                    m2 = kernels[key][0] * off_speed[0] - m1 * log_value
                    first[key] += 0.5 * m1
                    second[key] += 0.5 * m2
            return first, second

        near_first, near_second = evaluate(epsilon)
        far_first, far_second = evaluate(2.0 * epsilon)
        kress_self = _kress_log_self_weight(n_local)
        for key in _BLOCKS:
            first_val = (4.0 * near_first[key] - far_first[key]) / 3.0
            second_val = (4.0 * near_second[key] - far_second[key]) / 3.0
            diagonal[key][i] = kress_self * first_val + step * second_val

    return diagonal


# --------------------------------------------------------------- assembly --


@dataclass
class KdiffOperatorBlocks:
    single_layer_matrix: np.ndarray
    double_layer_matrix: np.ndarray
    adjoint_double_layer_matrix: np.ndarray
    hypersingular_matrix: np.ndarray
    num_boundary_samples: int


def boundary_points_normals_weights(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Extract plain-numpy points/normals/weights. Compressed samples only.

    Unlike ``gpr_bem_mod``, this does not support an uncompressed
    ``ImplicitBoundaryBand2D`` -- the local-neighbour diagonal treatment
    assumes the boundary has already been reduced to one node per boundary
    location, which is exactly what compression provides.
    """

    if not isinstance(boundary, ImplicitBoundarySamples2D):
        raise TypeError(
            "gpr_bem_kdiff operates on ImplicitBoundarySamples2D (compress_implicit_boundary_band's "
            "output) only, not an uncompressed ImplicitBoundaryBand2D."
        )
    points = boundary.points.detach().cpu().numpy().astype(float)
    normals = boundary.normals.detach().cpu().numpy().astype(float)
    weights = boundary.quadrature_weights.detach().cpu().numpy().reshape(-1).astype(float)
    return points, normals, weights


def build_kdiff_operator_blocks(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    k_exterior: complex,
    k_interior: complex,
    sdf_fn: Callable[[torch.Tensor], torch.Tensor] | None = None,
) -> KdiffOperatorBlocks:
    """Assemble the four Muller difference blocks directly on the real boundary.

    Off-diagonal: the differenced kernel evaluated between the two given
    nodes, weighted by the target node's own quadrature weight -- plain
    Nystrom quadrature, no offset, no correction for the log-singular block
    near (not at) the diagonal (see module docstring).

    Diagonal: ``_diagonal_terms``, the local-osculating-circle Richardson
    limit. ``sdf_fn``, if given, replaces that fit's neighbour-estimated
    curvature with the exact autograd curvature from ``_sdf_curvature`` --
    optional for now (see ``_sdf_curvature``'s docstring).
    """

    points, normals, weights = boundary_points_normals_weights(boundary)
    num_nodes = points.shape[0]

    geometry = _pair_geometry(points, normals, points, normals, outer=True)
    safe_r = np.where(np.eye(num_nodes, dtype=bool), 1.0, geometry[0])
    kernels, _ = _difference_kernels(safe_r, *geometry[1:], k_exterior, k_interior)

    diagonal = _diagonal_terms(points, normals, weights, k_exterior, k_interior, sdf_fn=sdf_fn)

    matrices: dict[str, np.ndarray] = {}
    for key in _BLOCKS:
        matrix = kernels[key] * weights[None, :]
        np.fill_diagonal(matrix, diagonal[key])
        matrices[key] = matrix

    return KdiffOperatorBlocks(
        single_layer_matrix=matrices["single"],
        double_layer_matrix=matrices["double"],
        adjoint_double_layer_matrix=matrices["adjoint"],
        hypersingular_matrix=matrices["hyper"],
        num_boundary_samples=num_nodes,
    )
