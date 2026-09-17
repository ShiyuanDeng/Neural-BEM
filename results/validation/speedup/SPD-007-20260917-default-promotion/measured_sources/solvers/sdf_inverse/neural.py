"""Smooth neural SDF representation and geometry-preserving re-distancing.

The network is a generic coordinate MLP.  It is never called an exact SDF:
signed-distance supervision and an Eikonal penalty are finite-sample numerical
conditions, not a global guarantee.  Re-distancing is performed against the
closed node polygon of an already validated :class:`PeriodicCurve2D` by
default. The opt-in smooth target uses its supplied continuous producer and
independently refined closest-point distances.
Boundary and normal-offset constraints are sampled densely and uniformly in
polygon arc length so an MLP cannot pass only at the solver vertices while
drifting between them; Eikonal regularisation fixes the field scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial
import math
import operator
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import torch
from torch import nn

from ordered_boundary import (
    PeriodicCurve2D,
    PeriodicParameterization2D,
    sampled_self_intersection_count,
)


Bounds2D = tuple[tuple[float, float], tuple[float, float]]


def _canonical_bounds(bounds: Any) -> Bounds2D:
    if np.iscomplexobj(bounds):
        raise ValueError("bounds must be real-valued.")
    values = np.asarray(bounds, dtype=np.float64)
    if values.shape != (2, 2) or not np.all(np.isfinite(values)):
        raise ValueError("bounds must be finite ((xmin, ymin), (xmax, ymax)).")
    if np.any(values[1] <= values[0]):
        raise ValueError("Upper bounds must exceed lower bounds.")
    return (
        (float(values[0, 0]), float(values[0, 1])),
        (float(values[1, 0]), float(values[1, 1])),
    )


def _positive_integer(value: object, *, name: str, allow_zero: bool = False) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be an integer, not bool.")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise TypeError(f"{name} must be an integer.") from exc
    minimum = 0 if allow_zero else 1
    if result < minimum:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {relation}.")
    return int(result)


def _finite_positive(value: object, *, name: str, allow_zero: bool = False) -> float:
    result = float(value)
    valid = result >= 0.0 if allow_zero else result > 0.0
    if not math.isfinite(result) or not valid:
        relation = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be finite and {relation}.")
    return result


class SmoothMLPSDF2D(nn.Module):
    """Coordinate-normalized tanh MLP with output measured in physical metres."""

    claims_signed_distance = False
    trained_against_signed_distance = False

    def __init__(
        self,
        *,
        bounds: Bounds2D,
        hidden_features: int = 64,
        hidden_layers: int = 2,
        fourier_frequencies: tuple[float, ...] = (1.0, 2.0, 4.0, 8.0),
        geometric_center: tuple[float, float] | None = None,
        geometric_radius: float | None = None,
        seed: int = 0,
        dtype: torch.dtype = torch.float64,
        device: torch.device | str | None = None,
    ) -> None:
        super().__init__()
        resolved_bounds = _canonical_bounds(bounds)
        width = _positive_integer(hidden_features, name="hidden_features")
        depth = _positive_integer(hidden_layers, name="hidden_layers")
        if dtype not in {torch.float32, torch.float64}:
            raise TypeError("dtype must be torch.float32 or torch.float64.")
        if isinstance(seed, (bool, np.bool_)):
            raise TypeError("seed must be an integer, not bool.")
        resolved_seed = int(operator.index(seed))
        frequencies = np.asarray(fourier_frequencies, dtype=np.float64)
        if (
            frequencies.ndim != 1
            or frequencies.size < 1
            or not np.all(np.isfinite(frequencies))
            or np.any(frequencies <= 0.0)
        ):
            raise ValueError("fourier_frequencies must contain finite positive values.")

        bounds_array = np.asarray(resolved_bounds, dtype=np.float64)
        center = np.mean(bounds_array, axis=0)
        # Isotropic normalization preserves the Eikonal norm: if
        # F(x)=L*n((x-c)/L), then grad_x F=grad_z n.
        length_scale = 0.5 * float(np.max(bounds_array[1] - bounds_array[0]))
        self.register_buffer(
            "coordinate_center",
            torch.as_tensor(center, dtype=dtype, device=device),
        )
        self.register_buffer(
            "coordinate_scale",
            torch.tensor(length_scale, dtype=dtype, device=device),
        )
        self.register_buffer(
            "fourier_frequencies",
            torch.as_tensor(frequencies, dtype=dtype, device=device),
        )

        # ``nn.Linear`` initializes itself from Torch's global generator before
        # the local NumPy initialization below replaces those values.  Forking
        # the relevant generator prevents construction of a locally seeded
        # model from perturbing the caller's random stream.
        rng_devices = (
            [self.coordinate_center.device]
            if self.coordinate_center.device.type == "cuda"
            else []
        )
        with torch.random.fork_rng(devices=rng_devices, enabled=True):
            layers: list[nn.Module] = []
            input_features = 2 + 4 * int(frequencies.size)
            for _ in range(depth):
                layers.append(nn.Linear(input_features, width, dtype=dtype, device=device))
                layers.append(nn.Tanh())
                input_features = width
            layers.append(nn.Linear(input_features, 1, dtype=dtype, device=device))
        self.network = nn.Sequential(*layers)
        self.bounds = resolved_bounds
        self.hidden_features = width
        self.hidden_layers = depth
        self.seed = resolved_seed
        self._reset_with_local_rng(resolved_seed)
        if (geometric_center is None) != (geometric_radius is None):
            raise ValueError(
                "geometric_center and geometric_radius must be supplied together."
            )
        self.has_geometric_initialization = geometric_center is not None
        if self.has_geometric_initialization:
            center_values = np.asarray(geometric_center, dtype=np.float64)
            radius_value = float(geometric_radius)
            if center_values.shape != (2,) or not np.all(np.isfinite(center_values)):
                raise ValueError("geometric_center must contain two finite coordinates.")
            if not math.isfinite(radius_value) or radius_value <= 0.0:
                raise ValueError("geometric_radius must be finite and positive.")
            self.register_buffer(
                "geometric_center",
                torch.as_tensor(center_values, dtype=dtype, device=device),
            )
            self.register_buffer(
                "geometric_radius",
                torch.tensor(radius_value, dtype=dtype, device=device),
            )
            # A zero residual head makes the randomly initialized hidden MLP a
            # topology-valid wrong circle at iteration zero.  All layers remain
            # trainable once the head receives its first gradient.
            final = self.network[-1]
            assert isinstance(final, nn.Linear)
            with torch.no_grad():
                final.weight.zero_()
                final.bias.zero_()

    def _reset_with_local_rng(self, seed: int) -> None:
        generator = np.random.default_rng(seed)
        with torch.no_grad():
            for module in self.network:
                if not isinstance(module, nn.Linear):
                    continue
                fan_in = int(module.weight.shape[1])
                fan_out = int(module.weight.shape[0])
                bound = math.sqrt(6.0 / (fan_in + fan_out))
                weights = generator.uniform(-bound, bound, size=tuple(module.weight.shape))
                biases = generator.uniform(-bound, bound, size=tuple(module.bias.shape))
                module.weight.copy_(
                    torch.as_tensor(weights, dtype=module.weight.dtype, device=module.weight.device)
                )
                module.bias.copy_(
                    torch.as_tensor(biases, dtype=module.bias.dtype, device=module.bias.device)
                )

    def forward(self, points: torch.Tensor) -> torch.Tensor:
        if not isinstance(points, torch.Tensor):
            raise TypeError("points must be a torch.Tensor.")
        if points.ndim != 2 or points.shape[1] != 2:
            raise ValueError("points must have shape (N, 2).")
        if not points.is_floating_point():
            raise TypeError("points must have floating-point dtype.")
        if points.device != self.coordinate_center.device:
            raise ValueError("points and model must be on the same device.")
        scale = self.coordinate_scale.to(dtype=points.dtype)
        normalized = (points - self.coordinate_center.to(dtype=points.dtype)[None, :]) / scale
        phases = math.pi * normalized[:, :, None] * self.fourier_frequencies.to(
            dtype=points.dtype
        )[None, None, :]
        encoded = torch.cat(
            (
                normalized,
                torch.sin(phases).reshape(points.shape[0], -1),
                torch.cos(phases).reshape(points.shape[0], -1),
            ),
            dim=1,
        )
        residual = scale * self.network(encoded)
        if not self.has_geometric_initialization:
            return residual
        delta = points - self.geometric_center.to(dtype=points.dtype)[None, :]
        radial_distance = torch.sqrt(
            torch.sum(delta * delta, dim=1, keepdim=True)
            + torch.finfo(points.dtype).tiny
        )
        return radial_distance - self.geometric_radius.to(dtype=points.dtype) + residual

    def spatial_gradient(
        self, points: torch.Tensor, *, create_graph: bool = True
    ) -> torch.Tensor:
        points_for_gradient = points.detach().clone().requires_grad_(True)
        values = self(points_for_gradient)
        return torch.autograd.grad(
            values,
            points_for_gradient,
            grad_outputs=torch.ones_like(values),
            create_graph=create_graph,
            retain_graph=create_graph,
            only_inputs=True,
        )[0]

    def initialization_metadata(self) -> dict[str, object]:
        return {
            "kind": "coordinate_normalized_tanh_mlp",
            "claims_signed_distance": False,
            "trained_against_signed_distance": bool(self.trained_against_signed_distance),
            "hidden_features": self.hidden_features,
            "hidden_layers": self.hidden_layers,
            "fourier_frequencies": self.fourier_frequencies.detach().cpu().tolist(),
            "parameter_count": int(sum(parameter.numel() for parameter in self.parameters())),
            "seed": self.seed,
            "dtype": str(self.coordinate_center.dtype),
            "device": str(self.coordinate_center.device),
            "bounds": self.bounds,
            "geometric_initialization": (
                None
                if not self.has_geometric_initialization
                else {
                    "kind": "fixed_circle_residual_skip",
                    "center": self.geometric_center.detach().cpu().tolist(),
                    "radius": float(self.geometric_radius.detach().cpu()),
                }
            ),
        }


def _validated_polygon(curve: PeriodicCurve2D) -> np.ndarray:
    if not isinstance(curve, PeriodicCurve2D):
        raise TypeError("curve must be an ordered_boundary.PeriodicCurve2D.")
    points = np.array(curve.points, dtype=np.float64, copy=True)
    if points.ndim != 2 or points.shape[0] < 4 or points.shape[1] != 2:
        raise ValueError("curve points must have shape (N, 2), N >= 4.")
    edges = np.roll(points, -1, axis=0) - points
    edge_lengths = np.linalg.norm(edges, axis=1)
    scale = max(float(np.max(np.ptp(points, axis=0))), 1.0)
    if np.any(edge_lengths <= 64.0 * np.finfo(float).eps * scale):
        raise ValueError("curve node polygon contains a zero-length edge.")
    area = 0.5 * float(
        np.sum(points[:, 0] * np.roll(points[:, 1], -1) - np.roll(points[:, 0], -1) * points[:, 1])
    )
    if not math.isfinite(area) or area <= 64.0 * np.finfo(float).eps * scale**2:
        raise ValueError("curve node polygon must be nondegenerate and counterclockwise.")
    intersections = sampled_self_intersection_count(points)
    if intersections:
        raise ValueError(
            f"curve node polygon has {intersections} sampled self-intersection(s)."
        )
    return points


def _dense_arclength_boundary_samples(
    curve: PeriodicCurve2D,
    oversampling_factor: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample the node polygon and its interpolated normals in arc length.

    Subdividing by node index would overweight short edges when a curve is not
    perfectly uniform.  This routine instead walks cumulative polygon length,
    and linearly interpolates the already validated smooth node normals at the
    same edge fractions.  The sampled points remain exactly on the polygon
    used by :func:`signed_distance_to_curve_polygon`.
    """

    polygon = _validated_polygon(curve)
    factor = _positive_integer(
        oversampling_factor,
        name="oversampling_factor",
    )
    edges = np.roll(polygon, -1, axis=0) - polygon
    edge_lengths = np.linalg.norm(edges, axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(edge_lengths)))
    perimeter = float(cumulative[-1])
    count = factor * polygon.shape[0]
    distances = perimeter * np.arange(count, dtype=np.float64) / count
    edge_indices = np.searchsorted(cumulative[1:], distances, side="right")
    fractions = (
        distances - cumulative[edge_indices]
    ) / edge_lengths[edge_indices]
    points = polygon[edge_indices] + fractions[:, None] * edges[edge_indices]

    node_normals = np.asarray(curve.normals, dtype=np.float64)
    next_normals = np.roll(node_normals, -1, axis=0)
    normals = (
        (1.0 - fractions)[:, None] * node_normals[edge_indices]
        + fractions[:, None] * next_normals[edge_indices]
    )
    normal_lengths = np.linalg.norm(normals, axis=1)
    if np.any(normal_lengths <= 64.0 * np.finfo(float).eps):
        raise ValueError("interpolated boundary normals must remain nonzero.")
    normals /= normal_lengths[:, None]
    points.setflags(write=False)
    normals.setflags(write=False)
    return points, normals


