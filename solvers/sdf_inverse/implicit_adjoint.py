"""Implicit MLP + Method B inversion with a discrete Kress adjoint.

The accepted state is always the neural field.  The adjoint contracts the
geometry dependence of the solved Kress system, and a branch-local reverse
of extraction/Method B transfers that covector into the network.  Neither
network-weight nor BEM finite differences are used to construct an update.
Every line-search trial rebuilds the actual neural zero contour and solves
it.  Adam moments advance only with an accepted neural update.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import math
from time import perf_counter
from typing import Any, Callable

import numpy as np
import torch

from .forward import PairedForwardResult, predict_paired_response
from .geometry import OrderedSDFGeometryConfig, OrderedSDFGeometryError
from .models import TorchParameterController
from .optimization import ComplexScatteredData, normalized_complex_residual


@dataclass(frozen=True)
class ImplicitMLPAdjointConfig:
    max_iterations: int = 60
    learning_rate: float = 1.0e-3
    eikonal_weight: float = 0.01
    regularization_samples: int = 512
    random_seed: int = 0
    max_backtracks: int = 12
    backtrack_factor: float = 0.5
    armijo_fraction: float = 1.0e-4
    maximum_boundary_step_m: float = 2.0e-3
    gradient_clip_norm: float = 10.0
    gradient_tolerance: float = 1.0e-10
    loss_tolerance: float = 1.0e-12

    def __post_init__(self):
        for name in ("max_iterations", "regularization_samples", "max_backtracks"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if isinstance(self.random_seed, bool) or not isinstance(self.random_seed, (int, np.integer)) or self.random_seed < 0:
            raise ValueError("random_seed must be a nonnegative integer.")
        for name in ("learning_rate", "maximum_boundary_step_m", "gradient_clip_norm",
                     "gradient_tolerance", "loss_tolerance"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive.")
        if not math.isfinite(self.eikonal_weight) or self.eikonal_weight < 0:
            raise ValueError("eikonal_weight must be finite and nonnegative.")
        for name in ("backtrack_factor", "armijo_fraction"):
            if not 0.0 < getattr(self, name) < 1.0:
                raise ValueError(f"{name} must lie between zero and one.")


@dataclass(frozen=True)
class ImplicitMLPIteration:
    iteration: int
    parameter_names: tuple[str, ...]
    parameter_vector: np.ndarray
    physical_parameters: dict[str, float]
    loss: float
    relative_l2_error: float
    gradient: np.ndarray | None
    step: np.ndarray
    evaluation_count: int
    timings: dict[str, float]
    geometry_points: np.ndarray
    maximum_system_residual: float
    objective: float
    eikonal_loss: float
    data_gradient: np.ndarray | None
    backtracks: int = 0
    step_method: str = "initial"
    # Compatibility with existing trajectory renderers; Adam has no LM damping.
    damping: float = 0.0
    gradient_evaluated: bool = True


@dataclass(frozen=True)
class ImplicitMLPInverseResult:
    solver: str
    parameter_names: tuple[str, ...]
    iterations: tuple[ImplicitMLPIteration, ...]
    converged: bool
    stop_reason: str
    total_evaluation_count: int
    maximum_system_residual: float
    total_forward_seconds: float
    total_seconds: float
    infeasible_trial_count: int
    diagnostics: dict[str, Any] = field(default_factory=dict)
    cache_hit_count: int = 0
    maximum_frozen_jacobian_columns: int = 0

    @property
    def initial_iteration(self):
        return self.iterations[0]

    @property
    def final_iteration(self):
        return self.iterations[-1]


def _trainable(model):
    parameters = tuple(p for p in model.parameters() if p.requires_grad)
    if not parameters:
        raise ValueError("The implicit field must have trainable parameters.")
    if any(p.dtype != torch.float64 for p in parameters):
        raise ValueError("The verified Method-B adjoint path requires float64 network parameters.")
    return parameters


def _flatten_gradient(values, parameters):
    result = np.concatenate([
        np.zeros(p.numel()) if value is None else value.detach().cpu().numpy().reshape(-1)
        for value, p in zip(values, parameters)
    ])
    if not np.all(np.isfinite(result)):
        raise FloatingPointError("The implicit adjoint produced a non-finite parameter gradient.")
    return result


def _residual_transform(data):
    """The exact fixed normalization used by normalized_complex_residual."""
    observed = data.observed_scattered_response
    norms = np.linalg.norm(observed, axis=0)
    reference = max(float(np.max(norms)),
                    float(np.linalg.norm(observed)) / math.sqrt(observed.shape[1]), 1.0)
    scales = np.maximum(norms, max(1.0e-12 * reference, np.finfo(float).tiny))
    weights = np.ones(observed.shape[1]) if data.frequency_weights is None else data.frequency_weights
    factors = np.broadcast_to(np.sqrt(weights) / scales, observed.shape).reshape(-1)
    return np.diag(np.concatenate((factors, factors)))


def implicit_mlp_data_gradient(
    model,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    forward_result: PairedForwardResult | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Differentiate the actual local weight -> Method B -> Kress objective.

    The conversion uses its current marching/interpolation/projection branches.
    A topology or branch change is evaluated afresh by the line search; this
    derivative does not claim smoothness across such changes.  The returned
    gradient follows trainable model parameter order, without extra arc weights.
    """
    from gpr_bem_kress.shape_derivative import build_paired_objective_adjoint
    from gpr_bem_kress.geometry_pullback import build_kress_geometry_pullback
    from .method_b_pullback import build_method_b_pullback

    parameters = _trainable(model)
    started = perf_counter()
    forward = forward_result
    if forward is None:
        forward = predict_paired_response(model, data.forward_problem, geometry_config,
                                         solver="kress", retain_kress_state=True)
    if forward.solver != "kress" or len(forward.kress_states) != data.observed_scattered_response.shape[1]:
        raise ValueError("The neural adjoint needs retained production Kress states at every frequency.")
    pairs = np.arange(data.observed_scattered_response.shape[0])
    adjoint = build_paired_objective_adjoint(
        forward.kress_states, data.observed_scattered_response, pairs, pairs,
        residual_transform=_residual_transform(data),
    )
    residual, _ = normalized_complex_residual(forward.scattered_response,
                                              data.observed_scattered_response,
                                              data.frequency_weights)
    if not np.allclose(adjoint.residual, residual, rtol=2.0e-12, atol=1.0e-13):
        raise RuntimeError("Kress adjoint and neural acceptance objectives disagree.")
    geometry_gradient = build_kress_geometry_pullback(adjoint)
    conversion = build_method_b_pullback(model, geometry_config,
                                         reference_curve=forward.geometry_build.curve)
    point_dual = torch.tensor(geometry_gradient.points, dtype=conversion.points.dtype,
                             device=conversion.points.device)
    first_dual = torch.tensor(geometry_gradient.first_derivatives,
                             dtype=conversion.first_derivatives.dtype,
                             device=conversion.first_derivatives.device)
    surrogate = (point_dual * conversion.points).sum() + (first_dual * conversion.first_derivatives).sum()
    gradient = _flatten_gradient(torch.autograd.grad(surrogate, parameters, allow_unused=True), parameters)
    return gradient, {
        "method": "kress_discrete_adjoint_method_b_reverse",
        "adjoint_solve_count": len(forward.kress_states),
        "finite_difference_probes": 0,
        "method_b_replay_maximum_error": float(conversion.maximum_replay_error),
        "gradient_seconds": float(perf_counter() - started),
    }


