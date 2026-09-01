"""bem_gradients foundations for implicit-boundary TMz experiments."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.special import hankel1
import torch

from .backend import AssemblyBackend, get_assembly_backend
from .ibim_geometry import ImplicitBoundaryBand2D, ImplicitBoundarySamples2D
from .ibim_tmz_forward import (
    implicit_double_layer_potential_from_band,
    implicit_single_layer_potential_from_band,
)
from .ibim_shape_derivative_prototype import (
    full_system_action_directional_derivative_from_wavenumbers,
    single_sample_system_action_directional_derivative_from_wavenumbers,
)
from .ibim_tmz_system import (
    ImplicitTMzForwardResult,
    ImplicitTMzMultiFrequencyForwardResult,
    solve_ibim_tmz_frequency_response,
    solve_ibim_tmz_total_field_batch,
)
from .materials import Material
from .neural_sdf import shape_gradient_surrogate_loss
from .signal_processing import bscan_from_frequency_response, trapz_weights as _trapz_weights

__all__ = [
    "ImplicitTMzAdjointContext",
    "ImplicitTMzMultiFrequencyAdjointResult",
    "ImplicitTMzBscanAdjointResult",
    "ImplicitTMzLeadingOrderDirectionalResult",
    "ImplicitTMzMultiFrequencyLeadingOrderDirectionalResult",
    "ImplicitTMzBscanLeadingOrderDirectionalResult",
    "build_ibim_receiver_operator_rows",
    "complex_l2_data_misfit",
    "ibim_adjoint_context_from_receiver_dual",
    "ibim_bscan_leading_order_point_directional_gradient",
    "ibim_bscan_leading_order_normal_shape_gradient",
    "ibim_leading_order_point_directional_gradient",
    "ibim_leading_order_normal_shape_gradient",
    "ibim_multifrequency_leading_order_point_directional_gradient",
    "ibim_multifrequency_leading_order_normal_shape_gradient",
    "ibim_shape_gradient_surrogate_loss",
    "prepare_ibim_adjoint_context",
    "prepare_ibim_multifrequency_adjoint_context",
    "prepare_ibim_bscan_adjoint_context",
]


@dataclass(frozen=True)
class ImplicitTMzAdjointContext:
    """Single-frequency implicit-boundary discrete adjoint context."""

    loss: float
    residual: np.ndarray
    receiver_dual: np.ndarray
    state_vector: np.ndarray
    adjoint_vector: np.ndarray
    system_matrix: np.ndarray
    adjoint_rhs: np.ndarray
    single_layer_rows: np.ndarray
    double_layer_rows: np.ndarray
    forward: ImplicitTMzForwardResult


@dataclass(frozen=True)
class ImplicitTMzMultiFrequencyAdjointResult:
    """Multi-frequency aggregation of single-frequency IBIM adjoint contexts."""

    angular_frequencies: np.ndarray
    frequency_weights: np.ndarray
    loss: float
    loss_by_frequency: np.ndarray
    frequency_response: np.ndarray
    forwards: tuple[ImplicitTMzForwardResult, ...]
    per_frequency_contexts: tuple[ImplicitTMzAdjointContext, ...]


@dataclass(frozen=True)
class ImplicitTMzBscanAdjointResult:
    """Time-domain B-scan adjoint data for implicit-boundary TMz."""

    angular_frequencies: np.ndarray
    time_vector: np.ndarray
    frequency_window: np.ndarray
    time_gate_start: float | None
    time_gate_mask: np.ndarray
    time_sample_weights: np.ndarray
    loss: float
    frequency_response: np.ndarray
    weighted_frequency_response: np.ndarray
    bscan: np.ndarray
    residual: np.ndarray
    frequency_response_dual: np.ndarray
    forwards: tuple[ImplicitTMzForwardResult, ...]
    per_frequency_contexts: tuple[ImplicitTMzAdjointContext, ...]


@dataclass(frozen=True)
class ImplicitTMzLeadingOrderDirectionalResult:
    """Leading-order point-motion directional derivative for one IBIM frequency solve."""

    directional_gradient: float
    rhs_directional: np.ndarray
    system_action_directional: np.ndarray
    state_sensitivity_rhs: np.ndarray
    receiver_directional: np.ndarray


@dataclass(frozen=True)
class ImplicitTMzMultiFrequencyLeadingOrderDirectionalResult:
    """Weighted multifrequency aggregation of leading-order IBIM point derivatives."""

    directional_gradient: float
    angular_frequencies: np.ndarray
    frequency_weights: np.ndarray
    per_frequency_results: tuple[ImplicitTMzLeadingOrderDirectionalResult, ...]


@dataclass(frozen=True)
class ImplicitTMzBscanLeadingOrderDirectionalResult:
    """Time-domain B-scan aggregation of leading-order IBIM point derivatives."""

    directional_gradient: float
    angular_frequencies: np.ndarray
    time_vector: np.ndarray
    per_frequency_results: tuple[ImplicitTMzLeadingOrderDirectionalResult, ...]


@dataclass(frozen=True)
class _PairwiseGeometryCache:
    """Cached pairwise geometry for a fixed receiver/source point set."""

    receiver_points: np.ndarray
    source_points: np.ndarray
    displacement: np.ndarray
    distance: np.ndarray


@dataclass(frozen=True)
class _LeadingOrderBoundaryGeometryCache:
    """Geometry cache shared across contexts for leading-order normal gradients."""

    boundary_points: np.ndarray
    normals: np.ndarray
    weights: np.ndarray
    offset_distance: float
    source_points: np.ndarray
    receiver_points: np.ndarray
    outside_points: tuple[np.ndarray, np.ndarray, np.ndarray]
    inside_points: tuple[np.ndarray, np.ndarray, np.ndarray]
    incident_geometry: _PairwiseGeometryCache
    receiver_geometry: _PairwiseGeometryCache
    offset_geometries: tuple[_PairwiseGeometryCache, ...]


def complex_l2_data_misfit(predicted: np.ndarray, observed: np.ndarray) -> tuple[float, np.ndarray]:
    """Return ``0.5 * mean(|predicted - observed|^2)`` and the residual."""

    predicted_array = np.asarray(predicted, dtype=np.complex128)
    observed_array = np.asarray(observed, dtype=np.complex128)
    if predicted_array.shape != observed_array.shape:
        raise ValueError("predicted and observed must have the same shape.")
    residual = predicted_array - observed_array
    loss = 0.5 * float(np.mean(np.abs(residual) ** 2))
    return loss, residual


def build_ibim_receiver_operator_rows(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    receiver_points,
    wavenumber: complex,
    *,
    use_strict_quadrature: bool = False,
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> tuple[np.ndarray, np.ndarray]:
    """Build dense receiver rows for the implicit single/double-layer potentials."""

    resolved_backend = _resolve_backend(backend, complex_precision=complex_precision)
    num_boundary = int(boundary.num_samples)
    identity = resolved_backend.xp.eye(num_boundary, dtype=resolved_backend.complex_dtype)
    single_rows = implicit_single_layer_potential_from_band(
        receiver_points,
        boundary,
        identity,
        complex(wavenumber),
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials[0]
    double_rows = implicit_double_layer_potential_from_band(
        receiver_points,
        boundary,
        identity,
        complex(wavenumber),
        use_strict_quadrature=use_strict_quadrature,
        backend=resolved_backend,
        complex_precision=complex_precision,
    ).potentials[0]
    return (
        np.asarray(resolved_backend.to_host(single_rows), dtype=np.complex128),
        np.asarray(resolved_backend.to_host(double_rows), dtype=np.complex128),
    )


def prepare_ibim_adjoint_context(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequency: float,
    source_strength,
    observed_data,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    formulation: str | None = "muller",
    normal_derivative_scheme: str | None = "analytic_extrapolated",
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzAdjointContext:
    """Build the single-frequency implicit-boundary adjoint context from observed data."""

    forward, single_rows, double_rows = _prepare_ibim_forward_receiver_rows(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        formulation=formulation,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=backend,
        complex_precision=complex_precision,
    )
    observed_array = np.asarray(observed_data, dtype=np.complex128)
    loss, residual = complex_l2_data_misfit(forward.total_receiver, observed_array)
    receiver_dual = residual / residual.size
    return ibim_adjoint_context_from_receiver_dual(
        forward,
        single_rows,
        double_rows,
        receiver_dual=receiver_dual,
        loss=loss,
        residual=residual,
    )


def _prepare_ibim_forward_receiver_rows(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequency: float,
    source_strength,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    formulation: str | None = "muller",
    normal_derivative_scheme: str | None = "analytic_extrapolated",
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> tuple[ImplicitTMzForwardResult, np.ndarray, np.ndarray]:
    """Solve the forward IBIM system and build receiver rows once."""

    forward = solve_ibim_tmz_total_field_batch(
        boundary,
        source_points,
        receiver_points,
        angular_frequency,
        source_strength,
        exterior=exterior,
        interior=interior,
        eps0=eps0,
        mu0=mu0,
        offset_distance=offset_distance,
        use_strict_quadrature=use_strict_quadrature,
        formulation=formulation,
        normal_derivative_scheme=normal_derivative_scheme,
        backend=backend,
        complex_precision=complex_precision,
    )
    single_rows, double_rows = build_ibim_receiver_operator_rows(
        boundary,
        receiver_points,
        forward.system.k_exterior,
        use_strict_quadrature=use_strict_quadrature,
        backend=backend,
        complex_precision=complex_precision,
    )
    return forward, single_rows, double_rows


def prepare_ibim_multifrequency_adjoint_context(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequencies,
    source_strength,
    observed_data,
    *,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    frequency_weights: np.ndarray | None = None,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    formulation: str | None = "muller",
    normal_derivative_scheme: str | None = "analytic_extrapolated",
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzMultiFrequencyAdjointResult:
    """Build single-frequency IBIM adjoint contexts for a multi-frequency objective."""

    frequencies = _coerce_angular_frequencies(angular_frequencies)
    observed_array = _coerce_multifrequency_observed_data(observed_data, frequencies.size)
    weights = _coerce_frequency_weights(frequency_weights, frequencies.size)
    source_strengths = _coerce_multifrequency_source_strengths(
        source_strength,
        num_frequencies=frequencies.size,
        num_sources=int(np.asarray(source_points, dtype=float).shape[0]),
    )
    contexts: list[ImplicitTMzAdjointContext] = []
    forwards: list[ImplicitTMzForwardResult] = []
    loss_by_frequency = np.zeros(frequencies.size, dtype=float)
    for index, angular_frequency in enumerate(frequencies):
        forward, single_rows, double_rows = _prepare_ibim_forward_receiver_rows(
            boundary,
            source_points,
            receiver_points,
            float(angular_frequency),
            source_strengths[index],
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            formulation=formulation,
            normal_derivative_scheme=normal_derivative_scheme,
            backend=backend,
            complex_precision=complex_precision,
        )
        loss, residual = complex_l2_data_misfit(forward.total_receiver, observed_array[index])
        receiver_dual = residual / residual.size
        context = ibim_adjoint_context_from_receiver_dual(
            forward,
            single_rows,
            double_rows,
            receiver_dual=receiver_dual,
            loss=loss,
            residual=residual,
        )
        contexts.append(context)
        forwards.append(forward)
        loss_by_frequency[index] = context.loss
    frequency_response = np.stack([forward.total_receiver for forward in forwards], axis=1).astype(np.complex128)
    return ImplicitTMzMultiFrequencyAdjointResult(
        angular_frequencies=frequencies.copy(),
        frequency_weights=weights.copy(),
        loss=float(weights @ loss_by_frequency),
        loss_by_frequency=loss_by_frequency,
        frequency_response=frequency_response,
        forwards=tuple(forwards),
        per_frequency_contexts=tuple(contexts),
    )


def prepare_ibim_bscan_adjoint_context(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    source_points,
    receiver_points,
    angular_frequencies,
    source_strength,
    observed_bscan,
    *,
    time_vector,
    exterior: Material,
    interior: Material,
    eps0: float,
    mu0: float,
    frequency_window: np.ndarray | None = None,
    time_gate_start: float | None = None,
    sample_weights: np.ndarray | None = None,
    offset_distance: float | None = None,
    use_strict_quadrature: bool = False,
    formulation: str | None = "muller",
    normal_derivative_scheme: str | None = "analytic_extrapolated",
    backend: str | AssemblyBackend = "numpy",
    complex_precision: str = "complex128",
) -> ImplicitTMzBscanAdjointResult:
    """Build time-domain B-scan adjoint data for the implicit-boundary TMz system."""

    frequencies = _coerce_angular_frequencies(angular_frequencies)
    time_array = _coerce_time_vector(time_vector)
    window = _coerce_frequency_window(frequency_window, frequencies.size)
    observed_bscan_array = np.asarray(observed_bscan, dtype=float)
    if observed_bscan_array.ndim != 2:
        raise ValueError("observed_bscan must have shape (num_receivers, num_time_samples).")
    source_strengths = _coerce_multifrequency_source_strengths(
        source_strength,
        num_frequencies=frequencies.size,
        num_sources=int(np.asarray(source_points, dtype=float).shape[0]),
    )
    forwards: list[ImplicitTMzForwardResult] = []
    receiver_rows: list[tuple[np.ndarray, np.ndarray]] = []
    for index, angular_frequency in enumerate(frequencies):
        forward, single_rows, double_rows = _prepare_ibim_forward_receiver_rows(
            boundary,
            source_points,
            receiver_points,
            float(angular_frequency),
            source_strengths[index],
            exterior=exterior,
            interior=interior,
            eps0=eps0,
            mu0=mu0,
            offset_distance=offset_distance,
            use_strict_quadrature=use_strict_quadrature,
            formulation=formulation,
            normal_derivative_scheme=normal_derivative_scheme,
            backend=backend,
            complex_precision=complex_precision,
        )
        forwards.append(forward)
        receiver_rows.append((single_rows, double_rows))
    frequency_response = np.stack([forward.total_receiver for forward in forwards], axis=1).astype(np.complex128)
    predicted_bscan = bscan_from_frequency_response(
        frequency_response,
        frequencies,
        time_array,
        frequency_window=window,
    )
    sample_mask = _time_gate_mask(time_array, time_gate_start=time_gate_start)
    loss, time_residual = real_l2_data_misfit_masked(
        predicted_bscan,
        observed_bscan_array,
        sample_mask=sample_mask,
        sample_weights=sample_weights,
    )
    frequency_response_dual = _frequency_response_dual_from_bscan_residual(
        time_residual,
        frequencies,
        time_array,
        frequency_window=window,
        sample_mask=sample_mask,
        sample_weights=sample_weights,
    )
    contexts = tuple(
        ibim_adjoint_context_from_receiver_dual(
            forwards[index],
            receiver_rows[index][0],
            receiver_rows[index][1],
            receiver_dual=frequency_response_dual[:, index],
            loss=loss,
            residual=np.asarray(time_residual, dtype=np.complex128),
        )
        for index in range(frequencies.size)
    )
    time_sample_weights = _coerce_time_sample_weights(sample_weights, predicted_bscan.shape)
    return ImplicitTMzBscanAdjointResult(
        angular_frequencies=frequencies.copy(),
        time_vector=time_array.copy(),
        frequency_window=window.copy(),
        time_gate_start=None if time_gate_start is None else float(time_gate_start),
        time_gate_mask=sample_mask.copy(),
        time_sample_weights=time_sample_weights,
        loss=float(loss),
        frequency_response=frequency_response,
        weighted_frequency_response=frequency_response * window[None, :],
        bscan=predicted_bscan,
        residual=np.asarray(time_residual, dtype=float),
        frequency_response_dual=np.asarray(frequency_response_dual, dtype=np.complex128),
        forwards=tuple(forwards),
        per_frequency_contexts=contexts,
    )


def ibim_shape_gradient_surrogate_loss(
    model,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    shape_gradient: torch.Tensor,
    *,
    quadrature_weights: torch.Tensor | None = None,
    detach_boundary_points: bool = True,
    detach_quadrature: bool = True,
    detach_normalizer: bool = True,
    epsilon: float = 1.0e-8,
) -> torch.Tensor:
    """Build the Neural-SDF surrogate from implicit-boundary samples.

    The implicit-boundary samples are treated as fixed samples of the current
    interface, matching the coupling strategy used in the explicit panel phase.
    """

    if isinstance(boundary, ImplicitBoundaryBand2D):
        boundary_points = boundary.projected_points
        default_weights = boundary.quadrature_weights
    else:
        boundary_points = boundary.points
        default_weights = boundary.quadrature_weights

    points = boundary_points.detach() if detach_boundary_points else boundary_points
    if quadrature_weights is None:
        weights = default_weights
    else:
        weights = quadrature_weights
    if detach_quadrature:
        weights = weights.detach()
    return shape_gradient_surrogate_loss(
        model,
        points,
        shape_gradient,
        quadrature_weights=weights,
        detach_normalizer=detach_normalizer,
        epsilon=epsilon,
    )


def ibim_leading_order_point_directional_gradient(
    context: ImplicitTMzAdjointContext,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    point_directional,
    *,
    use_strict_quadrature: bool | None = None,
) -> ImplicitTMzLeadingOrderDirectionalResult:
    """Evaluate the leading-order IBIM directional derivative under frozen normals/weights.

    The geometry perturbation moves only the implicit-boundary sample points by the prescribed
    directional field ``point_directional``. Surface normals and quadrature weights are kept
    fixed, matching the first ``p_dot`` term in the IBIM derivation.
    """

    strict_quadrature = (
        context.forward.system.use_strict_quadrature if use_strict_quadrature is None else bool(use_strict_quadrature)
    )
    boundary_points, normals, weights = _boundary_point_normal_weight_arrays(
        boundary,
        use_strict_quadrature=strict_quadrature,
    )
    point_directional_array = _coerce_point_directional(point_directional, num_boundary_samples=boundary_points.shape[0])
    if boundary_points.shape[0] != context.forward.system.num_boundary_samples:
        raise ValueError("boundary sample count must match context.forward.system.num_boundary_samples.")

    rhs_directional = _ibim_incident_trace_point_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        point_directional=point_directional_array,
        source_points=context.forward.source_points,
        source_strengths=context.forward.source_strengths,
        wavenumber=context.forward.system.k_exterior,
    )
    system_action_directional = _ibim_system_action_point_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional_array,
        offset_distance=float(context.forward.system.offset_distance),
        wavenumber_exterior=context.forward.system.k_exterior,
        wavenumber_interior=context.forward.system.k_interior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
        formulation=context.forward.system.formulation,
        normal_derivative_scheme=context.forward.system.normal_derivative_scheme,
    )
    state_sensitivity_rhs = rhs_directional - system_action_directional
    receiver_directional = _ibim_receiver_action_point_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional_array,
        receiver_points=context.forward.receiver_points,
        wavenumber=context.forward.system.k_exterior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
    )
    directional_gradient = float(
        np.real(
            np.vdot(context.adjoint_vector, state_sensitivity_rhs)
            + np.vdot(context.receiver_dual, receiver_directional)
        )
    )
    return ImplicitTMzLeadingOrderDirectionalResult(
        directional_gradient=directional_gradient,
        rhs_directional=rhs_directional,
        system_action_directional=system_action_directional,
        state_sensitivity_rhs=state_sensitivity_rhs,
        receiver_directional=receiver_directional,
    )


def ibim_multifrequency_leading_order_point_directional_gradient(
    result: ImplicitTMzMultiFrequencyAdjointResult,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    point_directional,
    *,
    use_strict_quadrature: bool | None = None,
) -> ImplicitTMzMultiFrequencyLeadingOrderDirectionalResult:
    """Aggregate leading-order point-directional gradients for a weighted multifrequency loss."""

    per_frequency_results = tuple(
        ibim_leading_order_point_directional_gradient(
            context,
            boundary,
            point_directional,
            use_strict_quadrature=use_strict_quadrature,
        )
        for context in result.per_frequency_contexts
    )
    directional_gradient = float(
        np.sum(
            result.frequency_weights
            * np.asarray([item.directional_gradient for item in per_frequency_results], dtype=float)
        )
    )
    return ImplicitTMzMultiFrequencyLeadingOrderDirectionalResult(
        directional_gradient=directional_gradient,
        angular_frequencies=result.angular_frequencies.copy(),
        frequency_weights=result.frequency_weights.copy(),
        per_frequency_results=per_frequency_results,
    )


def ibim_bscan_leading_order_point_directional_gradient(
    result: ImplicitTMzBscanAdjointResult,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    point_directional,
    *,
    use_strict_quadrature: bool | None = None,
) -> ImplicitTMzBscanLeadingOrderDirectionalResult:
    """Aggregate leading-order point-directional gradients for a time-domain B-scan loss."""

    per_frequency_results = tuple(
        ibim_leading_order_point_directional_gradient(
            context,
            boundary,
            point_directional,
            use_strict_quadrature=use_strict_quadrature,
        )
        for context in result.per_frequency_contexts
    )
    directional_gradient = float(np.sum([item.directional_gradient for item in per_frequency_results], dtype=float))
    return ImplicitTMzBscanLeadingOrderDirectionalResult(
        directional_gradient=directional_gradient,
        angular_frequencies=result.angular_frequencies.copy(),
        time_vector=result.time_vector.copy(),
        per_frequency_results=per_frequency_results,
    )


def ibim_leading_order_normal_shape_gradient(
    context: ImplicitTMzAdjointContext,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    *,
    use_strict_quadrature: bool | None = None,
) -> np.ndarray:
    """Return the leading-order normal shape-gradient density on the boundary."""

    strict_quadrature = (
        context.forward.system.use_strict_quadrature if use_strict_quadrature is None else bool(use_strict_quadrature)
    )
    geometry_cache = _build_leading_order_boundary_geometry_cache(
        context,
        boundary,
        use_strict_quadrature=strict_quadrature,
    )
    num_samples = geometry_cache.boundary_points.shape[0]
    node_directional = np.zeros((num_samples,), dtype=float)
    for sample_index in range(num_samples):
        node_directional[sample_index] = _ibim_leading_order_single_sample_normal_gradient_cached(
            context=context,
            geometry_cache=geometry_cache,
            sample_index=sample_index,
        )
    return _node_directional_to_shape_gradient_density(node_directional, geometry_cache.weights)


def ibim_multifrequency_leading_order_normal_shape_gradient(
    result: ImplicitTMzMultiFrequencyAdjointResult,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    *,
    use_strict_quadrature: bool | None = None,
) -> np.ndarray:
    """Return the weighted multifrequency leading-order normal shape-gradient density."""

    strict_quadrature = (
        result.forwards[0].system.use_strict_quadrature if use_strict_quadrature is None else bool(use_strict_quadrature)
    )
    geometry_cache = _build_leading_order_boundary_geometry_cache(
        result.per_frequency_contexts[0],
        boundary,
        use_strict_quadrature=strict_quadrature,
    )
    node_directional = np.zeros((geometry_cache.boundary_points.shape[0],), dtype=float)
    for weight, context in zip(result.frequency_weights, result.per_frequency_contexts):
        node_directional += float(weight) * np.asarray(
            [
                _ibim_leading_order_single_sample_normal_gradient_cached(
                    context=context,
                    geometry_cache=geometry_cache,
                    sample_index=sample_index,
                )
                for sample_index in range(geometry_cache.boundary_points.shape[0])
            ],
            dtype=float,
        )
    return _node_directional_to_shape_gradient_density(node_directional, geometry_cache.weights)


def ibim_bscan_leading_order_normal_shape_gradient(
    result: ImplicitTMzBscanAdjointResult,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    *,
    use_strict_quadrature: bool | None = None,
) -> np.ndarray:
    """Return the B-scan leading-order normal shape-gradient density on the boundary."""

    strict_quadrature = (
        result.forwards[0].system.use_strict_quadrature if use_strict_quadrature is None else bool(use_strict_quadrature)
    )
    geometry_cache = _build_leading_order_boundary_geometry_cache(
        result.per_frequency_contexts[0],
        boundary,
        use_strict_quadrature=strict_quadrature,
    )
    node_directional = np.zeros((geometry_cache.boundary_points.shape[0],), dtype=float)
    for context in result.per_frequency_contexts:
        node_directional += np.asarray(
            [
                _ibim_leading_order_single_sample_normal_gradient_cached(
                    context=context,
                    geometry_cache=geometry_cache,
                    sample_index=sample_index,
                )
                for sample_index in range(geometry_cache.boundary_points.shape[0])
            ],
            dtype=float,
        )
    return _node_directional_to_shape_gradient_density(node_directional, geometry_cache.weights)


def ibim_adjoint_context_from_receiver_dual(
    forward: ImplicitTMzForwardResult,
    single_rows: np.ndarray,
    double_rows: np.ndarray,
    *,
    receiver_dual: np.ndarray,
    loss: float,
    residual: np.ndarray,
) -> ImplicitTMzAdjointContext:
    """Build the discrete adjoint state for a prescribed receiver dual."""

    state_vector = _state_vector_from_forward(forward)
    system_matrix = _to_host_complex_array(forward.system.system_matrix[0])
    receiver_dual_array = np.asarray(receiver_dual, dtype=np.complex128)
    if receiver_dual_array.shape != (forward.total_receiver.shape[0],):
        raise ValueError("receiver_dual must have shape (num_receivers,).")
    single_rows_array = np.asarray(single_rows, dtype=np.complex128)
    double_rows_array = np.asarray(double_rows, dtype=np.complex128)
    if single_rows_array.shape != double_rows_array.shape:
        raise ValueError("single_rows and double_rows must have the same shape.")
    if single_rows_array.shape[0] != receiver_dual_array.shape[0]:
        raise ValueError("Receiver rows must have one row per receiver.")

    adjoint_rhs = np.concatenate(
        (
            np.conjugate(double_rows_array) * receiver_dual_array[:, None],
            -np.conjugate(single_rows_array) * receiver_dual_array[:, None],
        ),
        axis=1,
    )
    adjoint_vector = np.linalg.solve(system_matrix.conjugate().T, adjoint_rhs.T).T
    return ImplicitTMzAdjointContext(
        loss=float(loss),
        residual=np.asarray(residual, dtype=np.complex128),
        receiver_dual=receiver_dual_array,
        state_vector=state_vector,
        adjoint_vector=np.asarray(adjoint_vector, dtype=np.complex128),
        system_matrix=system_matrix,
        adjoint_rhs=adjoint_rhs,
        single_layer_rows=single_rows_array,
        double_layer_rows=double_rows_array,
        forward=forward,
    )


def _resolve_backend(backend: str | AssemblyBackend, *, complex_precision: str) -> AssemblyBackend:
    if isinstance(backend, AssemblyBackend):
        return backend
    return get_assembly_backend(str(backend), complex_precision=complex_precision)


def _to_host_complex_array(values) -> np.ndarray:
    if isinstance(values, torch.Tensor):
        return np.asarray(values.detach().cpu().numpy(), dtype=np.complex128)
    if hasattr(values, "get"):
        return np.asarray(values.get(), dtype=np.complex128)
    return np.asarray(values, dtype=np.complex128)


def _state_vector_from_forward(forward: ImplicitTMzForwardResult) -> np.ndarray:
    return np.concatenate((forward.dirichlet_total, forward.neumann_total), axis=1).astype(np.complex128, copy=False)


def _coerce_point_directional(point_directional, *, num_boundary_samples: int) -> np.ndarray:
    direction = np.asarray(point_directional, dtype=float)
    if direction.shape != (num_boundary_samples, 2):
        raise ValueError("point_directional must have shape (num_boundary_samples, 2).")
    return direction


def _boundary_point_normal_weight_arrays(
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    *,
    use_strict_quadrature: bool,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    weight_attr = "strict_quadrature_weights" if use_strict_quadrature else "quadrature_weights"
    if isinstance(boundary, ImplicitBoundarySamples2D):
        return (
            np.asarray(boundary.points.detach().cpu(), dtype=float),
            np.asarray(boundary.normals.detach().cpu(), dtype=float),
            np.asarray(getattr(boundary, weight_attr).detach().cpu(), dtype=float).reshape(-1),
        )
    return (
        np.asarray(boundary.projected_points.detach().cpu(), dtype=float),
        np.asarray(boundary.normals.detach().cpu(), dtype=float),
        np.asarray(getattr(boundary, weight_attr).detach().cpu(), dtype=float).reshape(-1),
    )


def _build_pairwise_geometry_cache(receiver_points: np.ndarray, source_points: np.ndarray) -> _PairwiseGeometryCache:
    receiver_array = np.asarray(receiver_points, dtype=float)
    source_array = np.asarray(source_points, dtype=float)
    displacement = receiver_array[:, None, :] - source_array[None, :, :]
    distance = np.linalg.norm(displacement, axis=2)
    if np.min(distance) <= 1.0e-10:
        raise ValueError("Point-directional evaluation encountered singular receiver/source coincidence.")
    return _PairwiseGeometryCache(
        receiver_points=receiver_array,
        source_points=source_array,
        displacement=displacement,
        distance=distance,
    )


def _build_leading_order_boundary_geometry_cache(
    context: ImplicitTMzAdjointContext,
    boundary: ImplicitBoundaryBand2D | ImplicitBoundarySamples2D,
    *,
    use_strict_quadrature: bool,
) -> _LeadingOrderBoundaryGeometryCache:
    boundary_points, normals, weights = _boundary_point_normal_weight_arrays(
        boundary,
        use_strict_quadrature=use_strict_quadrature,
    )
    source_points = np.asarray(context.forward.source_points, dtype=float)
    receiver_points = np.asarray(context.forward.receiver_points, dtype=float)
    offset_distance = float(context.forward.system.offset_distance)
    outside_points = tuple(boundary_points + float(multiplier) * offset_distance * normals for multiplier in (1, 2, 3))
    inside_points = tuple(boundary_points - float(multiplier) * offset_distance * normals for multiplier in (1, 2, 3))
    return _LeadingOrderBoundaryGeometryCache(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        offset_distance=offset_distance,
        source_points=source_points,
        receiver_points=receiver_points,
        outside_points=outside_points,
        inside_points=inside_points,
        incident_geometry=_build_pairwise_geometry_cache(boundary_points, source_points),
        receiver_geometry=_build_pairwise_geometry_cache(receiver_points, boundary_points),
        offset_geometries=tuple(
            _build_pairwise_geometry_cache(points, boundary_points)
            for points in (*outside_points, *inside_points)
        ),
    )


def _build_point_directional_array(num_boundary_samples: int, sample_index: int, direction: np.ndarray) -> np.ndarray:
    point_directional = np.zeros((num_boundary_samples, 2), dtype=float)
    point_directional[sample_index] = np.asarray(direction, dtype=float)
    return point_directional


def _coerce_row_major_densities(densities: np.ndarray, *, num_boundary_samples: int) -> np.ndarray:
    density_array = np.asarray(densities, dtype=np.complex128)
    if density_array.ndim == 1:
        if density_array.shape[0] != num_boundary_samples:
            raise ValueError("density vector must have length num_boundary_samples.")
        return density_array[None, :]
    if density_array.ndim != 2 or density_array.shape[1] != num_boundary_samples:
        raise ValueError("densities must have shape (batch, num_boundary_samples).")
    return density_array


def _node_directional_to_shape_gradient_density(node_directional: np.ndarray, weights: np.ndarray) -> np.ndarray:
    node_values = np.asarray(node_directional, dtype=float).reshape(-1)
    weight_values = np.asarray(weights, dtype=float).reshape(-1)
    if node_values.shape != weight_values.shape:
        raise ValueError("node_directional and weights must have matching shape.")
    density = np.zeros_like(node_values)
    np.divide(
        node_values,
        weight_values,
        out=density,
        where=np.abs(weight_values) > 1.0e-15,
    )
    return density


def _muller_analytic_system_action_point_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    wavenumber_exterior: complex,
    wavenumber_interior: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
) -> np.ndarray:
    """Verified Muller ``A_dot q`` contraction for frozen normals/weights."""

    boundary_points_array = np.asarray(boundary_points, dtype=float)
    normals_array = np.asarray(normals, dtype=float)
    weights_array = np.asarray(weights, dtype=float).reshape(-1)
    point_directional_array = np.asarray(point_directional, dtype=float)
    num_boundary_samples = boundary_points_array.shape[0]
    dirichlet_density_array = _coerce_row_major_densities(
        dirichlet_density,
        num_boundary_samples=num_boundary_samples,
    )
    neumann_density_array = _coerce_row_major_densities(
        neumann_density,
        num_boundary_samples=num_boundary_samples,
    )
    if dirichlet_density_array.shape != neumann_density_array.shape:
        raise ValueError("dirichlet_density and neumann_density must have matching batch shape.")
    if point_directional_array.shape != boundary_points_array.shape:
        raise ValueError("point_directional must have shape (num_boundary_samples, 2).")
    if normals_array.shape != boundary_points_array.shape:
        raise ValueError("normals must have shape (num_boundary_samples, 2).")
    if weights_array.shape != (num_boundary_samples,):
        raise ValueError("weights must have shape (num_boundary_samples,).")

    tensor_kwargs = {"dtype": torch.float64}
    samples = ImplicitBoundarySamples2D(
        points=torch.as_tensor(boundary_points_array, **tensor_kwargs),
        normals=torch.as_tensor(normals_array, **tensor_kwargs),
        quadrature_weights=torch.as_tensor(weights_array, **tensor_kwargs),
        strict_quadrature_weights=torch.as_tensor(weights_array, **tensor_kwargs),
        merge_distance=0.5 * float(offset_distance),
        source_num_samples=num_boundary_samples,
        bounds=(
            (float(np.min(boundary_points_array[:, 0])), float(np.max(boundary_points_array[:, 0]))),
            (float(np.min(boundary_points_array[:, 1])), float(np.max(boundary_points_array[:, 1]))),
        ),
        level=0.0,
    )
    normal_velocity = np.zeros_like(point_directional_array)
    weight_velocity = np.zeros(num_boundary_samples, dtype=float)
    moved_samples = np.flatnonzero(np.linalg.norm(point_directional_array, axis=1) > 0.0)
    if moved_samples.size == 1:
        sample_index = int(moved_samples[0])
        direction = point_directional_array[sample_index]
        rows = [
            single_sample_system_action_directional_derivative_from_wavenumbers(
                samples,
                sample_index,
                direction,
                dirichlet_density_array[index],
                neumann_density_array[index],
                complex(wavenumber_exterior),
                complex(wavenumber_interior),
                float(offset_distance),
                use_strict_quadrature=True,
            )
            for index in range(dirichlet_density_array.shape[0])
        ]
        return np.stack(rows, axis=0).astype(np.complex128, copy=False)

    rows = [
        full_system_action_directional_derivative_from_wavenumbers(
            samples,
            point_directional_array,
            normal_velocity,
            weight_velocity,
            dirichlet_density_array[index],
            neumann_density_array[index],
            complex(wavenumber_exterior),
            complex(wavenumber_interior),
            float(offset_distance),
            use_strict_quadrature=True,
        )
        for index in range(dirichlet_density_array.shape[0])
    ]
    return np.stack(rows, axis=0).astype(np.complex128, copy=False)


def _ibim_leading_order_single_sample_normal_gradient(
    *,
    context: ImplicitTMzAdjointContext,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
) -> float:
    direction = np.asarray(normals[sample_index], dtype=float)
    rhs_directional = _ibim_incident_trace_single_sample_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        sample_index=sample_index,
        direction=direction,
        source_points=context.forward.source_points,
        source_strengths=context.forward.source_strengths,
        wavenumber=context.forward.system.k_exterior,
    )
    system_action_directional = _ibim_system_action_single_sample_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=float(context.forward.system.offset_distance),
        wavenumber_exterior=context.forward.system.k_exterior,
        wavenumber_interior=context.forward.system.k_interior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
        formulation=context.forward.system.formulation,
        normal_derivative_scheme=context.forward.system.normal_derivative_scheme,
    )
    state_sensitivity_rhs = rhs_directional - system_action_directional
    receiver_directional = _ibim_receiver_action_single_sample_directional_derivative(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        receiver_points=context.forward.receiver_points,
        wavenumber=context.forward.system.k_exterior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
    )
    return float(
        np.real(
            np.vdot(context.adjoint_vector, state_sensitivity_rhs)
            + np.vdot(context.receiver_dual, receiver_directional)
        )
    )


def _ibim_leading_order_single_sample_normal_gradient_cached(
    *,
    context: ImplicitTMzAdjointContext,
    geometry_cache: _LeadingOrderBoundaryGeometryCache,
    sample_index: int,
) -> float:
    direction = np.asarray(geometry_cache.normals[sample_index], dtype=float)
    point_directional = _build_point_directional_array(geometry_cache.boundary_points.shape[0], sample_index, direction)
    rhs_directional = _ibim_incident_trace_point_directional_derivative_cached(
        geometry_cache=geometry_cache,
        sample_index=sample_index,
        direction=direction,
        source_points=context.forward.source_points,
        source_strengths=context.forward.source_strengths,
        wavenumber=context.forward.system.k_exterior,
    )
    system_action_directional = _ibim_system_action_point_directional_derivative_cached(
        geometry_cache=geometry_cache,
        point_directional=point_directional,
        offset_distance=float(context.forward.system.offset_distance),
        wavenumber_exterior=context.forward.system.k_exterior,
        wavenumber_interior=context.forward.system.k_interior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
        formulation=context.forward.system.formulation,
        normal_derivative_scheme=context.forward.system.normal_derivative_scheme,
    )
    state_sensitivity_rhs = rhs_directional - system_action_directional
    receiver_directional = _ibim_receiver_action_point_directional_derivative_cached(
        geometry_cache=geometry_cache,
        sample_index=sample_index,
        direction=direction,
        receiver_points=context.forward.receiver_points,
        wavenumber=context.forward.system.k_exterior,
        dirichlet_density=context.forward.dirichlet_total,
        neumann_density=context.forward.neumann_total,
    )
    return float(
        np.real(
            np.vdot(context.adjoint_vector, state_sensitivity_rhs)
            + np.vdot(context.receiver_dual, receiver_directional)
        )
    )


def _ibim_incident_trace_point_directional_derivative_cached(
    *,
    geometry_cache: _LeadingOrderBoundaryGeometryCache,
    sample_index: int,
    direction: np.ndarray,
    source_points: np.ndarray,
    source_strengths: np.ndarray,
    wavenumber: complex,
) -> np.ndarray:
    if geometry_cache is None:
        raise ValueError("geometry_cache is required for cached incident-trace evaluation.")
    source_points_array = np.asarray(source_points, dtype=float)
    strengths = np.asarray(source_strengths, dtype=np.complex128).reshape(-1)
    if source_points_array.shape[0] != strengths.shape[0]:
        raise ValueError("source_points and source_strengths must have the same batch size.")
    incident_geometry = geometry_cache.incident_geometry
    boundary_points = geometry_cache.boundary_points
    normals = geometry_cache.normals
    num_boundary_samples = boundary_points.shape[0]
    result = np.zeros((source_points_array.shape[0], 2 * num_boundary_samples), dtype=np.complex128)
    receiver_normal = normals[sample_index]
    displacement = np.transpose(incident_geometry.displacement[sample_index : sample_index + 1], (1, 0, 2))
    distance = np.transpose(incident_geometry.distance[sample_index : sample_index + 1], (1, 0))
    distance_directional = np.sum(displacement * direction[None, None, :], axis=2) / distance
    z = complex(wavenumber) * distance
    h0 = hankel1(0, z)
    h1 = hankel1(1, z)
    h2 = hankel1(2, z)
    h1_radial_directional = 0.5 * complex(wavenumber) * (h0 - h2) * distance_directional
    dirichlet_directional = strengths[:, None] * (-0.25j * complex(wavenumber) * h1 * distance_directional)
    numerator = np.einsum("bnd,d->bn", displacement, receiver_normal, optimize=True)
    factor = numerator / distance
    numerator_directional = np.einsum("d,d->", receiver_normal, direction) * np.ones_like(numerator)
    factor_directional = numerator_directional / distance - numerator * distance_directional / (distance**2)
    neumann_directional = strengths[:, None] * (
        -0.25j * complex(wavenumber) * (h1_radial_directional * factor + h1 * factor_directional)
    )
    result[:, sample_index] = dirichlet_directional[:, 0]
    result[:, num_boundary_samples + sample_index] = neumann_directional[:, 0]
    return result


def _ibim_system_action_point_directional_derivative_cached(
    *,
    geometry_cache: _LeadingOrderBoundaryGeometryCache,
    point_directional: np.ndarray,
    offset_distance: float,
    wavenumber_exterior: complex,
    wavenumber_interior: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
    formulation: str = "muller",
    normal_derivative_scheme: str = "analytic_extrapolated",
) -> np.ndarray:
    boundary_points = geometry_cache.boundary_points
    normals = geometry_cache.normals
    weights = geometry_cache.weights
    if formulation == "muller" and normal_derivative_scheme == "analytic_extrapolated":
        return _muller_analytic_system_action_point_directional_derivative(
            boundary_points=boundary_points,
            normals=normals,
            weights=weights,
            point_directional=point_directional,
            offset_distance=offset_distance,
            wavenumber_exterior=wavenumber_exterior,
            wavenumber_interior=wavenumber_interior,
            dirichlet_density=dirichlet_density,
            neumann_density=neumann_density,
        )
    single_layer_action = _single_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    single_layer_action += _single_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    double_layer_action = _double_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    double_layer_action += _double_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    adjoint_double_layer_action = _single_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    adjoint_double_layer_action += _single_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    hypersingular_trace_action = _double_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    hypersingular_trace_action += _double_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    top = -double_layer_action + single_layer_action
    bottom = -hypersingular_trace_action + adjoint_double_layer_action
    return np.concatenate((top, bottom), axis=1).astype(np.complex128, copy=False)


def _ibim_receiver_action_point_directional_derivative_cached(
    *,
    geometry_cache: _LeadingOrderBoundaryGeometryCache,
    sample_index: int,
    direction: np.ndarray,
    receiver_points: np.ndarray,
    wavenumber: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
) -> np.ndarray:
    boundary_points = geometry_cache.boundary_points
    normals = geometry_cache.normals
    weights = geometry_cache.weights
    double_directional = _double_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points,
        source_normals=normals,
        source_weights=weights,
        densities=dirichlet_density,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=_build_point_directional_array(boundary_points.shape[0], sample_index, direction),
        geometry_cache=None,
    )
    single_directional = _single_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points,
        source_weights=weights,
        densities=neumann_density,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=_build_point_directional_array(boundary_points.shape[0], sample_index, direction),
        geometry_cache=None,
    )
    return _paired_receiver_response(double_directional - single_directional)


def _single_layer_boundary_trace_single_sample_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        outside_points = geometry_cache.outside_points[0]
        inside_points = geometry_cache.inside_points[0]
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        offset_distance = geometry_cache.offset_distance
    else:
        outside_points = boundary_points + offset_distance * normals
        inside_points = boundary_points - offset_distance * normals
    outside = _single_layer_single_sample_directional_potential(
        receiver_points=outside_points,
        source_points=boundary_points,
        source_weights=weights,
        sample_index=sample_index,
        direction=direction,
        densities=densities,
        wavenumber=wavenumber,
        geometry_cache=geometry_cache.offset_geometries[0] if geometry_cache is not None else None,
    )
    inside = _single_layer_single_sample_directional_potential(
        receiver_points=inside_points,
        source_points=boundary_points,
        source_weights=weights,
        sample_index=sample_index,
        direction=direction,
        densities=densities,
        wavenumber=wavenumber,
        geometry_cache=geometry_cache.offset_geometries[3] if geometry_cache is not None else None,
    )
    return 0.5 * (outside + inside)


def _double_layer_boundary_trace_single_sample_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        outside_points = geometry_cache.outside_points[0]
        inside_points = geometry_cache.inside_points[0]
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        offset_distance = geometry_cache.offset_distance
    else:
        outside_points = boundary_points + offset_distance * normals
        inside_points = boundary_points - offset_distance * normals
    outside = _double_layer_single_sample_directional_potential(
        receiver_points=outside_points,
        source_points=boundary_points,
        source_normals=normals,
        source_weights=weights,
        sample_index=sample_index,
        direction=direction,
        densities=densities,
        wavenumber=wavenumber,
        geometry_cache=geometry_cache.offset_geometries[0] if geometry_cache is not None else None,
    )
    inside = _double_layer_single_sample_directional_potential(
        receiver_points=inside_points,
        source_points=boundary_points,
        source_normals=normals,
        source_weights=weights,
        sample_index=sample_index,
        direction=direction,
        densities=densities,
        wavenumber=wavenumber,
        geometry_cache=geometry_cache.offset_geometries[3] if geometry_cache is not None else None,
    )
    return 0.5 * (outside + inside)


def _single_layer_normal_derivative_trace_single_sample_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    outside_samples: list[np.ndarray] = []
    inside_samples: list[np.ndarray] = []
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        outside_points = geometry_cache.outside_points
        inside_points = geometry_cache.inside_points
        offset_distance = geometry_cache.offset_distance
    else:
        outside_points = tuple(boundary_points + float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        inside_points = tuple(boundary_points - float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
    for multiplier in (1, 2, 3):
        outside_samples.append(
            _single_layer_single_sample_directional_potential(
                receiver_points=outside_points[multiplier - 1],
                source_points=boundary_points,
                source_weights=weights,
                sample_index=sample_index,
                direction=direction,
                densities=densities,
                wavenumber=wavenumber,
                geometry_cache=geometry_cache.offset_geometries[multiplier - 1] if geometry_cache is not None else None,
            )
        )
        inside_samples.append(
            _single_layer_single_sample_directional_potential(
                receiver_points=inside_points[multiplier - 1],
                source_points=boundary_points,
                source_weights=weights,
                sample_index=sample_index,
                direction=direction,
                densities=densities,
                wavenumber=wavenumber,
                geometry_cache=geometry_cache.offset_geometries[multiplier + 2] if geometry_cache is not None else None,
            )
        )
    outside_derivative = _one_sided_normal_derivative(outside_samples, float(offset_distance), from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, float(offset_distance), from_inside=True)
    return 0.5 * (outside_derivative + inside_derivative)


def _double_layer_normal_derivative_trace_single_sample_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    outside_samples: list[np.ndarray] = []
    inside_samples: list[np.ndarray] = []
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        outside_points = geometry_cache.outside_points
        inside_points = geometry_cache.inside_points
        offset_distance = geometry_cache.offset_distance
    else:
        outside_points = tuple(boundary_points + float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        inside_points = tuple(boundary_points - float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
    for multiplier in (1, 2, 3):
        outside_samples.append(
            _double_layer_single_sample_directional_potential(
                receiver_points=outside_points[multiplier - 1],
                source_points=boundary_points,
                source_normals=normals,
                source_weights=weights,
                sample_index=sample_index,
                direction=direction,
                densities=densities,
                wavenumber=wavenumber,
                geometry_cache=geometry_cache.offset_geometries[multiplier - 1] if geometry_cache is not None else None,
            )
        )
        inside_samples.append(
            _double_layer_single_sample_directional_potential(
                receiver_points=inside_points[multiplier - 1],
                source_points=boundary_points,
                source_normals=normals,
                source_weights=weights,
                sample_index=sample_index,
                direction=direction,
                densities=densities,
                wavenumber=wavenumber,
                geometry_cache=geometry_cache.offset_geometries[multiplier + 2] if geometry_cache is not None else None,
            )
        )
    outside_derivative = _one_sided_normal_derivative(outside_samples, float(offset_distance), from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, float(offset_distance), from_inside=True)
    return 0.5 * (outside_derivative + inside_derivative)


def _ibim_system_action_single_sample_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    offset_distance: float,
    wavenumber_exterior: complex,
    wavenumber_interior: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
    formulation: str = "muller",
    normal_derivative_scheme: str = "analytic_extrapolated",
) -> np.ndarray:
    if formulation == "muller" and normal_derivative_scheme == "analytic_extrapolated":
        point_directional = _build_point_directional_array(boundary_points.shape[0], sample_index, direction)
        return _muller_analytic_system_action_point_directional_derivative(
            boundary_points=boundary_points,
            normals=normals,
            weights=weights,
            point_directional=point_directional,
            offset_distance=offset_distance,
            wavenumber_exterior=wavenumber_exterior,
            wavenumber_interior=wavenumber_interior,
            dirichlet_density=dirichlet_density,
            neumann_density=neumann_density,
        )
    single_layer_action = _single_layer_boundary_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    single_layer_action += _single_layer_boundary_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    double_layer_action = _double_layer_boundary_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    double_layer_action += _double_layer_boundary_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    adjoint_double_layer_action = _single_layer_normal_derivative_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    adjoint_double_layer_action += _single_layer_normal_derivative_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    hypersingular_trace_action = _double_layer_normal_derivative_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
        geometry_cache=geometry_cache,
    )
    hypersingular_trace_action += _double_layer_normal_derivative_trace_single_sample_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        sample_index=sample_index,
        direction=direction,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
        geometry_cache=geometry_cache,
    )
    top = -double_layer_action + single_layer_action
    bottom = -hypersingular_trace_action + adjoint_double_layer_action
    return np.concatenate((top, bottom), axis=1).astype(np.complex128, copy=False)


def _ibim_incident_trace_single_sample_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    source_points: np.ndarray,
    source_strengths: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        incident_geometry = geometry_cache.incident_geometry
        source_points_array = geometry_cache.source_points
    else:
        boundary_points = np.asarray(boundary_points, dtype=float)
        normals = np.asarray(normals, dtype=float)
        incident_geometry = None
        source_points_array = np.asarray(source_points, dtype=float)
    strengths = np.asarray(source_strengths, dtype=np.complex128).reshape(-1)
    if source_points_array.shape[0] != strengths.shape[0]:
        raise ValueError("source_points and source_strengths must have the same batch size.")
    num_boundary_samples = boundary_points.shape[0]
    result = np.zeros((source_points_array.shape[0], 2 * num_boundary_samples), dtype=np.complex128)
    receiver_point = boundary_points[sample_index : sample_index + 1]
    receiver_normal = normals[sample_index]
    if geometry_cache is not None:
        displacement = incident_geometry.displacement[sample_index : sample_index + 1]
        distance = incident_geometry.distance[sample_index : sample_index + 1]
    else:
        displacement = receiver_point[None, :, :] - source_points_array[:, None, :]
        distance = np.linalg.norm(displacement, axis=2)
        if np.min(distance) <= 1.0e-10:
            raise ValueError("Boundary samples coincide with source points in incident-trace derivative evaluation.")
    distance_directional = np.sum(displacement * direction[None, None, :], axis=2) / distance
    z = complex(wavenumber) * distance
    h0 = hankel1(0, z)
    h1 = hankel1(1, z)
    h2 = hankel1(2, z)
    h1_radial_directional = 0.5 * complex(wavenumber) * (h0 - h2) * distance_directional
    dirichlet_directional = strengths[:, None] * (-0.25j * complex(wavenumber) * h1 * distance_directional)
    numerator = np.einsum("bnd,d->bn", displacement, receiver_normal, optimize=True)
    factor = numerator / distance
    numerator_directional = np.einsum("d,d->", receiver_normal, direction) * np.ones_like(numerator)
    factor_directional = numerator_directional / distance - numerator * distance_directional / (distance**2)
    neumann_directional = strengths[:, None] * (
        -0.25j * complex(wavenumber) * (h1_radial_directional * factor + h1 * factor_directional)
    )
    result[:, sample_index] = dirichlet_directional[:, 0]
    result[:, num_boundary_samples + sample_index] = neumann_directional[:, 0]
    return result


def _ibim_receiver_action_single_sample_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    receiver_points: np.ndarray,
    wavenumber: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        receiver_points = geometry_cache.receiver_points
    double_directional = _double_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points[sample_index : sample_index + 1],
        source_normals=normals[sample_index : sample_index + 1],
        source_weights=weights[sample_index : sample_index + 1],
        densities=np.asarray(dirichlet_density, dtype=np.complex128)[:, sample_index : sample_index + 1],
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=direction[None, :],
        geometry_cache=None,
    )
    single_directional = _single_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points[sample_index : sample_index + 1],
        source_weights=weights[sample_index : sample_index + 1],
        densities=np.asarray(neumann_density, dtype=np.complex128)[:, sample_index : sample_index + 1],
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=direction[None, :],
        geometry_cache=None,
    )
    return _paired_receiver_response(double_directional - single_directional)


def _single_layer_single_sample_directional_potential(
    *,
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    source_weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _PairwiseGeometryCache | None = None,
) -> np.ndarray:
    density_array = _coerce_row_major_densities(densities, num_boundary_samples=source_points.shape[0])
    receiver_array = np.asarray(receiver_points, dtype=float)
    source_array = np.asarray(source_points, dtype=float)
    source_weights_array = np.asarray(source_weights, dtype=float)
    num_receivers = receiver_array.shape[0]
    receiver_only = np.zeros((density_array.shape[0], num_receivers), dtype=np.complex128)
    receiver_directional = np.zeros_like(receiver_array, dtype=float)
    receiver_directional[sample_index] = np.asarray(direction, dtype=float)
    receiver_contribution = _single_layer_point_directional_potential(
        receiver_points=receiver_array,
        source_points=source_array,
        source_weights=source_weights_array,
        densities=density_array,
        wavenumber=wavenumber,
        receiver_directional=receiver_directional,
        source_directional=None,
        geometry_cache=geometry_cache,
    )
    receiver_only[:, sample_index] = receiver_contribution[:, sample_index]
    source_directional = np.zeros_like(source_array, dtype=float)
    source_directional[sample_index] = np.asarray(direction, dtype=float)
    source_only = _single_layer_point_directional_potential(
        receiver_points=receiver_array,
        source_points=source_array,
        source_weights=source_weights_array,
        densities=density_array,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=source_directional,
        geometry_cache=geometry_cache,
    )
    return receiver_only + source_only


def _double_layer_single_sample_directional_potential(
    *,
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    sample_index: int,
    direction: np.ndarray,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _PairwiseGeometryCache | None = None,
) -> np.ndarray:
    density_array = _coerce_row_major_densities(densities, num_boundary_samples=source_points.shape[0])
    receiver_array = np.asarray(receiver_points, dtype=float)
    source_array = np.asarray(source_points, dtype=float)
    normals_array = np.asarray(source_normals, dtype=float)
    source_weights_array = np.asarray(source_weights, dtype=float)
    num_receivers = receiver_array.shape[0]
    receiver_only = np.zeros((density_array.shape[0], num_receivers), dtype=np.complex128)
    receiver_directional = np.zeros_like(receiver_array, dtype=float)
    receiver_directional[sample_index] = np.asarray(direction, dtype=float)
    receiver_contribution = _double_layer_point_directional_potential(
        receiver_points=receiver_array,
        source_points=source_array,
        source_normals=normals_array,
        source_weights=source_weights_array,
        densities=density_array,
        wavenumber=wavenumber,
        receiver_directional=receiver_directional,
        source_directional=None,
        geometry_cache=geometry_cache,
    )
    receiver_only[:, sample_index] = receiver_contribution[:, sample_index]
    source_directional = np.zeros_like(source_array, dtype=float)
    source_directional[sample_index] = np.asarray(direction, dtype=float)
    source_only = _double_layer_point_directional_potential(
        receiver_points=receiver_array,
        source_points=source_array,
        source_normals=normals_array,
        source_weights=source_weights_array,
        densities=density_array,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=source_directional,
        geometry_cache=geometry_cache,
    )
    return receiver_only + source_only


def _pairwise_geometry_directional_terms(
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    *,
    receiver_directional: np.ndarray | None,
    source_directional: np.ndarray | None,
    geometry_cache: _PairwiseGeometryCache | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if geometry_cache is None:
        displacement = np.asarray(receiver_points, dtype=float)[:, None, :] - np.asarray(source_points, dtype=float)[None, :, :]
        distance = np.linalg.norm(displacement, axis=2)
        if np.min(distance) <= 1.0e-10:
            raise ValueError("Point-directional evaluation encountered singular receiver/source coincidence.")
    else:
        displacement = geometry_cache.displacement
        distance = geometry_cache.distance
    if receiver_directional is None:
        receiver_direction = np.zeros_like(np.asarray(receiver_points, dtype=float), dtype=float)
    else:
        receiver_direction = np.asarray(receiver_directional, dtype=float)
    if source_directional is None:
        source_direction = np.zeros_like(np.asarray(source_points, dtype=float), dtype=float)
    else:
        source_direction = np.asarray(source_directional, dtype=float)
    relative_direction = receiver_direction[:, None, :] - source_direction[None, :, :]
    distance_directional = np.sum(displacement * relative_direction, axis=2) / distance
    return displacement, distance, distance_directional


def _single_layer_point_directional_potential(
    *,
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    source_weights: np.ndarray,
    densities: np.ndarray,
    wavenumber: complex,
    receiver_directional: np.ndarray | None,
    source_directional: np.ndarray | None,
    geometry_cache: _PairwiseGeometryCache | None = None,
) -> np.ndarray:
    density_array = _coerce_row_major_densities(densities, num_boundary_samples=source_points.shape[0])
    displacement, distance, distance_directional = _pairwise_geometry_directional_terms(
        receiver_points,
        source_points,
        receiver_directional=receiver_directional,
        source_directional=source_directional,
        geometry_cache=geometry_cache,
    )
    kernel_argument = complex(wavenumber) * distance
    kernel_directional = -0.25j * complex(wavenumber) * hankel1(1, kernel_argument) * distance_directional
    weighted_density = density_array * np.asarray(source_weights, dtype=float)[None, :]
    return np.einsum("mn,bn->bm", kernel_directional, weighted_density, optimize=True)


def _double_layer_point_directional_potential(
    *,
    receiver_points: np.ndarray,
    source_points: np.ndarray,
    source_normals: np.ndarray,
    source_weights: np.ndarray,
    densities: np.ndarray,
    wavenumber: complex,
    receiver_directional: np.ndarray | None,
    source_directional: np.ndarray | None,
    geometry_cache: _PairwiseGeometryCache | None = None,
) -> np.ndarray:
    density_array = _coerce_row_major_densities(densities, num_boundary_samples=source_points.shape[0])
    displacement, distance, distance_directional = _pairwise_geometry_directional_terms(
        receiver_points,
        source_points,
        receiver_directional=receiver_directional,
        source_directional=source_directional,
        geometry_cache=geometry_cache,
    )
    normals = np.asarray(source_normals, dtype=float)
    numerator = np.einsum("mnd,nd->mn", displacement, normals, optimize=True)
    factor = numerator / distance
    if receiver_directional is None:
        receiver_direction = np.zeros_like(receiver_points, dtype=float)
    else:
        receiver_direction = np.asarray(receiver_directional, dtype=float)
    if source_directional is None:
        source_direction = np.zeros_like(source_points, dtype=float)
    else:
        source_direction = np.asarray(source_directional, dtype=float)
    relative_direction = receiver_direction[:, None, :] - source_direction[None, :, :]
    numerator_directional = np.einsum("mnd,nd->mn", relative_direction, normals, optimize=True)
    factor_directional = numerator_directional / distance - numerator * distance_directional / (distance**2)
    z = complex(wavenumber) * distance
    h0 = hankel1(0, z)
    h1 = hankel1(1, z)
    h2 = hankel1(2, z)
    h1_radial_directional = 0.5 * complex(wavenumber) * (h0 - h2) * distance_directional
    kernel_directional = 0.25j * complex(wavenumber) * (h1_radial_directional * factor + h1 * factor_directional)
    weighted_density = density_array * np.asarray(source_weights, dtype=float)[None, :]
    return np.einsum("mn,bn->bm", kernel_directional, weighted_density, optimize=True)


def _one_sided_normal_derivative(sample_values: list[np.ndarray], step: float, *, from_inside: bool) -> np.ndarray:
    if len(sample_values) != 3:
        raise ValueError("sample_values must contain evaluations at offsets h, 2h, and 3h.")
    sign = 1.0 if from_inside else -1.0
    return sign * (5.0 * sample_values[0] - 8.0 * sample_values[1] + 3.0 * sample_values[2]) / (2.0 * step)


def _single_layer_boundary_trace_point_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        outside_points = geometry_cache.outside_points[0]
        inside_points = geometry_cache.inside_points[0]
        outside = _single_layer_point_directional_potential(
            receiver_points=outside_points,
            source_points=boundary_points,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
            geometry_cache=geometry_cache.offset_geometries[0],
        )
        inside = _single_layer_point_directional_potential(
            receiver_points=inside_points,
            source_points=boundary_points,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
            geometry_cache=geometry_cache.offset_geometries[3],
        )
    else:
        outside = _single_layer_point_directional_potential(
            receiver_points=boundary_points + offset_distance * normals,
            source_points=boundary_points,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
        )
        inside = _single_layer_point_directional_potential(
            receiver_points=boundary_points - offset_distance * normals,
            source_points=boundary_points,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
        )
    return 0.5 * (outside + inside)


def _double_layer_boundary_trace_point_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        outside_points = geometry_cache.outside_points[0]
        inside_points = geometry_cache.inside_points[0]
        outside = _double_layer_point_directional_potential(
            receiver_points=outside_points,
            source_points=boundary_points,
            source_normals=normals,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
            geometry_cache=geometry_cache.offset_geometries[0],
        )
        inside = _double_layer_point_directional_potential(
            receiver_points=inside_points,
            source_points=boundary_points,
            source_normals=normals,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
            geometry_cache=geometry_cache.offset_geometries[3],
        )
    else:
        outside = _double_layer_point_directional_potential(
            receiver_points=boundary_points + offset_distance * normals,
            source_points=boundary_points,
            source_normals=normals,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
        )
        inside = _double_layer_point_directional_potential(
            receiver_points=boundary_points - offset_distance * normals,
            source_points=boundary_points,
            source_normals=normals,
            source_weights=weights,
            densities=densities,
            wavenumber=wavenumber,
            receiver_directional=point_directional,
            source_directional=point_directional,
        )
    return 0.5 * (outside + inside)


def _single_layer_normal_derivative_trace_point_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    outside_samples: list[np.ndarray] = []
    inside_samples: list[np.ndarray] = []
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        offset_distance = geometry_cache.offset_distance
        outside_points = geometry_cache.outside_points
        inside_points = geometry_cache.inside_points
        offset_geometries = geometry_cache.offset_geometries
    else:
        outside_points = tuple(boundary_points + float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        inside_points = tuple(boundary_points - float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        offset_geometries = (None, None, None, None, None, None)
    for multiplier in (1, 2, 3):
        outside_samples.append(
            _single_layer_point_directional_potential(
                receiver_points=outside_points[multiplier - 1],
                source_points=boundary_points,
                source_weights=weights,
                densities=densities,
                wavenumber=wavenumber,
                receiver_directional=point_directional,
                source_directional=point_directional,
                geometry_cache=offset_geometries[multiplier - 1],
            )
        )
        inside_samples.append(
            _single_layer_point_directional_potential(
                receiver_points=inside_points[multiplier - 1],
                source_points=boundary_points,
                source_weights=weights,
                densities=densities,
                wavenumber=wavenumber,
                receiver_directional=point_directional,
                source_directional=point_directional,
                geometry_cache=offset_geometries[multiplier + 2],
            )
        )
    outside_derivative = _one_sided_normal_derivative(outside_samples, float(offset_distance), from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, float(offset_distance), from_inside=True)
    return 0.5 * (outside_derivative + inside_derivative)


def _double_layer_normal_derivative_trace_point_directional(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    densities: np.ndarray,
    wavenumber: complex,
    geometry_cache: _LeadingOrderBoundaryGeometryCache | None = None,
) -> np.ndarray:
    outside_samples: list[np.ndarray] = []
    inside_samples: list[np.ndarray] = []
    if geometry_cache is not None:
        boundary_points = geometry_cache.boundary_points
        normals = geometry_cache.normals
        weights = geometry_cache.weights
        offset_distance = geometry_cache.offset_distance
        outside_points = geometry_cache.outside_points
        inside_points = geometry_cache.inside_points
        offset_geometries = geometry_cache.offset_geometries
    else:
        outside_points = tuple(boundary_points + float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        inside_points = tuple(boundary_points - float(multiplier) * float(offset_distance) * normals for multiplier in (1, 2, 3))
        offset_geometries = (None, None, None, None, None, None)
    for multiplier in (1, 2, 3):
        outside_samples.append(
            _double_layer_point_directional_potential(
                receiver_points=outside_points[multiplier - 1],
                source_points=boundary_points,
                source_normals=normals,
                source_weights=weights,
                densities=densities,
                wavenumber=wavenumber,
                receiver_directional=point_directional,
                source_directional=point_directional,
                geometry_cache=offset_geometries[multiplier - 1],
            )
        )
        inside_samples.append(
            _double_layer_point_directional_potential(
                receiver_points=inside_points[multiplier - 1],
                source_points=boundary_points,
                source_normals=normals,
                source_weights=weights,
                densities=densities,
                wavenumber=wavenumber,
                receiver_directional=point_directional,
                source_directional=point_directional,
                geometry_cache=offset_geometries[multiplier + 2],
            )
        )
    outside_derivative = _one_sided_normal_derivative(outside_samples, float(offset_distance), from_inside=False)
    inside_derivative = _one_sided_normal_derivative(inside_samples, float(offset_distance), from_inside=True)
    return 0.5 * (outside_derivative + inside_derivative)


def _ibim_system_action_point_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    offset_distance: float,
    wavenumber_exterior: complex,
    wavenumber_interior: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
    formulation: str = "muller",
    normal_derivative_scheme: str = "analytic_extrapolated",
) -> np.ndarray:
    if formulation == "muller" and normal_derivative_scheme == "analytic_extrapolated":
        return _muller_analytic_system_action_point_directional_derivative(
            boundary_points=boundary_points,
            normals=normals,
            weights=weights,
            point_directional=point_directional,
            offset_distance=offset_distance,
            wavenumber_exterior=wavenumber_exterior,
            wavenumber_interior=wavenumber_interior,
            dirichlet_density=dirichlet_density,
            neumann_density=neumann_density,
        )
    single_layer_action = _single_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
    )
    single_layer_action += _single_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
    )
    double_layer_action = _double_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
    )
    double_layer_action += _double_layer_boundary_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
    )
    adjoint_double_layer_action = _single_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_exterior,
    )
    adjoint_double_layer_action += _single_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=neumann_density,
        wavenumber=wavenumber_interior,
    )
    hypersingular_trace_action = _double_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_exterior,
    )
    hypersingular_trace_action += _double_layer_normal_derivative_trace_point_directional(
        boundary_points=boundary_points,
        normals=normals,
        weights=weights,
        point_directional=point_directional,
        offset_distance=offset_distance,
        densities=dirichlet_density,
        wavenumber=wavenumber_interior,
    )
    top = -double_layer_action + single_layer_action
    bottom = -hypersingular_trace_action + adjoint_double_layer_action
    return np.concatenate((top, bottom), axis=1).astype(np.complex128, copy=False)


def _ibim_incident_trace_point_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    point_directional: np.ndarray,
    source_points: np.ndarray,
    source_strengths: np.ndarray,
    wavenumber: complex,
) -> np.ndarray:
    source_points_array = np.asarray(source_points, dtype=float)
    strengths = np.asarray(source_strengths, dtype=np.complex128).reshape(-1)
    if source_points_array.shape[0] != strengths.shape[0]:
        raise ValueError("source_points and source_strengths must have the same batch size.")
    displacement = boundary_points[None, :, :] - source_points_array[:, None, :]
    distance = np.linalg.norm(displacement, axis=2)
    if np.min(distance) <= 1.0e-10:
        raise ValueError("Boundary samples coincide with source points in incident-trace derivative evaluation.")
    distance_directional = np.sum(displacement * point_directional[None, :, :], axis=2) / distance
    z = complex(wavenumber) * distance
    h0 = hankel1(0, z)
    h1 = hankel1(1, z)
    h2 = hankel1(2, z)
    h1_radial_directional = 0.5 * complex(wavenumber) * (h0 - h2) * distance_directional

    dirichlet_directional = strengths[:, None] * (-0.25j * complex(wavenumber) * h1 * distance_directional)

    numerator = np.einsum("bnd,nd->bn", displacement, normals, optimize=True)
    factor = numerator / distance
    numerator_directional = np.einsum("nd,bnd->bn", normals, np.broadcast_to(point_directional[None, :, :], displacement.shape), optimize=True)
    factor_directional = numerator_directional / distance - numerator * distance_directional / (distance**2)
    neumann_directional = strengths[:, None] * (
        -0.25j * complex(wavenumber) * (h1_radial_directional * factor + h1 * factor_directional)
    )
    return np.concatenate((dirichlet_directional, neumann_directional), axis=1).astype(np.complex128, copy=False)


def _paired_receiver_response(potentials: np.ndarray) -> np.ndarray:
    potential_array = np.asarray(potentials, dtype=np.complex128)
    if potential_array.ndim != 2:
        raise ValueError("potentials must have shape (batch, num_receivers).")
    if potential_array.shape[0] != potential_array.shape[1]:
        raise ValueError("Receiver directional evaluation currently expects one receiver per batch/source.")
    return np.diag(potential_array).astype(np.complex128, copy=False)


def _ibim_receiver_action_point_directional_derivative(
    *,
    boundary_points: np.ndarray,
    normals: np.ndarray,
    weights: np.ndarray,
    point_directional: np.ndarray,
    receiver_points: np.ndarray,
    wavenumber: complex,
    dirichlet_density: np.ndarray,
    neumann_density: np.ndarray,
) -> np.ndarray:
    double_directional = _double_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points,
        source_normals=normals,
        source_weights=weights,
        densities=dirichlet_density,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=point_directional,
    )
    single_directional = _single_layer_point_directional_potential(
        receiver_points=np.asarray(receiver_points, dtype=float),
        source_points=boundary_points,
        source_weights=weights,
        densities=neumann_density,
        wavenumber=wavenumber,
        receiver_directional=None,
        source_directional=point_directional,
    )
    return _paired_receiver_response(double_directional - single_directional)


def _coerce_angular_frequencies(angular_frequencies) -> np.ndarray:
    frequencies = np.atleast_1d(np.asarray(angular_frequencies, dtype=float))
    if frequencies.ndim != 1 or frequencies.size == 0:
        raise ValueError("angular_frequencies must be a non-empty scalar or 1D array.")
    return frequencies


def _coerce_multifrequency_observed_data(observed_data: np.ndarray, num_frequencies: int) -> np.ndarray:
    observed_array = np.asarray(observed_data, dtype=np.complex128)
    if num_frequencies == 1 and observed_array.ndim == 1:
        return observed_array[None, :]
    if observed_array.ndim != 2 or observed_array.shape[0] != num_frequencies:
        raise ValueError("observed_data must have shape (num_frequencies, num_receivers).")
    return observed_array


def _coerce_frequency_weights(frequency_weights: np.ndarray | None, num_frequencies: int) -> np.ndarray:
    if frequency_weights is None:
        return np.ones(num_frequencies, dtype=float)
    weights = np.asarray(frequency_weights, dtype=float)
    if weights.shape != (num_frequencies,):
        raise ValueError("frequency_weights must have shape (num_frequencies,).")
    return weights


def _coerce_time_vector(time_vector) -> np.ndarray:
    time_array = np.asarray(time_vector, dtype=float)
    if time_array.ndim != 1 or time_array.size == 0:
        raise ValueError("time_vector must be a non-empty 1D array.")
    return time_array


def _coerce_frequency_window(frequency_window: np.ndarray | None, num_frequencies: int) -> np.ndarray:
    if frequency_window is None:
        return np.ones(num_frequencies, dtype=float)
    window = np.asarray(frequency_window, dtype=float)
    if window.shape != (num_frequencies,):
        raise ValueError("frequency_window must have shape (num_frequencies,).")
    return window


def _coerce_multifrequency_source_strengths(
    source_strength,
    *,
    num_frequencies: int,
    num_sources: int,
) -> tuple[complex | np.ndarray, ...]:
    source_strength_array = np.asarray(source_strength, dtype=np.complex128)
    if source_strength_array.ndim == 0:
        scalar = complex(source_strength_array.item())
        return tuple(scalar for _ in range(num_frequencies))
    if source_strength_array.ndim == 1:
        if source_strength_array.shape[0] == num_sources and source_strength_array.shape[0] != num_frequencies:
            shared = np.asarray(source_strength_array, dtype=np.complex128)
            return tuple(shared.copy() for _ in range(num_frequencies))
        if source_strength_array.shape[0] == num_frequencies and source_strength_array.shape[0] != num_sources:
            return tuple(complex(source_strength_array[index]) for index in range(num_frequencies))
        if source_strength_array.shape[0] == num_frequencies == num_sources:
            raise ValueError(
                "Ambiguous 1D source_strength: it matches both num_frequencies and num_sources."
            )
    if source_strength_array.ndim == 2:
        if source_strength_array.shape == (num_frequencies, num_sources):
            return tuple(np.asarray(source_strength_array[index], dtype=np.complex128) for index in range(num_frequencies))
        if source_strength_array.shape == (num_frequencies, 1):
            return tuple(complex(source_strength_array[index, 0]) for index in range(num_frequencies))
    raise ValueError(
        "source_strength must be scalar, shape-(num_sources,), shape-(num_frequencies,), "
        "or shape-(num_frequencies, num_sources)."
    )


def _time_gate_mask(time_vector: np.ndarray, *, time_gate_start: float | None = None) -> np.ndarray:
    time_array = _coerce_time_vector(time_vector)
    if time_gate_start is None:
        return np.ones(time_array.shape, dtype=bool)
    mask = time_array >= float(time_gate_start)
    if not np.any(mask):
        raise ValueError("time_gate_start excludes every time sample in the current time_vector.")
    return mask


def _coerce_time_sample_weights(sample_weights: np.ndarray | None, predicted_shape: tuple[int, ...]) -> np.ndarray:
    if sample_weights is None:
        return np.ones(predicted_shape, dtype=float)
    weights = np.asarray(sample_weights, dtype=float)
    if np.any(weights < 0.0):
        raise ValueError("sample_weights must be non-negative.")
    if weights.ndim == 1:
        if len(predicted_shape) != 2 or weights.shape != (predicted_shape[1],):
            raise ValueError("1D sample_weights must have shape (num_time_samples,).")
        return np.broadcast_to(weights[None, :], predicted_shape).astype(float, copy=True)
    if weights.shape != predicted_shape:
        raise ValueError("sample_weights must be 1D over time or have the same shape as predicted.")
    return weights.astype(float, copy=True)


def real_l2_data_misfit_masked(
    predicted: np.ndarray,
    observed: np.ndarray,
    *,
    sample_mask: np.ndarray | None = None,
    sample_weights: np.ndarray | None = None,
) -> tuple[float, np.ndarray]:
    predicted_array = np.asarray(predicted, dtype=float)
    observed_array = np.asarray(observed, dtype=float)
    if predicted_array.shape != observed_array.shape:
        raise ValueError("predicted and observed must have the same shape.")
    residual = predicted_array - observed_array
    if sample_mask is None:
        active_mask = np.ones(predicted_array.shape, dtype=bool)
    else:
        mask = np.asarray(sample_mask, dtype=bool)
        if mask.ndim == 1:
            if predicted_array.ndim != 2 or mask.shape != (predicted_array.shape[1],):
                raise ValueError("1D sample_mask must have shape (num_time_samples,).")
            active_mask = np.broadcast_to(mask[None, :], predicted_array.shape)
        elif mask.shape == predicted_array.shape:
            active_mask = mask
        else:
            raise ValueError("sample_mask must be 1D over time or have the same shape as predicted.")
    weights = _coerce_time_sample_weights(sample_weights, predicted_array.shape)
    active_weights = np.where(active_mask, weights, 0.0)
    active_weight_sum = float(np.sum(active_weights))
    if active_weight_sum <= 0.0:
        raise ValueError("sample_mask excludes every sample.")
    weighted_residual = residual * active_weights
    loss = 0.5 * float(np.sum(active_weights * residual**2) / active_weight_sum)
    return loss, weighted_residual


def _inverse_frequency_transform_matrix(
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    *,
    frequency_window: np.ndarray | None = None,
) -> np.ndarray:
    frequencies = _coerce_angular_frequencies(angular_frequencies)
    time_array = _coerce_time_vector(time_vector)
    window = _coerce_frequency_window(frequency_window, frequencies.size)
    integration_weights = _trapz_weights(frequencies) / (2.0 * np.pi)
    return (window * integration_weights)[:, None] * np.exp(-1j * frequencies[:, None] * time_array[None, :])


def _frequency_response_dual_from_bscan_residual(
    residual: np.ndarray,
    angular_frequencies: np.ndarray,
    time_vector: np.ndarray,
    *,
    frequency_window: np.ndarray | None = None,
    sample_mask: np.ndarray | None = None,
    sample_weights: np.ndarray | None = None,
) -> np.ndarray:
    residual_array = np.asarray(residual, dtype=float)
    if residual_array.ndim != 2:
        raise ValueError("residual must have shape (batch, num_times).")
    transform = _inverse_frequency_transform_matrix(
        angular_frequencies,
        time_vector,
        frequency_window=frequency_window,
    )
    active_weights = _coerce_time_sample_weights(sample_weights, residual_array.shape)
    if sample_mask is None:
        active_weight_sum = float(np.sum(active_weights))
    else:
        mask = np.asarray(sample_mask, dtype=bool)
        if mask.ndim == 1:
            if mask.shape != (residual_array.shape[1],):
                raise ValueError("1D sample_mask must have shape (num_time_samples,).")
            active_mask = np.broadcast_to(mask[None, :], residual_array.shape)
        elif mask.shape == residual_array.shape:
            active_mask = mask
        else:
            raise ValueError("sample_mask must be 1D over time or have the same shape as residual.")
        active_weight_sum = float(np.sum(np.where(active_mask, active_weights, 0.0)))
        if active_weight_sum <= 0.0:
            raise ValueError("sample_mask excludes every sample.")
    if sample_mask is None and active_weight_sum <= 0.0:
        raise ValueError("sample_weights exclude every sample.")
    return 2.0 * (residual_array / active_weight_sum) @ np.conjugate(transform).T
