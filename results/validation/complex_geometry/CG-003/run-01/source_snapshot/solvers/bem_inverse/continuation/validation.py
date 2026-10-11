"""Spatially pruned polygon checks with the ordered-boundary tolerance rules."""
import numpy as np
from scipy.spatial import cKDTree
from ordered_boundary.validation_cache import array_key, memoized_validation


def self_intersections(points, relative_tolerance=1e-12):
    """Count nonadjacent crossing/touching segments without all-pairs arrays.

    Intersecting segments have centers at most half the sum of their lengths
    apart. The largest segment length therefore gives a conservative search
    radius. Padding also includes the reference predicate's tolerated touches.
    This prunes comparisons, not geometry samples or admissibility conditions.
    """
    points = np.asarray(points, float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("Expected at least three finite planar points.")
    if not np.isfinite(relative_tolerance) or relative_tolerance < 0:
        raise ValueError("Tolerance must be finite and nonnegative.")
    return memoized_validation("hybrid_self_intersection",
        lambda: (array_key(points), array_key(np.asarray(relative_tolerance))),
        lambda: _self_intersections(points, relative_tolerance))


def _self_intersections(points, relative_tolerance):
    """Unchanged predicate; called only after public input validation."""
    scale = max(np.linalg.norm(np.ptp(points, axis=0)), np.finfo(float).tiny)
    length_tolerance = relative_tolerance * scale
    cross_tolerance = relative_tolerance * scale ** 2
    end = np.roll(points, -1, axis=0)
    delta = end - points
    radius = np.max(np.linalg.norm(delta, axis=1)) + np.sqrt(2) * length_tolerance
    # Include roundoff in center construction for translated coordinate systems.
    radius += 16 * np.finfo(float).eps * max(scale, float(np.max(np.abs(points))))
    pairs = cKDTree(points + delta / 2).query_pairs(radius, output_type="ndarray")
    if not len(pairs):
        return 0
    gap = pairs[:, 1] - pairs[:, 0]
    i, j = pairs[(gap > 1) & (gap < len(points) - 1)].T
    a, b, c, d = points[i], end[i], points[j], end[j]

    def cross(first, second):
        return first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]

    def on_segment(point, start, stop):
        return np.all((point >= np.minimum(start, stop) - length_tolerance)
                      & (point <= np.maximum(start, stop) + length_tolerance), axis=1)

    o1, o2 = cross(b - a, c - a), cross(b - a, d - a)
    o3, o4 = cross(d - c, a - c), cross(d - c, b - c)
    proper = (((o1 > cross_tolerance) & (o2 < -cross_tolerance)
              | (o1 < -cross_tolerance) & (o2 > cross_tolerance))
              & ((o3 > cross_tolerance) & (o4 < -cross_tolerance)
              | (o3 < -cross_tolerance) & (o4 > cross_tolerance)))
    touching = ((np.abs(o1) <= cross_tolerance) & on_segment(c, a, b)
                | (np.abs(o2) <= cross_tolerance) & on_segment(d, a, b)
                | (np.abs(o3) <= cross_tolerance) & on_segment(a, c, d)
                | (np.abs(o4) <= cross_tolerance) & on_segment(b, c, d))
    return int(np.count_nonzero(proper | touching))
