"""Deterministic one-to-two component split used for extraction validation.

The fixture follows a Cassini oval through its only topology-changing value,
then smoothly blends the two regular lobes to two exact circle signed-distance
functions.  It is deliberately an analytic validation input, not an inverse
model: a renderer can evaluate the critical frame, while
:func:`build_cassini_split_geometry` refuses to send that nonregular zero set
to Method B or a boundary-integral solver.

In local coordinates ``(u, v)``, the Cassini portion is

``(((u-a)^2+v^2) ((u+a)^2+v^2) - b^4) / (4 b^3)``.

The division gives the field units of length and makes its boundary gradient
unit magnitude at the initial circle (``a=0``).  The dimensionless topology
parameter is ``a / b - 1``: negative means one loop, zero is the pinched
Bernoulli lemniscate, and positive means two loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import operator
from typing import Any

import numpy as np
import torch
from torch import nn


class CassiniSplitTransitionError(RuntimeError):
    """A critical, nonregular split frame was requested for a solver."""


class CassiniSplitTopology(str, Enum):
    """Mathematical topology of one frame's zero set."""

    ONE_COMPONENT = "one_component"
    CRITICAL_PINCH = "critical_pinch"
    TWO_COMPONENTS = "two_components"


class CassiniSplitStage(str, Enum):
    """Visual stage within the complete circle-to-two-circles trajectory."""

    INITIAL_CIRCLE = "initial_circle"
    PRE_SPLIT_CASSINI = "pre_split_cassini"
    CRITICAL_PINCH = "critical_pinch"
    POST_SPLIT_CASSINI = "post_split_cassini"
    POST_SPLIT_BLEND = "post_split_blend"
    EXACT_TWO_CIRCLES = "exact_two_circles"


