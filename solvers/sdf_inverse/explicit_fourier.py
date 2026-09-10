"""Cartesian fallback chart for topology-event contours.

The fixed-topology LM seam needs only parameter count, vector/rebuild and a
validated boundary. Radial components remain the economical default chart.
"""
from __future__ import annotations

from dataclasses import dataclass
import operator

import numpy as np

from ordered_boundary import (
    BoundaryValidationConfig, OrderedBoundaryValidationError, fourier_curve,
    validate_periodic_parameterization,
)
from .geometry import OrderedSDFGeometryError


@dataclass(frozen=True)
class CartesianFourierCurveState:
    cosine_coefficients: np.ndarray
    sine_coefficients: np.ndarray
    component_id: str
    name: str = "cartesian_fourier_inverse_curve"
    source_identifier: str | None = None
    initial_projection_rms_m: float = 0.0
    initial_projection_maximum_m: float = 0.0

    def __post_init__(self):
        c = np.array(self.cosine_coefficients, dtype=float, copy=True)
        s = np.array(self.sine_coefficients, dtype=float, copy=True)
        if c.ndim != 2 or c.shape[1] != 2 or len(c) < 2 or c.shape != s.shape:
            raise ValueError("Cartesian coefficients require matching (K+1, 2) arrays.")
        if not np.all(np.isfinite(c)) or not np.all(np.isfinite(s)) or np.any(s[0]):
            raise ValueError("Invalid Cartesian Fourier coefficients.")
        if not isinstance(self.component_id, str) or not self.component_id.strip():
            raise ValueError("component_id must be nonempty.")
        for label in ("initial_projection_rms_m", "initial_projection_maximum_m"):
            value = float(getattr(self, label))
            if not np.isfinite(value) or value < 0.0:
                raise ValueError(f"{label} must be finite and non-negative.")
            object.__setattr__(self, label, value)
        c.setflags(write=False)
        s.setflags(write=False)
        object.__setattr__(self, "cosine_coefficients", c)
        object.__setattr__(self, "sine_coefficients", s)

    @property
    def maximum_mode(self):
        return len(self.cosine_coefficients) - 1

    @property
    def center(self):
        return self.cosine_coefficients[0]

    @property
    def mean_radius_m(self):
        p = self.parameterization().discretize(128).points
        area = .5 * np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1))
        return np.sqrt(abs(area) / np.pi)

    @property
    def parameter_count(self):
        return 4 * self.maximum_mode + 2

    @property
    def parameter_names(self):
        return tuple(f"{self.component_id}.{kind}_{k}_{axis}_m"
                     for kind, modes in (("cos", range(self.maximum_mode + 1)),
                                         ("sin", range(1, self.maximum_mode + 1)))
                     for k in modes for axis in ("x", "y"))

    def parameter_vector(self):
        return np.concatenate((self.cosine_coefficients.ravel(), self.sine_coefficients[1:].ravel()))

    def from_parameter_vector(self, vector):
        v = np.asarray(vector, dtype=float)
        if v.shape != (self.parameter_count,):
            raise ValueError("Wrong Cartesian parameter count.")
        n = self.cosine_coefficients.size
        return self._replaced(v[:n].reshape(-1, 2),
                              np.vstack((np.zeros(2), v[n:].reshape(-1, 2))))

    def _replaced(self, cosine, sine):
        return CartesianFourierCurveState(cosine, sine, self.component_id,
            name=self.name, source_identifier=self.source_identifier,
            initial_projection_rms_m=self.initial_projection_rms_m,
            initial_projection_maximum_m=self.initial_projection_maximum_m)

    @staticmethod
    def active_parameter_count(maximum_mode):
        """Stored real coefficients through ``maximum_mode``: ``4 K + 2``."""
        mode = operator.index(maximum_mode)
        if isinstance(maximum_mode, bool) or mode < 1:
            raise ValueError("maximum_mode must be a positive integer.")
        return 4 * mode + 2

    def incremented(self, coefficients, *, maximum_mode=None):
        """Return the state after one additive step on modes ``0..A``.

        The active band ``A`` may be lower than the stored bandwidth, so a
        continuation stage moves only its low-mode prefix while the state
        stays authoritative at full bandwidth.  The step is ordered
        ``c_0x, c_0y, c_1x, c_1y, ..., c_Ax, c_Ay, s_1x, s_1y, ..., s_Ax, s_Ay``,
        matching :meth:`parameter_vector` at band ``A``.
        """
        active = self.maximum_mode if maximum_mode is None else operator.index(maximum_mode)
        if isinstance(maximum_mode, bool) or active < 1:
            raise ValueError("maximum_mode must be a positive integer.")
        if active > self.maximum_mode:
            raise ValueError("maximum_mode cannot exceed the state's maximum mode.")
        values = np.asarray(coefficients, dtype=float)
        expected = self.active_parameter_count(active)
        if values.shape != (expected,) or not np.all(np.isfinite(values)):
            raise ValueError(f"coefficients must contain {expected} finite values.")
        cosine = np.array(self.cosine_coefficients, dtype=float, copy=True)
        sine = np.array(self.sine_coefficients, dtype=float, copy=True)
        cosine[: active + 1] += values[: 2 * active + 2].reshape(-1, 2)
        sine[1 : active + 1] += values[2 * active + 2 :].reshape(-1, 2)
        return self._replaced(cosine, sine)

    def parameterization(self):
        return fourier_curve(self.cosine_coefficients, self.sine_coefficients,
                             component_id=self.component_id)

    def boundary_curve(self, config):
        if min(config.num_nodes, config.validation_resolution) < 2 * self.maximum_mode + 2:
            raise OrderedSDFGeometryError("Cartesian Fourier chart is undersampled.")
        curve = self.parameterization()
        try:
            report = validate_periodic_parameterization(curve, BoundaryValidationConfig(
                num_samples_per_component=config.validation_resolution,
                fourier_bandwidth=self.maximum_mode), raise_on_error=True)
        except OrderedBoundaryValidationError as exc:
            raise OrderedSDFGeometryError(str(exc)) from exc
        if (np.any(np.asarray(report.bounding_box_min) <= config.bounds[0]) or
                np.any(np.asarray(report.bounding_box_max) >= config.bounds[1])):
            raise OrderedSDFGeometryError("Cartesian curve leaves geometry bounds.")
        return curve.discretize(config.num_nodes, require_even=True)
