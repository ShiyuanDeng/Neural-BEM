"""Ragged, component-aware boundary trajectories.

An implicit zero set may change from one closed component to several.  A
trajectory therefore cannot be represented faithfully by a dense ``(K,N,2)``
array: that layout silently assumes both a fixed component count and a fixed
node correspondence.  This module stores the two independent ragged axes
explicitly::

    frames -> components -> points

The representation is deliberately solver-neutral.  Solver-ready frames can
be constructed from :class:`ordered_boundary.OrderedBoundary2D`, while a
singular topology-transition frame may retain raw plotting polylines and an
explicit non-solver-ready status.  No interpolation across a topology change
is implied by the storage format.
"""

from __future__ import annotations

from dataclasses import dataclass
import operator
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from ordered_boundary import OrderedBoundary2D


SOLVER_READY = "solver_ready"
TOPOLOGY_TRANSITION = "topology_transition"
INVALID = "invalid"
FRAME_STATUSES = frozenset((SOLVER_READY, TOPOLOGY_TRANSITION, INVALID))
_FORMAT_VERSION = 1


def _readonly_float_array(values: Any, *, name: str, ndim: int) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    try:
        result = np.array(values, dtype=np.float64, copy=True)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real array.") from exc
    if result.ndim != ndim or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite {ndim}-dimensional array.")
    result.setflags(write=False)
    return result


