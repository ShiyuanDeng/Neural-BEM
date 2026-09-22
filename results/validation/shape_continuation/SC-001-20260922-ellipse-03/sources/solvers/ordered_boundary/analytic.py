"""Exact analytic and Fourier-series continuous parameterization producers."""

from __future__ import annotations

import numpy as np

from ._array_utils import readonly_float_array
from .parameterization import CurveProvenance2D, PeriodicParameterization2D


def circle(
    center: tuple[float, float],
    radius: float,
    *,
    component_id: str = "circle",
    name: str = "circle",
) -> PeriodicParameterization2D:
    """Counterclockwise circle with canonical phase at the positive x-axis."""

    origin = readonly_float_array(center, name="center", ndim=1)
    if origin.shape != (2,):
        raise ValueError("center must contain two coordinates.")
    value = float(radius)
    if not np.isfinite(value) or value <= 0.0:
        raise ValueError("radius must be finite and positive.")

    def evaluator(parameters: np.ndarray):
        cosine = np.cos(parameters)
        sine = np.sin(parameters)
        radial = np.stack((cosine, sine), axis=-1)
        tangent = np.stack((-sine, cosine), axis=-1)
        return origin + value * radial, value * tangent, -value * radial, -value * tangent

    return PeriodicParameterization2D(
        component_id,
        evaluator,
        name=name,
        provenance=CurveProvenance2D(source_kind="analytic"),
    )


def ellipse(
    center: tuple[float, float],
    semi_major: float,
    semi_minor: float,
    *,
    rotation: float = 0.0,
    component_id: str = "ellipse",
    name: str = "ellipse",
) -> PeriodicParameterization2D:
    """Counterclockwise rotated ellipse with an explicit smooth evaluator."""

    origin = readonly_float_array(center, name="center", ndim=1)
    if origin.shape != (2,):
        raise ValueError("center must contain two coordinates.")
    major = float(semi_major)
    minor = float(semi_minor)
    angle = float(rotation)
    if not np.isfinite(major) or not np.isfinite(minor) or major <= 0.0 or minor <= 0.0:
        raise ValueError("semi-axis lengths must be finite and positive.")
    if not np.isfinite(angle):
        raise ValueError("rotation must be finite.")
    cosine_angle, sine_angle = np.cos(angle), np.sin(angle)
    rotation_matrix = readonly_float_array(
        ((cosine_angle, -sine_angle), (sine_angle, cosine_angle)),
        name="rotation_matrix",
        ndim=2,
    )

    def rotate(values: np.ndarray) -> np.ndarray:
        return np.einsum("...d,ed->...e", values, rotation_matrix)

    def evaluator(parameters: np.ndarray):
        cosine = np.cos(parameters)
        sine = np.sin(parameters)
        local_points = np.stack((major * cosine, minor * sine), axis=-1)
        local_first = np.stack((-major * sine, minor * cosine), axis=-1)
        local_second = np.stack((-major * cosine, -minor * sine), axis=-1)
        local_third = -local_first
        return (
            origin + rotate(local_points),
            rotate(local_first),
            rotate(local_second),
            rotate(local_third),
        )

    return PeriodicParameterization2D(
        component_id,
        evaluator,
        name=name,
        provenance=CurveProvenance2D(source_kind="analytic"),
    )


