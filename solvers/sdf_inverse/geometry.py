"""Shared SDF-to-ordered-boundary geometry for inverse forward models.

The extraction and Method-B fit intentionally run outside either BEM package.
Both forward solvers therefore consume the same immutable
:class:`ordered_boundary.PeriodicCurve2D`; the MOD adapter below only changes
the container and array type used to present those nodes to its legacy API.
"""

from __future__ import annotations

from dataclasses import dataclass
import operator
from time import perf_counter
from typing import Any, TYPE_CHECKING

import numpy as np

from ordered_boundary import BoundaryValidationConfig, PeriodicCurve2D
from sdf_to_ordered_boundary import (
    ArcLengthConfig,
    FrontendConfig,
    MethodBConfig,
    ProjectionConfig,
    TorchImplicitField2D,
    fit_method_b,
    prepare_single_component,
)

if TYPE_CHECKING:
    from gpr_bem_mod import ImplicitBoundarySamples2D


Bounds2D = tuple[tuple[float, float], tuple[float, float]]


def _canonical_bounds(bounds: Any) -> Bounds2D:
    if np.iscomplexobj(bounds):
        raise ValueError("bounds must be real-valued.")
    try:
        values = np.asarray(bounds, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "bounds must be ((xmin, ymin), (xmax, ymax)) with finite values."
        ) from exc
    if values.shape != (2, 2) or not np.all(np.isfinite(values)):
        raise ValueError(
            "bounds must be ((xmin, ymin), (xmax, ymax)) with finite values."
        )
    if np.any(values[1] <= values[0]):
        raise ValueError("Upper bounds must be strictly greater than lower bounds.")
    return (
        (float(values[0, 0]), float(values[0, 1])),
        (float(values[1, 0]), float(values[1, 1])),
    )


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


def _finite_nonnegative(value: Any, *, name: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number, not bool.")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a real number.") from exc
    if not np.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


@dataclass(frozen=True)
class OrderedSDFGeometryConfig:
    """Validated extraction, fitting, and discretisation resolutions.

    ``bounds`` uses ``((xmin, ymin), (xmax, ymax))`` and ``grid_shape`` uses
    ``(ny, nx)``.  Method B needs at least ``2 * bandwidth + 1`` projected
    samples.  The node grid additionally needs one spare point and an even
    count for Kress quadrature.
    """

    bounds: Bounds2D
    grid_shape: tuple[int, int] = (97, 97)
    projected_samples: int = 64
    bandwidth: int = 10
    num_nodes: int = 64
    arclength_dense_resolution: int = 512
    validation_resolution: int = 256

    def __post_init__(self) -> None:
        bounds = _canonical_bounds(self.bounds)
        try:
            grid_count = len(self.grid_shape)
        except TypeError as exc:
            raise TypeError("grid_shape must be a two-element sequence (ny, nx).") from exc
        if grid_count != 2:
            raise ValueError("grid_shape must be a two-element sequence (ny, nx).")
        grid_shape = (
            _integer_at_least(self.grid_shape[0], name="grid_shape[0]", minimum=2),
            _integer_at_least(self.grid_shape[1], name="grid_shape[1]", minimum=2),
        )
        bandwidth = _integer_at_least(self.bandwidth, name="bandwidth", minimum=1)
        projected_samples = _integer_at_least(
            self.projected_samples, name="projected_samples", minimum=8
        )
        if projected_samples < 2 * bandwidth + 1:
            raise ValueError(
                "projected_samples must be at least 2 * bandwidth + 1 for "
                "the Method-B Fourier fit."
            )
        num_nodes = _integer_at_least(self.num_nodes, name="num_nodes", minimum=8)
        if num_nodes % 2:
            raise ValueError("num_nodes must be even for Kress quadrature.")
        if num_nodes < 2 * bandwidth + 2:
            raise ValueError(
                "num_nodes must be at least 2 * bandwidth + 2 to sample the "
                "fitted Fourier curve without aliasing."
            )
        dense_resolution = _integer_at_least(
            self.arclength_dense_resolution,
            name="arclength_dense_resolution",
            minimum=16,
        )
        validation_resolution = _integer_at_least(
            self.validation_resolution,
            name="validation_resolution",
            minimum=16,
        )
        minimum_fourier_resolution = 2 * bandwidth + 2
        if dense_resolution < minimum_fourier_resolution:
            raise ValueError(
                "arclength_dense_resolution must be at least 2 * bandwidth + 2."
            )
        if validation_resolution < minimum_fourier_resolution:
            raise ValueError(
                "validation_resolution must be at least 2 * bandwidth + 2."
            )

        object.__setattr__(self, "bounds", bounds)
        object.__setattr__(self, "grid_shape", grid_shape)
        object.__setattr__(self, "projected_samples", projected_samples)
        object.__setattr__(self, "bandwidth", bandwidth)
        object.__setattr__(self, "num_nodes", num_nodes)
        object.__setattr__(self, "arclength_dense_resolution", dense_resolution)
        object.__setattr__(self, "validation_resolution", validation_resolution)