def _readonly_offsets(values: Any, *, name: str, terminal: int) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be integer-valued.")
    raw = np.asarray(values)
    if raw.ndim != 1 or raw.size < 1:
        raise ValueError(f"{name} must be a non-empty one-dimensional array.")
    try:
        integers = np.array(raw, dtype=np.int64, copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be integer-valued.") from exc
    if not np.array_equal(raw, integers):
        raise ValueError(f"{name} must be integer-valued.")
    if integers[0] != 0 or integers[-1] != terminal:
        raise ValueError(f"{name} must start at zero and end at {terminal}.")
    if np.any(np.diff(integers) < 0):
        raise ValueError(f"{name} must be non-decreasing.")
    integers.setflags(write=False)
    return integers


def _text_tuple(values: Iterable[Any], *, name: str, allow_empty: bool) -> tuple[str, ...]:
    result = tuple(str(value) for value in values)
    if not allow_empty and any(not value.strip() for value in result):
        raise ValueError(f"{name} entries must be non-empty strings.")
    return result


@dataclass(frozen=True)
class BoundaryTrajectoryFrame:
    """One visual boundary state and its solver-readiness classification.

    ``components`` are periodic plotting polylines without a required repeated
    endpoint.  A ``topology_transition`` component is allowed to be singular;
    its status prevents callers from mistaking it for BEM geometry.  Direct
    construction records caller-supplied metadata; use :meth:`from_boundary`
    when ``solver_ready`` must originate from a validated
    :class:`~ordered_boundary.OrderedBoundary2D`.  A serialized frame does not
    reconstruct derivatives or quadrature data and is not itself BEM input.
    """

    parameter: float
    status: str
    components: tuple[np.ndarray, ...]
    component_ids: tuple[str, ...] = ()
    parent_ids: tuple[str, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        parameter = float(self.parameter)
        if not np.isfinite(parameter):
            raise ValueError("parameter must be finite.")
        if self.status not in FRAME_STATUSES:
            allowed = ", ".join(sorted(FRAME_STATUSES))
            raise ValueError(f"status must be one of: {allowed}.")

        components: list[np.ndarray] = []
        for index, values in enumerate(self.components):
            points = _readonly_float_array(
                values,
                name=f"components[{index}]",
                ndim=2,
            )
            if points.shape[1:] != (2,) or points.shape[0] < 2:
                raise ValueError(
                    f"components[{index}] must have shape (N, 2), N >= 2."
                )
            components.append(points)

        ids = self.component_ids
        if not ids and components:
            ids = tuple(f"component_{index:03d}" for index in range(len(components)))
        ids = _text_tuple(ids, name="component_ids", allow_empty=False)
        if len(ids) != len(components):
            raise ValueError("component_ids must contain one ID per component.")
        if len(set(ids)) != len(ids):
            raise ValueError("component_ids must be unique within a frame.")

        parents = self.parent_ids
        if not parents and components:
            parents = ("",) * len(components)
        parents = _text_tuple(parents, name="parent_ids", allow_empty=True)
        if len(parents) != len(components):
            raise ValueError("parent_ids must contain one entry per component.")

        message = str(self.message)
        if self.status != SOLVER_READY and not message.strip():
            raise ValueError("A non-solver-ready frame must explain why it is unusable.")
        if self.status == SOLVER_READY and not components:
            raise ValueError("A solver-ready frame must contain at least one component.")

        object.__setattr__(self, "parameter", parameter)
        object.__setattr__(self, "components", tuple(components))
        object.__setattr__(self, "component_ids", ids)
        object.__setattr__(self, "parent_ids", parents)
        object.__setattr__(self, "message", message)

    @property
    def solver_ready(self) -> bool:
        return self.status == SOLVER_READY

    @property
    def num_components(self) -> int:
        return len(self.components)

    @classmethod
    def from_boundary(
        cls,
        boundary: OrderedBoundary2D,
        *,
        parameter: float,
        component_ids: tuple[str, ...] | None = None,
        parent_ids: tuple[str, ...] = (),
        message: str = "",
    ) -> "BoundaryTrajectoryFrame":
        """Copy a validated solver boundary into one solver-ready frame."""

        if not isinstance(boundary, OrderedBoundary2D):
            raise TypeError("boundary must be an OrderedBoundary2D.")
        ids = boundary.component_ids if component_ids is None else component_ids
        return cls(
            parameter=parameter,
            status=SOLVER_READY,
            components=tuple(component.points for component in boundary.components),
            component_ids=ids,
            parent_ids=parent_ids,
            message=message,
        )


@dataclass(frozen=True)
class RaggedBoundaryTrajectory:
    """Immutable CSR-like storage for a sequence of boundary frames."""

    points: np.ndarray
    component_point_offsets: np.ndarray
    frame_component_offsets: np.ndarray
    parameters: np.ndarray
    statuses: tuple[str, ...]
    component_ids: tuple[str, ...]
    component_parent_ids: tuple[str, ...]
    messages: tuple[str, ...]
    parameter_name: str = "transition_parameter"

    def __post_init__(self) -> None:
        points = _readonly_float_array(self.points, name="points", ndim=2)
        if points.shape[1:] != (2,):
            raise ValueError("points must have shape (P, 2).")
        component_ids = _text_tuple(
            self.component_ids,
            name="component_ids",
            allow_empty=False,
        )
        component_parents = _text_tuple(
            self.component_parent_ids,
            name="component_parent_ids",
            allow_empty=True,
        )
        component_offsets = _readonly_offsets(
            self.component_point_offsets,
            name="component_point_offsets",
            terminal=points.shape[0],
        )
        component_count = component_offsets.size - 1
        if len(component_ids) != component_count:
            raise ValueError("component_ids must contain one ID per stored component.")
        if len(component_parents) != component_count:
            raise ValueError(
                "component_parent_ids must contain one entry per stored component."
            )
        if np.any(np.diff(component_offsets) < 2):
            raise ValueError("Every stored component must contain at least two points.")

        frame_offsets = _readonly_offsets(
            self.frame_component_offsets,
            name="frame_component_offsets",
            terminal=component_count,
        )
        frame_count = frame_offsets.size - 1
        parameters = _readonly_float_array(
            self.parameters,
            name="parameters",
            ndim=1,
        )
        if parameters.shape != (frame_count,):
            raise ValueError("parameters must contain one value per frame.")
        statuses = _text_tuple(self.statuses, name="statuses", allow_empty=False)
        if len(statuses) != frame_count or any(
            status not in FRAME_STATUSES for status in statuses
        ):
            raise ValueError("statuses must contain one valid status per frame.")
        messages = _text_tuple(self.messages, name="messages", allow_empty=True)
        if len(messages) != frame_count:
            raise ValueError("messages must contain one entry per frame.")
        for frame_index, status in enumerate(statuses):
            component_slice = slice(frame_offsets[frame_index], frame_offsets[frame_index + 1])
            frame_ids = component_ids[component_slice]
            if len(set(frame_ids)) != len(frame_ids):
                raise ValueError("Component IDs must be unique within every frame.")
            if status == SOLVER_READY and not frame_ids:
                raise ValueError("Every solver-ready frame must contain a component.")
            if status != SOLVER_READY and not messages[frame_index].strip():
                raise ValueError(
                    "Every non-solver-ready frame must carry an explanatory message."
                )

        parameter_name = str(self.parameter_name).strip()
        if not parameter_name:
            raise ValueError("parameter_name must be a non-empty string.")

        object.__setattr__(self, "points", points)
        object.__setattr__(self, "component_point_offsets", component_offsets)
        object.__setattr__(self, "frame_component_offsets", frame_offsets)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "statuses", statuses)
        object.__setattr__(self, "component_ids", component_ids)
        object.__setattr__(self, "component_parent_ids", component_parents)
        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "parameter_name", parameter_name)

    @property
    def num_frames(self) -> int:
        return int(self.parameters.size)

    @property
    def num_stored_components(self) -> int:
        return len(self.component_ids)

    @classmethod
    def from_frames(
        cls,
        frames: Iterable[BoundaryTrajectoryFrame],
        *,
        parameter_name: str = "transition_parameter",
    ) -> "RaggedBoundaryTrajectory":
        """Pack frames without imposing a fixed component or point count."""

        resolved = tuple(frames)
        if not resolved:
            raise ValueError("frames must contain at least one frame.")
        if not all(isinstance(frame, BoundaryTrajectoryFrame) for frame in resolved):
            raise TypeError("frames must contain only BoundaryTrajectoryFrame objects.")

        point_blocks: list[np.ndarray] = []
        component_offsets = [0]
        frame_offsets = [0]
        component_ids: list[str] = []
        parent_ids: list[str] = []
        for frame in resolved:
            for points, component_id, parent_id in zip(
                frame.components,
                frame.component_ids,
                frame.parent_ids,
            ):
                point_blocks.append(points)
                component_offsets.append(component_offsets[-1] + points.shape[0])
                component_ids.append(component_id)
                parent_ids.append(parent_id)
            frame_offsets.append(frame_offsets[-1] + frame.num_components)
        points = (
            np.concatenate(point_blocks, axis=0)
            if point_blocks
            else np.empty((0, 2), dtype=np.float64)
        )
        return cls(
            points=points,
            component_point_offsets=np.asarray(component_offsets, dtype=np.int64),
            frame_component_offsets=np.asarray(frame_offsets, dtype=np.int64),
            parameters=np.asarray([frame.parameter for frame in resolved]),
            statuses=tuple(frame.status for frame in resolved),
            component_ids=tuple(component_ids),
            component_parent_ids=tuple(parent_ids),
            messages=tuple(frame.message for frame in resolved),
            parameter_name=parameter_name,
        )

    def frame(self, index: int) -> BoundaryTrajectoryFrame:
        """Reconstruct one owned, immutable frame by integer index."""

        if isinstance(index, (bool, np.bool_)):
            raise TypeError("index must be an integer, not bool.")
        try:
            resolved = operator.index(index)
        except TypeError as exc:
            raise TypeError("index must be an integer.") from exc
        if resolved < 0:
            resolved += self.num_frames
        if resolved < 0 or resolved >= self.num_frames:
            raise IndexError(index)
        first_component = int(self.frame_component_offsets[resolved])
        last_component = int(self.frame_component_offsets[resolved + 1])
        components = tuple(
            self.points[
                self.component_point_offsets[component_index] :
                self.component_point_offsets[component_index + 1]
            ]
            for component_index in range(first_component, last_component)
        )
        return BoundaryTrajectoryFrame(
            parameter=float(self.parameters[resolved]),
            status=self.statuses[resolved],
            components=components,
            component_ids=self.component_ids[first_component:last_component],
            parent_ids=self.component_parent_ids[first_component:last_component],
            message=self.messages[resolved],
        )

    def save_npz(self, path: str | Path) -> Path:
        """Write a portable archive readable with ``allow_pickle=False``."""

        destination = Path(path)
        if destination.suffix != ".npz":
            destination = Path(f"{destination}.npz")
        destination.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            destination,
            format_version=np.asarray(_FORMAT_VERSION, dtype=np.int64),
            points=self.points,
            component_point_offsets=self.component_point_offsets,
            frame_component_offsets=self.frame_component_offsets,
            parameters=self.parameters,
            statuses=np.asarray(self.statuses, dtype=np.str_),
            component_ids=np.asarray(self.component_ids, dtype=np.str_),
            component_parent_ids=np.asarray(self.component_parent_ids, dtype=np.str_),
            messages=np.asarray(self.messages, dtype=np.str_),
            parameter_name=np.asarray(self.parameter_name, dtype=np.str_),
        )
        return destination

    @classmethod
    def load_npz(cls, path: str | Path) -> "RaggedBoundaryTrajectory":
        """Load and fully validate a trajectory archive."""

        source = Path(path)
        with np.load(source, allow_pickle=False) as archive:
            required = {
                "format_version",
                "points",
                "component_point_offsets",
                "frame_component_offsets",
                "parameters",
                "statuses",
                "component_ids",
                "component_parent_ids",
                "messages",
                "parameter_name",
            }
            missing = sorted(required.difference(archive.files))
            if missing:
                raise ValueError(
                    "Trajectory archive is missing: " + ", ".join(missing) + "."
                )
            version = int(np.asarray(archive["format_version"]).item())
            if version != _FORMAT_VERSION:
                raise ValueError(
                    f"Unsupported trajectory format version {version}; "
                    f"expected {_FORMAT_VERSION}."
                )
            return cls(
                points=archive["points"],
                component_point_offsets=archive["component_point_offsets"],
                frame_component_offsets=archive["frame_component_offsets"],
                parameters=archive["parameters"],
                statuses=tuple(str(value) for value in archive["statuses"]),
                component_ids=tuple(str(value) for value in archive["component_ids"]),
                component_parent_ids=tuple(
                    str(value) for value in archive["component_parent_ids"]
                ),
                messages=tuple(str(value) for value in archive["messages"]),
                parameter_name=str(np.asarray(archive["parameter_name"]).item()),
            )


__all__ = [
    "BoundaryTrajectoryFrame",
    "FRAME_STATUSES",
    "INVALID",
    "RaggedBoundaryTrajectory",
    "SOLVER_READY",
    "TOPOLOGY_TRANSITION",
]
