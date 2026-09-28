"""Bounded spatial pruning of the existing sampled-polygon predicate.

This selects candidate segment pairs, not fewer geometry samples. Dense
polygons, ill-scaled inputs and large candidate sets use the original chunked
calculation supplied by the caller.
"""
from __future__ import annotations

import numpy as np

from ._array_utils import cross2d


def _make_tree(points):
    # The reference ordered-boundary package retains its NumPy-only dependency.
    from scipy.spatial import cKDTree
    return cKDTree(points)


def _candidate_pairs(points, length_tolerance):
    count = len(points)
    ends = np.roll(points, -1, axis=0)
    with np.errstate(over="ignore", invalid="ignore"):
        deltas = ends - points
        centers = points + deltas / 2
        scale = float(np.linalg.norm(np.ptp(points, axis=0)))
        radius = float(np.max(np.linalg.norm(deltas, axis=1)))
        radius += np.sqrt(2.) * length_tolerance
        radius += 16 * np.finfo(float).eps * max(scale, float(np.max(np.abs(points))))
    if not np.isfinite(radius) or not np.isfinite(centers).all():
        return None
    # count_neighbors includes self-pairs and both orders. Count first so a
    # folded/dense polygon cannot allocate an unbounded query_pairs array.
    tree = _make_tree(centers)
    budget = min(262144, max(4096, 16 * count))
    try:
        candidates = (int(tree.count_neighbors(tree, radius)) - count) // 2
        if candidates > budget:
            return None
        pairs = tree.query_pairs(radius, output_type="ndarray")
    except ValueError:
        # SciPy may decline extreme finite coordinates when distances overflow.
        return None
    gap = pairs[:, 1] - pairs[:, 0]
    return pairs[(gap > 1) & (gap < count - 1)]


def spatial_self_intersection_count(points, cross_tolerance, length_tolerance, *, fallback):
    """Count with the dense reference's exact orientation/touching rules.

    For a crossing, midpoint distance is bounded by half the sum of segment
    lengths. For a tolerated touch, an endpoint lies in the other segment's
    length-padded box, so sqrt(2)*length_tolerance covers the extra distance.
    The largest segment length bounds both cases. The padding also covers
    roundoff in midpoint construction, including translated coordinates.
    """
    if (not np.isfinite(cross_tolerance) or not np.isfinite(length_tolerance)
            or cross_tolerance < 0 or length_tolerance < 0):
        return fallback(points, cross_tolerance, length_tolerance)
    pairs = _candidate_pairs(points, length_tolerance)
    if pairs is None:
        return fallback(points, cross_tolerance, length_tolerance)
    if not len(pairs):
        return 0
    ends = np.roll(points, -1, axis=0)
    i, j = pairs.T
    a, b, c, d = points[i], ends[i], points[j], ends[j]
    o1, o2 = cross2d(b-a, c-a), cross2d(b-a, d-a)
    o3, o4 = cross2d(d-c, a-c), cross2d(d-c, b-c)

    def within(point, start, stop):
        return np.all((point >= np.minimum(start, stop) - length_tolerance)
                      & (point <= np.maximum(start, stop) + length_tolerance), axis=1)

    proper = (((o1 > cross_tolerance) & (o2 < -cross_tolerance)
               | (o1 < -cross_tolerance) & (o2 > cross_tolerance))
              & ((o3 > cross_tolerance) & (o4 < -cross_tolerance)
                 | (o3 < -cross_tolerance) & (o4 > cross_tolerance)))
    touching = ((np.abs(o1) <= cross_tolerance) & within(c, a, b)
                | (np.abs(o2) <= cross_tolerance) & within(d, a, b)
                | (np.abs(o3) <= cross_tolerance) & within(a, c, d)
                | (np.abs(o4) <= cross_tolerance) & within(b, c, d))
    return int(np.count_nonzero(proper | touching))
