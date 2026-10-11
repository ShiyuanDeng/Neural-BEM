"""Minimal IBIM Neural-SDF inverse loop for single-circle B-scan experiments."""

from __future__ import annotations

import importlib
from dataclasses import dataclass, replace
from time import perf_counter
from typing import Callable

import numpy as np
import torch

from config import simulation_config as cfg

from .ibim_geometry import (
    ImplicitBoundaryBand2D,
    ImplicitBoundarySamples2D,
    build_implicit_boundary_band,
    compress_implicit_boundary_band,
)
from .ibim_tmz_adjoint import (
    ImplicitTMzBscanAdjointResult,
    ibim_bscan_leading_order_normal_shape_gradient,
    ibim_shape_gradient_surrogate_loss,
    prepare_ibim_bscan_adjoint_context,
)
from .neural_sdf import (
    SirenSDF2D,
    circle_signed_distance,
    eikonal_loss,
    laplacian_loss,
    sample_uniform_points,
)
from .materials import Material

__all__ = [
    "IBIMInverseConfig",
    "IBIMInverseIteration",
    "IBIMInverseResult",
    "extract_ibim_boundary_band",
    "extract_ibim_boundary_samples",
    "build_single_circle_bscan_benchmark_config",
    "build_single_circle_bscan_benchmark_stage_schedule",
    "build_single_circle_bscan_smoke_config",
    "build_single_circle_bscan_stage_schedule",
    "compute_bscan_quality_metrics",
    "compute_boundary_geometry_metrics",
    "initialize_sdf_with_circle",
    "resolve_ibim_assembly_backend",
    "run_ibim_bscan_inverse",
    "run_ibim_single_circle_bscan_inverse",
]


_IBIMInitializer = Callable[[SirenSDF2D, "IBIMInverseConfig"], np.ndarray]
_IBIMProgressCallback = Callable[[int, int, str, dict[str, float]], None]
_SHAPE_GRADIENT_FALLBACKS = frozenset({"error", "finite_difference"})


def _validate_shape_gradient_fallback(value: str) -> str:
    if value not in _SHAPE_GRADIENT_FALLBACKS:
        choices = ", ".join(sorted(_SHAPE_GRADIENT_FALLBACKS))
        raise ValueError(f"shape_gradient_fallback must be one of: {choices}.")
    return value


@dataclass(frozen=True)
class IBIMInverseConfig:
    """Configuration for the single-circle IBIM inverse loop."""

    bounds: tuple[tuple[float, float], tuple[float, float]]
    grid_shape: tuple[int, int] = (129, 129)
    band_half_width: float | None = None
    delta_half_width: float | None = None
    merge_distance: float | None = None
    offset_distance: float | None = None
    num_initialization_steps: int = 300
    initialization_batch_size: int = 2048
    initialization_learning_rate: float = 2.0e-4
    num_inverse_steps: int = 10
    inverse_learning_rate: float = 5.0e-6
    num_regularization_points: int = 1024
    eikonal_weight: float = 1.0e-2
    laplacian_weight: float = 1.0e-6
    boundary_consistency_weight: float = 1.0e-2
    time_gate_start: float | None = None
    bscan_time_weights: np.ndarray | None = None
    use_strict_quadrature: bool = False
    formulation: str | None = "muller"
    normal_derivative_scheme: str | None = "analytic_extrapolated"
    scan_position_stride: int = 4
    gradient_clip_norm: float | None = 1.0
    device: str = "cpu"
    dtype: torch.dtype = torch.float32
    seed: int = 0
    reinitialize_model: bool = True
    complex_precision: str = "complex128"
    shape_gradient_fallback: str = "error"

    def __post_init__(self) -> None:
        _validate_shape_gradient_fallback(self.shape_gradient_fallback)


