"""Atlas layers along trajectories, in the clean backend's update coordinates.

Coordinates are the backend's: real Fourier coefficients (metres) of the
normal distance h in the current normalized arclength, ordered
`[a0, a1..aP, b1..bP]`. Each frequency is normalized as a single-frequency
stage would be (weight 1), so the stage objective's Gauss-Newton block and
gradient are exactly the weighted sums of these per-frequency layers.

Layers per (state, k): sensitivity, signed gradient, Gauss-Newton block and
spectrum, the LM step at a declared damping and a truncated GN step. The
true-error layer is evaluation-only: it needs the truth and must never be
passed to any fitting, step or policy code.
"""
from dataclasses import dataclass

import numpy as np

from .forward import solve, shape_jacobian
from .geometry import normal_basis, grid_size, integer
from .lm_backend import normalize


@dataclass(frozen=True)
class Cell:
    """One frequency at one state. Arrays are indexed by update coordinate."""
    wavenumber: float
    loss: float  # 0.5 ||r||^2 with this frequency's own normalization
    relative_residual: float
    gradient: np.ndarray  # J^T r
    gauss_newton: np.ndarray  # J^T J (P x P, symmetric)
    system_residual: float

    @property
    def sensitivity(self):
        return np.sqrt(np.clip(np.diag(self.gauss_newton), 0, None))

    def eigen(self):
        values, vectors = np.linalg.eigh(self.gauss_newton)
        order = np.argsort(values)[::-1]
        return np.clip(values[order], 0, None), vectors[:, order]


def orders(band):
    """Harmonic order of each coordinate: 0, 1..P, 1..P."""
    band = integer(band, "band", minimum=0)
    harmonics = np.arange(1, band + 1)
    return np.concatenate(([0], harmonics, harmonics))


def cell(curve, observation, contrast, nodes, band, length_unit_m, *, floor=1e-12):
    """One forward solve and one reciprocal Jacobian at one frequency."""
    state = solve(curve, observation.wavenumber, contrast, observation.acquisition, nodes)
    basis = normal_basis(state.curve, band) / length_unit_m
    jacobian = shape_jacobian(state, basis)  # paired: (pairs, coordinates)
    observed = np.asarray(observation.scattered)[:, None]
    rows = normalize(jacobian[:, None, :], observed, (1.0,), floor)
    residual = normalize((state.prediction - observation.scattered)[:, None], observed, (1.0,), floor)
    gram = rows.T @ rows
    return Cell(float(observation.wavenumber), 0.5 * float(residual @ residual),
                float(np.linalg.norm(state.prediction - observation.scattered)
                      / np.linalg.norm(observation.scattered)),
                rows.T @ residual, 0.5 * (gram + gram.T), float(state.system_residual))


def lm_step(gauss_newton, gradient, damping, floor=1.0):
    """The backend's LM proposal before clipping: -(G + lambda diag(max(diag G, floor)))^-1 g."""
    scaling = np.maximum(np.diag(gauss_newton), floor)
    return np.linalg.solve(gauss_newton + damping * np.diag(scaling), -gradient)


def conditional_step(gauss_newton, gradient, keep, damping, floor=1.0):
    """LM step solved only over the coordinates `keep`; zero elsewhere.

    This is the step the backend would propose with that coordinate set. A
    slice of a larger solve is a different quantity: eliminating the other
    coordinates changes the Schur complement (review 2026-09-24, point 1).
    """
    keep = np.asarray(keep)
    step = np.zeros(len(gradient))
    step[keep] = lm_step(gauss_newton[np.ix_(keep, keep)], gradient[keep], damping, floor)
    return step


def band_coordinates(band, atlas_band):
    """Indices of harmonics 0..band inside an atlas vector ordered a0, a1..aP, b1..bP."""
    band = integer(band, "band", minimum=0)
    if band > atlas_band:
        raise ValueError("band exceeds the atlas band.")
    return np.r_[0, np.arange(1, band + 1), atlas_band + np.arange(1, band + 1)]


