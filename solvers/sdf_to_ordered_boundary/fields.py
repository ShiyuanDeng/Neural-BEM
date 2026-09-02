"""Solver-neutral implicit-field adapters and analytic benchmark fields.

The conversion pipeline deliberately needs only field values and spatial first
derivatives.  This module keeps that contract independent of the active IBIM
solvers and returns NumPy arrays at its public boundary.  The optional Torch
adapter imports Torch lazily so analytic and callable fields do not acquire a
hard neural-runtime dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np


Array = np.ndarray


@runtime_checkable
class ImplicitField2D(Protocol):
    """An implicit field whose target boundary is ``value(xy) == 0``.

    Implementations accept physical coordinates in ``(x, y)`` order with
    shape ``(..., 2)``.  Values have shape ``(...)`` and gradients have shape
    ``(..., 2)``.  The front end does not assume that the field is a calibrated
    signed-distance function.
    """

    def value(self, xy: Array) -> Array:
        """Evaluate the scalar field."""

    def gradient(self, xy: Array) -> Array:
        """Evaluate the spatial gradient in physical ``(x, y)`` order."""


def _points_array(xy: Any) -> Array:
    if np.iscomplexobj(xy):
        raise ValueError("xy must be real-valued.")
    points = np.asarray(xy, dtype=np.float64)
    if points.ndim < 1 or points.shape[-1] != 2:
        raise ValueError("xy must have shape (..., 2).")
    if not np.all(np.isfinite(points)):
        raise ValueError("xy must contain only finite coordinates.")
    return points


def _field_values(values: Any, point_shape: tuple[int, ...]) -> Array:
    if np.iscomplexobj(values):
        raise ValueError("Field values must be real-valued.")
    result = np.asarray(values, dtype=np.float64)
    if result.shape == point_shape + (1,):
        result = result[..., 0]
    if result.shape != point_shape:
        raise ValueError(
            f"Field values must have shape {point_shape}; received {result.shape}."
        )
    if not np.all(np.isfinite(result)):
        raise ValueError("Field values must be finite.")
    return result


def _field_gradients(values: Any, point_shape: tuple[int, ...]) -> Array:
    if np.iscomplexobj(values):
        raise ValueError("Field gradients must be real-valued.")
    result = np.asarray(values, dtype=np.float64)
    expected = point_shape + (2,)
    if result.shape != expected:
        raise ValueError(
            f"Field gradients must have shape {expected}; received {result.shape}."
        )
    if not np.all(np.isfinite(result)):
        raise ValueError("Field gradients must be finite.")
    return result


@dataclass(frozen=True)
class CallableImplicitField2D:
    """Adapt NumPy-compatible value and gradient callables to the field contract."""

    value_function: Callable[[Array], Any]
    gradient_function: Callable[[Array], Any]
    name: str = "callable_implicit_field"
    is_signed_distance: bool = False
    sign_convention: str = "negative_inside"

    def __post_init__(self) -> None:
        if not callable(self.value_function):
            raise TypeError("value_function must be callable.")
        if not callable(self.gradient_function):
            raise TypeError("gradient_function must be callable.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.is_signed_distance, (bool, np.bool_)):
            raise TypeError("is_signed_distance must be boolean.")
        if self.sign_convention not in {"negative_inside", "positive_inside", "unspecified"}:
            raise ValueError(
                "sign_convention must be 'negative_inside', 'positive_inside', or 'unspecified'."
            )
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "is_signed_distance", bool(self.is_signed_distance))

    def value(self, xy: Array) -> Array:
        points = _points_array(xy)
        return _field_values(self.value_function(points), points.shape[:-1])

    def gradient(self, xy: Array) -> Array:
        points = _points_array(xy)
        return _field_gradients(self.gradient_function(points), points.shape[:-1])


@dataclass(frozen=True)
class TorchImplicitField2D:
    """Lazily adapt a Torch model to :class:`ImplicitField2D`.

    ``model`` is evaluated on a flattened ``(num_points, 2)`` tensor.  If no
    ``gradient_function`` is supplied, a model method named
    ``spatial_gradient`` is used when present; otherwise the spatial gradient
    is obtained with ``torch.autograd.grad``.  Torch is imported only when the
    adapter is evaluated.
    """

    model: Any
    gradient_function: Callable[[Any], Any] | None = None
    device: Any = None
    dtype: Any = None
    name: str = "torch_implicit_field"
    is_signed_distance: bool = False
    sign_convention: str = "negative_inside"

    def __post_init__(self) -> None:
        if not callable(self.model):
            raise TypeError("model must be callable.")
        if self.gradient_function is not None and not callable(self.gradient_function):
            raise TypeError("gradient_function must be callable when supplied.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string.")
        if not isinstance(self.is_signed_distance, (bool, np.bool_)):
            raise TypeError("is_signed_distance must be boolean.")
        if self.sign_convention not in {"negative_inside", "positive_inside", "unspecified"}:
            raise ValueError(
                "sign_convention must be 'negative_inside', 'positive_inside', or 'unspecified'."
            )
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "is_signed_distance", bool(self.is_signed_distance))

    @staticmethod
    def _torch_module():
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - exercised only without optional dependency
            raise ImportError(
                "TorchImplicitField2D requires the optional 'torch' dependency."
            ) from exc
        return torch

    def _tensor_options(self) -> tuple[Any, Any]:
        device = self.device
        dtype = self.dtype
        if device is not None and dtype is not None:
            return device, dtype
        candidates = ()
        parameters = getattr(self.model, "parameters", None)
        if callable(parameters):
            candidates = parameters()
        try:
            reference = next(iter(candidates))
        except StopIteration:
            reference = None
        if reference is None:
            buffers = getattr(self.model, "buffers", None)
            if callable(buffers):
                try:
                    reference = next(iter(buffers()))
                except StopIteration:
                    reference = None
        if reference is not None:
            if device is None:
                device = reference.device
            if dtype is None:
                dtype = reference.dtype
        return device, dtype

    def _as_tensor(self, points: Array, *, requires_grad: bool = False):
        torch = self._torch_module()
        device, dtype = self._tensor_options()
        kwargs = {}
        if device is not None:
            kwargs["device"] = device
        if dtype is not None:
            kwargs["dtype"] = dtype
        tensor = torch.as_tensor(points.reshape(-1, 2), **kwargs)
        if not tensor.is_floating_point():
            tensor = tensor.to(dtype=torch.get_default_dtype())
        if requires_grad:
            tensor = tensor.detach().requires_grad_(True)
        return tensor

    @staticmethod
    def _flat_tensor_values(values: Any, count: int):
        if getattr(values, "numel", lambda: -1)() != count:
            shape = tuple(getattr(values, "shape", ()))
            raise ValueError(
                f"Torch model must return one value per point; received shape {shape}."
            )
        return values.reshape(count)

    def value(self, xy: Array) -> Array:
        torch = self._torch_module()
        points = _points_array(xy)
        tensor = self._as_tensor(points)
        with torch.no_grad():
            values = self._flat_tensor_values(self.model(tensor), tensor.shape[0])
        return _field_values(values.detach().cpu().numpy(), points.shape[:-1])

    def gradient(self, xy: Array) -> Array:
        torch = self._torch_module()
        points = _points_array(xy)
        tensor = self._as_tensor(points, requires_grad=True)
        with torch.enable_grad():
            if self.gradient_function is not None:
                gradients = self.gradient_function(tensor)
            elif callable(getattr(self.model, "spatial_gradient", None)):
                gradients = self.model.spatial_gradient(tensor)
            else:
                values = self._flat_tensor_values(self.model(tensor), tensor.shape[0])
                gradients = torch.autograd.grad(
                    values.sum(), tensor, create_graph=False, retain_graph=False
                )[0]
        return _field_gradients(
            gradients.detach().cpu().numpy().reshape(points.shape),
            points.shape[:-1],
        )


@dataclass(frozen=True)
class FieldEvaluationCounts:
    """Number of vectorized calls and physical point evaluations."""

    value_calls: int
    value_points: int
    gradient_calls: int
    gradient_points: int


@dataclass
class CountedImplicitField2D:
    """Transparent field wrapper that records calls and evaluated points."""

    field: ImplicitField2D
    value_calls: int = 0
    value_points: int = 0
    gradient_calls: int = 0
    gradient_points: int = 0

    @property
    def name(self) -> str:
        return str(getattr(self.field, "name", type(self.field).__name__))

    @property
    def is_signed_distance(self) -> bool:
        return bool(getattr(self.field, "is_signed_distance", False))

    @property
    def sign_convention(self) -> str:
        return str(getattr(self.field, "sign_convention", "unspecified"))

    @property
    def counts(self) -> FieldEvaluationCounts:
        return FieldEvaluationCounts(
            value_calls=self.value_calls,
            value_points=self.value_points,
            gradient_calls=self.gradient_calls,
            gradient_points=self.gradient_points,
        )

    def reset_counts(self) -> None:
        self.value_calls = 0
        self.value_points = 0
        self.gradient_calls = 0
        self.gradient_points = 0

    def value(self, xy: Array) -> Array:
        points = _points_array(xy)
        self.value_calls += 1
        self.value_points += int(points.reshape(-1, 2).shape[0])
        return _field_values(self.field.value(points), points.shape[:-1])

    def gradient(self, xy: Array) -> Array:
        points = _points_array(xy)
        self.gradient_calls += 1
        self.gradient_points += int(points.reshape(-1, 2).shape[0])
        return _field_gradients(self.field.gradient(points), points.shape[:-1])


def _center_tuple(center: Any) -> tuple[float, float]:
    values = _points_array(center)
    if values.shape != (2,):
        raise ValueError("center must contain exactly two coordinates.")
    return float(values[0]), float(values[1])


@dataclass(frozen=True)
class CircleSDF:
    """Exact Euclidean signed-distance field of a circle."""

    center: tuple[float, float]
    radius: float
    name: str = "circle_sdf"
    is_signed_distance: bool = True
    sign_convention: str = "negative_inside"

    def __post_init__(self) -> None:
        center = _center_tuple(self.center)
        radius = float(self.radius)
        if not np.isfinite(radius) or radius <= 0.0:
            raise ValueError("radius must be finite and positive.")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "radius", radius)

    def value(self, xy: Array) -> Array:
        points = _points_array(xy)
        return np.linalg.norm(points - np.asarray(self.center), axis=-1) - self.radius

    def gradient(self, xy: Array) -> Array:
        points = _points_array(xy)
        relative = points - np.asarray(self.center)
        radii = np.linalg.norm(relative, axis=-1)
        gradients = np.zeros_like(relative)
        np.divide(relative, radii[..., None], out=gradients, where=radii[..., None] > 0.0)
        return gradients

    def reference_parameterization(self, *, component_id: str = "circle"):
        from ordered_boundary import circle

        return circle(self.center, self.radius, component_id=component_id, name=self.name)


@dataclass(frozen=True)
class EllipseLevelSet:
    """Smooth dimensionless ellipse level set, explicitly not a true SDF."""

    center: tuple[float, float]
    semi_major: float
    semi_minor: float
    rotation: float = 0.0
    name: str = "ellipse_level_set"
    is_signed_distance: bool = False
    sign_convention: str = "negative_inside"

    def __post_init__(self) -> None:
        center = _center_tuple(self.center)
        major = float(self.semi_major)
        minor = float(self.semi_minor)
        rotation = float(self.rotation)
        if not np.isfinite(major) or major <= 0.0:
            raise ValueError("semi_major must be finite and positive.")
        if not np.isfinite(minor) or minor <= 0.0:
            raise ValueError("semi_minor must be finite and positive.")
        if not np.isfinite(rotation):
            raise ValueError("rotation must be finite.")
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "semi_major", major)
        object.__setattr__(self, "semi_minor", minor)
        object.__setattr__(self, "rotation", rotation)

    @property
    def _rotation_matrix(self) -> Array:
        cosine = np.cos(self.rotation)
        sine = np.sin(self.rotation)
        return np.asarray(((cosine, -sine), (sine, cosine)), dtype=np.float64)

    def _local_coordinates(self, points: Array) -> Array:
        return (points - np.asarray(self.center)) @ self._rotation_matrix

    def value(self, xy: Array) -> Array:
        points = _points_array(xy)
        local = self._local_coordinates(points)
        scaled = local / np.asarray((self.semi_major, self.semi_minor))
        return np.linalg.norm(scaled, axis=-1) - 1.0

    def gradient(self, xy: Array) -> Array:
        points = _points_array(xy)
        local = self._local_coordinates(points)
        scaled = local / np.asarray((self.semi_major, self.semi_minor))
        radial = np.linalg.norm(scaled, axis=-1)
        local_gradient = np.zeros_like(local)
        numerator = local / np.asarray((self.semi_major**2, self.semi_minor**2))
        np.divide(
            numerator,
            radial[..., None],
            out=local_gradient,
            where=radial[..., None] > 0.0,
        )
        return local_gradient @ self._rotation_matrix.T

    def reference_parameterization(self, *, component_id: str = "ellipse"):
        from ordered_boundary import ellipse

        return ellipse(
            self.center,
            self.semi_major,
            self.semi_minor,
            rotation=self.rotation,
            component_id=component_id,
            name=self.name,
        )


@dataclass(frozen=True)
class RadialFourierLevelSet:
    """Generic radial Fourier level set ``rho - r(theta)``.

    The coefficient arrays store modes ``1, ..., K``.  The field has distance
    units but is not generally a Euclidean signed-distance function.  Positivity
    of the supplied radius is checked densely at construction.
    """

    center: tuple[float, float]
    mean_radius: float
    cosine_coefficients: Array
    sine_coefficients: Array | None = None
    rotation: float = 0.0
    name: str = "radial_fourier_level_set"
    is_signed_distance: bool = False
    sign_convention: str = "negative_inside"

    def __post_init__(self) -> None:
        center = _center_tuple(self.center)
        mean_radius = float(self.mean_radius)
        rotation = float(self.rotation)
        cosine = np.asarray(self.cosine_coefficients, dtype=np.float64)
        if cosine.ndim != 1:
            raise ValueError("cosine_coefficients must be one-dimensional.")
        if self.sine_coefficients is None:
            sine = np.zeros_like(cosine)
        else:
            sine = np.asarray(self.sine_coefficients, dtype=np.float64)
        if sine.shape != cosine.shape:
            raise ValueError("sine_coefficients must match cosine_coefficients.")
        if not np.isfinite(mean_radius) or mean_radius <= 0.0:
            raise ValueError("mean_radius must be finite and positive.")
        if not np.isfinite(rotation):
            raise ValueError("rotation must be finite.")
        if not np.all(np.isfinite(cosine)) or not np.all(np.isfinite(sine)):
            raise ValueError("Fourier coefficients must be finite.")
        cosine = cosine.copy()
        sine = sine.copy()
        cosine.setflags(write=False)
        sine.setflags(write=False)
        object.__setattr__(self, "center", center)
        object.__setattr__(self, "mean_radius", mean_radius)
        object.__setattr__(self, "rotation", rotation)
        object.__setattr__(self, "cosine_coefficients", cosine)
        object.__setattr__(self, "sine_coefficients", sine)
        probe_count = max(4096, 64 * max(1, cosine.size))
        probe = 2.0 * np.pi * np.arange(probe_count, dtype=np.float64) / probe_count
        if float(np.min(self._radius_derivatives(probe)[0])) <= 0.0:
            raise ValueError("The radial Fourier representation must remain positive.")

    @classmethod
    def star(
        cls,
        center: tuple[float, float],
        mean_radius: float,
        amplitude: float,
        lobes: int,
        *,
        rotation: float = 0.0,
        name: str = "radial_fourier_star_level_set",
    ) -> "RadialFourierLevelSet":
        mode = int(lobes)
        relative_amplitude = float(amplitude)
        if mode < 1:
            raise ValueError("lobes must be a positive integer.")
        if not np.isfinite(relative_amplitude) or abs(relative_amplitude) >= 1.0:
            raise ValueError("amplitude must be finite with abs(amplitude) < 1.")
        cosine = np.zeros(mode, dtype=np.float64)
        cosine[mode - 1] = float(mean_radius) * relative_amplitude
        return cls(center, mean_radius, cosine, rotation=rotation, name=name)

    @property
    def bandwidth(self) -> int:
        return int(self.cosine_coefficients.size)

    def _radius_derivatives(self, angle: Array) -> tuple[Array, Array, Array, Array]:
        values = np.asarray(angle, dtype=np.float64)
        modes = np.arange(1, self.bandwidth + 1, dtype=np.float64)
        phase = values[..., None] * modes
        cosine_phase = np.cos(phase)
        sine_phase = np.sin(phase)
        cosine = self.cosine_coefficients
        sine = self.sine_coefficients
        radius = self.mean_radius + np.einsum("...k,k->...", cosine_phase, cosine) + np.einsum(
            "...k,k->...", sine_phase, sine
        )
        first = np.einsum("...k,k->...", -sine_phase * modes, cosine) + np.einsum(
            "...k,k->...", cosine_phase * modes, sine
        )
        squared = modes**2
        second = np.einsum("...k,k->...", -cosine_phase * squared, cosine) + np.einsum(
            "...k,k->...", -sine_phase * squared, sine
        )
        cubed = modes**3
        third = np.einsum("...k,k->...", sine_phase * cubed, cosine) + np.einsum(
            "...k,k->...", -cosine_phase * cubed, sine
        )
        return radius, first, second, third

    def value(self, xy: Array) -> Array:
        points = _points_array(xy)
        relative = points - np.asarray(self.center)
        radii = np.linalg.norm(relative, axis=-1)
        local_angle = np.arctan2(relative[..., 1], relative[..., 0]) - self.rotation
        boundary_radius = self._radius_derivatives(local_angle)[0]
        return radii - boundary_radius

    def gradient(self, xy: Array) -> Array:
        points = _points_array(xy)
        relative = points - np.asarray(self.center)
        radii = np.linalg.norm(relative, axis=-1)
        angle = np.arctan2(relative[..., 1], relative[..., 0])
        local_angle = angle - self.rotation
        radial_first = self._radius_derivatives(local_angle)[1]
        radial_unit = np.stack((np.cos(angle), np.sin(angle)), axis=-1)
        angular_unit = np.stack((-np.sin(angle), np.cos(angle)), axis=-1)
        angular_gradient = np.zeros_like(angular_unit)
        np.divide(
            angular_unit,
            radii[..., None],
            out=angular_gradient,
            where=radii[..., None] > 0.0,
        )
        gradients = radial_unit - radial_first[..., None] * angular_gradient
        return np.where((radii > 0.0)[..., None], gradients, 0.0)

    def reference_parameterization(self, *, component_id: str = "radial_fourier"):
        from ordered_boundary import CurveProvenance2D, PeriodicParameterization2D

        field = self

        def evaluator(parameters: Array):
            radius, first, second, third = field._radius_derivatives(parameters)
            world_angle = parameters + field.rotation
            cosine = np.cos(world_angle)
            sine = np.sin(world_angle)
            radial = np.stack((cosine, sine), axis=-1)
            angular = np.stack((-sine, cosine), axis=-1)
            points = np.asarray(field.center) + radius[..., None] * radial
            d1 = first[..., None] * radial + radius[..., None] * angular
            d2 = (second - radius)[..., None] * radial + 2.0 * first[..., None] * angular
            d3 = (third - 3.0 * first)[..., None] * radial + (
                3.0 * second - radius
            )[..., None] * angular
            return points, d1, d2, d3

        return PeriodicParameterization2D(
            component_id=component_id,
            evaluator=evaluator,
            name=self.name,
            provenance=CurveProvenance2D(source_kind="analytic_implicit_reference"),
        )


__all__ = [
    "CallableImplicitField2D",
    "CircleSDF",
    "CountedImplicitField2D",
    "EllipseLevelSet",
    "FieldEvaluationCounts",
    "ImplicitField2D",
    "RadialFourierLevelSet",
    "TorchImplicitField2D",
]
