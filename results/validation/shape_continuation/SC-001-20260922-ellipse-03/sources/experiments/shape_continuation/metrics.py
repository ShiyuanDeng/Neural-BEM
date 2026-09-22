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
    """Symmetric vertex-to-segment distance and a conservative sampling bound."""
    points = [np.column_stack((z.real, z.imag)) for z in (first.values(count), second.values(count))]
    error = max(np.max(points_to_polygon_distance(points[0], points[1])),
                np.max(points_to_polygon_distance(points[1], points[0])))
    bound = max(np.max(np.linalg.norm(np.roll(p, -1, axis=0) - p, axis=1)) / 2 for p in points)
    return float(error), float(bound)