def _finite_real(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise TypeError(f"{name} must be a real number, not bool or complex.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _finite_positive(value: Any, *, name: str) -> float:
    result = _finite_real(value, name=name)
    if result <= 0.0:
        raise ValueError(f"{name} must be strictly positive.")
    return result


def _unit_interval(value: Any, *, name: str) -> float:
    result = _finite_real(value, name=name)
    if result < 0.0 or result > 1.0:
        raise ValueError(f"{name} must lie in the closed interval [0, 1].")
    return result


def _canonical_center(value: Any) -> tuple[float, float]:
    if np.iscomplexobj(value):
        raise ValueError("center must be real-valued.")
    try:
        center = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError("center must contain two finite coordinates.") from exc
    if center.shape != (2,) or not np.all(np.isfinite(center)):
        raise ValueError("center must contain two finite coordinates.")
    return float(center[0]), float(center[1])


def _real_floating_dtype(dtype: torch.dtype) -> torch.dtype:
    if dtype not in {
        torch.float16,
        torch.bfloat16,
        torch.float32,
        torch.float64,
    }:
        raise TypeError("dtype must be a real floating-point torch dtype.")
    return dtype


def _smoothstep(unit_value: float) -> float:
    """C1 easing with exact endpoint values."""

    if unit_value <= 0.0:
        return 0.0
    if unit_value >= 1.0:
        return 1.0
    return unit_value * unit_value * (3.0 - 2.0 * unit_value)


def _integer_at_least(value: Any, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return result


@dataclass(frozen=True)
class CassiniSplitConfig:
    """Geometry and timing of the analytic split trajectory.

    ``cassini_radius`` is ``b`` in the implicit equation and is also the
    radius of the initial exact zero-set circle.  The foci start together,
    reach ``a=b`` at ``critical_progress``, and finish at
    ``final_focal_half_distance`` when the post-split blend starts.

    When ``final_circle_radius`` is omitted, ``b^2 / (2 a_final)`` is used.
    That is the leading-order radius of a Cassini lobe about either focus, so
    the later blend has little geometric motion while ending at an exact
    two-circle SDF.
    """

    center: tuple[float, float] = (0.5, 0.5)
    cassini_radius: float = 0.12
    final_focal_half_distance: float = 0.16
    final_circle_radius: float | None = None
    rotation_radians: float = 0.0
    critical_progress: float = 0.55
    blend_start_progress: float = 0.78

    def __post_init__(self) -> None:
        center = _canonical_center(self.center)
        radius = _finite_positive(self.cassini_radius, name="cassini_radius")
        final_focus = _finite_positive(
            self.final_focal_half_distance,
            name="final_focal_half_distance",
        )
        if final_focus <= radius:
            raise ValueError(
                "final_focal_half_distance must exceed cassini_radius so the "
                "post-split zero set has two components."
            )
        final_radius = (
            radius * radius / (2.0 * final_focus)
            if self.final_circle_radius is None
            else _finite_positive(
                self.final_circle_radius,
                name="final_circle_radius",
            )
        )
        if final_radius >= final_focus:
            raise ValueError(
                "final_circle_radius must be smaller than "
                "final_focal_half_distance so the endpoint circles are disjoint."
            )
        rotation = _finite_real(self.rotation_radians, name="rotation_radians")
        critical = _unit_interval(
            self.critical_progress,
            name="critical_progress",
        )
        blend_start = _unit_interval(
            self.blend_start_progress,
            name="blend_start_progress",
        )
        if critical <= 0.0:
            raise ValueError("critical_progress must be strictly positive.")
        if blend_start <= critical or blend_start >= 1.0:
            raise ValueError(
                "blend_start_progress must lie strictly between "
                "critical_progress and 1."
            )

        object.__setattr__(self, "center", center)
        object.__setattr__(self, "cassini_radius", radius)
        object.__setattr__(self, "final_focal_half_distance", final_focus)
        object.__setattr__(self, "final_circle_radius", final_radius)
        object.__setattr__(self, "rotation_radians", rotation)
        object.__setattr__(self, "critical_progress", critical)
        object.__setattr__(self, "blend_start_progress", blend_start)

    @property
    def critical_split_parameter(self) -> float:
        """Critical value of ``a / b - 1``."""

        return 0.0

    @property
    def exact_circle_centers(self) -> tuple[tuple[float, float], ...]:
        """World-coordinate endpoint centres in left-to-right local order."""

        direction = np.asarray(
            (math.cos(self.rotation_radians), math.sin(self.rotation_radians)),
            dtype=np.float64,
        )
        center = np.asarray(self.center, dtype=np.float64)
        offset = self.final_focal_half_distance * direction
        return (
            (float(center[0] - offset[0]), float(center[1] - offset[1])),
            (float(center[0] + offset[0]), float(center[1] + offset[1])),
        )

    @property
    def exact_circle_radii(self) -> tuple[float, float]:
        """Radii of the two exact endpoint circles."""

        assert self.final_circle_radius is not None
        return self.final_circle_radius, self.final_circle_radius

    @property
    def exact_circle_clearance(self) -> float:
        """Surface-to-surface separation at the exact endpoint."""

        assert self.final_circle_radius is not None
        return 2.0 * (
            self.final_focal_half_distance - self.final_circle_radius
        )


@dataclass(frozen=True)
class CassiniSplitFrame:
    """Immutable metadata needed to label and audit one video frame."""

    progress: float
    focal_half_distance: float
    normalized_split_parameter: float
    exact_circle_blend_weight: float
    topology: CassiniSplitTopology
    stage: CassiniSplitStage

    def __post_init__(self) -> None:
        progress = _unit_interval(self.progress, name="progress")
        focus = _finite_real(
            self.focal_half_distance,
            name="focal_half_distance",
        )
        parameter = _finite_real(
            self.normalized_split_parameter,
            name="normalized_split_parameter",
        )
        blend = _unit_interval(
            self.exact_circle_blend_weight,
            name="exact_circle_blend_weight",
        )
        if focus < 0.0:
            raise ValueError("focal_half_distance must be non-negative.")
        if not isinstance(self.topology, CassiniSplitTopology):
            raise TypeError("topology must be a CassiniSplitTopology value.")
        if not isinstance(self.stage, CassiniSplitStage):
            raise TypeError("stage must be a CassiniSplitStage value.")
        if self.topology is CassiniSplitTopology.CRITICAL_PINCH and blend != 0.0:
            raise ValueError("The critical Cassini frame cannot be circle-blended.")
        object.__setattr__(self, "progress", progress)
        object.__setattr__(self, "focal_half_distance", focus)
        object.__setattr__(self, "normalized_split_parameter", parameter)
        object.__setattr__(self, "exact_circle_blend_weight", blend)

    @property
    def solver_ready(self) -> bool:
        """Whether the zero set is regular enough to enter boundary fitting."""

        return self.topology is not CassiniSplitTopology.CRITICAL_PINCH

    @property
    def expected_num_components(self) -> int | None:
        """Analytic component count, or ``None`` at the topology event."""

        if self.topology is CassiniSplitTopology.ONE_COMPONENT:
            return 1
        if self.topology is CassiniSplitTopology.TWO_COMPONENTS:
            return 2
        return None

    @property
    def is_exact_circle_endpoint(self) -> bool:
        return self.stage is CassiniSplitStage.EXACT_TWO_CIRCLES

    def require_solver_ready(self) -> None:
        """Reject the pinch before Fourier fitting can smooth it into two loops."""

        if not self.solver_ready:
            raise CassiniSplitTransitionError(
                "The Cassini split is at its critical parameter a / b - 1 = 0. "
                "The zero set self-touches and has zero gradient at the pinch, "
                "so this frame is drawable but cannot be fitted or solved."
            )


@dataclass(frozen=True)
class CassiniSplitTrajectory2D:
    """Generate analytic fields along a deterministic one-to-two split."""

    config: CassiniSplitConfig = CassiniSplitConfig()

    def __post_init__(self) -> None:
        if not isinstance(self.config, CassiniSplitConfig):
            raise TypeError("config must be a CassiniSplitConfig object.")

    @property
    def critical_progress(self) -> float:
        return self.config.critical_progress

    def frame(self, progress: float) -> CassiniSplitFrame:
        """Return exact topology and interpolation metadata at ``progress``."""

        value = _unit_interval(progress, name="progress")
        critical = self.config.critical_progress
        blend_start = self.config.blend_start_progress
        tolerance = 32.0 * np.finfo(np.float64).eps * max(1.0, abs(critical))
        if abs(value - critical) <= tolerance:
            value = critical

        if value < critical:
            local = value / critical
            focus = self.config.cassini_radius * _smoothstep(local)
            blend = 0.0
            topology = CassiniSplitTopology.ONE_COMPONENT
            stage = (
                CassiniSplitStage.INITIAL_CIRCLE
                if value == 0.0
                else CassiniSplitStage.PRE_SPLIT_CASSINI
            )
        elif value == critical:
            focus = self.config.cassini_radius
            blend = 0.0
            topology = CassiniSplitTopology.CRITICAL_PINCH
            stage = CassiniSplitStage.CRITICAL_PINCH
        elif value < blend_start:
            local = (value - critical) / (blend_start - critical)
            focus = self.config.cassini_radius + (
                self.config.final_focal_half_distance
                - self.config.cassini_radius
            ) * _smoothstep(local)
            blend = 0.0
            topology = CassiniSplitTopology.TWO_COMPONENTS
            stage = CassiniSplitStage.POST_SPLIT_CASSINI
        else:
            focus = self.config.final_focal_half_distance
            blend = _smoothstep((value - blend_start) / (1.0 - blend_start))
            topology = CassiniSplitTopology.TWO_COMPONENTS
            stage = (
                CassiniSplitStage.EXACT_TWO_CIRCLES
                if value == 1.0
                else CassiniSplitStage.POST_SPLIT_BLEND
            )

        split_parameter = focus / self.config.cassini_radius - 1.0
        if topology is CassiniSplitTopology.CRITICAL_PINCH:
            split_parameter = self.config.critical_split_parameter
        return CassiniSplitFrame(
            progress=value,
            focal_half_distance=focus,
            normalized_split_parameter=split_parameter,
            exact_circle_blend_weight=blend,
            topology=topology,
            stage=stage,
        )

    def model(
        self,
        progress: float,
        *,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> "CassiniSplitSDF2D":
        """Create the immutable analytic field for one trajectory frame."""

        return CassiniSplitSDF2D(
            config=self.config,
            frame=self.frame(progress),
            dtype=dtype,
            device=device,
        )

    def critical_raw_contours(
        self,
        *,
        num_points_per_lobe: int = 257,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return exact drawable polylines for the pinched zero set.

        Each polyline begins and ends at the shared critical point.  They are
        intentionally *raw* visualization data rather than admissible closed
        boundary components: their shared endpoint has zero field gradient.
        """

        count = _integer_at_least(
            num_points_per_lobe,
            name="num_points_per_lobe",
            minimum=3,
        )
        b = self.config.cassini_radius
        angle_ranges = (
            (-0.25 * math.pi, 0.25 * math.pi),
            (0.75 * math.pi, 1.25 * math.pi),
        )
        cosine = math.cos(self.config.rotation_radians)
        sine = math.sin(self.config.rotation_radians)
        rotation = np.asarray(((cosine, -sine), (sine, cosine)))
        center = np.asarray(self.config.center)
        contours = []
        for lower, upper in angle_ranges:
            angles = np.linspace(lower, upper, count, dtype=np.float64)
            radial_squared = 2.0 * b * b * np.cos(2.0 * angles)
            radii = np.sqrt(np.maximum(radial_squared, 0.0))
            local = np.column_stack(
                (radii * np.cos(angles), radii * np.sin(angles))
            )
            world = local @ rotation.T + center[None, :]
            # Avoid tiny libm-dependent endpoint offsets where cos(pi/2)
            # should be exactly zero.
            world[[0, -1], :] = center
            world.setflags(write=False)
            contours.append(world)
        return contours[0], contours[1]


class CassiniSplitSDF2D(nn.Module):
    """Torch implicit field for one frame of a Cassini split trajectory."""

    def __init__(
        self,
        *,
        config: CassiniSplitConfig,
        frame: CassiniSplitFrame,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        if not isinstance(config, CassiniSplitConfig):
            raise TypeError("config must be a CassiniSplitConfig object.")
        if not isinstance(frame, CassiniSplitFrame):
            raise TypeError("frame must be a CassiniSplitFrame object.")
        resolved_dtype = _real_floating_dtype(dtype)
        self.config = config
        self.frame = frame
        self.register_buffer(
            "center",
            torch.as_tensor(config.center, dtype=resolved_dtype, device=device),
        )
        self.register_buffer(
            "focal_half_distance",
            torch.as_tensor(
                frame.focal_half_distance,
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.register_buffer(
            "cassini_radius",
            torch.as_tensor(
                config.cassini_radius,
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.register_buffer(
            "final_focal_half_distance",
            torch.as_tensor(
                config.final_focal_half_distance,
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.register_buffer(
            "final_circle_radius",
            torch.as_tensor(
                config.final_circle_radius,
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.register_buffer(
            "circle_blend_weight",
            torch.as_tensor(
                frame.exact_circle_blend_weight,
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.register_buffer(
            "rotation_radians",
            torch.as_tensor(
                config.rotation_radians,
                dtype=resolved_dtype,
                device=device,
            ),
        )

    @property
    def topology(self) -> CassiniSplitTopology:
        return self.frame.topology

    @property
    def solver_ready(self) -> bool:
        return self.frame.solver_ready

    def require_solver_ready(self) -> None:
        self.frame.require_solver_ready()

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have a real floating-point dtype.")
        if points.device != self.center.device:
            raise ValueError(
                "points and CassiniSplitSDF2D buffers must be on the same device."
            )

        center = self.center.to(dtype=points.dtype)
        angle = self.rotation_radians.to(dtype=points.dtype)
        cosine = torch.cos(angle)
        sine = torch.sin(angle)
        relative = points - center[None, :]
        local_u = relative[:, 0] * cosine + relative[:, 1] * sine
        local_v = -relative[:, 0] * sine + relative[:, 1] * cosine

        focus = self.focal_half_distance.to(dtype=points.dtype)
        radius = self.cassini_radius.to(dtype=points.dtype)
        vertical_squared = local_v * local_v
        first_distance_squared = (local_u - focus) ** 2 + vertical_squared
        second_distance_squared = (local_u + focus) ** 2 + vertical_squared
        cassini = (
            first_distance_squared * second_distance_squared - radius**4
        ) / (4.0 * radius**3)

        final_focus = self.final_focal_half_distance.to(dtype=points.dtype)
        final_radius = self.final_circle_radius.to(dtype=points.dtype)
        left_circle = torch.sqrt(
            (local_u + final_focus) ** 2 + vertical_squared
        ) - final_radius
        right_circle = torch.sqrt(
            (local_u - final_focus) ** 2 + vertical_squared
        ) - final_radius
        exact_circle_union = torch.minimum(left_circle, right_circle)
        blend = self.circle_blend_weight.to(dtype=points.dtype)
        values = (1.0 - blend) * cassini + blend * exact_circle_union
        return values[:, None]

    def physical_geometry(self) -> dict[str, float | str | bool | None]:
        """Detached frame metadata suitable for an artifact or video label."""

        return {
            "progress": self.frame.progress,
            "stage": self.frame.stage.value,
            "topology": self.frame.topology.value,
            "solver_ready": self.frame.solver_ready,
            "expected_num_components": self.frame.expected_num_components,
            "focal_half_distance": self.frame.focal_half_distance,
            "cassini_radius": self.config.cassini_radius,
            "normalized_split_parameter": self.frame.normalized_split_parameter,
            "critical_split_parameter": self.config.critical_split_parameter,
            "exact_circle_blend_weight": self.frame.exact_circle_blend_weight,
        }

    @property
    def geometry_dict(self) -> dict[str, float | str | bool | None]:
        return self.physical_geometry()


@dataclass(frozen=True)
class CassiniSplitGeometryBuild:
    """One solver-ready fixture frame paired with its extracted geometry."""

    frame: CassiniSplitFrame
    model: CassiniSplitSDF2D
    geometry: Any

    def __post_init__(self) -> None:
        if not isinstance(self.frame, CassiniSplitFrame):
            raise TypeError("frame must be a CassiniSplitFrame object.")
        if not isinstance(self.model, CassiniSplitSDF2D):
            raise TypeError("model must be a CassiniSplitSDF2D object.")
        self.frame.require_solver_ready()
        observed = getattr(self.geometry, "num_components", None)
        if observed != self.frame.expected_num_components:
            raise ValueError(
                "Extracted component count does not match the analytic Cassini "
                f"topology: expected {self.frame.expected_num_components}, "
                f"observed {observed}."
            )


def build_cassini_split_geometry(
    trajectory: CassiniSplitTrajectory2D,
    progress: float,
    geometry_config: Any,
    *,
    dtype: torch.dtype = torch.float64,
    device: torch.device | str | None = None,
) -> CassiniSplitGeometryBuild:
    """Extract one regular split frame and retain its analytic event metadata.

    The critical frame is rejected before marching squares.  This matters
    because grid sampling followed by Fourier fitting can otherwise round a
    self-touching contour into a pair of apparently separated loops.
    """

    if not isinstance(trajectory, CassiniSplitTrajectory2D):
        raise TypeError("trajectory must be a CassiniSplitTrajectory2D object.")
    model = trajectory.model(progress, dtype=dtype, device=device)
    model.require_solver_ready()

    # Local import keeps raw-field/video use independent from the geometry
    # stack and avoids a package import cycle.
    from .geometry import build_multicomponent_ordered_sdf_geometry

    geometry = build_multicomponent_ordered_sdf_geometry(model, geometry_config)
    return CassiniSplitGeometryBuild(
        frame=model.frame,
        model=model,
        geometry=geometry,
    )


__all__ = [
    "CassiniSplitConfig",
    "CassiniSplitFrame",
    "CassiniSplitGeometryBuild",
    "CassiniSplitSDF2D",
    "CassiniSplitStage",
    "CassiniSplitTopology",
    "CassiniSplitTrajectory2D",
    "CassiniSplitTransitionError",
    "build_cassini_split_geometry",
]