def _eikonal(model, sample_points, *, create_graph):
    points = sample_points.detach().clone().requires_grad_(True)
    values = model(points)
    spatial = torch.autograd.grad(values.sum(), points, create_graph=create_graph)[0]
    return ((torch.linalg.vector_norm(spatial, dim=1) - 1.0) ** 2).mean()


@dataclass
class _Evaluation:
    forward: PairedForwardResult
    loss: float
    relative: float
    eikonal: float
    objective: float


def run_implicit_mlp_adjoint_inverse(
    model,
    controller: TorchParameterController,
    data: ComplexScatteredData,
    geometry_config: OrderedSDFGeometryConfig,
    *,
    config: ImplicitMLPAdjointConfig | None = None,
    progress_callback: Callable[[ImplicitMLPIteration], None] | None = None,
) -> ImplicitMLPInverseResult:
    """Update neural weights with Adam and accept their re-extracted geometry.

    Backtracking requires both a strictly lower actual data loss and Armijo
    decrease in data + fixed-sample Eikonal objective.  Infeasible topology is
    rejected.  Solver/derivative errors propagate after restoring the last
    accepted weights; there is no finite-difference fallback.  A non-descent
    Adam direction is replaced by an adjoint-gradient direction and its
    momentum is reset upon acceptance.
    """
    from .neural_optimization import maximum_curve_set_distance

    config = ImplicitMLPAdjointConfig() if config is None else config
    if not isinstance(config, ImplicitMLPAdjointConfig):
        raise TypeError("config must be an ImplicitMLPAdjointConfig.")
    parameters = _trainable(model)
    if controller.model is not model or controller.num_parameters != sum(p.numel() for p in parameters):
        raise ValueError("The controller must own this model's trainable parameters.")
    bounds = np.asarray(geometry_config.bounds)
    rng = np.random.default_rng(config.random_seed)
    points = torch.tensor(rng.uniform(bounds[0], bounds[1], (config.regularization_samples, 2)),
                          dtype=parameters[0].dtype, device=parameters[0].device)
    optimizer = torch.optim.Adam(parameters, lr=config.learning_rate)
    started = perf_counter()
    accepted_parameters = controller.parameter_vector()
    evaluations = infeasible = adjoint_solves = rejected = 0
    forward_seconds = maximum_residual = gradient_seconds = 0.0
    replay_error = 0.0
    records = []
    converged = False
    stop_reason = "maximum_iterations"
    last_step = np.zeros_like(accepted_parameters)
    last_backtracks = 0
    last_method = "initial"

    def evaluate():
        nonlocal evaluations, infeasible, forward_seconds, maximum_residual
        evaluations += 1
        trial_started = perf_counter()
        try:
            forward = predict_paired_response(model, data.forward_problem, geometry_config,
                                             solver="kress", retain_kress_state=True)
        except OrderedSDFGeometryError:
            infeasible += 1
            raise
        finally:
            forward_seconds += float(perf_counter() - trial_started)
        maximum_residual = max(maximum_residual, float(np.max(forward.linear_system_relative_residuals)))
        residual, relative = normalized_complex_residual(forward.scattered_response,
                                                         data.observed_scattered_response,
                                                         data.frequency_weights)
        loss = 0.5 * float(residual @ residual)
        eikonal = float(_eikonal(model, points, create_graph=False).detach().cpu())
        objective = loss + config.eikonal_weight * eikonal
        if not math.isfinite(objective):
            raise FloatingPointError("The actual neural objective is non-finite.")
        return _Evaluation(forward, loss, relative, eikonal, objective)

    try:
        current = evaluate()
        for iteration in range(config.max_iterations + 1):
            controller.assign(accepted_parameters)
            terminal = current.loss <= config.loss_tolerance or iteration == config.max_iterations
            # A valid final geometry need not have a differentiable extraction
            # branch when no further step is requested. Missing gradients are
            # explicit, not fabricated zeros or stale preceding gradients.
            if terminal:
                gradient = data_gradient = None
                diagnostic = {"gradient_seconds": 0.0}
            else:
                data_gradient, diagnostic = implicit_mlp_data_gradient(
                    model, data, geometry_config, forward_result=current.forward)
                adjoint_solves += diagnostic["adjoint_solve_count"]
                gradient_seconds += diagnostic["gradient_seconds"]
                replay_error = max(replay_error, diagnostic["method_b_replay_maximum_error"])
                if config.eikonal_weight:
                    penalty = config.eikonal_weight * _eikonal(model, points, create_graph=True)
                    regularizer_gradient = _flatten_gradient(
                        torch.autograd.grad(penalty, parameters, allow_unused=True), parameters)
                else:
                    regularizer_gradient = np.zeros_like(data_gradient)
                gradient = data_gradient + regularizer_gradient
            record = ImplicitMLPIteration(
                iteration=iteration, parameter_names=controller.names,
                parameter_vector=accepted_parameters.copy(),
                physical_parameters=controller.physical_parameter_dict(),
                loss=current.loss, relative_l2_error=current.relative,
                gradient=None if gradient is None else gradient.copy(),
                step=last_step.copy(), evaluation_count=evaluations,
                timings={"gradient_seconds": diagnostic["gradient_seconds"],
                         "forward_seconds": current.forward.total_seconds},
                geometry_points=np.array(current.forward.geometry_build.curve.points, copy=True),
                maximum_system_residual=maximum_residual, objective=current.objective,
                eikonal_loss=current.eikonal,
                data_gradient=None if data_gradient is None else data_gradient.copy(),
                backtracks=last_backtracks, step_method=last_method,
                gradient_evaluated=not terminal,
            )
            records.append(record)
            if progress_callback is not None:
                progress_callback(record)
            if current.loss <= config.loss_tolerance:
                converged, stop_reason = True, "data_loss_tolerance"
                break
            if iteration == config.max_iterations:
                break
            projected = accepted_parameters - controller.project(accepted_parameters - gradient)
            if np.linalg.norm(projected, ord=np.inf) <= config.gradient_tolerance:
                stop_reason = "stationary_above_data_tolerance"
                break
            optimizer_before = copy.deepcopy(optimizer.state_dict())
            optimizer.zero_grad(set_to_none=True)
            offset = 0
            for parameter in parameters:
                count = parameter.numel()
                parameter.grad = torch.tensor(gradient[offset:offset + count], dtype=parameter.dtype,
                                              device=parameter.device).reshape(parameter.shape)
                offset += count
            torch.nn.utils.clip_grad_norm_(parameters, config.gradient_clip_norm)
            optimizer.step()
            adam_proposal = controller.project(controller.parameter_vector()) - accepted_parameters
            controller.assign(accepted_parameters)
            # Both directions are computed from the adjoint, never from FD.
            steepest = -gradient * (config.learning_rate / max(float(np.max(np.abs(gradient))), 1.0e-30))
            steepest = controller.project(accepted_parameters + steepest) - accepted_parameters
            accepted = None
            current_curve = current.forward.geometry_build.curve.points
            for method, proposal in (("adam", adam_proposal), ("adjoint_steepest_descent", steepest)):
                if gradient @ proposal >= 0.0 or data_gradient @ proposal >= 0.0:
                    continue
                for backtrack in range(config.max_backtracks + 1):
                    candidate_parameters = controller.project(
                        accepted_parameters + config.backtrack_factor**backtrack * proposal)
                    step = candidate_parameters - accepted_parameters
                    if not np.any(step):
                        continue
                    controller.assign(candidate_parameters)
                    try:
                        candidate = evaluate()
                    except OrderedSDFGeometryError:
                        rejected += 1
                        continue
                    candidate_curve = candidate.forward.geometry_build.curve.points
                    drift = maximum_curve_set_distance(current_curve, candidate_curve)
                    if (drift <= config.maximum_boundary_step_m
                            and candidate.loss < current.loss
                            and candidate.loss <= current.loss + config.armijo_fraction * float(data_gradient @ step)
                            and candidate.objective <= current.objective + config.armijo_fraction * float(gradient @ step)):
                        accepted = candidate, candidate_parameters, step, backtrack, method
                        break
                    rejected += 1
                if accepted is not None:
                    break
                controller.assign(accepted_parameters)
            if accepted is None:
                optimizer.load_state_dict(optimizer_before)
                controller.assign(accepted_parameters)
                stop_reason = "no_decreasing_neural_step"
                break
            current, accepted_parameters, last_step, last_backtracks, last_method = accepted
            if last_method != "adam":
                optimizer.state.clear()
    finally:
        controller.assign(accepted_parameters)

    return ImplicitMLPInverseResult(
        solver="kress", parameter_names=controller.names, iterations=tuple(records),
        converged=converged, stop_reason=stop_reason, total_evaluation_count=evaluations,
        maximum_system_residual=maximum_residual, total_forward_seconds=forward_seconds,
        total_seconds=float(perf_counter() - started), infeasible_trial_count=infeasible,
        diagnostics={
            "pipeline": "implicit_mlp_method_b", "geometry_owner": "mlp_weights",
            "optimizer": "kress_adjoint_adam_with_backtracking",
            "gradient_method": "kress_discrete_adjoint_method_b_reverse",
            "finite_difference_probes": 0, "curve_distillation_steps": 0,
            "adjoint_solve_count": adjoint_solves, "gradient_seconds": gradient_seconds,
            "rejected_trial_count": rejected, "method_b_replay_maximum_error": replay_error,
            "acceptance": "actual_reextracted_mlp_data_and_regularized_objective",
            "convergence": "data_tolerance_only; geometry and distance accuracy require separate audits",
            "conversion_derivative": "branch_local; topology and interpolation branch switches are not differentiated",
        },
    )


__all__ = ["ImplicitMLPAdjointConfig", "ImplicitMLPIteration", "ImplicitMLPInverseResult",
           "implicit_mlp_data_gradient", "run_implicit_mlp_adjoint_inverse"]