@dataclass(frozen=True)
class IBIMInverseIteration:
    """Logged metrics for one IBIM inverse update."""

    iteration: int
    bscan_loss: float
    surrogate_loss: float
    eikonal_loss: float
    laplacian_loss: float
    boundary_consistency_loss: float
    total_loss: float
    boundary_measure: float
    boundary_measure_strict: float
    mean_radius: float
    shape_gradient_norm: float
    boundary_points: np.ndarray
    boundary_normals: np.ndarray
    boundary_weights: np.ndarray
    boundary_strict_weights: np.ndarray
    adjoint_result: ImplicitTMzBscanAdjointResult
    frequency_losses: np.ndarray | None = None
    timing: dict[str, float] | None = None
    shape_gradient_method: str = "leading_order"


@dataclass(frozen=True)
class IBIMInverseResult:
    """Result bundle for the IBIM inverse prototype."""

    initialization_loss_history: np.ndarray
    initial_boundary_points: np.ndarray
    initial_boundary_normals: np.ndarray
    initial_boundary_weights: np.ndarray
    initial_boundary_strict_weights: np.ndarray
    iterations: tuple[IBIMInverseIteration, ...]
    final_boundary_points: np.ndarray
    final_boundary_normals: np.ndarray
    final_boundary_weights: np.ndarray
    final_boundary_strict_weights: np.ndarray


def build_single_circle_bscan_stage_schedule() -> tuple[tuple[int, int, float], ...]:
    """Return the single-circle IBIM B-scan stage schedule."""

    return (
        (13, 2, 2.0e-6),
        (25, 2, 1.5e-6),
        (50, 1, 1.0e-6),
        (100, 1, 5.0e-7),
    )


def build_single_circle_bscan_benchmark_stage_schedule() -> tuple[tuple[int, int, float], ...]:
    """Return the benchmark schedule for the single-circle IBIM inverse loop."""

    return build_single_circle_bscan_stage_schedule()


def build_single_circle_bscan_smoke_config(
    *,
    device: str,
    seed: int = 7,
    use_strict_quadrature: bool = True,
    time_gate_start: float = 2.0e-9,
) -> IBIMInverseConfig:
    """Construct a stable single-circle smoke config.

    The defaults are tuned to keep the boundary samples dense enough while
    still being lightweight for a quick inverse-loop validation.
    """

    schedule = build_single_circle_bscan_stage_schedule()
    num_inverse_steps = int(sum(step_count for _freqs, step_count, _lr in schedule))
    return IBIMInverseConfig(
        bounds=((0.0, 0.0), (float(cfg.DOMAIN_WIDTH), float(cfg.DOMAIN_HEIGHT))),
        grid_shape=(65, 65),
        band_half_width=0.06,
        delta_half_width=0.03,
        merge_distance=0.018,
        # None defers to _default_trace_offset_distance, which sizes the offset against
        # the merge distance the compression actually used. A fixed value cannot: the
        # boundary is rebuilt every iteration as the SDF moves, and compression may
        # shrink the requested merge_distance by up to 32x to meet its sample floor.
        offset_distance=None,
        num_initialization_steps=10,
        initialization_batch_size=64,
        initialization_learning_rate=2.0e-4,
        num_inverse_steps=num_inverse_steps,
        inverse_learning_rate=3.0e-6,
        num_regularization_points=128,
        eikonal_weight=1.0e-2,
        laplacian_weight=1.0e-6,
        boundary_consistency_weight=5.0e-3,
        time_gate_start=time_gate_start,
        scan_position_stride=8,
        gradient_clip_norm=1.0,
        device=device,
        dtype=torch.float32,
        seed=seed,
        reinitialize_model=True,
        use_strict_quadrature=use_strict_quadrature,
    )


def build_single_circle_bscan_benchmark_config(
    *,
    device: str,
    seed: int = 7,
    use_strict_quadrature: bool = True,
    time_gate_start: float = 2.0e-9,
    scan_position_stride: int = 4,
) -> IBIMInverseConfig:
    """Construct a GPU-benchmark-friendly single-circle config.

    This keeps the validation scene intact but uses a denser sampling stride than
    the smoke helper so the inverse loop exercises the GPU path more realistically.
    """

    benchmark_config = build_single_circle_bscan_smoke_config(
        device=device,
        seed=seed,
        use_strict_quadrature=use_strict_quadrature,
        time_gate_start=time_gate_start,
    )
    return replace(benchmark_config, scan_position_stride=int(scan_position_stride))


