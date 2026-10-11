"""Branch-local automatic differentiation of the production Method-B map.

The neural field owns the geometry.  Marching-squares connectivity and its
canonical starting vertex are discrete decisions; after those decisions have
been made at the current field, every continuous operation is replayed in
Torch: grid-edge interpolation, both polygon resamplings and Newton
projections, chord parameters, Fourier least squares, the numerical arc-length
inverse, and the final native Fourier refit.  No perturbed field or BEM solve
is used to construct a derivative.

This is a derivative on the current extraction branch, not a derivative
through changes in contour topology.  Every proposed neural update still
requires a fresh production extraction and forward evaluation.  Exact grid
vertex crossings are rejected because they do not determine a unique smooth
marching-squares branch.  Other discrete branch boundaries (phase selection,
interpolation bins, Newton convergence/clipping) have the usual one-sided
branch interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch

from ordered_boundary import PeriodicCurve2D
from sdf_to_ordered_boundary import FrontendConfig, ProjectionConfig, TorchImplicitField2D
from sdf_to_ordered_boundary.frontend import (
    ComponentCountError,
    _physical_contours,
    evaluate_cartesian_grid,
)

from .geometry import (
    OrderedSDFGeometryConfig,
    _model_tensor_options,
    _projection_residual_tolerance,
    build_ordered_sdf_geometry,
)


class MethodBPullbackError(RuntimeError):
    """The current Method-B conversion has no admissible verified pullback."""


@dataclass(frozen=True)
class MethodBPullback:
    """Native Fourier geometry tensors connected to the implicit model.

    ``points`` and the derivatives use the production uniform parameter grid,
    with derivatives taken with respect to its angle in radians.  Contract
    solver covectors with these tensors and backpropagate that scalar; do not
    apply a second boundary quadrature weight to covectors already weighted
    by the solver's discrete derivative.
    """

    points: torch.Tensor
    first_derivatives: torch.Tensor
    second_derivatives: torch.Tensor
    curve: PeriodicCurve2D
    maximum_replay_error: float


def _values(model: Any, points: torch.Tensor, dtype: torch.dtype) -> torch.Tensor:
    values = model(points.to(dtype=dtype))
    if not isinstance(values, torch.Tensor) or values.numel() != points.shape[0]:
        raise MethodBPullbackError("The implicit model must return one scalar per point.")
    values = values.reshape(-1).to(dtype=torch.float64)
    if not bool(torch.isfinite(values.detach()).all()):
        raise MethodBPullbackError("The implicit model returned non-finite values.")
    return values


def _interpolate(
    targets: torch.Tensor, abscissae: torch.Tensor, ordinates: torch.Tensor
) -> torch.Tensor:
    """NumPy-interp equivalent, differentiating the current interval formula."""

    differences = torch.diff(abscissae)
    if not bool((differences.detach() > 0.0).all()):
        raise MethodBPullbackError("Method-B interpolation requires increasing abscissae.")
    indices = torch.searchsorted(abscissae.detach(), targets.detach(), right=True) - 1
    indices = indices.clamp(0, abscissae.numel() - 2)
    fraction = (targets - abscissae[indices]) / differences[indices]
    if ordinates.ndim == 2:
        fraction = fraction[:, None]
    return ordinates[indices] + fraction * (ordinates[indices + 1] - ordinates[indices])


def _chord_lengths(points: torch.Tensor) -> torch.Tensor:
    lengths = torch.linalg.vector_norm(torch.roll(points, -1, dims=0) - points, dim=1)
    if not bool((lengths.detach() > 0.0).all()):
        raise MethodBPullbackError("The contour has a degenerate chord.")
    return lengths


def _resample(points: torch.Tensor, count: int) -> torch.Tensor:
    cumulative = torch.cat((points.new_zeros(1), torch.cumsum(_chord_lengths(points), 0)))
    targets = cumulative[-1] * torch.arange(count, device=points.device, dtype=points.dtype) / count
    return _interpolate(targets, cumulative, torch.cat((points, points[:1]), dim=0))


def _project(
    model: Any, points: torch.Tensor, dtype: torch.dtype, config: FrontendConfig
) -> torch.Tensor:
    """Replay the native safeguarded Newton algorithm with an attached graph."""

    settings = config.projection
    max_step = settings.max_step_grid_fraction * min(config.grid_spacing)
    converged = torch.zeros(points.shape[0], dtype=torch.bool, device=points.device)
    for _ in range(settings.max_iterations):
        indices = torch.nonzero(~converged, as_tuple=False).reshape(-1)
        if indices.numel() == 0:
            break
        active_points = points[indices]
        # Input gradients need their own differentiable argument even for a
        # parameter-free model.  Do not use model.spatial_gradient(): the
        # legacy helper detaches coordinates and loses the Newton Hessian term.
        if not active_points.requires_grad:
            active_points = active_points.requires_grad_(True)
        values = _values(model, active_points, dtype)
        newly_converged = values.detach().abs() <= settings.residual_tolerance
        converged[indices[newly_converged]] = True
        remaining = ~newly_converged
        if not bool(remaining.any()):
            continue
        if not values.requires_grad:
            raise MethodBPullbackError("The implicit field has no spatial derivative.")
        gradients = torch.autograd.grad(values.sum(), active_points, create_graph=True)[0]
        gradients = gradients[remaining]
        norms = torch.linalg.vector_norm(gradients, dim=1)
        if bool((norms.detach() < settings.gradient_tolerance).any()):
            raise MethodBPullbackError("Zero-set projection encountered a critical field point.")
        corrections = values[remaining, None] * gradients / (
            norms[:, None].square() + settings.denominator_epsilon
        )
        correction_norms = torch.linalg.vector_norm(corrections, dim=1)
        clipped = correction_norms.detach() > max_step
        if bool(clipped.any()):
            # Clamp only the selected branches.  This avoids 0/0 in inactive
            # branches which would otherwise contaminate the backward pass.
            scales = torch.ones_like(correction_norms)
            scales = scales.index_copy(0, torch.nonzero(clipped).reshape(-1), max_step / correction_norms[clipped])
            corrections = corrections * scales[:, None]
        indices = indices[remaining]
        points = points.index_copy(0, indices, points[indices] - corrections)
    final_values = _values(model, points, dtype)
    if bool((final_values.detach().abs() > settings.residual_tolerance).any()):
        raise MethodBPullbackError("Differentiable zero-set projection did not converge.")
    return points


def _edge_intersections(
    model: Any, raw_contour: np.ndarray, config: FrontendConfig,
    *, device: Any, dtype: torch.dtype,
) -> torch.Tensor:
    """Recover the active marching-squares edges from canonical raw vertices."""

    lower = np.asarray(config.bounds[0])
    spacing = np.asarray(config.grid_spacing)
    coordinates = (raw_contour - lower) / spacing
    nearest = np.rint(coordinates)
    integer = np.abs(coordinates - nearest) < 2.0e-10
    if bool(np.any(np.all(integer, axis=1))):
        raise MethodBPullbackError(
            "The zero contour crosses an exact Cartesian grid vertex; "
            "the marching-squares derivative is not unique on this branch boundary."
        )
    if not bool(np.all(np.any(integer, axis=1))):
        raise MethodBPullbackError("Cannot identify the native marching-squares grid edges.")
    first_indices = np.floor(coordinates)
    first_indices[integer] = nearest[integer]
    second_indices = first_indices.copy()
    second_indices[~integer] += 1.0
    first = torch.tensor(lower + spacing * first_indices, device=device, dtype=torch.float64)
    second = torch.tensor(lower + spacing * second_indices, device=device, dtype=torch.float64)
    first_values = _values(model, first, dtype)
    second_values = _values(model, second, dtype)
    denominator = first_values - second_values
    if bool((denominator.detach() == 0.0).any()):
        raise MethodBPullbackError("A marching-squares edge has a singular zero crossing.")
    fraction = first_values / denominator
    if not bool(((fraction.detach() > 0.0) & (fraction.detach() < 1.0)).all()):
        raise MethodBPullbackError("The active marching-squares edge no longer brackets zero.")
    return first + fraction[:, None] * (second - first)


def _basis(parameters: torch.Tensor, bandwidth: int, order: int = 0) -> torch.Tensor:
    modes = torch.arange(1, bandwidth + 1, device=parameters.device, dtype=parameters.dtype)
    angles = parameters[:, None] * modes[None, :] + order * (np.pi / 2.0)
    factors = modes.pow(order)
    harmonics = torch.stack((torch.cos(angles) * factors, torch.sin(angles) * factors), dim=-1)
    constant = torch.ones_like(parameters) if order == 0 else torch.zeros_like(parameters)
    return torch.cat((constant[:, None], harmonics.reshape(parameters.numel(), -1)), dim=1)


def _fit(parameters: torch.Tensor, points: torch.Tensor, bandwidth: int) -> torch.Tensor:
    design = _basis(parameters, bandwidth)
    # The native implementation rejects rank deficiency, so the differentiable
    # branch can use the unique full-column-rank least-squares solution.
    singular = torch.linalg.svdvals(design.detach())
    threshold = torch.finfo(design.dtype).eps * max(design.shape) * singular[0]
    if bool(singular[-1] <= threshold):
        raise MethodBPullbackError("The Fourier least-squares design is rank deficient.")
    return torch.linalg.lstsq(design, points, driver="gels").solution


def build_method_b_pullback(
    model: Any,
    config: OrderedSDFGeometryConfig,
    *,
    reference_curve: PeriodicCurve2D | None = None,
) -> MethodBPullback:
    """Build and verify differentiable native geometry at the current field.

    Pass the curve from the already evaluated production forward call to avoid
    repeating its geometry validation.  The replay must match positions and
    both native derivatives; mismatches fail rather than silently substituting
    a different curve or a frozen-normal surrogate.  Model parameter ``.grad``
    buffers are not changed by this function.
    """

    if not isinstance(config, OrderedSDFGeometryConfig):
        raise TypeError("config must be OrderedSDFGeometryConfig.")
    if reference_curve is None:
        reference_curve = build_ordered_sdf_geometry(model, config).curve
    if not isinstance(reference_curve, PeriodicCurve2D):
        raise TypeError("reference_curve must be PeriodicCurve2D.")
    device, dtype = _model_tensor_options(model)
    frontend_config = FrontendConfig(
        bounds=config.bounds,
        grid_shape=config.grid_shape,
        projected_samples=config.projected_samples,
        projection=ProjectionConfig(residual_tolerance=_projection_residual_tolerance(dtype)),
    )
    field = TorchImplicitField2D(model, device=device, dtype=dtype)
    grid = evaluate_cartesian_grid(field, frontend_config)
    contours = _physical_contours(grid, frontend_config)
    if len(contours) != 1:
        raise ComponentCountError(len(contours))

    with torch.enable_grad():
        points = _edge_intersections(model, contours[0], frontend_config, device=device, dtype=dtype)
        for _ in range(2):
            points = _project(model, _resample(points, config.projected_samples), dtype, frontend_config)
        lengths = _chord_lengths(points)
        parameters = 2.0 * np.pi * torch.cat((points.new_zeros(1), torch.cumsum(lengths[:-1], 0))) / lengths.sum()
        coefficients = _fit(parameters, points, config.bandwidth)

        dense_count = config.arclength_dense_resolution
        dense_parameters = 2.0 * np.pi * torch.arange(dense_count + 1, device=device, dtype=torch.float64) / dense_count
        speeds = torch.linalg.vector_norm(_basis(dense_parameters, config.bandwidth, 1) @ coefficients, dim=1)
        if not bool((speeds.detach() > 0.0).all()):
            raise MethodBPullbackError("The initial Fourier curve has zero native speed.")
        increments = (np.pi / dense_count) * (speeds[:-1] + speeds[1:])
        cumulative = torch.cat((points.new_zeros(1), torch.cumsum(increments, 0)))
        uniform_parameters = 2.0 * np.pi * torch.arange(config.projected_samples, device=device, dtype=torch.float64) / config.projected_samples
        inverse_parameters = _interpolate(uniform_parameters / (2.0 * np.pi) * cumulative[-1], cumulative, dense_parameters)
        refit_points = _basis(inverse_parameters, config.bandwidth) @ coefficients
        final_coefficients = _fit(uniform_parameters, refit_points, config.bandwidth)
        node_parameters = 2.0 * np.pi * torch.arange(config.num_nodes, device=device, dtype=torch.float64) / config.num_nodes
        tensors = tuple(_basis(node_parameters, config.bandwidth, order) @ final_coefficients for order in range(3))

    references = (reference_curve.points, reference_curve.first_derivatives, reference_curve.second_derivatives)
    errors = []
    for tensor, reference in zip(tensors, references):
        detached = tensor.detach().cpu().numpy()
        if detached.shape != reference.shape:
            raise MethodBPullbackError("The pullback and production curve have different node shapes.")
        error = float(np.max(np.abs(detached - reference)))
        errors.append(error)
        scale = max(float(np.max(np.abs(reference))), np.finfo(np.float64).tiny)
        # Native field arithmetic can be float32; the geometry arithmetic is
        # float64 in both paths.  This tolerance checks branch replay, not the
        # accuracy of the curve relative to the true zero set.
        tolerance = max(2.0e-10, 64.0 * float(torch.finfo(dtype).eps)) * scale
        if not np.isfinite(error) or error > tolerance:
            raise MethodBPullbackError(
                f"Differentiable Method B disagrees with production geometry: {error:.3e} > {tolerance:.3e}."
            )
    return MethodBPullback(*tensors, reference_curve, max(errors))


__all__ = ["MethodBPullback", "MethodBPullbackError", "build_method_b_pullback"]