def predicted_decrease(gauss_newton, gradient, step):
    """Gauss-Newton model decrease -g.q - q.G.q/2 of 0.5||r||^2 for step q."""
    return float(-gradient @ step - 0.5 * step @ gauss_newton @ step)


def rms_weights(band):
    """Fourier mass of normalized arclength: mean(h^2) = sum w_i c_i^2, w = (1, 1/2, ..., 1/2)."""
    return np.r_[1.0, np.full(2 * integer(band, "band", minimum=0), 0.5)]


def physical_norm(values, band):
    """RMS normal displacement (m) of coefficient vectors along the last axis."""
    return np.sqrt(np.sum(rms_weights(band) * np.asarray(values) ** 2, axis=-1))


def physical_cosine(a, b, band):
    """Cosine between two normal displacements in the L2(arclength) metric."""
    w = rms_weights(band)
    na, nb = physical_norm(a, band), physical_norm(b, band)
    return np.where((na > 0) & (nb > 0), np.sum(w * a * b, axis=-1) / np.maximum(na * nb, 1e-300), np.nan)


def gn_step(gauss_newton, gradient, relative_cutoff=1e-10):
    """Truncated Gauss-Newton step; its predicted decrease is 0.5 g^T H^+ g."""
    values, vectors = np.linalg.eigh(gauss_newton)
    keep = values > relative_cutoff * max(values.max(), np.finfo(float).tiny)
    projected = vectors[:, keep].T @ gradient
    return -(vectors[:, keep] @ (projected / values[keep])), float(0.5 * np.sum(projected ** 2 / values[keep]))


def stage_sum(cells, weights):
    """Stage objective block and gradient as weighted sums of per-frequency layers."""
    gauss_newton = sum(w * c.gauss_newton for c, w in zip(cells, weights))
    gradient = sum(w * c.gradient for c, w in zip(cells, weights))
    return gauss_newton, gradient


def pair_magnitude(values, band):
    """Combine cos/sin coordinates of each harmonic in quadrature: (P+1,)."""
    values = np.asarray(values, float)
    head = np.abs(values[..., :1])
    tail = np.sqrt(values[..., 1:band + 1] ** 2 + values[..., band + 1:] ** 2)
    return np.concatenate((head, tail), axis=-1)


# --- evaluation only -------------------------------------------------------

def true_error(curve, truth_points, band, length_unit_m, count=None):
    """EVALUATION ONLY. Signed closest-distance error PROXY, per harmonic.

    `h(s) = -signed_distance_to_truth(point)`, positive where the truth lies
    outside the current curve. Closest distance is measured along the
    truth's normal, not the current one, so this is the required normal move
    only where the two normals align (see `normal_ray_error`). Kept under its
    SC-022 name for replay. Returned coefficients use the backend ordering
    and metres; `beyond` is the RMS of what band P cannot express.
    """
    from matplotlib.path import Path as Polygon
    from .metrics import points_to_polygon_distance
    count = count or grid_size(max(curve.band, band))
    nodes = curve.nodes(count)
    polygon = np.column_stack((np.real(truth_points), np.imag(truth_points)))
    distance = points_to_polygon_distance(nodes.points, polygon)
    inside = Polygon(polygon).contains_points(nodes.points)
    h = np.where(inside, distance, -distance) * length_unit_m
    basis = normal_basis(nodes, band)
    weights = nodes.arc_length_weights
    gram = basis.T @ (weights[:, None] * basis)
    coefficients = np.linalg.solve(gram, basis.T @ (weights * h))
    remainder = h - basis @ coefficients
    rms = lambda x: float(np.sqrt(np.sum(weights * x ** 2) / np.sum(weights)))
    return coefficients, dict(rms_m=rms(h), beyond_band_rms_m=rms(remainder),
                              maximum_m=float(np.max(np.abs(h))))


