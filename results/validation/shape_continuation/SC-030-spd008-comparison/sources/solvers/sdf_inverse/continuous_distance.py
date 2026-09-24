"""Numerically refined signed distance to a continuous periodic curve.

All sampled local minima are refined, including competing branches on concave
curves. Doubling the localization grid checks numerical agreement; it is not
a certificate that arbitrary unresolved continuous features cannot exist.
Neither the localization grid nor the tolerance depends on BEM node count.
"""

from __future__ import annotations

import operator
from time import perf_counter
import numpy as np

from ordered_boundary import PeriodicParameterization2D, sampled_self_intersection_count


class ContinuousDistanceRefinementError(ValueError):
    """Configured localization/refinement failed its numerical agreement gate."""


def _count(value, name, minimum):
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer.")
    result = operator.index(value)
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


def _localized_distances(points, curve, count, iterations):
    step = curve.period / count
    parameters = curve.parameter_origin + step * np.arange(count)
    scan = curve.evaluate(parameters).points
    result = np.empty(len(points))
    largest_candidate_count = 0
    golden = (np.sqrt(5.0) - 1.0) / 2.0
    for start in range(0, len(points), 128):
        queries = points[start : start + 128]
        squared = np.sum((queries[:, None] - scan[None]) ** 2, axis=-1)
        before = np.roll(squared, 1, axis=1)
        after = np.roll(squared, -1, axis=1)
        minima = (squared <= before) & (squared <= after)
        minima &= (squared < before) | (squared < after)
        minima[np.arange(len(queries)), np.argmin(squared, axis=1)] = True
        rows, indices = np.nonzero(minima)
        largest_candidate_count = max(largest_candidate_count, int(minima.sum(1).max()))
        candidate_queries = queries[rows]
        left = curve.parameter_origin + step * (indices - 1)
        right = curve.parameter_origin + step * (indices + 1)

        def objective(t):
            return np.sum((curve.evaluate(t).points - candidate_queries) ** 2, axis=-1)

        first = right - golden * (right - left)
        second = left + golden * (right - left)
        first_value, second_value = objective(first), objective(second)
        for _ in range(iterations):
            keep_left = first_value < second_value
            left = np.where(keep_left, left, first)
            right = np.where(keep_left, second, right)
            survivor = np.where(keep_left, first, second)
            survivor_value = np.where(keep_left, first_value, second_value)
            probe = np.where(
                keep_left,
                right - golden * (right - left),
                left + golden * (right - left),
            )
            probe_value = objective(probe)
            first = np.where(keep_left, probe, survivor)
            second = np.where(keep_left, survivor, probe)
            first_value = np.where(keep_left, probe_value, survivor_value)
            second_value = np.where(keep_left, survivor_value, probe_value)
        best_parameter = np.where(first_value < second_value, first, second)
        best_value = np.minimum(first_value, second_value)
        # Pick the global best among the independently refined local candidates.
        order = np.lexsort((best_value, rows))
        selected = order[np.r_[True, np.diff(rows[order]) != 0]]
        evaluation = curve.evaluate(best_parameter[selected])
        tangents = evaluation.first_derivatives
        speeds = np.linalg.norm(tangents, axis=1)
        if np.any(speeds <= np.finfo(float).tiny):
            raise ValueError("Continuous distance requires a regular curve.")
        normals = np.column_stack((tangents[:, 1], -tangents[:, 0])) / speeds[:, None]
        displacement = queries - evaluation.points
        # At a true smooth closest point, the outward normal gives the material
        # side even on concave branches. This is not a nearest-edge sign rule.
        projection = np.einsum("nd,nd->n", displacement, normals)
        result[start : start + len(queries)] = np.where(
            projection < 0.0, -1.0, 1.0
        ) * np.sqrt(best_value[selected])
    return result, largest_candidate_count