def compute_boundary_geometry_metrics(points: np.ndarray) -> dict[str, float]:
    """Compute lightweight geometry diagnostics for a single closed curve."""

    boundary_points = np.asarray(points, dtype=float)
    if boundary_points.ndim != 2 or boundary_points.shape[1] != 2:
        raise ValueError("boundary points must have shape (N, 2)")
    center = np.mean(boundary_points, axis=0)
    radius = np.linalg.norm(boundary_points - center[None, :], axis=1)
    diffs = np.roll(boundary_points, -1, axis=0) - boundary_points
    perimeter = float(np.sum(np.linalg.norm(diffs, axis=1)))
    area = float(
        0.5
        * np.abs(
            np.dot(boundary_points[:, 0], np.roll(boundary_points[:, 1], -1))
            - np.dot(boundary_points[:, 1], np.roll(boundary_points[:, 0], -1))
        )
    )
    return {
        "center_x": float(center[0]),
        "center_y": float(center[1]),
        "mean_radius": float(np.mean(radius)),
        "radius_std": float(np.std(radius)),
        "perimeter": perimeter,
        "area": area,
        "num_points": float(boundary_points.shape[0]),
    }


def compute_bscan_quality_metrics(
    true_bscan: np.ndarray,
    predicted_bscan: np.ndarray,
    time_vector: np.ndarray,
    *,
    gate_start: float = 2.0e-9,
) -> dict[str, float]:
    """Compute robust error diagnostics for a B-scan pair."""

    truth = np.asarray(true_bscan, dtype=float)
    prediction = np.asarray(predicted_bscan, dtype=float)
    if truth.shape != prediction.shape:
        raise ValueError("true and predicted B-scans must have matching shapes")
    time_values = np.asarray(time_vector, dtype=float).reshape(-1)
    if truth.shape[1] != time_values.size:
        raise ValueError("time_vector must match the second axis of the B-scan")

    error = prediction - truth
    gate_mask = time_values >= float(gate_start)
    flat_truth = truth.reshape(-1)
    flat_prediction = prediction.reshape(-1)
    flat_error = error.reshape(-1)
    correlation_all = float(np.corrcoef(flat_truth, flat_prediction)[0, 1]) if flat_truth.size > 1 else 1.0
    if gate_mask.any():
        gate_truth = truth[:, gate_mask].reshape(-1)
        gate_prediction = prediction[:, gate_mask].reshape(-1)
        correlation_gate = (
            float(np.corrcoef(gate_truth, gate_prediction)[0, 1]) if gate_truth.size > 1 else 1.0
        )
        rel_gate = float(np.linalg.norm(error[:, gate_mask]) / max(np.linalg.norm(truth[:, gate_mask]), 1.0e-12))
    else:
        correlation_gate = float("nan")
        rel_gate = float("nan")

    return {
        "relative_error_all": float(np.linalg.norm(flat_error) / max(np.linalg.norm(flat_truth), 1.0e-12)),
        "relative_error_gate": rel_gate,
        "correlation_all": correlation_all,
        "correlation_gate": correlation_gate,
        "error_l2": float(np.linalg.norm(flat_error)),
        "truth_l2": float(np.linalg.norm(flat_truth)),
        "prediction_l2": float(np.linalg.norm(flat_prediction)),
        "gate_start_s": float(gate_start),
        "gate_fraction": float(np.mean(gate_mask)),
    }


def resolve_ibim_assembly_backend(device: str | torch.device) -> str:
    """Select CuPy only when both Torch CUDA and the CuPy package are available."""

    resolved_device = torch.device(device)
    if resolved_device.type != "cuda" or not torch.cuda.is_available():
        return "numpy"
    try:
        importlib.import_module("cupy")
    except Exception:
        return "numpy"
    return "cupy"


def _initialize_cuda_runtime(device: torch.device, *, backend: str) -> None:
    """Force a current CUDA context before any Torch/CuPy backward pass."""

    if device.type != "cuda" or not torch.cuda.is_available():
        return
    index = 0 if device.index is None else int(device.index)
    torch.cuda.set_device(index)
    torch.cuda.init()
    torch.zeros(1, device=device)
    if backend == "cupy":
        cupy = importlib.import_module("cupy")
        cupy.cuda.Device(index).use()