def normal_ray_error(curve, truth_points, band, length_unit_m, count=None, chunk=64):
    """EVALUATION ONLY. Signed move along each current normal to the nearest truth crossing.

    For a node x with outward unit normal n, h(x) is the t of smallest |t|
    with x + t n on the truth polygon: the normal move that reaches the
    truth. Nodes whose normal line misses the truth keep the closest-distance
    proxy; `coverage` is the fraction that did not. `alignment` is |t| over
    the closest distance: 1 when the normals agree, large when the ray meets
    the truth far from the closest point. Coefficients as in `true_error`.
    """
    from matplotlib.path import Path as Polygon
    from .metrics import points_to_polygon_distance
    count = count or grid_size(max(curve.band, band))
    nodes = curve.nodes(count)
    p, n = nodes.points, nodes.normals
    polygon = np.column_stack((np.real(truth_points), np.imag(truth_points)))
    edge = np.roll(polygon, -1, axis=0) - polygon
    closest = points_to_polygon_distance(p, polygon)
    inside = Polygon(polygon).contains_points(p)
    proxy = np.where(inside, closest, -closest)
    ray = np.full(len(p), np.nan)
    for start in range(0, len(p), chunk):
        q, m = p[start:start + chunk, None, :], n[start:start + chunk, None, :]
        offset = polygon[None] - q  # (nodes, edges, 2)
        denominator = m[..., 0] * edge[None, :, 1] - m[..., 1] * edge[None, :, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (offset[..., 0] * edge[None, :, 1] - offset[..., 1] * edge[None, :, 0]) / denominator
            u = (offset[..., 0] * m[..., 1] - offset[..., 1] * m[..., 0]) / denominator
        t = np.where((denominator != 0) & (u >= 0) & (u < 1), t, np.inf)
        pick = np.argmin(np.abs(t), axis=1)
        best = t[np.arange(len(pick)), pick]
        ray[start:start + chunk] = np.where(np.isfinite(best), best, np.nan)
    covered = np.isfinite(ray)
    h = np.where(covered, ray, proxy) * length_unit_m
    basis = normal_basis(nodes, band)
    weights = nodes.arc_length_weights
    gram = basis.T @ (weights[:, None] * basis)
    coefficients = np.linalg.solve(gram, basis.T @ (weights * h))
    remainder = h - basis @ coefficients
    rms = lambda x: float(np.sqrt(np.sum(weights * x ** 2) / np.sum(weights)))
    alignment = np.abs(ray[covered]) / np.maximum(closest[covered], 1e-15)
    return coefficients, dict(rms_m=rms(h), beyond_band_rms_m=rms(remainder), maximum_m=float(np.max(np.abs(h))),
                              coverage=float(np.mean(covered)),
                              proxy_difference_rms_m=rms((h - proxy * length_unit_m)),
                              misaligned_fraction=float(np.mean(alignment > 2.0)) if covered.any() else 1.0,
                              median_alignment=float(np.median(alignment)) if covered.any() else float("nan"))


def symmetric_rms_distance(curve, truth_points, length_unit_m, count=4096):
    """EVALUATION ONLY. RMS of closest distances both ways (m), arclength weighted on the curve."""
    from .metrics import points_to_polygon_distance
    nodes = curve.nodes(count)
    polygon = np.column_stack((np.real(truth_points), np.imag(truth_points)))
    forward = points_to_polygon_distance(nodes.points, polygon)
    weights = nodes.arc_length_weights / np.sum(nodes.arc_length_weights)
    z = curve.values(count)
    backward = points_to_polygon_distance(polygon, np.column_stack((z.real, z.imag)))
    segment = np.abs(np.diff(np.r_[truth_points, truth_points[0]]))
    mass = 0.5 * (segment + np.roll(segment, 1))
    return float(np.sqrt(0.5 * np.sum(weights * forward ** 2) + 0.5 * np.sum(mass * backward ** 2) / np.sum(mass))
                 * length_unit_m)
