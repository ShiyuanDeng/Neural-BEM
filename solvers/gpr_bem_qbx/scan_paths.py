"""Scan-path helpers for canonical IBIM/Neural-SDF experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = [
    "RectangularLoopScan2D",
    "build_rectangular_bistatic_scan",
    "subset_rectangular_loop_scan",
]


@dataclass(frozen=True)
class RectangularLoopScan2D:
    """Closed rectangular bistatic scan with tangent-aligned Tx/Rx pairs."""

    source_points: np.ndarray
    receiver_points: np.ndarray
    center_points: np.ndarray
    tangents: np.ndarray
    path_coordinate: np.ndarray
    edge_index: np.ndarray
    edge_names: tuple[str, ...]
    edge_boundaries: np.ndarray
    rectangle_vertices: np.ndarray


def build_rectangular_bistatic_scan(
    *,
    left: float,
    right: float,
    top: float,
    bottom: float,
    separation: float,
    top_count: int,
    right_count: int,
    bottom_count: int,
    left_count: int,
) -> RectangularLoopScan2D:
    """Return a closed rectangular scan that avoids ambiguous corner tangents."""

    left_value = float(left)
    right_value = float(right)
    top_value = float(top)
    bottom_value = float(bottom)
    separation_value = float(separation)
    if right_value <= left_value:
        raise ValueError("right must be greater than left.")
    if bottom_value <= top_value:
        raise ValueError("bottom must be greater than top.")
    if separation_value <= 0.0:
        raise ValueError("separation must be positive.")

    counts = (
        int(top_count),
        int(right_count),
        int(bottom_count),
        int(left_count),
    )
    if min(counts) < 1:
        raise ValueError("Each edge must contain at least one scan point.")

    half_separation = 0.5 * separation_value
    width = right_value - left_value
    height = bottom_value - top_value
    if width <= separation_value or height <= separation_value:
        raise ValueError("Rectangle must be wider and taller than the Tx/Rx separation.")

    x_left = left_value + half_separation
    x_right = right_value - half_separation
    y_top = top_value + half_separation
    y_bottom = bottom_value - half_separation
    top_length = x_right - x_left
    right_length = y_bottom - y_top

    top_centers = np.column_stack(
        (
            np.linspace(x_left, x_right, counts[0], dtype=float),
            np.full(counts[0], top_value, dtype=float),
        )
    )
    right_centers = np.column_stack(
        (
            np.full(counts[1], right_value, dtype=float),
            np.linspace(y_top, y_bottom, counts[1], dtype=float),
        )
    )
    bottom_centers = np.column_stack(
        (
            np.linspace(x_right, x_left, counts[2], dtype=float),
            np.full(counts[2], bottom_value, dtype=float),
        )
    )
    left_centers = np.column_stack(
        (
            np.full(counts[3], left_value, dtype=float),
            np.linspace(y_bottom, y_top, counts[3], dtype=float),
        )
    )

    centers = np.vstack((top_centers, right_centers, bottom_centers, left_centers))
    tangents = np.vstack(
        (
            np.tile(np.array([[1.0, 0.0]], dtype=float), (counts[0], 1)),
            np.tile(np.array([[0.0, 1.0]], dtype=float), (counts[1], 1)),
            np.tile(np.array([[-1.0, 0.0]], dtype=float), (counts[2], 1)),
            np.tile(np.array([[0.0, -1.0]], dtype=float), (counts[3], 1)),
        )
    )
    edge_index = np.concatenate(
        (
            np.full(counts[0], 0, dtype=int),
            np.full(counts[1], 1, dtype=int),
            np.full(counts[2], 2, dtype=int),
            np.full(counts[3], 3, dtype=int),
        )
    )

    path_coordinate = np.concatenate(
        (
            np.linspace(0.0, top_length, counts[0], dtype=float),
            top_length + separation_value + np.linspace(0.0, right_length, counts[1], dtype=float),
            top_length + right_length + 2.0 * separation_value + np.linspace(0.0, top_length, counts[2], dtype=float),
            2.0 * top_length + right_length + 3.0 * separation_value
            + np.linspace(0.0, right_length, counts[3], dtype=float),
        )
    )

    edge_boundaries = _edge_boundaries(path_coordinate, edge_index)
    offset = half_separation * tangents
    source_points = centers - offset
    receiver_points = centers + offset
    rectangle_vertices = np.array(
        [
            [left_value, top_value],
            [right_value, top_value],
            [right_value, bottom_value],
            [left_value, bottom_value],
            [left_value, top_value],
        ],
        dtype=float,
    )
    return RectangularLoopScan2D(
        source_points=source_points,
        receiver_points=receiver_points,
        center_points=centers,
        tangents=tangents,
        path_coordinate=path_coordinate,
        edge_index=edge_index,
        edge_names=("top", "right", "bottom", "left"),
        edge_boundaries=edge_boundaries,
        rectangle_vertices=rectangle_vertices,
    )


def subset_rectangular_loop_scan(scan: RectangularLoopScan2D, indices: np.ndarray) -> RectangularLoopScan2D:
    """Return a subsetted rectangular scan while preserving edge metadata."""

    subset = np.asarray(indices, dtype=int).reshape(-1)
    if subset.size == 0:
        raise ValueError("indices must not be empty.")
    return RectangularLoopScan2D(
        source_points=scan.source_points[subset],
        receiver_points=scan.receiver_points[subset],
        center_points=scan.center_points[subset],
        tangents=scan.tangents[subset],
        path_coordinate=scan.path_coordinate[subset],
        edge_index=scan.edge_index[subset],
        edge_names=scan.edge_names,
        edge_boundaries=_edge_boundaries(scan.path_coordinate[subset], scan.edge_index[subset]),
        rectangle_vertices=scan.rectangle_vertices.copy(),
    )


def _edge_boundaries(path_coordinate: np.ndarray, edge_index: np.ndarray) -> np.ndarray:
    path = np.asarray(path_coordinate, dtype=float).reshape(-1)
    edges = np.asarray(edge_index, dtype=int).reshape(-1)
    if path.size != edges.size:
        raise ValueError("path_coordinate and edge_index must have the same length.")
    change_indices = np.flatnonzero(np.diff(edges) != 0)
    if change_indices.size == 0:
        return np.empty((0,), dtype=float)
    return 0.5 * (path[change_indices] + path[change_indices + 1])