@dataclass(frozen=True)
class OrderedSDFGeometryBuild:
    """One reusable ordered curve and auditable preprocessing diagnostics."""

    curve: PeriodicCurve2D
    frontend_seconds: float
    fit_seconds: float
    discretize_seconds: float
    total_seconds: float
    maximum_projected_sdf_residual: float
    maximum_curve_sdf_residual: float
    maximum_normalized_curve_residual: float
    speed_ratio: float
    config: OrderedSDFGeometryConfig

    def __post_init__(self) -> None:
        if not isinstance(self.curve, PeriodicCurve2D):
            raise TypeError("curve must be an ordered_boundary.PeriodicCurve2D.")
        if not isinstance(self.config, OrderedSDFGeometryConfig):
            raise TypeError("config must be an OrderedSDFGeometryConfig.")
        for name in (
            "frontend_seconds",
            "fit_seconds",
            "discretize_seconds",
            "total_seconds",
            "maximum_projected_sdf_residual",
            "maximum_curve_sdf_residual",
            "maximum_normalized_curve_residual",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )
        speed_ratio = _finite_nonnegative(self.speed_ratio, name="speed_ratio")
        if speed_ratio < 1.0:
            raise ValueError("speed_ratio must be at least one.")
        object.__setattr__(self, "speed_ratio", speed_ratio)


def _torch_module():
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - Torch is a project dependency
        raise ImportError("Ordered SDF geometry requires the 'torch' dependency.") from exc
    return torch


def _model_tensor_options(model: Any) -> tuple[Any, Any]:
    """Infer evaluation device and floating dtype from a module's state."""

    torch = _torch_module()
    reference = None
    for accessor_name in ("parameters", "buffers"):
        accessor = getattr(model, accessor_name, None)
        if not callable(accessor):
            continue
        try:
            reference = next(iter(accessor()))
        except StopIteration:
            continue
        if reference is not None:
            break
    if reference is None:
        return torch.device("cpu"), torch.get_default_dtype()
    if not isinstance(reference, torch.Tensor):
        raise TypeError("Model parameters and buffers must be torch.Tensor objects.")
    if not reference.is_floating_point():
        raise TypeError("The model's inferred evaluation dtype must be floating-point.")
    return reference.device, reference.dtype


def _projection_residual_tolerance(dtype: Any) -> float:
    """Resolve a meaningful zero-set tolerance for the model's arithmetic."""

    torch = _torch_module()
    try:
        machine_epsilon = float(torch.finfo(dtype).eps)
    except TypeError as exc:
        raise TypeError("The model's inferred dtype must support floating arithmetic.") from exc
    return max(1.0e-10, 8.0 * machine_epsilon)


