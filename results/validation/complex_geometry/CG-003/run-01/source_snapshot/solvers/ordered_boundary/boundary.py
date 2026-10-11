"""Immutable node-based multi-component boundary for BIE assemblers."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._array_utils import readonly_float_array, readonly_int_array
from .curve import PeriodicCurve2D


@dataclass(frozen=True)
class OrderedBoundary2D:
    """One or more ordered node curves, flattened without losing topology.

    This is the solver-facing BIE geometry object. Its arrays are explicit,
    owned, and read-only; it contains no SDF and no hidden curve evaluator.
    """

    components: tuple[PeriodicCurve2D, ...]
    component_slices: tuple[slice, ...] = field(init=False)
    component_ids: tuple[str, ...] = field(init=False)
    parameters: np.ndarray = field(init=False)
    points: np.ndarray = field(init=False)
    first_derivatives: np.ndarray = field(init=False)
    second_derivatives: np.ndarray = field(init=False)
    third_derivatives: np.ndarray | None = field(init=False)
    speeds: np.ndarray = field(init=False)
    tangents: np.ndarray = field(init=False)
    normals: np.ndarray = field(init=False)
    curvatures: np.ndarray = field(init=False)
    arc_length_weights: np.ndarray = field(init=False)
    node_component_indices: np.ndarray = field(init=False)
    node_local_indices: np.ndarray = field(init=False)
    component_offsets: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        components = tuple(self.components)
        if not components:
            raise ValueError("At least one node-based periodic component is required.")
        if not all(isinstance(component, PeriodicCurve2D) for component in components):
            raise TypeError("components must contain only node-based PeriodicCurve2D objects.")
        ids = tuple(component.component_id for component in components)
        if len(set(ids)) != len(ids):
            raise ValueError("component_id values must be unique.")

        slices = []
        offset = 0
        for component in components:
            slices.append(slice(offset, offset + component.num_nodes))
            offset += component.num_nodes

        def concatenate(name: str) -> np.ndarray:
            return readonly_float_array(
                np.concatenate([getattr(component, name) for component in components], axis=0),
                name=name,
            )

        node_components = readonly_int_array(
            np.concatenate(
                [
                    np.full(component.num_nodes, index, dtype=np.int64)
                    for index, component in enumerate(components)
                ]
            ),
            name="node_component_indices",
            ndim=1,
        )
        node_local_indices = readonly_int_array(
            np.concatenate(
                [np.arange(component.num_nodes, dtype=np.int64) for component in components]
            ),
            name="node_local_indices",
            ndim=1,
        )
        component_offsets = readonly_int_array(
            [item.start for item in slices] + [slices[-1].stop],
            name="component_offsets",
            ndim=1,
        )

        object.__setattr__(self, "components", components)
        object.__setattr__(self, "component_slices", tuple(slices))
        object.__setattr__(self, "component_ids", ids)
        for name in (
            "parameters",
            "points",
            "first_derivatives",
            "second_derivatives",
            "speeds",
            "tangents",
            "normals",
            "curvatures",
            "arc_length_weights",
        ):
            object.__setattr__(self, name, concatenate(name))
        if all(component.third_derivatives is not None for component in components):
            object.__setattr__(self, "third_derivatives", concatenate("third_derivatives"))
        else:
            object.__setattr__(self, "third_derivatives", None)
        object.__setattr__(self, "node_component_indices", node_components)
        object.__setattr__(self, "node_local_indices", node_local_indices)
        object.__setattr__(self, "component_offsets", component_offsets)

    @property
    def num_components(self) -> int:
        return len(self.components)

    @property
    def num_nodes(self) -> int:
        return int(self.points.shape[0])

    @property
    def perimeter(self) -> float:
        return float(sum(component.perimeter for component in self.components))

    def component(self, component: int | str) -> PeriodicCurve2D:
        if isinstance(component, str):
            try:
                index = self.component_ids.index(component)
            except ValueError as exc:
                raise KeyError(component) from exc
            return self.components[index]
        return self.components[int(component)]
