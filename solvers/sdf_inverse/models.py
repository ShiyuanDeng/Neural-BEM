"""Small, auditable implicit models for solver-comparison inversions.

The finite-difference inverse in :mod:`sdf_inverse.optimization` is intended
for low-dimensional controls.  :class:`TorchParameterController` therefore
places an explicit limit on the number of scalar controls instead of making a
large neural network look computationally tractable by accident.  Models need
a regular negative-inside zero contour; their values need not be distances.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
from typing import Sequence

import numpy as np
import torch
from torch import nn


def _real_floating_dtype(dtype: torch.dtype) -> torch.dtype:
    if dtype not in {
        torch.float16,
        torch.bfloat16,
        torch.float32,
        torch.float64,
    }:
        raise TypeError("dtype must be a real floating-point torch dtype.")
    return dtype


class CircleSDF2D(nn.Module):
    """Trainable exact signed distance to one circle.

    The radius is stored in logarithmic coordinates so every finite parameter
    vector represents a positive radius.  The sign convention is negative in
    the interior, matching the implicit geometry front ends in this repository.
    """

    def __init__(
        self,
        *,
        center: tuple[float, float] = (0.0, 0.0),
        radius: float = 1.0,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        resolved_dtype = _real_floating_dtype(dtype)
        center_values = np.asarray(center, dtype=np.float64)
        radius_value = float(radius)
        if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
            raise ValueError("center must contain exactly two finite coordinates.")
        if not math.isfinite(radius_value) or radius_value <= 0.0:
            raise ValueError("radius must be finite and positive.")
        self.center = nn.Parameter(
            torch.as_tensor(center_values, dtype=resolved_dtype, device=device)
        )
        self.log_radius = nn.Parameter(
            torch.tensor(
                math.log(radius_value),
                dtype=resolved_dtype,
                device=device,
            )
        )

    @property
    def radius(self) -> torch.Tensor:
        """Positive differentiable radius tensor."""

        return torch.exp(self.log_radius)

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have a floating-point dtype.")
        if points.device != self.center.device:
            raise ValueError(
                "points and CircleSDF2D parameters must be on the same device."
            )
        delta = points - self.center.to(dtype=points.dtype)[None, :]
        radius = self.radius.to(dtype=points.dtype)
        return torch.linalg.norm(delta, dim=1, keepdim=True) - radius

    def physical_geometry(self) -> dict[str, float]:
        """Return detached geometry in physical coordinates for logs/artifacts."""

        center = self.center.detach().cpu().to(dtype=torch.float64).numpy()
        return {
            "center_x": float(center[0]),
            "center_y": float(center[1]),
            "radius": float(self.radius.detach().cpu().to(dtype=torch.float64)),
        }

    @property
    def geometry_dict(self) -> dict[str, float]:
        """Property alias for user-facing inspection."""

        return self.physical_geometry()


class EllipseLevelSet2D(nn.Module):
    """Trainable rotated ellipse represented by a non-distance level set.

    The zero contour is an ellipse, but the returned value is the dimensionless
    quadratic ``(x'/a)^2 + (y'/b)^2 - 1``.  This deliberately exercises the
    implicit-field pipeline without relying on signed-distance magnitudes.
    Rotation is fixed because it becomes unidentifiable when the recovered
    semi-axes meet at the circular target.
    """

    claims_signed_distance = False

    def __init__(
        self,
        *,
        center: tuple[float, float] = (0.0, 0.0),
        semi_axes: tuple[float, float] = (1.0, 0.75),
        rotation_radians: float = 0.0,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        resolved_dtype = _real_floating_dtype(dtype)
        center_values = np.asarray(center, dtype=np.float64)
        axes_values = np.asarray(semi_axes, dtype=np.float64)
        angle = float(rotation_radians)
        if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
            raise ValueError("center must contain exactly two finite coordinates.")
        if (
            axes_values.shape != (2,)
            or not np.all(np.isfinite(axes_values))
            or np.any(axes_values <= 0.0)
        ):
            raise ValueError("semi_axes must contain exactly two finite positive values.")
        if not math.isfinite(angle):
            raise ValueError("rotation_radians must be finite.")
        self.center = nn.Parameter(
            torch.as_tensor(center_values, dtype=resolved_dtype, device=device)
        )
        self.log_semi_axes = nn.Parameter(
            torch.log(torch.as_tensor(axes_values, dtype=resolved_dtype, device=device))
        )
        cosine = math.cos(angle)
        sine = math.sin(angle)
        self.register_buffer(
            "rotation_matrix",
            torch.tensor(
                ((cosine, -sine), (sine, cosine)),
                dtype=resolved_dtype,
                device=device,
            ),
        )
        self.rotation_radians = angle

    @property
    def semi_axes(self) -> torch.Tensor:
        return torch.exp(self.log_semi_axes)

    @property
    def radius(self) -> torch.Tensor:
        """Geometric-mean radius, equal to the radius at the circle limit."""

        return torch.sqrt(torch.prod(self.semi_axes))

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have a floating-point dtype.")
        if points.device != self.center.device:
            raise ValueError(
                "points and EllipseLevelSet2D parameters must be on the same device."
            )
        delta = points - self.center.to(dtype=points.dtype)[None, :]
        local = delta @ self.rotation_matrix.to(dtype=points.dtype)
        normalized = local / self.semi_axes.to(dtype=points.dtype)[None, :]
        return torch.sum(normalized**2, dim=1, keepdim=True) - 1.0

    def physical_geometry(self) -> dict[str, float]:
        center = self.center.detach().cpu().to(dtype=torch.float64).numpy()
        axes = self.semi_axes.detach().cpu().to(dtype=torch.float64).numpy()
        return {
            "center_x": float(center[0]),
            "center_y": float(center[1]),
            "radius": float(math.sqrt(float(axes[0] * axes[1]))),
            "semi_axis_x": float(axes[0]),
            "semi_axis_y": float(axes[1]),
            "axis_ratio": float(max(axes) / min(axes)),
            "rotation_radians": self.rotation_radians,
        }

    def initialization_metadata(self) -> dict[str, object]:
        return {
            "kind": "rotated_quadratic_ellipse",
            "claims_signed_distance": False,
            "fixed_rotation_radians": self.rotation_radians,
        }


class RadialRandomFeatureImplicit2D(nn.Module):
    """Topology-constrained random-feature neural implicit field.

    A fixed seeded tanh feature layer acts on the polar direction and a small
    trainable output head perturbs a circle's radius.  The field is generally
    not a signed distance, while the bounded radial envelope keeps exactly one
    star-shaped zero contour.  This is an honest small neural stress case for
    parameter finite differences; it is not full-SIREN training.
    """

    claims_signed_distance = False

    def __init__(
        self,
        *,
        center: tuple[float, float] = (0.0, 0.0),
        radius: float = 1.0,
        hidden_features: int = 4,
        random_seed: int = 17,
        relative_amplitude: float = 0.15,
        feature_sharpness: float = 3.0,
        field_scale: float = 2.0,
        output_weights: Sequence[float] | np.ndarray | None = None,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        resolved_dtype = _real_floating_dtype(dtype)
        center_values = np.asarray(center, dtype=np.float64)
        radius_value = float(radius)
        hidden_count = _positive_integer(hidden_features, name="hidden_features")
        if hidden_count < 2:
            raise ValueError("hidden_features must be at least two.")
        if isinstance(random_seed, (bool, np.bool_)):
            raise TypeError("random_seed must be an integer, not bool.")
        try:
            seed = int(operator.index(random_seed))
        except TypeError as exc:
            raise TypeError("random_seed must be an integer.") from exc
        amplitude = float(relative_amplitude)
        sharpness = float(feature_sharpness)
        scale = float(field_scale)
        if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
            raise ValueError("center must contain exactly two finite coordinates.")
        if not math.isfinite(radius_value) or radius_value <= 0.0:
            raise ValueError("radius must be finite and positive.")
        if not math.isfinite(amplitude) or amplitude <= 0.0 or amplitude >= 0.5:
            raise ValueError("relative_amplitude must lie in the interval (0, 0.5).")
        if not math.isfinite(sharpness) or sharpness <= 0.0:
            raise ValueError("feature_sharpness must be finite and positive.")
        if not math.isfinite(scale) or scale <= 0.0:
            raise ValueError("field_scale must be finite and positive.")

        generator = np.random.default_rng(seed)
        hidden_weights = generator.normal(size=(hidden_count, 2))
        hidden_weights /= np.linalg.norm(hidden_weights, axis=1, keepdims=True)
        hidden_bias = generator.uniform(-0.5, 0.5, size=hidden_count)
        angles = np.linspace(0.0, 2.0 * np.pi, 4096, endpoint=False)
        directions = np.column_stack((np.cos(angles), np.sin(angles)))
        feature_mean = np.mean(
            np.tanh(sharpness * (directions @ hidden_weights.T) + hidden_bias),
            axis=0,
        )
        if output_weights is None:
            initial_output = generator.normal(size=hidden_count)
            initial_output *= 0.8 / max(float(np.max(np.abs(initial_output))), 1.0e-12)
        else:
            if np.iscomplexobj(output_weights):
                raise ValueError("output_weights must be real-valued.")
            initial_output = np.asarray(output_weights, dtype=np.float64)
        if (
            initial_output.shape != (hidden_count,)
            or not np.all(np.isfinite(initial_output))
        ):
            raise ValueError(
                f"output_weights must contain {hidden_count} finite values."
            )

        self.center = nn.Parameter(
            torch.as_tensor(center_values, dtype=resolved_dtype, device=device)
        )
        self.log_radius = nn.Parameter(
            torch.tensor(math.log(radius_value), dtype=resolved_dtype, device=device)
        )
        self.output_weights = nn.Parameter(
            torch.as_tensor(initial_output, dtype=resolved_dtype, device=device)
        )
        self.register_buffer(
            "hidden_weights",
            torch.as_tensor(hidden_weights, dtype=resolved_dtype, device=device),
        )
        self.register_buffer(
            "hidden_bias",
            torch.as_tensor(hidden_bias, dtype=resolved_dtype, device=device),
        )
        self.register_buffer(
            "feature_mean",
            torch.as_tensor(feature_mean, dtype=resolved_dtype, device=device),
        )
        self.random_seed = seed
        self.relative_amplitude = amplitude
        self.feature_sharpness = sharpness
        self.field_scale = scale

    @property
    def radius(self) -> torch.Tensor:
        return torch.exp(self.log_radius)

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (num_points, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have a floating-point dtype.")
        if points.device != self.center.device:
            raise ValueError(
                "points and RadialRandomFeatureImplicit2D parameters must be on "
                "the same device."
            )
        delta = points - self.center.to(dtype=points.dtype)[None, :]
        radial_distance = torch.linalg.norm(delta, dim=1)
        denominator_floor = max(float(torch.finfo(points.dtype).eps), 1.0e-12)
        direction = delta / torch.clamp(
            radial_distance[:, None], min=denominator_floor
        )
        features = torch.tanh(
            self.feature_sharpness
            * (direction @ self.hidden_weights.to(dtype=points.dtype).T)
            + self.hidden_bias.to(dtype=points.dtype)
        ) - self.feature_mean.to(dtype=points.dtype)
        relative_perturbation = self.relative_amplitude * torch.mean(
            features * self.output_weights.to(dtype=points.dtype)[None, :],
            dim=1,
        )
        boundary_radius = self.radius.to(dtype=points.dtype) * (
            1.0 + relative_perturbation
        )
        return (self.field_scale * (radial_distance - boundary_radius))[:, None]

    def physical_geometry(self) -> dict[str, float]:
        center = self.center.detach().cpu().to(dtype=torch.float64).numpy()
        weights = (
            self.output_weights.detach().cpu().to(dtype=torch.float64).numpy()
        )
        return {
            "center_x": float(center[0]),
            "center_y": float(center[1]),
            "radius": float(self.radius.detach().cpu().to(dtype=torch.float64)),
            "network_weight_l2": float(np.linalg.norm(weights)),
            "network_weight_max_abs": float(np.max(np.abs(weights))),
        }

    def initialization_metadata(self) -> dict[str, object]:
        return {
            "kind": "topology_constrained_random_feature_neural_implicit",
            "claims_signed_distance": False,
            "random_seed": self.random_seed,
            "hidden_features": int(self.output_weights.numel()),
            "relative_amplitude": self.relative_amplitude,
            "feature_sharpness": self.feature_sharpness,
            "field_scale": self.field_scale,
            "fixed_hidden_weights": self.hidden_weights.detach().cpu().numpy(),
            "fixed_hidden_bias": self.hidden_bias.detach().cpu().numpy(),
            "fixed_feature_mean": self.feature_mean.detach().cpu().numpy(),
        }


@dataclass(frozen=True)
class _ParameterLayout:
    name: str
    parameter: nn.Parameter
    shape: torch.Size
    start: int
    stop: int


def _positive_integer(value: object, *, name: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    if result < 1:
        raise ValueError(f"{name} must be positive.")
    return int(result)


def _expanded_parameter_names(
    named_parameters: Sequence[tuple[str, nn.Parameter]],
) -> tuple[str, ...]:
    labels: list[str] = []
    for name, parameter in named_parameters:
        if parameter.numel() == 1:
            labels.append(name)
            continue
        shape = tuple(int(value) for value in parameter.shape)
        for flat_index in range(parameter.numel()):
            index = np.unravel_index(flat_index, shape)
            suffix = ",".join(str(value) for value in index)
            labels.append(f"{name}[{suffix}]")
    return tuple(labels)


def _finite_vector(
    values: float | Sequence[float] | np.ndarray,
    *,
    size: int,
    name: str,
) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim == 0:
        array = np.full(size, float(array), dtype=np.float64)
    else:
        array = np.asarray(array, dtype=np.float64).reshape(-1)
        if array.shape != (size,):
            raise ValueError(f"{name} must be scalar or have shape ({size},).")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values.")
    return array


class TorchParameterController:
    """Stable NumPy-vector view of a small module's trainable parameters.

    Parameters are visited in ``model.named_parameters()`` order.  Assignment
    copies each slice back using the parameter's original shape, device and
    dtype.  Bounds are deliberately mandatory and finite: a black-box finite-
    difference optimizer should have an explicit physical safety envelope.
    Callers must choose that envelope so every finite-difference and line-search
    trial retains an extractable, topology-valid zero set inside the configured
    geometry box.
    """

    def __init__(
        self,
        model: nn.Module,
        *,
        lower_bounds: float | Sequence[float] | np.ndarray,
        upper_bounds: float | Sequence[float] | np.ndarray,
        names: Sequence[str] | None = None,
        max_parameters: int = 32,
    ) -> None:
        if not isinstance(model, nn.Module):
            raise TypeError("model must be a torch.nn.Module.")
        limit = _positive_integer(max_parameters, name="max_parameters")
        named = tuple(
            (name, parameter)
            for name, parameter in model.named_parameters()
            if parameter.requires_grad
        )
        if not named:
            raise ValueError("model has no requires-grad parameters.")
        for name, parameter in named:
            if parameter.is_complex() or not parameter.is_floating_point():
                raise TypeError(
                    f"Trainable parameter {name!r} must use a real floating dtype."
                )

        count = int(sum(parameter.numel() for _, parameter in named))
        if count < 1:
            raise ValueError(
                "model requires at least one scalar requires-grad parameter."
            )
        if count > limit:
            raise ValueError(
                "Finite-difference control requested for "
                f"{count} scalar parameters, exceeding max_parameters={limit}. "
                "Use a low-dimensional physical/shape controller or an adjoint; "
                "direct finite differences over a large random network are not "
                "scalable."
            )

        if names is None:
            resolved_names = _expanded_parameter_names(named)
        else:
            resolved_names = tuple(str(value).strip() for value in names)
            if len(resolved_names) != count:
                raise ValueError(
                    f"names must contain exactly {count} scalar labels."
                )
            if any(not value for value in resolved_names):
                raise ValueError("names must contain only non-empty labels.")
            if len(set(resolved_names)) != len(resolved_names):
                raise ValueError("names must be unique.")

        lower = _finite_vector(
            lower_bounds,
            size=count,
            name="lower_bounds",
        )
        upper = _finite_vector(
            upper_bounds,
            size=count,
            name="upper_bounds",
        )
        if np.any(lower >= upper):
            raise ValueError(
                "Every lower bound must be strictly less than its upper bound."
            )

        layouts: list[_ParameterLayout] = []
        start = 0
        for name, parameter in named:
            stop = start + int(parameter.numel())
            layouts.append(
                _ParameterLayout(
                    name=name,
                    parameter=parameter,
                    shape=parameter.shape,
                    start=start,
                    stop=stop,
                )
            )
            start = stop

        lower.setflags(write=False)
        upper.setflags(write=False)
        self.model = model
        self._layouts = tuple(layouts)
        self._names = resolved_names
        self._lower_bounds = lower
        self._upper_bounds = upper
        self._max_parameters = limit

        initial = self.parameter_vector()
        if np.any(initial < lower) or np.any(initial > upper):
            offending = [
                resolved_names[index]
                for index in np.flatnonzero((initial < lower) | (initial > upper))
            ]
            raise ValueError(
                "Initial parameters lie outside their bounds: "
                + ", ".join(offending)
            )

    @property
    def num_parameters(self) -> int:
        return len(self._names)

    @property
    def names(self) -> tuple[str, ...]:
        return self._names

    @property
    def lower_bounds(self) -> np.ndarray:
        return self._lower_bounds

    @property
    def upper_bounds(self) -> np.ndarray:
        return self._upper_bounds

    @property
    def max_parameters(self) -> int:
        return self._max_parameters

    def parameter_vector(self) -> np.ndarray:
        """Return an independent float64 vector in stable parameter order."""

        pieces = [
            layout.parameter.detach().reshape(-1).cpu().to(dtype=torch.float64).numpy()
            for layout in self._layouts
        ]
        vector = np.concatenate(pieces).astype(np.float64, copy=True)
        if not np.all(np.isfinite(vector)):
            raise ValueError("model parameters contain non-finite values.")
        return vector

    def flatten(self) -> np.ndarray:
        """Alias for :meth:`parameter_vector`."""

        return self.parameter_vector()

    def project(self, values: Sequence[float] | np.ndarray) -> np.ndarray:
        vector = self._coerce_vector(values)
        return np.clip(vector, self._lower_bounds, self._upper_bounds)

    def assign(self, values: Sequence[float] | np.ndarray) -> None:
        """Assign one bounded vector without changing parameter metadata."""

        vector = self._coerce_vector(values)
        if np.any(vector < self._lower_bounds) or np.any(vector > self._upper_bounds):
            raise ValueError("assigned parameter vector lies outside controller bounds.")
        with torch.no_grad():
            for layout in self._layouts:
                values_tensor = torch.as_tensor(
                    vector[layout.start : layout.stop],
                    dtype=layout.parameter.dtype,
                    device=layout.parameter.device,
                ).reshape(layout.shape)
                layout.parameter.copy_(values_tensor)

    def physical_parameter_dict(self) -> dict[str, float]:
        """Return model-provided physical geometry or named raw controls."""

        physical_geometry = getattr(self.model, "physical_geometry", None)
        if callable(physical_geometry):
            values = physical_geometry()
            if not isinstance(values, dict):
                raise TypeError("model.physical_geometry() must return a dict.")
            result = {str(key): float(value) for key, value in values.items()}
            if not result or not all(math.isfinite(value) for value in result.values()):
                raise ValueError(
                    "model.physical_geometry() must contain finite numeric values."
                )
            return result
        vector = self.parameter_vector()
        return {
            name: float(value) for name, value in zip(self._names, vector)
        }

    def _coerce_vector(
        self,
        values: Sequence[float] | np.ndarray,
    ) -> np.ndarray:
        vector = np.asarray(values, dtype=np.float64)
        if vector.shape != (self.num_parameters,):
            raise ValueError(
                f"parameter vector must have shape ({self.num_parameters},)."
            )
        if not np.all(np.isfinite(vector)):
            raise ValueError("parameter vector must contain only finite values.")
        return np.array(vector, dtype=np.float64, copy=True)


def build_circle_parameter_controller(
    model: CircleSDF2D,
    *,
    center_bounds: tuple[tuple[float, float], tuple[float, float]],
    radius_bounds: tuple[float, float],
    max_parameters: int = 3,
) -> TorchParameterController:
    """Construct the bounded ``(center_x, center_y, log_radius)`` controller."""

    if not isinstance(model, CircleSDF2D):
        raise TypeError("model must be a CircleSDF2D.")
    center_values = np.asarray(center_bounds, dtype=np.float64)
    radius_values = np.asarray(radius_bounds, dtype=np.float64)
    if center_values.shape != (2, 2) or not np.all(np.isfinite(center_values)):
        raise ValueError(
            "center_bounds must be ((x_lower, x_upper), (y_lower, y_upper))."
        )
    if np.any(center_values[:, 0] >= center_values[:, 1]):
        raise ValueError("Each center lower bound must be less than its upper bound.")
    if radius_values.shape != (2,) or not np.all(np.isfinite(radius_values)):
        raise ValueError("radius_bounds must contain two finite values.")
    if radius_values[0] <= 0.0 or radius_values[0] >= radius_values[1]:
        raise ValueError(
            "radius_bounds must be positive and strictly increasing."
        )
    return TorchParameterController(
        model,
        lower_bounds=(
            center_values[0, 0],
            center_values[1, 0],
            math.log(float(radius_values[0])),
        ),
        upper_bounds=(
            center_values[0, 1],
            center_values[1, 1],
            math.log(float(radius_values[1])),
        ),
        names=("center_x", "center_y", "log_radius"),
        max_parameters=max_parameters,
    )


def build_ellipse_parameter_controller(
    model: EllipseLevelSet2D,
    *,
    center_bounds: tuple[tuple[float, float], tuple[float, float]],
    semi_axis_bounds: tuple[float, float],
    max_parameters: int = 4,
) -> TorchParameterController:
    """Construct bounded center and semi-axis controls for an ellipse level set."""

    if not isinstance(model, EllipseLevelSet2D):
        raise TypeError("model must be an EllipseLevelSet2D.")
    center_values = np.asarray(center_bounds, dtype=np.float64)
    axis_values = np.asarray(semi_axis_bounds, dtype=np.float64)
    if center_values.shape != (2, 2) or not np.all(np.isfinite(center_values)):
        raise ValueError(
            "center_bounds must be ((x_lower, x_upper), (y_lower, y_upper))."
        )
    if np.any(center_values[:, 0] >= center_values[:, 1]):
        raise ValueError("Each center lower bound must be less than its upper bound.")
    if axis_values.shape != (2,) or not np.all(np.isfinite(axis_values)):
        raise ValueError("semi_axis_bounds must contain two finite values.")
    if axis_values[0] <= 0.0 or axis_values[0] >= axis_values[1]:
        raise ValueError(
            "semi_axis_bounds must be positive and strictly increasing."
        )
    return TorchParameterController(
        model,
        lower_bounds=(
            center_values[0, 0],
            center_values[1, 0],
            math.log(float(axis_values[0])),
            math.log(float(axis_values[0])),
        ),
        upper_bounds=(
            center_values[0, 1],
            center_values[1, 1],
            math.log(float(axis_values[1])),
            math.log(float(axis_values[1])),
        ),
        names=("center_x", "center_y", "log_semi_axis_x", "log_semi_axis_y"),
        max_parameters=max_parameters,
    )


def build_radial_random_feature_parameter_controller(
    model: RadialRandomFeatureImplicit2D,
    *,
    center_bounds: tuple[tuple[float, float], tuple[float, float]],
    radius_bounds: tuple[float, float],
    output_weight_bounds: tuple[float, float] = (-1.0, 1.0),
    max_parameters: int | None = None,
) -> TorchParameterController:
    """Bound a random-feature field while preserving its star-shaped topology."""

    if not isinstance(model, RadialRandomFeatureImplicit2D):
        raise TypeError("model must be a RadialRandomFeatureImplicit2D.")
    center_values = np.asarray(center_bounds, dtype=np.float64)
    radius_values = np.asarray(radius_bounds, dtype=np.float64)
    weight_values = np.asarray(output_weight_bounds, dtype=np.float64)
    if center_values.shape != (2, 2) or not np.all(np.isfinite(center_values)):
        raise ValueError(
            "center_bounds must be ((x_lower, x_upper), (y_lower, y_upper))."
        )
    if np.any(center_values[:, 0] >= center_values[:, 1]):
        raise ValueError("Each center lower bound must be less than its upper bound.")
    if radius_values.shape != (2,) or not np.all(np.isfinite(radius_values)):
        raise ValueError("radius_bounds must contain two finite values.")
    if radius_values[0] <= 0.0 or radius_values[0] >= radius_values[1]:
        raise ValueError("radius_bounds must be positive and strictly increasing.")
    if weight_values.shape != (2,) or not np.all(np.isfinite(weight_values)):
        raise ValueError("output_weight_bounds must contain two finite values.")
    if weight_values[0] >= weight_values[1]:
        raise ValueError("output_weight_bounds must be strictly increasing.")
    maximum_weight = float(np.max(np.abs(weight_values)))
    if 2.0 * model.relative_amplitude * maximum_weight >= 1.0:
        raise ValueError(
            "output_weight_bounds are too wide to guarantee a positive radial "
            "zero contour for this relative_amplitude."
        )
    hidden_count = int(model.output_weights.numel())
    parameter_count = 3 + hidden_count
    limit = parameter_count if max_parameters is None else max_parameters
    return TorchParameterController(
        model,
        lower_bounds=(
            center_values[0, 0],
            center_values[1, 0],
            math.log(float(radius_values[0])),
            *([float(weight_values[0])] * hidden_count),
        ),
        upper_bounds=(
            center_values[0, 1],
            center_values[1, 1],
            math.log(float(radius_values[1])),
            *([float(weight_values[1])] * hidden_count),
        ),
        names=(
            "center_x",
            "center_y",
            "log_radius",
            *(f"network_output_weight[{index}]" for index in range(hidden_count)),
        ),
        max_parameters=limit,
    )


circle_parameter_controller = build_circle_parameter_controller


__all__ = [
    "CircleSDF2D",
    "EllipseLevelSet2D",
    "RadialRandomFeatureImplicit2D",
    "TorchParameterController",
    "build_circle_parameter_controller",
    "build_ellipse_parameter_controller",
    "build_radial_random_feature_parameter_controller",
    "circle_parameter_controller",
]