def _evaluate_shape_gradient_with_fallback(
    primary: Callable[[], np.ndarray],
    finite_difference: Callable[[], np.ndarray],
    *,
    policy: str,
) -> tuple[np.ndarray, str]:
    """Evaluate the adjoint gradient, optionally using the explicit debug fallback."""

    fallback_policy = _validate_shape_gradient_fallback(policy)
    try:
        return primary(), "leading_order"
    except Exception as primary_error:
        if fallback_policy == "error":
            raise
        try:
            return finite_difference(), "finite_difference"
        except Exception as fallback_error:
            raise RuntimeError(
                "The leading-order shape gradient and the requested finite-difference "
                f"fallback both failed; the original error was {primary_error!r}."
            ) from fallback_error


def _clone_boundary_with_points(
    boundary: ImplicitBoundarySamples2D,
    points: np.ndarray,
) -> ImplicitBoundarySamples2D:
    """Clone an implicit-boundary sample set with new point coordinates."""

    return replace(
        boundary,
        points=torch.as_tensor(points, dtype=boundary.points.dtype, device=boundary.points.device),
    )


def _estimate_bscan_shape_gradient_finite_difference(
    boundary: ImplicitBoundarySamples2D,
    *,
    source_points: np.ndarray,
    receiver_points: np.ndarray,
    angular_frequencies: float | np.ndarray,
    source_strength: complex | np.ndarray,
    observed_bscan: np.ndarray,
    time_vector: np.ndarray,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    frequency_window: np.ndarray | None,
    time_gate_start: float | None,
    sample_weights: np.ndarray | None,
    offset_distance: float | None,
    use_strict_quadrature: bool,
    formulation: str | None,
    normal_derivative_scheme: str | None,
    backend: str,
    complex_precision: str,
    max_fd_samples: int = 1,
    fd_step: float | None = None,
) -> np.ndarray:
    """Fallback normal-direction shape gradient via a sparse boundary finite difference."""

    source_points_array = np.asarray(source_points, dtype=float)
    receiver_points_array = np.asarray(receiver_points, dtype=float)
    observed_bscan_array = np.asarray(observed_bscan, dtype=float)
    time_vector_array = np.asarray(time_vector, dtype=float)
    angular_frequencies_array = np.asarray(angular_frequencies, dtype=float)
    source_strength_array = np.asarray(source_strength)
    boundary_points = np.asarray(boundary.points.detach().cpu(), dtype=float)
    boundary_normals = np.asarray(boundary.normals.detach().cpu(), dtype=float)
    weight_tensor = boundary.strict_quadrature_weights if use_strict_quadrature else boundary.quadrature_weights
    boundary_weights = np.asarray(weight_tensor.detach().cpu(), dtype=float).reshape(-1)
    num_samples = boundary_points.shape[0]
    shape_gradient = np.zeros(num_samples, dtype=float)
    if num_samples == 0:
        return shape_gradient
    sample_indices = np.linspace(0, num_samples - 1, min(int(max_fd_samples), num_samples), dtype=int)
    base_step = float(fd_step) if fd_step is not None else max(1.0e-4, 0.15 * float(offset_distance or 0.03))
    for sample_index in sample_indices:
        normal = np.asarray(boundary_normals[sample_index], dtype=float)
        normal_norm = float(np.linalg.norm(normal))
        if not np.isfinite(normal_norm) or normal_norm <= 1.0e-12:
            continue
        direction = normal / normal_norm
        perturbed_plus = boundary_points.copy()
        perturbed_minus = boundary_points.copy()
        perturbed_plus[sample_index] = boundary_points[sample_index] + base_step * direction
        perturbed_minus[sample_index] = boundary_points[sample_index] - base_step * direction
        plus_boundary = _clone_boundary_with_points(boundary, perturbed_plus)
        minus_boundary = _clone_boundary_with_points(boundary, perturbed_minus)
        plus_result = prepare_ibim_bscan_adjoint_context(
            plus_boundary,
            source_points_array,
            receiver_points_array,
            angular_frequencies_array,
            source_strength_array,
            observed_bscan_array,
            time_vector=time_vector_array,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            frequency_window=frequency_window,
            time_gate_start=time_gate_start,
            sample_weights=sample_weights,
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            formulation=formulation,
            normal_derivative_scheme=normal_derivative_scheme,
            backend=backend,
            complex_precision=complex_precision,
        )
        minus_result = prepare_ibim_bscan_adjoint_context(
            minus_boundary,
            source_points_array,
            receiver_points_array,
            angular_frequencies_array,
            source_strength_array,
            observed_bscan_array,
            time_vector=time_vector_array,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            frequency_window=frequency_window,
            time_gate_start=time_gate_start,
            sample_weights=sample_weights,
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            formulation=formulation,
            normal_derivative_scheme=normal_derivative_scheme,
            backend=backend,
            complex_precision=complex_precision,
        )
        node_weight = float(boundary_weights[sample_index])
        if abs(node_weight) <= 1.0e-15:
            continue
        node_directional = (plus_result.loss - minus_result.loss) / (2.0 * base_step)
        shape_gradient[sample_index] = node_directional / node_weight
    return shape_gradient