def signed_distance_to_continuous_curve(
    query_points,
    curve: PeriodicParameterization2D,
    *,
    tolerance_m: float = 1.0e-6,
    initial_samples: int = 256,
    maximum_samples: int = 4096,
    refinement_iterations: int = 40,
    return_diagnostics: bool = False,
):
    """Return negative-inside distance after independent localization checks.

    The caller supplies a regular, simple, counterclockwise continuous curve.
    Sampled regularity/orientation/simplicity is checked at the starting grid.
    Failure of successive signed-distance agreement raises, never silently
    reverting to the solver polygon. Diagnostics describe observed numerical
    agreement only; unresolved minima can require a denser starting grid.
    """

    if not isinstance(curve, PeriodicParameterization2D):
        raise TypeError("curve must be a PeriodicParameterization2D.")
    if np.iscomplexobj(query_points):
        raise ValueError("query_points must be real-valued.")
    points = np.asarray(query_points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
        raise ValueError("query_points must have finite shape (N, 2).")
    if isinstance(tolerance_m, (bool, np.bool_)) or np.iscomplexobj(tolerance_m):
        raise ValueError("tolerance_m must be a finite positive real number.")
    tolerance = float(tolerance_m)
    if not np.isfinite(tolerance) or tolerance <= 0.0:
        raise ValueError("tolerance_m must be finite and positive.")
    initial = _count(initial_samples, "initial_samples", 32)
    maximum = _count(maximum_samples, "maximum_samples", 2 * initial)
    iterations = _count(refinement_iterations, "refinement_iterations", 8)
    started = perf_counter()
    sampled = curve.discretize(initial)
    if sampled_self_intersection_count(sampled.points):
        raise ValueError("Continuous distance requires a simple curve.")
    coarse, candidates = _localized_distances(points, curve, initial, iterations)
    count = initial
    levels = 1
    while count < maximum:
        count = min(2 * count, maximum)
        levels += 1
        refined, refined_candidates = _localized_distances(points, curve, count, iterations)
        agreement = float(np.max(np.abs(refined - coarse))) if len(points) else 0.0
        candidates = max(candidates, refined_candidates)
        if agreement <= tolerance:
            refined.setflags(write=False)
            diagnostics = {
                "distance_target_tolerance_m": tolerance,
                "distance_refinement_agreement_m": agreement,
                "distance_localization_samples": float(count),
                "distance_refinement_iterations": float(iterations),
                "distance_maximum_local_candidates": float(candidates),
                "distance_query_count": float(len(points)),
                "distance_localization_levels": float(levels),
                "distance_target_seconds": perf_counter() - started,
            }
            return (refined, diagnostics) if return_diagnostics else refined
        coarse = refined
    raise ContinuousDistanceRefinementError(
        "Continuous signed distance did not reach numerical refinement agreement "
        f"{tolerance:.6g} m by {maximum} localization samples (change {agreement:.6g} m)."
    )


def smooth_boundary_samples(curve, count, *, localization_samples=2048):
    """Sample the continuous curve at approximately uniform arc length.

    Polygon lengths provide only the parameter map; returned points and normals
    are evaluated on the continuous curve, with a resolution independent of BEM.
    """

    count = _count(count, "count", 8)
    dense_count = max(_count(localization_samples, "localization_samples", 32), count)
    dense = curve.discretize(dense_count)
    lengths = np.linalg.norm(np.roll(dense.points, -1, axis=0) - dense.points, axis=1)
    cumulative = np.r_[0.0, np.cumsum(lengths)]
    parameters = np.r_[dense.parameters, curve.parameter_origin + curve.period]
    desired = cumulative[-1] * np.arange(count) / count
    evaluation = curve.evaluate(np.interp(desired, cumulative, parameters))
    tangents = evaluation.first_derivatives
    normals = np.column_stack((tangents[:, 1], -tangents[:, 0]))
    normals /= np.linalg.norm(normals, axis=1)[:, None]
    return evaluation.points, normals