def build_ordered_sdf_geometry(
    model: Any,
    config: OrderedSDFGeometryConfig,
) -> OrderedSDFGeometryBuild:
    """Extract one smooth zero-set component and fit its ordered Method-B curve.

    The model is evaluated in the device and dtype inferred from its first
    parameter or buffer.  Parameter-free callables use Torch's default dtype
    on CPU.  Multiple, missing, open, boundary-touching, self-intersecting, or
    non-regular components fail through the front-end's explicit exceptions;
    no component or representation fallback is performed.
    """

    if not callable(model):
        raise TypeError("model must be callable on torch tensors of shape (n, 2).")
    if not isinstance(config, OrderedSDFGeometryConfig):
        raise TypeError("config must be an OrderedSDFGeometryConfig.")

    device, dtype = _model_tensor_options(model)
    source_identifier = f"{type(model).__module__}.{type(model).__qualname__}"
    component_id = "ordered-sdf-component"
    total_started = perf_counter()
    field = TorchImplicitField2D(
        model,
        device=device,
        dtype=dtype,
        name=source_identifier,
        sign_convention="negative_inside",
    )

    frontend_started = perf_counter()
    frontend = prepare_single_component(
        field,
        FrontendConfig(
            bounds=config.bounds,
            grid_shape=config.grid_shape,
            projected_samples=config.projected_samples,
            projection=ProjectionConfig(
                residual_tolerance=_projection_residual_tolerance(dtype)
            ),
        ),
    )
    frontend_seconds = perf_counter() - frontend_started
    component = frontend.single_component
    if not component.projection_passes:
        raise RuntimeError("The SDF front end returned no zero-set projection diagnostics.")
    projection_residual = float(
        component.projection_passes[-1].maximum_residual
    )

    method_config = MethodBConfig(
        bandwidth=config.bandwidth,
        arclength=ArcLengthConfig(
            dense_resolution=config.arclength_dense_resolution,
            refit_sample_count=None,
            validation_resolution=config.validation_resolution,
        ),
        validation=BoundaryValidationConfig(
            num_samples_per_component=config.validation_resolution
        ),
    )
    fit_started = perf_counter()
    fit = fit_method_b(
        component,
        config=method_config,
        component_id=component_id,
        source_identifier=source_identifier,
        projection_residual=projection_residual,
    )
    fit_seconds = perf_counter() - fit_started
    if fit.status != "success":
        reason = fit.failure_reason or "no failure reason was supplied"
        raise RuntimeError(f"Method B failed to fit the zero set: {reason}.")
    if fit.parameterization is None:
        raise RuntimeError("Method B returned no periodic parameterization.")

    discretize_started = perf_counter()
    curve = fit.parameterization.discretize(config.num_nodes, require_even=True)
    discretize_seconds = perf_counter() - discretize_started

    # PeriodicCurve2D owns read-only NumPy arrays.  Copy them before the Torch
    # adapter sees them to avoid exposing immutable storage through a tensor.
    curve_values = np.asarray(
        field.value(np.array(curve.points, dtype=np.float64, copy=True)),
        dtype=np.float64,
    )
    expected_shape = (curve.num_nodes,)
    if curve_values.shape != expected_shape:
        raise RuntimeError(
            "The model returned an unexpected value shape while validating the "
            f"ordered curve: expected {expected_shape}, received {curve_values.shape}."
        )
    if not np.all(np.isfinite(curve_values)):
        raise ValueError("The model returned non-finite values on the ordered curve.")
    curve_gradients = np.asarray(
        field.gradient(np.array(curve.points, dtype=np.float64, copy=True)),
        dtype=np.float64,
    )
    if curve_gradients.shape != (curve.num_nodes, 2) or not np.all(
        np.isfinite(curve_gradients)
    ):
        raise ValueError("The model returned invalid gradients on the ordered curve.")
    curve_gradient_norms = np.linalg.norm(curve_gradients, axis=1)
    if np.any(curve_gradient_norms <= np.finfo(np.float64).tiny):
        raise ValueError("The ordered zero contour must have nonzero field gradient.")
    minimum_speed = float(np.min(curve.speeds))
    maximum_speed = float(np.max(curve.speeds))
    if minimum_speed <= 0.0 or not np.isfinite(maximum_speed):
        raise ValueError("The ordered curve must have finite positive speed.")

    return OrderedSDFGeometryBuild(
        curve=curve,
        frontend_seconds=float(frontend_seconds),
        fit_seconds=float(fit_seconds),
        discretize_seconds=float(discretize_seconds),
        total_seconds=float(perf_counter() - total_started),
        maximum_projected_sdf_residual=projection_residual,
        maximum_curve_sdf_residual=float(np.max(np.abs(curve_values))),
        maximum_normalized_curve_residual=float(
            np.max(np.abs(curve_values) / curve_gradient_norms)
        ),
        speed_ratio=maximum_speed / minimum_speed,
        config=config,
    )


def ordered_curve_to_mod_boundary(
    curve: PeriodicCurve2D,
    bounds: Bounds2D,
) -> ImplicitBoundarySamples2D:
    """Present an ordered curve to MOD without changing its nodes or weights.

    Ordinary and strict MOD quadrature both receive the curve's periodic
    trapezoid arc-length weights.  All tensors are independent CPU float64
    copies, and ``merge_distance`` is the mean node arc weight because there
    is no implicit-cloud merge operation in this adapter.
    """

    if not isinstance(curve, PeriodicCurve2D):
        raise TypeError("curve must be an ordered_boundary.PeriodicCurve2D.")
    canonical_bounds = _canonical_bounds(bounds)
    from gpr_bem_mod import ImplicitBoundarySamples2D

    torch = _torch_module()
    points = torch.tensor(
        np.array(curve.points, dtype=np.float64, copy=True), dtype=torch.float64
    )
    normals = torch.tensor(
        np.array(curve.normals, dtype=np.float64, copy=True), dtype=torch.float64
    )
    weights = torch.tensor(
        np.array(curve.arc_length_weights, dtype=np.float64, copy=True),
        dtype=torch.float64,
    ).reshape(curve.num_nodes, 1)
    merge_distance = float(np.mean(curve.arc_length_weights))
    if not np.isfinite(merge_distance) or merge_distance <= 0.0:
        raise ValueError("The ordered curve must have finite positive arc weights.")
    return ImplicitBoundarySamples2D(
        points=points,
        normals=normals,
        quadrature_weights=weights.clone(),
        strict_quadrature_weights=weights.clone(),
        merge_distance=merge_distance,
        source_num_samples=curve.num_nodes,
        bounds=canonical_bounds,
        level=0.0,
    )


__all__ = [
    "OrderedSDFGeometryBuild",
    "OrderedSDFGeometryConfig",
    "build_ordered_sdf_geometry",
    "ordered_curve_to_mod_boundary",
]
