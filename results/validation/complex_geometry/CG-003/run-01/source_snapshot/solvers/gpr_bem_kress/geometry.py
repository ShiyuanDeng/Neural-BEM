"""Narrow adapter from :class:`PeriodicCurve2D` to a canonical Kress grid."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import numpy as np

from ordered_boundary import PeriodicCurve2D, sampled_self_intersection_count

TWO_PI = 2.0 * np.pi


def _readonly(values: np.ndarray, *, dtype=None) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True, order="C")
    result.setflags(write=False)
    return result


def _geometry_identifier(curve: PeriodicCurve2D) -> str:
    digest = hashlib.sha256()
    digest.update(curve.component_id.encode("utf-8"))
    digest.update(np.asarray([curve.period, curve.parameter_origin], dtype="<f8").tobytes())
    for values in (
        curve.parameters,
        curve.points,
        curve.first_derivatives,
        curve.second_derivatives,
    ):
        digest.update(np.ascontiguousarray(values, dtype="<f8").tobytes())
    return f"{curve.component_id}:{digest.hexdigest()[:16]}"


@dataclass(frozen=True)
class PeriodicCurveAdapter:
    """Affine-normalized view of one immutable periodic curve.

    ``PeriodicCurve2D`` permits a general native period.  Kress' standard
    logarithm is expressed on ``theta in [0, 2*pi)``.  This adapter changes
    only that coordinate: node order, cyclic phase, points, normals, and
    physical ``ds`` weights remain exactly those owned by the input curve.
    """

    curve: PeriodicCurve2D
    theta: np.ndarray = field(init=False)
    theta_step: float = field(init=False)
    theta_first_derivatives: np.ndarray = field(init=False)
    theta_second_derivatives: np.ndarray = field(init=False)
    theta_speeds: np.ndarray = field(init=False)
    geometry_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("curve must be an ordered_boundary.PeriodicCurve2D object.")
        count = self.curve.num_nodes
        if count < 8:
            raise ValueError("The ordered Kress solver requires at least 8 nodes.")
        if count % 2:
            raise ValueError("Kress product integration requires an even number of nodes.")

        native_to_theta = self.curve.period / TWO_PI
        theta = TWO_PI * (
            self.curve.parameters - self.curve.parameter_origin
        ) / self.curve.period
        expected = TWO_PI * np.arange(count, dtype=np.float64) / count
        if not np.allclose(theta, expected, rtol=0.0, atol=2.0e-13):
            raise ValueError("curve parameters do not map to the canonical endpoint-free grid.")

        theta_first = native_to_theta * self.curve.first_derivatives
        theta_second = native_to_theta**2 * self.curve.second_derivatives
        theta_speeds = native_to_theta * self.curve.speeds
        expected_weights = (TWO_PI / count) * theta_speeds
        if not np.allclose(
            expected_weights,
            self.curve.arc_length_weights,
            rtol=5.0e-13,
            atol=5.0e-15,
        ):
            raise ValueError("curve arc-length weights are inconsistent with its node derivatives.")
        if not np.all(np.isfinite(theta_speeds)) or np.any(theta_speeds <= 0.0):
            raise ValueError("curve must have finite positive speed at every Kress node.")
        intersections = sampled_self_intersection_count(self.curve.points)
        if intersections:
            raise ValueError(
                "The ordered Kress solver requires one simple component; "
                f"the sampled node polygon has {intersections} self-intersection(s)."
            )

        object.__setattr__(self, "theta", _readonly(theta, dtype=np.float64))
        object.__setattr__(self, "theta_step", TWO_PI / count)
        object.__setattr__(
            self,
            "theta_first_derivatives",
            _readonly(theta_first, dtype=np.float64),
        )
        object.__setattr__(
            self,
            "theta_second_derivatives",
            _readonly(theta_second, dtype=np.float64),
        )
        object.__setattr__(
            self,
            "theta_speeds",
            _readonly(theta_speeds, dtype=np.float64),
        )
        object.__setattr__(self, "geometry_id", _geometry_identifier(self.curve))

    @property
    def num_nodes(self) -> int:
        return self.curve.num_nodes

    @property
    def points(self) -> np.ndarray:
        return self.curve.points

    @property
    def normals(self) -> np.ndarray:
        return self.curve.normals

    @property
    def arc_length_weights(self) -> np.ndarray:
        return self.curve.arc_length_weights


def adapt_periodic_curve(curve: PeriodicCurve2D) -> PeriodicCurveAdapter:
    """Validate and expose the sole geometry seam accepted by this solver."""

    return PeriodicCurveAdapter(curve)


__all__ = ["PeriodicCurveAdapter", "adapt_periodic_curve"]