def star(
    center: tuple[float, float],
    mean_radius: float,
    amplitude: float,
    lobes: int,
    *,
    rotation: float = 0.0,
    component_id: str = "star",
    name: str = "star",
) -> PeriodicParameterization2D:
    """Smooth radial star ``r(t)=r0(1+a cos(m(t-rotation)))``."""

    origin = readonly_float_array(center, name="center", ndim=1)
    if origin.shape != (2,):
        raise ValueError("center must contain two coordinates.")
    radius = float(mean_radius)
    relative_amplitude = float(amplitude)
    mode = int(lobes)
    angle = float(rotation)
    if not np.isfinite(radius) or radius <= 0.0:
        raise ValueError("mean_radius must be finite and positive.")
    if not np.isfinite(relative_amplitude) or abs(relative_amplitude) >= 1.0:
        raise ValueError("amplitude must be finite with abs(amplitude) < 1.")
    if mode < 1:
        raise ValueError("lobes must be a positive integer.")
    if not np.isfinite(angle):
        raise ValueError("rotation must be finite.")
    cosine_angle, sine_angle = np.cos(angle), np.sin(angle)
    rotation_matrix = readonly_float_array(
        ((cosine_angle, -sine_angle), (sine_angle, cosine_angle)),
        name="rotation_matrix",
        ndim=2,
    )

    def rotate(values: np.ndarray) -> np.ndarray:
        return np.einsum("...d,ed->...e", values, rotation_matrix)

    def evaluator(parameters: np.ndarray):
        radius_values = radius * (1.0 + relative_amplitude * np.cos(mode * parameters))
        radius_first = -radius * relative_amplitude * mode * np.sin(mode * parameters)
        radius_second = -radius * relative_amplitude * mode**2 * np.cos(mode * parameters)
        radius_third = radius * relative_amplitude * mode**3 * np.sin(mode * parameters)
        cosine = np.cos(parameters)
        sine = np.sin(parameters)
        radial = np.stack((cosine, sine), axis=-1)
        angular = np.stack((-sine, cosine), axis=-1)
        local_points = radius_values[..., None] * radial
        local_first = radius_first[..., None] * radial + radius_values[..., None] * angular
        local_second = (
            (radius_second - radius_values)[..., None] * radial
            + 2.0 * radius_first[..., None] * angular
        )
        local_third = (
            (radius_third - 3.0 * radius_first)[..., None] * radial
            + (3.0 * radius_second - radius_values)[..., None] * angular
        )
        return (
            origin + rotate(local_points),
            rotate(local_first),
            rotate(local_second),
            rotate(local_third),
        )

    return PeriodicParameterization2D(
        component_id,
        evaluator,
        name=name,
        provenance=CurveProvenance2D(source_kind="analytic"),
    )


def fourier_curve(
    cosine_coefficients,
    sine_coefficients=None,
    *,
    component_id: str,
    name: str = "fourier_curve",
    period: float = 2.0 * np.pi,
    parameter_origin: float = 0.0,
) -> PeriodicParameterization2D:
    """Build a continuous parameterization from real vector Fourier coefficients.

    ``cosine_coefficients[m]`` and ``sine_coefficients[m]`` are the x/y
    coefficients of mode ``m``.  Mode zero's sine coefficient must be zero.
    This is a geometry producer, not a fitting routine: future SDF extraction
    can fit coefficients independently, validate here, and then discretize to
    node-based ``PeriodicCurve2D`` geometry.
    """

    cosine = readonly_float_array(cosine_coefficients, name="cosine_coefficients", ndim=2)
    if cosine.shape[1] != 2 or cosine.shape[0] < 2:
        raise ValueError("cosine_coefficients must have shape (num_modes + 1, 2) with a nonzero mode.")
    if sine_coefficients is None:
        sine_values = np.zeros_like(cosine)
    else:
        sine_values = readonly_float_array(sine_coefficients, name="sine_coefficients", ndim=2)
        if sine_values.shape != cosine.shape:
            raise ValueError("sine_coefficients must match cosine_coefficients.")
    if not np.allclose(sine_values[0], 0.0, rtol=0.0, atol=1.0e-15):
        raise ValueError("The mode-zero sine coefficient must be zero.")
    sine = readonly_float_array(sine_values, name="sine_coefficients", ndim=2)
    period_value = float(period)
    origin_value = float(parameter_origin)
    if not np.isfinite(period_value) or period_value <= 0.0:
        raise ValueError("period must be finite and positive.")
    if not np.isfinite(origin_value):
        raise ValueError("parameter_origin must be finite.")
    modes = np.arange(cosine.shape[0], dtype=np.float64)
    angular_scale = 2.0 * np.pi / period_value

    def evaluator(parameters: np.ndarray):
        angle = angular_scale * (parameters - origin_value)
        phase = angle[..., None] * modes
        cos_phase = np.cos(phase)
        sin_phase = np.sin(phase)
        points = np.einsum("...m,md->...d", cos_phase, cosine) + np.einsum(
            "...m,md->...d", sin_phase, sine
        )
        first = angular_scale * (
            np.einsum("...m,md->...d", -sin_phase * modes, cosine)
            + np.einsum("...m,md->...d", cos_phase * modes, sine)
        )
        mode_squared = modes**2
        second = angular_scale**2 * (
            np.einsum("...m,md->...d", -cos_phase * mode_squared, cosine)
            + np.einsum("...m,md->...d", -sin_phase * mode_squared, sine)
        )
        mode_cubed = modes**3
        third = angular_scale**3 * (
            np.einsum("...m,md->...d", sin_phase * mode_cubed, cosine)
            + np.einsum("...m,md->...d", -cos_phase * mode_cubed, sine)
        )
        return points, first, second, third

    return PeriodicParameterization2D(
        component_id=component_id,
        evaluator=evaluator,
        name=name,
        period=period_value,
        parameter_origin=origin_value,
        provenance=CurveProvenance2D(source_kind="fourier"),
    )
