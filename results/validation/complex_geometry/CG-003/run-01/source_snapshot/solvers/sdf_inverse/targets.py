"""Analytic target shapes for the solver-neutral inverse comparison.

A target shape owns three consistent views of one geometry: the periodic
parameterization the independent Nystrom oracle integrates, the Torch implicit
field the extraction pipeline consumes, and an exact point-to-boundary
distance used to report geometry error.  Keeping them in one validated object
is what lets the driver claim that the observations, the true-boundary control
forward, and the reported distances all describe the same curve.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
from typing import Any, Callable

import numpy as np

from .models import StarLevelSet2D


# ``nystrom_ref.build_curve`` consumes exactly this signature.
Parameterization = Callable[[np.ndarray], tuple[np.ndarray, np.ndarray]]

# One over the golden ratio, the fixed contraction factor of the bracketed
# distance refinement below.
_INVERSE_GOLDEN_RATIO = 2.0 / (1.0 + math.sqrt(5.0))


def _finite_scalar(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or np.iscomplexobj(value):
        raise TypeError(f"{name} must be a real number, not bool or complex.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite.")
    return result


def _integer_at_least(value: Any, *, name: str, minimum: int) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")
    return int(result)


def _points_array(values: Any, *, name: str) -> np.ndarray:
    if np.iscomplexobj(values):
        raise ValueError(f"{name} must be real-valued.")
    points = np.asarray(values, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or points.shape[0] < 1:
        raise ValueError(f"{name} must have non-empty shape (num_points, 2).")
    if not np.all(np.isfinite(points)):
        raise ValueError(f"{name} must contain only finite coordinates.")
    return points


@dataclass(frozen=True)
class StarShape:
    """The smooth radial star ``r(t) = R (1 + a cos(m (t - phi)))``.

    With ``rotation_radians == 0`` this is bit-for-bit the curve
    ``nystrom_ref.star_parameterization`` produces, which is the target the
    checked forward comparison study already uses.
    """

    center: tuple[float, float]
    mean_radius: float
    amplitude: float
    lobes: int
    rotation_radians: float = 0.0

    def __post_init__(self) -> None:
        center = np.asarray(self.center, dtype=np.float64)
        if center.shape != (2,) or not np.all(np.isfinite(center)):
            raise ValueError("center must contain exactly two finite coordinates.")
        mean_radius = _finite_scalar(self.mean_radius, name="mean_radius")
        amplitude = _finite_scalar(self.amplitude, name="amplitude")
        rotation = _finite_scalar(self.rotation_radians, name="rotation_radians")
        lobes = _integer_at_least(self.lobes, name="lobes", minimum=2)
        if mean_radius <= 0.0:
            raise ValueError("mean_radius must be positive.")
        if abs(amplitude) >= 1.0:
            raise ValueError("amplitude must satisfy abs(amplitude) < 1.")
        object.__setattr__(self, "center", (float(center[0]), float(center[1])))
        object.__setattr__(self, "mean_radius", mean_radius)
        object.__setattr__(self, "amplitude", amplitude)
        object.__setattr__(self, "rotation_radians", rotation)
        object.__setattr__(self, "lobes", lobes)

    @property
    def maximum_radius(self) -> float:
        """Largest boundary radius, used to size extraction boxes."""

        return self.mean_radius * (1.0 + abs(self.amplitude))

    @property
    def minimum_radius(self) -> float:
        """Smallest boundary radius, always positive."""

        return self.mean_radius * (1.0 - abs(self.amplitude))

    @property
    def symmetry_period_radians(self) -> float:
        """Rotation periodicity ``2 pi / lobes`` of this star."""

        return 2.0 * math.pi / self.lobes

    def radius(self, parameters: np.ndarray) -> np.ndarray:
        """Boundary radius ``r(t)``."""

        angle = np.asarray(parameters, dtype=np.float64)
        return self.mean_radius * (
            1.0 + self.amplitude * np.cos(self.lobes * (angle - self.rotation_radians))
        )

    def boundary(self, parameters: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(points, tangents)`` at the given curve parameters."""

        angle = np.asarray(parameters, dtype=np.float64)
        radius = self.radius(angle)
        radius_prime = (
            -self.mean_radius
            * self.amplitude
            * self.lobes
            * np.sin(self.lobes * (angle - self.rotation_radians))
        )
        cosine = np.cos(angle)
        sine = np.sin(angle)
        radial = np.stack((cosine, sine), axis=-1)
        angular = np.stack((-sine, cosine), axis=-1)
        origin = np.asarray(self.center, dtype=np.float64)
        points = origin + radius[..., None] * radial
        tangents = radius_prime[..., None] * radial + radius[..., None] * angular
        return points, tangents

    def parameterization(self) -> Parameterization:
        """Return the callable the Nystrom oracle integrates."""

        return self.boundary

    def sample_boundary(self, num_samples: int = 2048) -> np.ndarray:
        """Return a dense open polyline of exact boundary points for plots."""

        count = _integer_at_least(num_samples, name="num_samples", minimum=8)
        angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
        return self.boundary(angles)[0]

    def implicit_model(self, *, dtype: Any = None, device: Any = None) -> StarLevelSet2D:
        """Return the exact Torch implicit field of this same curve."""

        import torch

        return StarLevelSet2D(
            center=self.center,
            mean_radius=self.mean_radius,
            amplitude=self.amplitude,
            lobes=self.lobes,
            rotation_radians=self.rotation_radians,
            dtype=torch.float64 if dtype is None else dtype,
            device="cpu" if device is None else device,
        )

    def distance_to_boundary(
        self,
        points: Any,
        *,
        coarse_samples: int = 4096,
        refinements: int = 48,
    ) -> np.ndarray:
        """Exact minimum Euclidean distance from each point to this curve.

        A coarse periodic scan brackets each minimum, then a golden-section
        search contracts that bracket.  Unlike a symmetric point-cloud
        Hausdorff distance against a sampled polygon, this does not report the
        finite node spacing of a discretised curve as geometry error.
        """

        query = _points_array(points, name="points")
        samples = _integer_at_least(coarse_samples, name="coarse_samples", minimum=64)
        iterations = _integer_at_least(refinements, name="refinements", minimum=1)
        step = 2.0 * np.pi / samples
        scan_parameters = step * np.arange(samples, dtype=np.float64)
        scan_points = self.boundary(scan_parameters)[0]

        distances = np.empty(query.shape[0], dtype=np.float64)
        block = 512
        for start in range(0, query.shape[0], block):
            chunk = query[start : start + block]
            squared = np.sum(
                (chunk[:, None, :] - scan_points[None, :, :]) ** 2, axis=2
            )
            nearest = np.argmin(squared, axis=1)
            # The scan is periodic, so the bracket may wrap; unwrapped
            # parameters stay valid because every trigonometric term is
            # 2 pi periodic.
            lower = step * (nearest - 1).astype(np.float64)
            upper = step * (nearest + 1).astype(np.float64)
            distances[start : start + chunk.shape[0]] = self._golden_section_distance(
                chunk, lower, upper, iterations=iterations
            )
        return distances

    def _distance_at(self, points: np.ndarray, parameters: np.ndarray) -> np.ndarray:
        boundary_points = self.boundary(parameters)[0]
        return np.linalg.norm(points - boundary_points, axis=1)

    def _golden_section_distance(
        self,
        points: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
        *,
        iterations: int,
    ) -> np.ndarray:
        left = np.array(lower, dtype=np.float64, copy=True)
        right = np.array(upper, dtype=np.float64, copy=True)
        first = right - _INVERSE_GOLDEN_RATIO * (right - left)
        second = left + _INVERSE_GOLDEN_RATIO * (right - left)
        first_value = self._distance_at(points, first)
        second_value = self._distance_at(points, second)
        for _ in range(iterations):
            # Keep the half-interval holding the smaller probe.  The surviving
            # probe becomes one of the next pair, so each sweep costs exactly
            # one distance evaluation per point.
            keep_left_half = first_value < second_value
            left = np.where(keep_left_half, left, first)
            right = np.where(keep_left_half, second, right)
            surviving = np.where(keep_left_half, first, second)
            surviving_value = np.where(keep_left_half, first_value, second_value)
            span = right - left
            probe = np.where(
                keep_left_half,
                right - _INVERSE_GOLDEN_RATIO * span,
                left + _INVERSE_GOLDEN_RATIO * span,
            )
            probe_value = self._distance_at(points, probe)
            first = np.where(keep_left_half, probe, surviving)
            first_value = np.where(keep_left_half, probe_value, surviving_value)
            second = np.where(keep_left_half, surviving, probe)
            second_value = np.where(keep_left_half, surviving_value, probe_value)
        return np.minimum(first_value, second_value)

    def parameter_dict(self) -> dict[str, float]:
        """Return a JSON-ready description of the target geometry."""

        return {
            "center_x_m": self.center[0],
            "center_y_m": self.center[1],
            "mean_radius_m": self.mean_radius,
            "amplitude": self.amplitude,
            "lobes": float(self.lobes),
            "rotation_radians": self.rotation_radians,
            "minimum_radius_m": self.minimum_radius,
            "maximum_radius_m": self.maximum_radius,
        }


__all__ = ["Parameterization", "StarShape"]
