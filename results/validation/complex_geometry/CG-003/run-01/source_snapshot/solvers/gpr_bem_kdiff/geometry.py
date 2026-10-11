"""Geometry helpers for 2D boundary element meshes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def _orientation(p0: np.ndarray, p1: np.ndarray, p2: np.ndarray) -> float:
    return float((p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0]))


def _point_segment_distance(point: np.ndarray, segment_start: np.ndarray, segment_end: np.ndarray) -> float:
    segment = segment_end - segment_start
    segment_norm_sq = float(segment @ segment)
    if segment_norm_sq == 0.0:
        return float(np.linalg.norm(point - segment_start))

    projection = float((point - segment_start) @ segment) / segment_norm_sq
    projection = min(1.0, max(0.0, projection))
    closest = segment_start + projection * segment
    return float(np.linalg.norm(point - closest))


def _segments_intersect(
    first_start: np.ndarray,
    first_end: np.ndarray,
    second_start: np.ndarray,
    second_end: np.ndarray,
    tolerance: float = 1.0e-12,
) -> bool:
    o1 = _orientation(first_start, first_end, second_start)
    o2 = _orientation(first_start, first_end, second_end)
    o3 = _orientation(second_start, second_end, first_start)
    o4 = _orientation(second_start, second_end, first_end)

    if abs(o1) <= tolerance and abs(o2) <= tolerance and abs(o3) <= tolerance and abs(o4) <= tolerance:
        return False

    return (o1 * o2 <= tolerance) and (o3 * o4 <= tolerance)


def segment_distance(
    first_start: np.ndarray,
    first_end: np.ndarray,
    second_start: np.ndarray,
    second_end: np.ndarray,
) -> float:
    """Return the minimum distance between two line segments."""

    if _segments_intersect(first_start, first_end, second_start, second_end):
        return 0.0

    return min(
        _point_segment_distance(first_start, second_start, second_end),
        _point_segment_distance(first_end, second_start, second_end),
        _point_segment_distance(second_start, first_start, first_end),
        _point_segment_distance(second_end, first_start, first_end),
    )


@dataclass(frozen=True)
class LocalisedSpace2D:
    """Element-local view of a continuous piecewise-linear boundary space."""

    local2global: np.ndarray
    global2local: tuple[tuple[tuple[int, int], ...], ...]
    map_to_localised_space: np.ndarray
    global_local_dofs: np.ndarray
    global_local_weights: np.ndarray
    color_map: np.ndarray
    sorted_panels_by_color: np.ndarray
    color_indexptr: np.ndarray

    @property
    def num_local_dofs(self) -> int:
        return int(self.local2global.size)

    @classmethod
    def from_panel_nodes(cls, panel_nodes: np.ndarray, num_global_dofs: int) -> "LocalisedSpace2D":
        panel_nodes_array = np.asarray(panel_nodes, dtype=int)
        if panel_nodes_array.ndim != 2 or panel_nodes_array.shape[1] != 2:
            raise ValueError("panel_nodes must have shape (num_panels, 2).")

        num_panels = int(panel_nodes_array.shape[0])
        if num_panels == 0:
            raise ValueError("At least one panel is required to build a localised space.")

        global2local_lists: list[list[tuple[int, int]]] = [[] for _ in range(int(num_global_dofs))]
        for panel_index, nodes in enumerate(panel_nodes_array):
            for local_node, global_dof in enumerate(nodes):
                global2local_lists[int(global_dof)].append((panel_index, local_node))

        color_map = -np.ones(num_panels, dtype=np.int32)
        for panel_index, nodes in enumerate(panel_nodes_array):
            neighbors: set[int] = {panel_index}
            for global_dof in nodes:
                neighbors.update(elem for elem, _ in global2local_lists[int(global_dof)])
            neighbors.discard(panel_index)
            neighbor_colors = {int(color_map[neighbor]) for neighbor in neighbors if color_map[neighbor] >= 0}
            color = 0
            while color in neighbor_colors:
                color += 1
            color_map[panel_index] = color

        ncolors = int(1 + np.max(color_map))
        sorted_panels = np.empty(num_panels, dtype=np.int32)
        color_indexptr = np.zeros(ncolors + 1, dtype=np.int32)
        count = 0
        for color in range(ncolors):
            panels = np.flatnonzero(color_map == color).astype(np.int32)
            sorted_panels[count : count + len(panels)] = panels
            count += len(panels)
            color_indexptr[color + 1] = count

        num_local_dofs = 2 * num_panels
        map_to_localised = np.zeros((num_local_dofs, int(num_global_dofs)), dtype=np.float64)
        local_rows = np.arange(num_local_dofs, dtype=np.int64)
        map_to_localised[local_rows, panel_nodes_array.ravel()] = 1.0
        max_multiplicity = max(len(entries) for entries in global2local_lists)
        global_local_dofs = np.zeros((int(num_global_dofs), max_multiplicity), dtype=np.int32)
        global_local_weights = np.zeros((int(num_global_dofs), max_multiplicity), dtype=np.float64)
        for global_dof, entries in enumerate(global2local_lists):
            for position, (panel_index, local_node) in enumerate(entries):
                global_local_dofs[global_dof, position] = 2 * int(panel_index) + int(local_node)
                global_local_weights[global_dof, position] = 1.0

        return cls(
            local2global=panel_nodes_array.copy(),
            global2local=tuple(tuple(entries) for entries in global2local_lists),
            map_to_localised_space=map_to_localised,
            global_local_dofs=global_local_dofs,
            global_local_weights=global_local_weights,
            color_map=color_map,
            sorted_panels_by_color=sorted_panels,
            color_indexptr=color_indexptr,
        )


@dataclass(frozen=True)
class BoundaryMesh2D:
    """Closed 2D boundary mesh with piecewise-linear panels."""

    nodes: np.ndarray
    panels: np.ndarray
    panel_surfaces: np.ndarray | None = None

    def __post_init__(self) -> None:
        nodes = np.asarray(self.nodes, dtype=float)
        panels = np.asarray(self.panels, dtype=int)
        panel_surfaces = self.panel_surfaces

        if nodes.ndim != 2 or nodes.shape[1] != 2:
            raise ValueError("nodes must have shape (num_nodes, 2).")
        if nodes.shape[0] < 3:
            raise ValueError("At least three boundary nodes are required.")
        if panels.ndim != 2 or panels.shape[1] != 2:
            raise ValueError("panels must have shape (num_panels, 2).")
        if np.any(panels < 0) or np.any(panels >= nodes.shape[0]):
            raise ValueError("panel indices must reference valid nodes.")
        if panel_surfaces is None:
            panel_surfaces_array = np.zeros(panels.shape[0], dtype=np.int32)
        else:
            panel_surfaces_array = np.asarray(panel_surfaces, dtype=np.int32)
            if panel_surfaces_array.shape != (panels.shape[0],):
                raise ValueError("panel_surfaces must have shape (num_panels,).")
            if np.any(panel_surfaces_array < 0):
                raise ValueError("panel_surfaces must be non-negative.")

        panel_start = nodes[panels[:, 0]]
        panel_end = nodes[panels[:, 1]]
        delta = panel_end - panel_start
        panel_length = np.linalg.norm(delta, axis=1)

        if np.any(panel_length <= 0.0):
            raise ValueError("Boundary panels must have non-zero length.")

        panel_tangent = delta / panel_length[:, None]
        panel_normal = np.column_stack((panel_tangent[:, 1], -panel_tangent[:, 0]))
        unique_surfaces, inverse_surfaces = np.unique(panel_surfaces_array, return_inverse=True)
        num_surfaces = int(unique_surfaces.size)
        surface_panel_indices = tuple(np.flatnonzero(inverse_surfaces == surface_index).astype(np.int32) for surface_index in range(num_surfaces))
        surface_node_indices = tuple(
            np.unique(panels[panel_indices].ravel()).astype(np.int32)
            for panel_indices in surface_panel_indices
        )
        surface_local_dof_indices = tuple(
            np.column_stack((2 * panel_indices, 2 * panel_indices + 1)).ravel().astype(np.int32)
            for panel_indices in surface_panel_indices
        )
        node_normals = np.zeros_like(nodes)
        node_surfaces = -np.ones(nodes.shape[0], dtype=np.int32)
        for panel_index, (start_node, end_node) in enumerate(panels):
            panel_weight = panel_length[panel_index]
            node_normals[start_node] += panel_weight * panel_normal[panel_index]
            node_normals[end_node] += panel_weight * panel_normal[panel_index]
            surface_index = inverse_surfaces[panel_index]
            if node_surfaces[start_node] < 0:
                node_surfaces[start_node] = surface_index
            if node_surfaces[end_node] < 0:
                node_surfaces[end_node] = surface_index
        node_normal_norm = np.linalg.norm(node_normals, axis=1)
        if np.any(node_normal_norm <= 0.0):
            raise ValueError("Boundary nodes must admit a non-zero averaged normal.")
        node_normals = node_normals / node_normal_norm[:, None]

        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "panels", panels)
        object.__setattr__(self, "panel_surfaces", inverse_surfaces.astype(np.int32))
        object.__setattr__(self, "panel_nodes", panels)
        object.__setattr__(self, "panel_start", panel_start)
        object.__setattr__(self, "panel_end", panel_end)
        object.__setattr__(self, "panel_length", panel_length)
        object.__setattr__(self, "panel_tangent", panel_tangent)
        object.__setattr__(self, "panel_normal", panel_normal)
        object.__setattr__(self, "num_panels", int(panels.shape[0]))
        object.__setattr__(self, "num_dofs", int(nodes.shape[0]))
        object.__setattr__(self, "num_surfaces", num_surfaces)
        object.__setattr__(self, "surface_panel_indices", surface_panel_indices)
        object.__setattr__(self, "surface_node_indices", surface_node_indices)
        object.__setattr__(self, "surface_local_dof_indices", surface_local_dof_indices)
        object.__setattr__(self, "node_normals", node_normals)
        object.__setattr__(self, "node_surfaces", node_surfaces)
        object.__setattr__(self, "localised_space", LocalisedSpace2D.from_panel_nodes(panels, nodes.shape[0]))

    @classmethod
    def from_closed_curve(cls, nodes: np.ndarray) -> "BoundaryMesh2D":
        return cls.from_closed_curves([nodes])

    @classmethod
    def from_closed_curves(cls, curves: list[np.ndarray] | tuple[np.ndarray, ...]) -> "BoundaryMesh2D":
        if len(curves) == 0:
            raise ValueError("At least one closed curve is required.")

        node_blocks: list[np.ndarray] = []
        panel_blocks: list[np.ndarray] = []
        panel_surfaces: list[np.ndarray] = []
        node_offset = 0

        for surface_index, curve in enumerate(curves):
            closed_nodes = np.asarray(curve, dtype=float)
            if closed_nodes.ndim != 2 or closed_nodes.shape[1] != 2:
                raise ValueError("Each curve must have shape (num_nodes, 2).")
            if closed_nodes.shape[0] < 3:
                raise ValueError("Each closed curve must have at least three nodes.")

            if np.linalg.norm(closed_nodes[0] - closed_nodes[-1]) <= 1.0e-12:
                closed_nodes = closed_nodes[:-1]

            num_nodes = closed_nodes.shape[0]
            if num_nodes < 3:
                raise ValueError("Each closed curve must have at least three distinct nodes.")

            panels = np.column_stack(
                (
                    node_offset + np.arange(num_nodes, dtype=np.int32),
                    node_offset + np.roll(np.arange(num_nodes, dtype=np.int32), -1),
                )
            )
            node_blocks.append(closed_nodes)
            panel_blocks.append(panels)
            panel_surfaces.append(np.full(num_nodes, surface_index, dtype=np.int32))
            node_offset += num_nodes

        return cls(
            nodes=np.vstack(node_blocks),
            panels=np.vstack(panel_blocks),
            panel_surfaces=np.concatenate(panel_surfaces),
        )

    @classmethod
    def from_circles(
        cls,
        centers: np.ndarray,
        radii: np.ndarray,
        num_panels_per_circle: np.ndarray | list[int] | tuple[int, ...] | int,
    ) -> "BoundaryMesh2D":
        centers_array = np.asarray(centers, dtype=float)
        radii_array = np.asarray(radii, dtype=float)
        if centers_array.ndim != 2 or centers_array.shape[1] != 2:
            raise ValueError("centers must have shape (num_circles, 2).")
        if radii_array.shape != (centers_array.shape[0],):
            raise ValueError("radii must have shape (num_circles,).")
        if np.any(radii_array <= 0.0):
            raise ValueError("radii must be strictly positive.")

        if np.isscalar(num_panels_per_circle):
            panel_counts = np.full(centers_array.shape[0], int(num_panels_per_circle), dtype=np.int32)
        else:
            panel_counts = np.asarray(num_panels_per_circle, dtype=np.int32)
            if panel_counts.shape != (centers_array.shape[0],):
                raise ValueError("num_panels_per_circle must have shape (num_circles,).")
        if np.any(panel_counts < 3):
            raise ValueError("Each circle must have at least three panels.")

        curves = []
        for center, radius, panel_count in zip(centers_array, radii_array, panel_counts):
            angles = np.linspace(0.0, 2.0 * np.pi, int(panel_count), endpoint=False)
            curves.append(
                np.column_stack(
                    (
                        float(center[0]) + float(radius) * np.cos(angles),
                        float(center[1]) + float(radius) * np.sin(angles),
                    )
                )
            )
        return cls.from_closed_curves(curves)

    @classmethod
    def from_circle(
        cls,
        center: tuple[float, float],
        radius: float,
        num_panels: int,
    ) -> "BoundaryMesh2D":
        return cls.from_circles(
            centers=np.asarray([center], dtype=float),
            radii=np.asarray([radius], dtype=float),
            num_panels_per_circle=np.asarray([num_panels], dtype=np.int32),
        )

    def panel_points(self, panel_index: int, local_coordinate: np.ndarray) -> np.ndarray:
        return self.panel_start[panel_index] + (
            self.panel_length[panel_index] * np.asarray(local_coordinate, dtype=float)
        )[:, None] * self.panel_tangent[panel_index]

    def panel_distance(self, target_panel: int, source_panel: int) -> float:
        return segment_distance(
            self.panel_start[target_panel],
            self.panel_end[target_panel],
            self.panel_start[source_panel],
            self.panel_end[source_panel],
        )

    def _clone_with_same_topology_nodes(self, nodes: np.ndarray) -> "BoundaryMesh2D":
        nodes_array = np.asarray(nodes, dtype=float)
        if nodes_array.shape != self.nodes.shape:
            raise ValueError("nodes must have the same shape as the current boundary mesh.")

        panel_start = nodes_array[self.panels[:, 0]]
        panel_end = nodes_array[self.panels[:, 1]]
        delta = panel_end - panel_start
        panel_length = np.linalg.norm(delta, axis=1)
        if np.any(panel_length <= 0.0):
            raise ValueError("Boundary panels must have non-zero length.")
        panel_tangent = delta / panel_length[:, None]
        panel_normal = np.column_stack((panel_tangent[:, 1], -panel_tangent[:, 0]))

        node_normals = np.zeros_like(nodes_array)
        for panel_index, (start_node, end_node) in enumerate(self.panels):
            panel_weight = panel_length[panel_index]
            weighted_normal = panel_weight * panel_normal[panel_index]
            node_normals[start_node] += weighted_normal
            node_normals[end_node] += weighted_normal
        node_normal_norm = np.linalg.norm(node_normals, axis=1)
        if np.any(node_normal_norm <= 0.0):
            raise ValueError("Boundary nodes must admit a non-zero averaged normal.")
        node_normals = node_normals / node_normal_norm[:, None]

        cloned = object.__new__(BoundaryMesh2D)
        object.__setattr__(cloned, "nodes", nodes_array)
        object.__setattr__(cloned, "panels", self.panels)
        object.__setattr__(cloned, "panel_surfaces", self.panel_surfaces)
        object.__setattr__(cloned, "panel_nodes", self.panel_nodes)
        object.__setattr__(cloned, "panel_start", panel_start)
        object.__setattr__(cloned, "panel_end", panel_end)
        object.__setattr__(cloned, "panel_length", panel_length)
        object.__setattr__(cloned, "panel_tangent", panel_tangent)
        object.__setattr__(cloned, "panel_normal", panel_normal)
        object.__setattr__(cloned, "num_panels", self.num_panels)
        object.__setattr__(cloned, "num_dofs", self.num_dofs)
        object.__setattr__(cloned, "num_surfaces", self.num_surfaces)
        object.__setattr__(cloned, "surface_panel_indices", self.surface_panel_indices)
        object.__setattr__(cloned, "surface_node_indices", self.surface_node_indices)
        object.__setattr__(cloned, "surface_local_dof_indices", self.surface_local_dof_indices)
        object.__setattr__(cloned, "node_normals", node_normals)
        object.__setattr__(cloned, "node_surfaces", self.node_surfaces)
        object.__setattr__(cloned, "localised_space", self.localised_space)
        return cloned

    def with_nodes(self, nodes: np.ndarray) -> "BoundaryMesh2D":
        """Return a mesh with updated node positions and unchanged topology."""

        return BoundaryMesh2D(
            nodes=np.asarray(nodes, dtype=float),
            panels=self.panels.copy(),
            panel_surfaces=self.panel_surfaces.copy(),
        )

    def displaced_nodes_along_normals(self, normal_displacement: float | np.ndarray) -> np.ndarray:
        """Return node coordinates displaced along the averaged node normals."""

        displacement = np.asarray(normal_displacement, dtype=float)
        if displacement.ndim == 0:
            displacement = np.full(self.num_dofs, float(displacement), dtype=float)
        if displacement.shape != (self.num_dofs,):
            raise ValueError("normal_displacement must be a scalar or have shape (num_nodes,).")
        return self.nodes + displacement[:, None] * self.node_normals

    def with_normal_displacement(self, normal_displacement: float | np.ndarray) -> "BoundaryMesh2D":
        """Return a topologically identical mesh displaced along node normals."""

        return self.with_nodes(self.displaced_nodes_along_normals(normal_displacement))

    def with_nodes_fast(self, nodes: np.ndarray) -> "BoundaryMesh2D":
        """Return a topologically identical mesh while reusing topology-only caches."""

        return self._clone_with_same_topology_nodes(nodes)

    def with_normal_displacement_fast(self, normal_displacement: float | np.ndarray) -> "BoundaryMesh2D":
        """Fast same-topology normal displacement for iterative shape updates."""

        return self._clone_with_same_topology_nodes(
            self.displaced_nodes_along_normals(normal_displacement)
        )
