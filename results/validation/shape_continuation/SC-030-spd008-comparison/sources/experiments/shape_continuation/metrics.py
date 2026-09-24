"""Evaluation-only geometry metrics; never imported by the optimizer."""
import numpy as np
from scipy.spatial import cKDTree


def points_to_polygon_distance(points, polygon):
    """Exact point-to-segment distances using a conservative spatial candidate set."""
    tree = cKDTree(polygon)
    upper = tree.query(points)[0]
    edges = np.roll(polygon, -1, axis=0) - polygon
    longest = np.max(np.linalg.norm(edges, axis=1))
    # Every endpoint of a segment closer than the nearest vertex is within
    # upper + longest of the query. Include the complete candidate set.
    candidates = tree.query_ball_point(points, upper + longest * (1 + 1e-12))
    owner = np.repeat(np.arange(len(points)), [len(c) for c in candidates])
    index = np.concatenate(candidates).astype(int)
    displacement = points[owner] - polygon[index]
    vector = edges[index]
    length2 = np.sum(vector * vector, axis=1)
    if np.any(length2 == 0):
        raise ValueError("Polygon must have no repeated consecutive vertices.")
    fraction = np.clip(np.sum(displacement * vector, axis=1) / length2, 0, 1)
    distance = np.linalg.norm(displacement - fraction[:, None] * vector, axis=1)
    result = upper.copy()
    np.minimum.at(result, owner, distance)
    return result


def boundary_distance(first, second, count=8192):
    """Sampled distance and a bound on its error for the continuous Fourier curves."""
    points = [np.column_stack((z.real, z.imag)) for z in (first.values(count), second.values(count))]
    error = max(np.max(points_to_polygon_distance(points[0], points[1])),
                np.max(points_to_polygon_distance(points[1], points[0])))
    bound = max(np.max(np.linalg.norm(np.roll(p, -1, axis=0) - p, axis=1)) / 2 for p in points)
    # The half-edge term covers unsampled points on the two polygons. Also
    # account for replacing each smooth Fourier curve by its polygon: linear
    # interpolation error <= dt^2 * sup|z''| / 8, with a Fourier triangle bound.
    bound += (2 * np.pi / count) ** 2 / 8 * sum(
        np.sum(curve.modes ** 2 * np.abs(curve.coefficients)) for curve in (first, second))
    return float(error), float(bound)


def polygon_area_error(truth, recovered):
    """Area of polygon set differences, normalized by the true polygon area.

    Both arguments are ordered (N,2) vertices of simple polygons. Invalid
    polygons are rejected, never repaired. Shapely is evaluation-only.
    """
    from shapely.geometry import Polygon
    polygons = []
    for vertices in (truth, recovered):
        vertices = np.asarray(vertices, float)
        if (vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3
                or not np.isfinite(vertices).all()):
            raise ValueError("Expected finite polygon vertices with shape (N,2).")
        polygon = Polygon(vertices)
        if not polygon.is_valid or polygon.area <= 0:
            raise ValueError("Area scoring requires valid simple polygons with positive area.")
        polygons.append(polygon)
    target, estimate = polygons
    missing = target.difference(estimate).area / target.area
    excess = estimate.difference(target).area / target.area
    return dict(relative_symmetric_difference=float(missing + excess),
                relative_missing_area=float(missing), relative_excess_area=float(excess),
                true_polygon_area=float(target.area), recovered_polygon_area=float(estimate.area))


def area_error(truth, recovered, count=4096):
    """§4 area score, interpreting 'set difference' as symmetric difference.

    Retain both directed differences to expose that interpretation. N/2N is
    an empirical polygon refinement check, not a continuous-curve certificate.
    """
    from .geometry import integer
    count = integer(count, "area samples", minimum=3)
    def score(n):
        vertices = [np.column_stack((z.real, z.imag))
                    for z in (truth.values(n), recovered.values(n))]
        return polygon_area_error(*vertices)
    coarse, fine = score(count), score(2 * count)
    return dict(fine, samples=2 * count, coarse_samples=count,
                coarse_relative_symmetric_difference=coarse["relative_symmetric_difference"],
                refinement_absolute_change=abs(fine["relative_symmetric_difference"]
                                               - coarse["relative_symmetric_difference"]))