def extract_ibim_boundary_band(
    model: SirenSDF2D,
    config: IBIMInverseConfig,
    *,
    device: torch.device | None = None,
) -> ImplicitBoundaryBand2D:
    """Sample the current SDF on a Cartesian grid and keep the implicit boundary band."""

    resolved_device = torch.device(config.device) if device is None else device
    band_half_width = float(config.band_half_width or 0.06)
    delta_half_width = float(config.delta_half_width or 0.5 * band_half_width)
    last_error: ValueError | None = None
    for scale in (1.0, 1.5, 2.0, 3.0):
        scaled_band_half_width = band_half_width * scale
        scaled_delta_half_width = min(delta_half_width * scale, scaled_band_half_width)
        try:
            return build_implicit_boundary_band(
                model,
                config.bounds,
                grid_shape=config.grid_shape,
                band_half_width=scaled_band_half_width,
                delta_half_width=scaled_delta_half_width,
                device=resolved_device,
                dtype=config.dtype,
            )
        except ValueError as exc:
            if "No sample points fell inside the implicit-boundary narrow band" not in str(exc):
                raise
            last_error = exc
    if last_error is not None:
        raise last_error
    raise ValueError("Failed to extract the implicit-boundary band.")


def extract_ibim_boundary_samples(
    model: SirenSDF2D,
    config: IBIMInverseConfig,
    *,
    device: torch.device | None = None,
    min_samples: int | None = None,
    merge_distance_floor: float | None = None,
) -> ImplicitBoundarySamples2D:
    """Extract a compressed implicit-boundary sample set from the current SDF."""

    resolved_floor = 0.15 * float(config.merge_distance or 0.03) if merge_distance_floor is None else float(merge_distance_floor)
    current_merge_distance = float(config.merge_distance or 0.03)
    final_samples: ImplicitBoundarySamples2D | None = None
    for _ in range(6):
        band = extract_ibim_boundary_band(model, config, device=device)
        final_samples = compress_implicit_boundary_band(
            band,
            merge_distance=current_merge_distance,
        )
        if min_samples is None or final_samples.num_samples >= int(min_samples):
            return final_samples
        if current_merge_distance <= resolved_floor:
            return final_samples
        current_merge_distance = max(current_merge_distance * 0.65, resolved_floor)
    assert final_samples is not None
    return final_samples


def initialize_sdf_with_circle(
    model: torch.nn.Module,
    *,
    center: tuple[float, float],
    radius: float,
    config: IBIMInverseConfig,
) -> np.ndarray:
    """Warm-start a Neural SDF to an analytic circle with supervised samples."""

    return _initialize_sdf_with_target(
        model,
        target_sdf_fn=lambda sample_points: circle_signed_distance(sample_points, center=center, radius=radius),
        config=config,
    )


