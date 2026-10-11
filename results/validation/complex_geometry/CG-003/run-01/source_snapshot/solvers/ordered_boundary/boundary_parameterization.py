"""Continuous multi-component producers for node-based ordered boundaries."""

from __future__ import annotations

from dataclasses import dataclass
import operator
from typing import Mapping, Sequence

import numpy as np

from .boundary import OrderedBoundary2D
from .parameterization import PeriodicParameterization2D


@dataclass(frozen=True)
class OrderedBoundaryParameterization2D:
    """Ordered continuous components that can be discretized at chosen sizes."""

    components: tuple[PeriodicParameterization2D, ...]

    def __post_init__(self) -> None:
        components = tuple(self.components)
        if not components:
            raise ValueError("At least one periodic parameterization is required.")
        if not all(isinstance(component, PeriodicParameterization2D) for component in components):
            raise TypeError("components must contain only PeriodicParameterization2D objects.")
        component_ids = tuple(component.component_id for component in components)
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("component_id values must be unique.")
        object.__setattr__(self, "components", components)

    @property
    def component_ids(self) -> tuple[str, ...]:
        return tuple(component.component_id for component in self.components)

    @property
    def num_components(self) -> int:
        return len(self.components)

    def component(self, component: int | str) -> PeriodicParameterization2D:
        if isinstance(component, str):
            try:
                index = self.component_ids.index(component)
            except ValueError as exc:
                raise KeyError(component) from exc
            return self.components[index]
        return self.components[int(component)]

    def discretize(
        self,
        node_counts: int | Sequence[int] | Mapping[str, int],
        *,
        require_even: bool = False,
    ) -> OrderedBoundary2D:
        """Create the explicit node boundary consumed by BIE assemblers."""

        counts = resolve_node_counts(self.component_ids, node_counts)
        return OrderedBoundary2D(
            tuple(
                component.discretize(count, require_even=require_even)
                for component, count in zip(self.components, counts)
            )
        )


def resolve_node_counts(
    component_ids: Sequence[str],
    node_counts: int | Sequence[int] | Mapping[str, int],
) -> tuple[int, ...]:
    """Normalize one/per-component node-count specifications."""

    ids = tuple(component_ids)

    def coerce_count(value) -> int:
        if isinstance(value, bool):
            raise TypeError("node counts must be integers, not bool.")
        try:
            return operator.index(value)
        except TypeError as exc:
            raise TypeError("node counts must be integers.") from exc

    if isinstance(node_counts, bool):
        raise TypeError("node counts must be integers, not bool.")
    if isinstance(node_counts, Mapping):
        missing = set(ids) - set(node_counts)
        extra = set(node_counts) - set(ids)
        if missing or extra:
            raise ValueError(
                f"node-count mapping mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
            )
        counts = tuple(coerce_count(node_counts[component_id]) for component_id in ids)
    elif isinstance(node_counts, (int, np.integer)) and not isinstance(node_counts, bool):
        counts = tuple(coerce_count(node_counts) for _ in ids)
    else:
        counts = tuple(coerce_count(value) for value in node_counts)
        if len(counts) != len(ids):
            raise ValueError("node_counts must provide one count per component.")
    if any(count < 3 for count in counts):
        raise ValueError("Every component needs at least three nodes.")
    return counts