def signed_distance_to_curve_polygon(
    query_points: np.ndarray,
    curve: PeriodicCurve2D,
    *,
    chunk_size: int = 4096,
) -> np.ndarray:
    """Signed Euclidean distance to the curve's closed node polygon.

    The sign is determined by even--odd containment (negative inside), not a
    nearest-edge normal, so concave curves are handled correctly.
    """

    polygon = _validated_polygon(curve)
    points = np.asarray(query_points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2 or not np.all(np.isfinite(points)):
        raise ValueError("query_points must have finite shape (N, 2).")
    chunk = _positive_integer(chunk_size, name="chunk_size")
    starts = polygon
    ends = np.roll(polygon, -1, axis=0)
    edges = ends - starts
    squared_lengths = np.sum(edges * edges, axis=1)
    result = np.empty(points.shape[0], dtype=np.float64)
    tiny = 64.0 * np.finfo(np.float64).eps
    for first in range(0, points.shape[0], chunk):
        values = points[first : first + chunk]
        displacement = values[:, None, :] - starts[None, :, :]
        fractions = np.sum(displacement * edges[None, :, :], axis=2) / squared_lengths[None, :]
        fractions = np.clip(fractions, 0.0, 1.0)
        closest = starts[None, :, :] + fractions[:, :, None] * edges[None, :, :]
        distances = np.sqrt(np.min(np.sum((values[:, None, :] - closest) ** 2, axis=2), axis=1))

        x = values[:, 0, None]
        y = values[:, 1, None]
        y0 = starts[None, :, 1]
        y1 = ends[None, :, 1]
        crosses_y = (y0 > y) != (y1 > y)
        denominator = y1 - y0
        safe_denominator = np.where(np.abs(denominator) > tiny, denominator, 1.0)
        crossing_x = starts[None, :, 0] + (y - y0) * edges[None, :, 0] / safe_denominator
        inside = np.count_nonzero(crosses_y & (x < crossing_x), axis=1) % 2 == 1
        distances[inside] *= -1.0
        result[first : first + values.shape[0]] = distances
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class NeuralRedistanceConfig:
    """Deterministic full-batch MLP fit to one accepted closed curve."""

    bounds: Bounds2D
    max_steps: int = 1200
    minimum_steps: int = 100
    warmup_steps: int = 150
    sample_count: int = 2048
    heldout_sample_count: int = 512
    learning_rate: float = 2.0e-3
    eikonal_weight: float = 1.0e-1
    boundary_weight: float = 200.0
    normal_offset_weight: float = 20.0
    box_boundary_weight: float = 5.0
    normal_offset_m: float = 2.0e-3
    distance_rms_tolerance_m: float = 5.0e-3
    boundary_max_tolerance_m: float = 1.0e-3
    eikonal_rms_tolerance: float = 2.0e-1
    check_interval: int = 20
    patience_checks: int = 15
    seed: int = 31415
    no_op_boundary_max_tolerance_m: float = 1.0e-6
    # Appended to retain positional compatibility with the original public
    # configuration constructor.
    boundary_oversampling_factor: int = 4
    # Smooth supervision is opt-in and independent of the solver-node polygon.
    distance_target: str = "legacy_polygon"
    distance_target_tolerance_m: float = 1.0e-6
    distance_initial_samples: int = 256
    distance_maximum_samples: int = 4096
    smooth_boundary_sample_count: int = 512
    # The polygon option freezes the historical sample locations for a pure
    # target-policy ablation; their smooth distance targets need not be zero.
    smooth_boundary_sampling: str = "continuous_curve"

    def __post_init__(self) -> None:
        object.__setattr__(self, "bounds", _canonical_bounds(self.bounds))
        for name in (
            "max_steps",
            "minimum_steps",
            "sample_count",
            "heldout_sample_count",
            "boundary_oversampling_factor",
            "check_interval",
            "patience_checks",
            "distance_initial_samples",
            "distance_maximum_samples",
            "smooth_boundary_sample_count",
        ):
            object.__setattr__(self, name, _positive_integer(getattr(self, name), name=name))
        object.__setattr__(
            self,
            "warmup_steps",
            _positive_integer(self.warmup_steps, name="warmup_steps", allow_zero=True),
        )
        if self.minimum_steps > self.max_steps:
            raise ValueError("minimum_steps cannot exceed max_steps.")
        if self.warmup_steps >= self.max_steps:
            raise ValueError("warmup_steps must be smaller than max_steps.")
        for name in (
            "learning_rate",
            "boundary_weight",
            "normal_offset_weight",
            "box_boundary_weight",
            "normal_offset_m",
            "distance_rms_tolerance_m",
            "boundary_max_tolerance_m",
            "eikonal_rms_tolerance",
            "no_op_boundary_max_tolerance_m",
            "distance_target_tolerance_m",
        ):
            object.__setattr__(self, name, _finite_positive(getattr(self, name), name=name))
        object.__setattr__(
            self,
            "eikonal_weight",
            _finite_positive(self.eikonal_weight, name="eikonal_weight", allow_zero=True),
        )
        if isinstance(self.seed, (bool, np.bool_)):
            raise TypeError("seed must be an integer, not bool.")
        object.__setattr__(self, "seed", int(operator.index(self.seed)))
        if self.no_op_boundary_max_tolerance_m > self.boundary_max_tolerance_m:
            raise ValueError(
                "no_op_boundary_max_tolerance_m cannot exceed "
                "boundary_max_tolerance_m."
            )
        if self.distance_target not in {"legacy_polygon", "smooth_curve"}:
            raise ValueError("distance_target must be legacy_polygon or smooth_curve.")
        if self.smooth_boundary_sampling not in {"continuous_curve", "legacy_polygon"}:
            raise ValueError(
                "smooth_boundary_sampling must be continuous_curve or legacy_polygon."
            )
        if self.distance_initial_samples < 32:
            raise ValueError("distance_initial_samples must be at least 32.")
        if self.distance_maximum_samples < 2 * self.distance_initial_samples:
            raise ValueError("distance_maximum_samples must permit one doubling.")
        if self.smooth_boundary_sample_count < 8:
            raise ValueError("smooth_boundary_sample_count must be at least 8.")


@dataclass(frozen=True)
class NeuralRedistanceResult:
    converged: bool
    steps: int
    stop_reason: str
    initial_total_loss: float
    final_total_loss: float
    final_distance_rms_m: float
    final_heldout_distance_rms_m: float
    final_boundary_max_abs_m: float
    final_eikonal_rms: float
    final_eikonal_maximum_deviation: float
    loss_history: np.ndarray
    diagnostics: Mapping[str, float]

    def __post_init__(self) -> None:
        history = np.array(self.loss_history, dtype=np.float64, copy=True)
        if history.ndim != 1 or history.size < 1 or not np.all(np.isfinite(history)):
            raise ValueError("loss_history must be a finite non-empty vector.")
        history.setflags(write=False)
        diagnostics = {str(key): float(value) for key, value in self.diagnostics.items()}
        if not all(math.isfinite(value) for value in diagnostics.values()):
            raise ValueError("diagnostics must contain finite values.")
        object.__setattr__(self, "loss_history", history)
        object.__setattr__(self, "diagnostics", MappingProxyType(diagnostics))


def _quality_metrics(
    model: nn.Module,
    points: torch.Tensor,
    targets: torch.Tensor,
    boundary_points: torch.Tensor,
    boundary_targets: torch.Tensor | None = None,
) -> tuple[float, float, float, float]:
    probes = points.detach().clone().requires_grad_(True)
    predictions = model(probes).reshape(-1)
    gradients = torch.autograd.grad(predictions.sum(), probes, create_graph=False)[0]
    deviations = torch.abs(torch.linalg.norm(gradients, dim=1) - 1.0)
    with torch.no_grad():
        distance_rms = torch.sqrt(torch.mean((predictions.detach() - targets) ** 2))
        boundary_values = model(boundary_points).reshape(-1)
        if boundary_targets is not None:
            boundary_values = boundary_values - boundary_targets
        boundary_max = torch.max(torch.abs(boundary_values))
    return (
        float(distance_rms.cpu()),
        float(boundary_max.cpu()),
        float(torch.sqrt(torch.mean(deviations**2)).detach().cpu()),
        float(torch.max(deviations).detach().cpu()),
    )


def _redistance_objective(
    model: nn.Module,
    sample_points: torch.Tensor,
    sample_targets: torch.Tensor,
    boundary_points: torch.Tensor,
    offset_points: torch.Tensor,
    offset_targets: torch.Tensor,
    box_points: torch.Tensor,
    box_targets: torch.Tensor,
    *,
    length_scale: float,
    config: NeuralRedistanceConfig,
    eikonal_weight: float,
    create_graph: bool,
    boundary_targets: torch.Tensor | None = None,
) -> torch.Tensor:
    """Evaluate the dimensionless supervised/Eikonal fit objective."""

    probes = sample_points.detach().clone().requires_grad_(True)
    predictions = model(probes).reshape(-1)
    gradients = torch.autograd.grad(
        predictions.sum(),
        probes,
        create_graph=create_graph,
        retain_graph=create_graph,
    )[0]
    distance_loss = torch.mean(((predictions - sample_targets) / length_scale) ** 2)
    boundary_values = model(boundary_points).reshape(-1)
    if boundary_targets is not None:
        boundary_values = boundary_values - boundary_targets
    boundary_loss = torch.mean((boundary_values / length_scale) ** 2)
    offset_loss = torch.mean(
        ((model(offset_points).reshape(-1) - offset_targets) / length_scale) ** 2
    )
    box_loss = torch.mean(
        ((model(box_points).reshape(-1) - box_targets) / length_scale) ** 2
    )
    eikonal_loss = torch.mean((torch.linalg.norm(gradients, dim=1) - 1.0) ** 2)
    return (
        distance_loss
        + config.boundary_weight * boundary_loss
        + config.normal_offset_weight * offset_loss
        + config.box_boundary_weight * box_loss
        + eikonal_weight * eikonal_loss
    )


def redistance_neural_sdf_to_curve(
    model: nn.Module,
    curve: PeriodicCurve2D,
    config: NeuralRedistanceConfig,
    *,
    continuous_curve: PeriodicParameterization2D | None = None,
) -> NeuralRedistanceResult:
    """Distill a frozen curve using the selected distance target.

    ``legacy_polygon`` preserves the historical targets and sampling exactly.
    ``smooth_curve`` requires an explicit continuous producer matching the
    supplied node positions and derivative jets. It independently refines its
    distance targets; normal offsets use evaluated distances rather than
    assuming they lie in a valid tubular neighborhood. The diagnostic
    ``smooth_boundary_sampling='legacy_polygon'`` keeps all historical sample
    locations and supervises their generally nonzero continuous distances.
    """

    if not isinstance(model, nn.Module):
        raise TypeError("model must be a torch.nn.Module.")
    if not isinstance(config, NeuralRedistanceConfig):
        raise TypeError("config must be a NeuralRedistanceConfig.")
    if config.distance_target == "smooth_curve":
        from .continuous_distance import (
            signed_distance_to_continuous_curve,
            smooth_boundary_samples,
        )

        if not isinstance(continuous_curve, PeriodicParameterization2D):
            raise TypeError("smooth_curve targets require continuous_curve.")
        if not isinstance(curve, PeriodicCurve2D):
            raise TypeError("curve must be a PeriodicCurve2D.")
        evaluation = continuous_curve.evaluate(curve.parameters)
        for name in ("points", "first_derivatives", "second_derivatives"):
            if not np.allclose(
                getattr(evaluation, name), getattr(curve, name),
                rtol=1.0e-9, atol=1.0e-11,
            ):
                raise ValueError("continuous_curve must match the supplied curve node jets.")
        if config.smooth_boundary_sampling == "continuous_curve":
            boundary_points, boundary_normals = smooth_boundary_samples(
                continuous_curve, config.smooth_boundary_sample_count,
            )
        else:
            boundary_points, boundary_normals = _dense_arclength_boundary_samples(
                curve, config.boundary_oversampling_factor,
            )
    else:
        boundary_points, boundary_normals = _dense_arclength_boundary_samples(
            curve,
            config.boundary_oversampling_factor,
        )
    # The helper above has already validated this exact node polygon.
    polygon = np.array(curve.points, dtype=np.float64, copy=True)
    trainable_parameters = tuple(
        parameter for parameter in model.parameters() if parameter.requires_grad
    )
    if not trainable_parameters:
        raise ValueError("model must have floating-point trainable parameters.")
    reference = trainable_parameters[0]
    if any(not parameter.is_floating_point() for parameter in trainable_parameters):
        raise ValueError("model must have floating-point trainable parameters.")
    if any(
        parameter.device != reference.device or parameter.dtype != reference.dtype
        for parameter in trainable_parameters
    ):
        raise ValueError("trainable model parameters must share one device and dtype.")
    bounds = np.asarray(config.bounds, dtype=np.float64)
    generator = np.random.default_rng(config.seed)
    uniform = generator.uniform(bounds[0], bounds[1], size=(config.sample_count, 2))
    heldout = generator.uniform(
        bounds[0], bounds[1], size=(config.heldout_sample_count, 2)
    )
    offset_points = np.vstack(
        (
            boundary_points + config.normal_offset_m * boundary_normals,
            boundary_points - config.normal_offset_m * boundary_normals,
        )
    )
    edge_count = max(32, int(math.ceil(math.sqrt(config.sample_count))))
    unit = np.linspace(0.0, 1.0, edge_count, endpoint=False)
    xmin, ymin = bounds[0]
    xmax, ymax = bounds[1]
    box_points = np.vstack(
        (
            np.column_stack((xmin + (xmax - xmin) * unit, np.full_like(unit, ymin))),
            np.column_stack((np.full_like(unit, xmax), ymin + (ymax - ymin) * unit)),
            np.column_stack((xmax - (xmax - xmin) * unit, np.full_like(unit, ymax))),
            np.column_stack((np.full_like(unit, xmin), ymax - (ymax - ymin) * unit)),
        )
    )
    distance_diagnostics = {}
    boundary_targets = None
    if config.distance_target == "smooth_curve":
        query_groups = (uniform, offset_points, heldout, box_points, boundary_points)
        all_targets, distance_diagnostics = signed_distance_to_continuous_curve(
            np.vstack(query_groups), continuous_curve,
            tolerance_m=config.distance_target_tolerance_m,
            initial_samples=config.distance_initial_samples,
            maximum_samples=config.distance_maximum_samples,
            return_diagnostics=True,
        )
        cuts = np.cumsum([len(group) for group in query_groups])[:-1]
        sample_targets, offset_targets, heldout_targets, box_targets, boundary_targets = (
            np.split(all_targets, cuts)
        )
        distance_diagnostics["smooth_distance_target"] = 1.0
        distance_diagnostics["legacy_sample_locations"] = float(
            config.smooth_boundary_sampling == "legacy_polygon"
        )
        # Check the continuously sampled boundary as well as the BEM nodes.
        bounds_probe = continuous_curve.discretize(config.distance_maximum_samples).points
        if np.any(bounds_probe <= bounds[0]) or np.any(bounds_probe >= bounds[1]):
            raise ValueError("The accepted curve must remain strictly inside redistance bounds.")
    else:
        sample_targets = signed_distance_to_curve_polygon(uniform, curve)
        offset_targets = signed_distance_to_curve_polygon(offset_points, curve)
        heldout_targets = signed_distance_to_curve_polygon(heldout, curve)
        box_targets = signed_distance_to_curve_polygon(box_points, curve)
    if np.any(polygon <= bounds[0]) or np.any(polygon >= bounds[1]):
        raise ValueError("The accepted curve must remain strictly inside redistance bounds.")
    if np.any(box_targets <= 0.0):
        raise ValueError("The accepted curve must remain strictly inside redistance bounds.")

    device = reference.device
    dtype = reference.dtype
    sample_tensor = torch.as_tensor(uniform, dtype=dtype, device=device)
    target_tensor = torch.as_tensor(
        np.array(sample_targets, copy=True), dtype=dtype, device=device
    )
    heldout_tensor = torch.as_tensor(heldout, dtype=dtype, device=device)
    heldout_target_tensor = torch.as_tensor(
        np.array(heldout_targets, copy=True), dtype=dtype, device=device
    )
    boundary_tensor = torch.as_tensor(
        np.array(boundary_points, copy=True), dtype=dtype, device=device
    )
    boundary_target_tensor = (
        None if boundary_targets is None else torch.as_tensor(
            np.array(boundary_targets, copy=True), dtype=dtype, device=device
        )
    )
    objective = _redistance_objective
    quality_metrics = _quality_metrics
    if boundary_target_tensor is not None:
        objective = partial(objective, boundary_targets=boundary_target_tensor)
        quality_metrics = partial(quality_metrics, boundary_targets=boundary_target_tensor)
    offset_tensor = torch.as_tensor(offset_points, dtype=dtype, device=device)
    offset_target_tensor = torch.as_tensor(
        np.array(offset_targets, copy=True), dtype=dtype, device=device
    )
    box_tensor = torch.as_tensor(box_points, dtype=dtype, device=device)
    box_target_tensor = torch.as_tensor(
        np.array(box_targets, copy=True), dtype=dtype, device=device
    )
    # Isotropic physical scale makes every term dimensionless and avoids metre-
    # squared losses that are misleadingly tiny.
    length_scale = 0.5 * float(np.max(bounds[1] - bounds[0]))
    history: list[float] = []
    best_full_loss = float("inf")
    best_full_loss_step = 0
    best_parameters: tuple[torch.Tensor, ...] | None = None
    patience_reference_loss = float("inf")
    stale_checks = 0
    converged = False
    stop_reason = "maximum_steps"
    last_full_objective_step = -1
    was_training = model.training
    # Parameter gradients work in inference mode.  Keeping the module there
    # makes full-batch redistancing deterministic for standard Dropout and
    # prevents BatchNorm running statistics from becoming hidden optimizer
    # state.  The caller's original mode is restored below.
    model.eval()
    try:
        initial_total_loss = float(
            objective(
                model,
                sample_tensor,
                target_tensor,
                boundary_tensor,
                offset_tensor,
                offset_target_tensor,
                box_tensor,
                box_target_tensor,
                length_scale=length_scale,
                config=config,
                eikonal_weight=config.eikonal_weight,
                create_graph=False,
            ).detach().cpu()
        )
        if not math.isfinite(initial_total_loss):
            raise FloatingPointError("Neural re-distancing produced a non-finite loss.")
        (
            initial_train_rms,
            initial_boundary_max,
            initial_eikonal_rms,
            initial_eikonal_max,
        ) = quality_metrics(model, sample_tensor, target_tensor, boundary_tensor)
        initial_heldout_rms, _, _, _ = quality_metrics(
            model, heldout_tensor, heldout_target_tensor, boundary_tensor
        )
        if (
            initial_heldout_rms <= config.distance_rms_tolerance_m
            and initial_boundary_max <= config.no_op_boundary_max_tolerance_m
            and initial_eikonal_rms <= config.eikonal_rms_tolerance
        ):
            if isinstance(model, SmoothMLPSDF2D):
                model.trained_against_signed_distance = True
            return NeuralRedistanceResult(
                converged=True,
                steps=0,
                stop_reason="already_satisfies_distance_boundary_and_eikonal_tolerances",
                initial_total_loss=initial_total_loss,
                final_total_loss=initial_total_loss,
                final_distance_rms_m=initial_train_rms,
                final_heldout_distance_rms_m=initial_heldout_rms,
                final_boundary_max_abs_m=initial_boundary_max,
                final_eikonal_rms=initial_eikonal_rms,
                final_eikonal_maximum_deviation=initial_eikonal_max,
                # Keep the existing non-empty history contract while reporting
                # the optimizer step count truthfully as zero.
                loss_history=np.asarray([initial_total_loss], dtype=np.float64),
                diagnostics={
                    **distance_diagnostics,
                    "polygon_node_count": float(curve.num_nodes),
                    "training_sample_count": float(uniform.shape[0]),
                    "boundary_sample_count": float(boundary_points.shape[0]),
                    "boundary_oversampling_factor": float(
                        config.boundary_oversampling_factor
                    ),
                    "normal_offset_sample_count": float(offset_points.shape[0]),
                    "box_boundary_sample_count": float(box_points.shape[0]),
                    "heldout_sample_count": float(heldout.shape[0]),
                    "length_scale_m": length_scale,
                    "best_full_objective_step": 0.0,
                    "best_full_objective_loss": initial_total_loss,
                },
            )

        # Construct Adam only when the audited input actually needs fitting.
        optimizer = torch.optim.Adam(trainable_parameters, lr=config.learning_rate)
        best_full_loss = initial_total_loss
        patience_reference_loss = initial_total_loss
        best_parameters = tuple(
            parameter.detach().clone() for parameter in trainable_parameters
        )
        last_full_objective_step = 0
        for step in range(1, config.max_steps + 1):
            optimizer.zero_grad(set_to_none=True)
            total = objective(
                model,
                sample_tensor,
                target_tensor,
                boundary_tensor,
                offset_tensor,
                offset_target_tensor,
                box_tensor,
                box_target_tensor,
                length_scale=length_scale,
                config=config,
                eikonal_weight=(
                    0.0 if step <= config.warmup_steps else config.eikonal_weight
                ),
                create_graph=True,
            )
            if not torch.isfinite(total):
                raise FloatingPointError("Neural re-distancing produced a non-finite loss.")
            total_value = float(total.detach().cpu())
            # Once one Eikonal-weighted update has occurred, the next step's
            # pre-update loss gives us the full objective for the intervening
            # state at no extra evaluation cost.  This preserves good states
            # that fall between the more expensive metric checks.
            if step > config.warmup_steps + 1 and total_value < best_full_loss:
                best_full_loss = total_value
                best_full_loss_step = step - 1
                best_parameters = tuple(
                    parameter.detach().clone() for parameter in trainable_parameters
                )
            total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 10.0)
            optimizer.step()
            history.append(total_value)

            # A tolerance or patience decision is only meaningful after at
            # least one update has used the Eikonal term.  In particular, the
            # default minimum_steps=100 must not stop a fit during the default
            # 150-step distance-only warm-up.
            if (
                step < max(config.minimum_steps, config.warmup_steps + 1)
                or step % config.check_interval
            ):
                continue
            checked_loss = float(
                objective(
                    model,
                    sample_tensor,
                    target_tensor,
                    boundary_tensor,
                    offset_tensor,
                    offset_target_tensor,
                    box_tensor,
                    box_target_tensor,
                    length_scale=length_scale,
                    config=config,
                    eikonal_weight=config.eikonal_weight,
                    create_graph=False,
                ).detach().cpu()
            )
            if not math.isfinite(checked_loss):
                raise FloatingPointError("Neural re-distancing produced a non-finite loss.")
            last_full_objective_step = step
            is_best_state = checked_loss < best_full_loss
            if is_best_state:
                best_full_loss = checked_loss
                best_full_loss_step = step
                best_parameters = tuple(
                    parameter.detach().clone() for parameter in trainable_parameters
                )
            train_rms, boundary_max, eikonal_rms, _ = quality_metrics(
                model, sample_tensor, target_tensor, boundary_tensor
            )
            heldout_rms, _, _, _ = quality_metrics(
                model, heldout_tensor, heldout_target_tensor, boundary_tensor
            )
            if (
                heldout_rms <= config.distance_rms_tolerance_m
                and boundary_max <= config.boundary_max_tolerance_m
                and eikonal_rms <= config.eikonal_rms_tolerance
                and is_best_state
            ):
                converged = True
                stop_reason = "distance_boundary_and_eikonal_tolerances"
                break
            improvement = patience_reference_loss - checked_loss
            if improvement > 1.0e-6 * max(abs(patience_reference_loss), 1.0):
                patience_reference_loss = checked_loss
                stale_checks = 0
            else:
                stale_checks += 1
            if stale_checks >= config.patience_checks:
                stop_reason = "stalled_before_tolerances"
                break

        # ``max_steps`` need not coincide with a check interval.  Include that
        # terminal state in the same full-objective comparison before rolling
        # back, otherwise the last few useful optimizer steps can be lost.
        terminal_step = len(history)
        if terminal_step != last_full_objective_step:
            terminal_loss = float(
                objective(
                    model,
                    sample_tensor,
                    target_tensor,
                    boundary_tensor,
                    offset_tensor,
                    offset_target_tensor,
                    box_tensor,
                    box_target_tensor,
                    length_scale=length_scale,
                    config=config,
                    eikonal_weight=config.eikonal_weight,
                    create_graph=False,
                ).detach().cpu()
            )
            if not math.isfinite(terminal_loss):
                raise FloatingPointError("Neural re-distancing produced a non-finite loss.")
            if terminal_loss < best_full_loss:
                best_full_loss = terminal_loss
                best_full_loss_step = terminal_step
                best_parameters = tuple(
                    parameter.detach().clone() for parameter in trainable_parameters
                )

        # Adam's last iterate is not generally its best iterate.  Return the
        # parameters with the lowest consistently evaluated full objective,
        # including the unmodified input model as step zero.
        assert best_parameters is not None
        with torch.no_grad():
            for parameter, best_parameter in zip(trainable_parameters, best_parameters):
                parameter.copy_(best_parameter)
    finally:
        model.train(was_training)

    # Audit the actual returned parameters in deterministic inference mode.
    # The reported endpoint losses both use the full objective, independent of
    # whether the optimizer was still in its distance-only warm-up stage.
    model.eval()
    try:
        train_rms, boundary_max, eikonal_rms, eikonal_max = quality_metrics(
            model, sample_tensor, target_tensor, boundary_tensor
        )
        heldout_rms, _, _, _ = quality_metrics(
            model, heldout_tensor, heldout_target_tensor, boundary_tensor
        )
        final_total_loss = float(
            objective(
                model,
                sample_tensor,
                target_tensor,
                boundary_tensor,
                offset_tensor,
                offset_target_tensor,
                box_tensor,
                box_target_tensor,
                length_scale=length_scale,
                config=config,
                eikonal_weight=config.eikonal_weight,
                create_graph=False,
            ).detach().cpu()
        )
    finally:
        model.train(was_training)
    terminal_tolerances_met = (
        heldout_rms <= config.distance_rms_tolerance_m
        and boundary_max <= config.boundary_max_tolerance_m
        and eikonal_rms <= config.eikonal_rms_tolerance
    )
    if terminal_tolerances_met and not converged:
        converged = True
        stop_reason = "distance_boundary_and_eikonal_tolerances_at_final_state"
    elif not terminal_tolerances_met and converged:
        converged = False
        stop_reason = "best_full_objective_state_failed_tolerances"
    if isinstance(model, SmoothMLPSDF2D):
        model.trained_against_signed_distance = terminal_tolerances_met
    return NeuralRedistanceResult(
        converged=converged,
        steps=len(history),
        stop_reason=stop_reason,
        initial_total_loss=initial_total_loss,
        final_total_loss=final_total_loss,
        final_distance_rms_m=train_rms,
        final_heldout_distance_rms_m=heldout_rms,
        final_boundary_max_abs_m=boundary_max,
        final_eikonal_rms=eikonal_rms,
        final_eikonal_maximum_deviation=eikonal_max,
        loss_history=np.asarray(history, dtype=np.float64),
        diagnostics={
            **distance_diagnostics,
            "polygon_node_count": float(curve.num_nodes),
            "training_sample_count": float(uniform.shape[0]),
            "boundary_sample_count": float(boundary_points.shape[0]),
            "boundary_oversampling_factor": float(
                config.boundary_oversampling_factor
            ),
            "normal_offset_sample_count": float(offset_points.shape[0]),
            "box_boundary_sample_count": float(box_points.shape[0]),
            "heldout_sample_count": float(heldout.shape[0]),
            "length_scale_m": length_scale,
            "best_full_objective_step": float(best_full_loss_step),
            "best_full_objective_loss": best_full_loss,
        },
    )


__all__ = [
    "NeuralRedistanceConfig",
    "NeuralRedistanceResult",
    "SmoothMLPSDF2D",
    "redistance_neural_sdf_to_curve",
    "signed_distance_to_curve_polygon",
]