def run_ibim_single_circle_bscan_inverse(
    model: SirenSDF2D,
    *,
    source_points: np.ndarray,
    receiver_points: np.ndarray,
    angular_frequencies: float | np.ndarray,
    source_strength: complex | np.ndarray,
    observed_bscan: np.ndarray,
    time_vector: np.ndarray,
    config: IBIMInverseConfig,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    frequency_window: np.ndarray | None = None,
    initializer: _IBIMInitializer | None = None,
    initial_circle_center: tuple[float, float] | None = None,
    initial_circle_radius: float | None = None,
    progress_callback: _IBIMProgressCallback | None = None,
    progress_label: str = "single-circle benchmark",
) -> IBIMInverseResult:
    """Run the minimal single-circle IBIM inverse loop."""

    source_points_array = np.asarray(source_points, dtype=float)
    receiver_points_array = np.asarray(receiver_points, dtype=float)
    observed_bscan_array = np.asarray(observed_bscan, dtype=float)
    time_vector_array = np.asarray(time_vector, dtype=float)
    device = torch.device(config.device)
    backend = resolve_ibim_assembly_backend(device)
    _initialize_cuda_runtime(device, backend=backend)

    torch.manual_seed(int(config.seed))
    np.random.seed(int(config.seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(config.seed))

    model.to(device=device, dtype=config.dtype)
    if config.reinitialize_model:
        if initializer is not None:
            initialization_history = np.asarray(initializer(model, config), dtype=float)
        else:
            if initial_circle_center is None or initial_circle_radius is None:
                raise ValueError(
                    "When reinitialize_model=True and no initializer is provided, "
                    "initial_circle_center and initial_circle_radius must be specified."
                )
            initialization_history = initialize_sdf_with_circle(
                model,
                center=initial_circle_center,
                radius=initial_circle_radius,
                config=config,
            )
    else:
        initialization_history = np.empty((0,), dtype=float)

    min_boundary_samples = max(48, int(0.75 * max(config.grid_shape)))
    initial_boundary = extract_ibim_boundary_samples(
        model,
        config,
        device=device,
        min_samples=min_boundary_samples,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=config.inverse_learning_rate)
    iterations: list[IBIMInverseIteration] = []

    for iteration in range(int(config.num_inverse_steps)):
        iteration_start = perf_counter()

        geometry_start = perf_counter()
        boundary = extract_ibim_boundary_samples(
            model,
            config,
            device=device,
            min_samples=min_boundary_samples,
        )
        geometry_time = perf_counter() - geometry_start

        adjoint_context_start = perf_counter()
        adjoint_result = prepare_ibim_bscan_adjoint_context(
            boundary,
            source_points_array,
            receiver_points_array,
            angular_frequencies,
            source_strength,
            observed_bscan_array,
            time_vector=time_vector_array,
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            frequency_window=frequency_window,
            time_gate_start=config.time_gate_start,
            sample_weights=config.bscan_time_weights,
            offset_distance=config.offset_distance,
            use_strict_quadrature=config.use_strict_quadrature,
            formulation=config.formulation,
            normal_derivative_scheme=config.normal_derivative_scheme,
            backend=backend,
            complex_precision=config.complex_precision,
        )
        adjoint_context_time = perf_counter() - adjoint_context_start
        shape_gradient_start = perf_counter()
        shape_gradient, shape_gradient_method = _evaluate_shape_gradient_with_fallback(
            lambda: ibim_bscan_leading_order_normal_shape_gradient(
                adjoint_result,
                boundary,
                use_strict_quadrature=config.use_strict_quadrature,
            ),
            lambda: _estimate_bscan_shape_gradient_finite_difference(
                boundary,
                source_points=source_points_array,
                receiver_points=receiver_points_array,
                angular_frequencies=angular_frequencies,
                source_strength=source_strength,
                observed_bscan=observed_bscan_array,
                time_vector=time_vector_array,
                exterior=exterior,
                interior=interior,
                eps0=eps0,
                mu0=mu0,
                frequency_window=frequency_window,
                time_gate_start=config.time_gate_start,
                sample_weights=config.bscan_time_weights,
                offset_distance=config.offset_distance,
                use_strict_quadrature=config.use_strict_quadrature,
                formulation=config.formulation,
                normal_derivative_scheme=config.normal_derivative_scheme,
                backend=backend,
                complex_precision=config.complex_precision,
            ),
            policy=config.shape_gradient_fallback,
        )
        shape_gradient_time = perf_counter() - shape_gradient_start

        optimizer_start = perf_counter()
        optimizer.zero_grad(set_to_none=True)
        quadrature_weights = (
            boundary.strict_quadrature_weights if config.use_strict_quadrature else boundary.quadrature_weights
        )
        surrogate = ibim_shape_gradient_surrogate_loss(
            model,
            boundary,
            torch.tensor(shape_gradient, device=device, dtype=config.dtype),
            quadrature_weights=quadrature_weights,
        )
        regularization_points = sample_uniform_points(
            config.bounds,
            config.num_regularization_points,
            device=device,
            dtype=config.dtype,
        )
        regularization_start = perf_counter()
        regularization_gradients = model.spatial_gradient(regularization_points)
        regularization_laplacian = model.laplacian(regularization_points)
        eikonal_penalty = eikonal_loss(regularization_gradients)
        laplacian_penalty = laplacian_loss(regularization_laplacian)
        boundary_points = boundary.points.detach().to(device=device, dtype=config.dtype)
        boundary_consistency = torch.mean(model(boundary_points) ** 2)
        regularization_time = perf_counter() - regularization_start
        total_loss = (
            surrogate
            + config.eikonal_weight * eikonal_penalty
            + config.laplacian_weight * laplacian_penalty
            + config.boundary_consistency_weight * boundary_consistency
        )
        total_loss.backward()
        if config.gradient_clip_norm is not None:
            torch.nn.utils.clip_grad_norm_(model.parameters(), float(config.gradient_clip_norm))
        optimizer.step()
        optimizer_time = perf_counter() - optimizer_start

        boundary_points_np = np.asarray(boundary.points.detach().cpu(), dtype=float)
        boundary_normals_np = np.asarray(boundary.normals.detach().cpu(), dtype=float)
        boundary_weights_np = np.asarray(boundary.quadrature_weights.detach().cpu(), dtype=float).reshape(-1)
        boundary_strict_weights_np = np.asarray(boundary.strict_quadrature_weights.detach().cpu(), dtype=float).reshape(-1)
        center = np.mean(boundary_points_np, axis=0)
        mean_radius = float(np.mean(np.linalg.norm(boundary_points_np - center[None, :], axis=1)))
        frequency_losses = np.asarray([context.loss for context in adjoint_result.per_frequency_contexts], dtype=float)
        iteration_timing = {
            "iteration_time_s": perf_counter() - iteration_start,
            "geometry_time_s": geometry_time,
            "adjoint_context_time_s": adjoint_context_time,
            "shape_gradient_time_s": shape_gradient_time,
            "shape_gradient_method": 0.0 if shape_gradient_method == "leading_order" else 1.0,
            "ibim_total_time_s": adjoint_context_time + shape_gradient_time,
            "regularization_time_s": regularization_time,
            "nn_update_time_s": optimizer_time,
        }
        iterations.append(
            IBIMInverseIteration(
                iteration=iteration,
                bscan_loss=float(adjoint_result.loss),
                surrogate_loss=float(surrogate.detach().cpu()),
                eikonal_loss=float(eikonal_penalty.detach().cpu()),
                laplacian_loss=float(laplacian_penalty.detach().cpu()),
                boundary_consistency_loss=float(boundary_consistency.detach().cpu()),
                total_loss=float(total_loss.detach().cpu()),
                boundary_measure=float(boundary.boundary_measure(strict=False).detach().cpu()),
                boundary_measure_strict=float(boundary.boundary_measure(strict=True).detach().cpu()),
                mean_radius=mean_radius,
                shape_gradient_norm=float(np.linalg.norm(shape_gradient)),
                boundary_points=boundary_points_np,
                boundary_normals=boundary_normals_np,
                boundary_weights=boundary_weights_np,
                boundary_strict_weights=boundary_strict_weights_np,
                adjoint_result=adjoint_result,
                frequency_losses=frequency_losses,
                timing=iteration_timing,
                shape_gradient_method=shape_gradient_method,
            )
        )
        if progress_callback is not None:
            progress_callback(
                iteration + 1,
                int(config.num_inverse_steps),
                progress_label,
                iteration_timing,
            )

    final_boundary = extract_ibim_boundary_samples(
        model,
        config,
        device=device,
        min_samples=min_boundary_samples,
    )
    return IBIMInverseResult(
        initialization_loss_history=initialization_history,
        initial_boundary_points=np.asarray(initial_boundary.points.detach().cpu(), dtype=float),
        initial_boundary_normals=np.asarray(initial_boundary.normals.detach().cpu(), dtype=float),
        initial_boundary_weights=np.asarray(initial_boundary.quadrature_weights.detach().cpu(), dtype=float).reshape(-1),
        initial_boundary_strict_weights=np.asarray(
            initial_boundary.strict_quadrature_weights.detach().cpu(),
            dtype=float,
        ).reshape(-1),
        iterations=tuple(iterations),
        final_boundary_points=np.asarray(final_boundary.points.detach().cpu(), dtype=float),
        final_boundary_normals=np.asarray(final_boundary.normals.detach().cpu(), dtype=float),
        final_boundary_weights=np.asarray(final_boundary.quadrature_weights.detach().cpu(), dtype=float).reshape(-1),
        final_boundary_strict_weights=np.asarray(
            final_boundary.strict_quadrature_weights.detach().cpu(),
            dtype=float,
        ).reshape(-1),
    )


def run_ibim_bscan_inverse(
    model: SirenSDF2D,
    *,
    source_points: np.ndarray,
    receiver_points: np.ndarray,
    angular_frequencies: float | np.ndarray,
    source_strength: complex | np.ndarray,
    observed_bscan: np.ndarray,
    time_vector: np.ndarray,
    config: IBIMInverseConfig,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    frequency_window: np.ndarray | None = None,
    initializer: _IBIMInitializer | None = None,
    initial_circle_center: tuple[float, float] | None = None,
    initial_circle_radius: float | None = None,
    progress_callback: _IBIMProgressCallback | None = None,
    progress_label: str = "single-circle benchmark",
) -> IBIMInverseResult:
    """Alias for the single-circle IBIM inverse loop."""

    return run_ibim_single_circle_bscan_inverse(
        model,
        source_points=source_points,
        receiver_points=receiver_points,
        angular_frequencies=angular_frequencies,
        source_strength=source_strength,
        observed_bscan=observed_bscan,
        time_vector=time_vector,
        config=config,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        frequency_window=frequency_window,
        initializer=initializer,
        initial_circle_center=initial_circle_center,
        initial_circle_radius=initial_circle_radius,
        progress_callback=progress_callback,
        progress_label=progress_label,
    )


def _initialize_sdf_with_target(
    model: torch.nn.Module,
    *,
    target_sdf_fn: Callable[[torch.Tensor], torch.Tensor],
    config: IBIMInverseConfig,
) -> np.ndarray:
    """Warm-start a Neural SDF to a target signed-distance function."""

    device = torch.device(config.device)
    torch.manual_seed(int(config.seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(config.seed))
    model.to(device=device, dtype=config.dtype)
    if hasattr(model, "reset_parameters"):
        model.reset_parameters()
    optimizer = torch.optim.Adam(model.parameters(), lr=config.initialization_learning_rate)
    loss_history: list[float] = []
    for _ in range(int(config.num_initialization_steps)):
        optimizer.zero_grad(set_to_none=True)
        sample_points = sample_uniform_points(
            config.bounds,
            config.initialization_batch_size,
            device=device,
            dtype=config.dtype,
        )
        predicted_sdf = model(sample_points)
        target_sdf = target_sdf_fn(sample_points)
        gradients = model.spatial_gradient(sample_points)
        loss = torch.mean((predicted_sdf - target_sdf) ** 2) + 1.0e-1 * eikonal_loss(gradients)
        loss.backward()
        optimizer.step()
        loss_history.append(float(loss.detach().cpu()))
    return np.asarray(loss_history, dtype=float)
