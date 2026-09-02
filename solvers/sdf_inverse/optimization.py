"""Common low-dimensional finite-difference inverse for paired BEM data.

Both forward solvers are treated as black boxes through
``sdf_inverse.forward.predict_paired_response``.  Consequently the numerical
Jacobian, damping, bounds, and acceptance policy are identical for MOD and
Kress; solver-specific derivatives cannot silently affect this comparison.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import operator
from time import perf_counter
from types import MappingProxyType
from typing import TYPE_CHECKING, Callable, Mapping, Sequence, Union

import numpy as np
import torch

from .models import TorchParameterController

if TYPE_CHECKING:
    from .forward import PairedForwardProblem, PairedForwardResult


ArrayLike = Union[float, Sequence[float], np.ndarray]
ProgressCallback = Callable[["ParameterFDIteration"], None]


def _readonly_array(values, *, dtype, ndim: int | None = None) -> np.ndarray:
    result = np.array(values, dtype=dtype, copy=True)
    if ndim is not None and result.ndim != ndim:
        raise ValueError(f"Expected an array with {ndim} dimensions.")
    result.setflags(write=False)
    return result


def _finite_complex_matrix(values, *, name: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.complex128)
    if result.ndim != 2 or result.shape[0] < 1 or result.shape[1] < 1:
        raise ValueError(f"{name} must have shape (num_pairs, num_frequencies).")
    if not np.all(np.isfinite(result.real)) or not np.all(np.isfinite(result.imag)):
        raise ValueError(f"{name} must contain only finite values.")
    return result


def _problem_expected_shape(problem: object) -> tuple[int, int] | None:
    num_pairs = getattr(problem, "num_pairs", None)
    if num_pairs is None:
        source_points = getattr(problem, "source_points", None)
        if source_points is not None:
            source_array = np.asarray(source_points)
            if source_array.ndim == 2:
                num_pairs = source_array.shape[0]

    num_frequencies = getattr(problem, "num_frequencies", None)
    if num_frequencies is None:
        frequencies = getattr(problem, "angular_frequencies", None)
        if frequencies is not None:
            frequency_array = np.asarray(frequencies)
            if frequency_array.ndim == 1:
                num_frequencies = frequency_array.size

    if num_pairs is None or num_frequencies is None:
        return None
    return int(num_pairs), int(num_frequencies)


@dataclass(frozen=True)
class ComplexScatteredData:
    """One immutable paired observation data set shared by both solvers."""

    forward_problem: "PairedForwardProblem"
    observed_scattered_response: np.ndarray
    frequency_weights: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.forward_problem is None:
            raise TypeError("forward_problem must be supplied.")
        observed = _finite_complex_matrix(
            self.observed_scattered_response,
            name="observed_scattered_response",
        )
        expected_shape = _problem_expected_shape(self.forward_problem)
        if expected_shape is not None and observed.shape != expected_shape:
            raise ValueError(
                "observed_scattered_response does not match forward_problem: "
                f"expected {expected_shape}, received {observed.shape}."
            )

        if self.frequency_weights is None:
            weights = np.ones(observed.shape[1], dtype=np.float64)
        else:
            weights = np.asarray(self.frequency_weights, dtype=np.float64)
            if weights.shape != (observed.shape[1],):
                raise ValueError(
                    "frequency_weights must have shape (num_frequencies,)."
                )
            if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
                raise ValueError(
                    "frequency_weights must be finite and non-negative."
                )
            if not np.any(weights > 0.0):
                raise ValueError("At least one frequency weight must be positive.")

        object.__setattr__(
            self,
            "observed_scattered_response",
            _readonly_array(observed, dtype=np.complex128, ndim=2),
        )
        object.__setattr__(
            self,
            "frequency_weights",
            _readonly_array(weights, dtype=np.float64, ndim=1),
        )


def normalized_complex_residual(
    predicted_scattered_response: np.ndarray,
    observed_scattered_response: np.ndarray,
    frequency_weights: np.ndarray | None = None,
    *,
    relative_floor: float = 1.0e-12,
) -> tuple[np.ndarray, float]:
    """Return a real least-squares residual and unweighted global relative L2.

    Each complex frequency column is divided by the observed column L2 norm,
    with a scale-aware floor, and multiplied by the square root of its
    frequency weight.  Real and imaginary parts are concatenated so ordinary
    real Gauss--Newton algebra applies.
    """

    predicted = _finite_complex_matrix(
        predicted_scattered_response,
        name="predicted_scattered_response",
    )
    observed = _finite_complex_matrix(
        observed_scattered_response,
        name="observed_scattered_response",
    )
    if predicted.shape != observed.shape:
        raise ValueError("predicted and observed responses must have matching shapes.")

    floor_fraction = float(relative_floor)
    if not math.isfinite(floor_fraction) or floor_fraction <= 0.0:
        raise ValueError("relative_floor must be finite and positive.")
    if frequency_weights is None:
        weights = np.ones(observed.shape[1], dtype=np.float64)
    else:
        weights = np.asarray(frequency_weights, dtype=np.float64)
        if weights.shape != (observed.shape[1],):
            raise ValueError(
                "frequency_weights must have shape (num_frequencies,)."
            )
        if not np.all(np.isfinite(weights)) or np.any(weights < 0.0):
            raise ValueError(
                "frequency_weights must be finite and non-negative."
            )
        if not np.any(weights > 0.0):
            raise ValueError("At least one frequency weight must be positive.")

    observed_column_norms = np.linalg.norm(observed, axis=0)
    # Including one gives the relative floor a useful absolute meaning when
    # an observed frequency (or the entire data set) is exactly zero.  A floor
    # based only on ``tiny`` can overflow an otherwise finite residual.
    reference_scale = max(
        float(np.max(observed_column_norms)),
        float(np.linalg.norm(observed)) / math.sqrt(observed.shape[1]),
        1.0,
    )
    scale_floor = max(
        floor_fraction * reference_scale,
        np.finfo(np.float64).tiny,
    )
    column_scales = np.maximum(observed_column_norms, scale_floor)
    normalized = (
        (predicted - observed)
        / column_scales[None, :]
        * np.sqrt(weights)[None, :]
    )
    residual = np.concatenate(
        (
            np.asarray(normalized.real, dtype=np.float64).reshape(-1),
            np.asarray(normalized.imag, dtype=np.float64).reshape(-1),
        )
    )
    global_floor = max(
        floor_fraction * reference_scale,
        np.finfo(np.float64).tiny,
    )
    global_relative_l2 = float(
        np.linalg.norm(predicted - observed)
        / max(float(np.linalg.norm(observed)), global_floor)
    )
    if not np.all(np.isfinite(residual)) or not math.isfinite(global_relative_l2):
        raise FloatingPointError(
            "Normalized response residual overflowed despite finite inputs."
        )
    return residual, global_relative_l2


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


def _positive_scalar_or_vector(values: ArrayLike, *, name: str):
    array = np.asarray(values, dtype=np.float64)
    if array.ndim > 1 or (array.ndim == 1 and array.size == 0):
        raise ValueError(f"{name} must be a scalar or non-empty one-dimensional array.")
    if not np.all(np.isfinite(array)) or np.any(array <= 0.0):
        raise ValueError(f"{name} must contain only finite positive values.")
    if array.ndim == 0:
        return float(array)
    result = np.array(array, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


def _finite_nonnegative(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
    return result


@dataclass(frozen=True)
class ParameterFDConfig:
    """Controls for bounded central-FD damped Gauss--Newton optimization."""

    max_iterations: int = 10
    finite_difference_steps: ArrayLike = 1.0e-4
    max_steps: ArrayLike = 2.0e-2
    initial_damping: float = 1.0e-3
    damping_increase: float = 10.0
    damping_decrease: float = 0.3
    max_damping_trials: int = 6
    max_backtracks: int = 8
    gradient_tolerance: float = 1.0e-8
    loss_tolerance: float = 1.0e-12
    relative_step_tolerance: float = 1.0e-8
    max_parameters: int = 32

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_iterations",
            _positive_integer(self.max_iterations, name="max_iterations"),
        )
        object.__setattr__(
            self,
            "max_damping_trials",
            _positive_integer(
                self.max_damping_trials,
                name="max_damping_trials",
            ),
        )
        object.__setattr__(
            self,
            "max_backtracks",
            _positive_integer(
                self.max_backtracks,
                name="max_backtracks",
                allow_zero=True,
            ),
        )
        object.__setattr__(
            self,
            "max_parameters",
            _positive_integer(self.max_parameters, name="max_parameters"),
        )
        object.__setattr__(
            self,
            "finite_difference_steps",
            _positive_scalar_or_vector(
                self.finite_difference_steps,
                name="finite_difference_steps",
            ),
        )
        object.__setattr__(
            self,
            "max_steps",
            _positive_scalar_or_vector(self.max_steps, name="max_steps"),
        )

        initial_damping = float(self.initial_damping)
        damping_increase = float(self.damping_increase)
        damping_decrease = float(self.damping_decrease)
        if not math.isfinite(initial_damping) or initial_damping <= 0.0:
            raise ValueError("initial_damping must be finite and positive.")
        if not math.isfinite(damping_increase) or damping_increase <= 1.0:
            raise ValueError("damping_increase must be finite and greater than one.")
        if (
            not math.isfinite(damping_decrease)
            or damping_decrease <= 0.0
            or damping_decrease > 1.0
        ):
            raise ValueError(
                "damping_decrease must be finite and in the interval (0, 1]."
            )
        object.__setattr__(self, "initial_damping", initial_damping)
        object.__setattr__(self, "damping_increase", damping_increase)
        object.__setattr__(self, "damping_decrease", damping_decrease)
        for name in (
            "gradient_tolerance",
            "loss_tolerance",
            "relative_step_tolerance",
        ):
            object.__setattr__(
                self,
                name,
                _finite_nonnegative(getattr(self, name), name=name),
            )

    def resolved_finite_difference_steps(self, count: int) -> np.ndarray:
        return _resolve_control_vector(
            self.finite_difference_steps,
            count=count,
            name="finite_difference_steps",
        )

    def resolved_max_steps(self, count: int) -> np.ndarray:
        return _resolve_control_vector(
            self.max_steps,
            count=count,
            name="max_steps",
        )


def _resolve_control_vector(values, *, count: int, name: str) -> np.ndarray:
    if np.ndim(values) == 0:
        result = np.full(count, float(values), dtype=np.float64)
    else:
        result = np.asarray(values, dtype=np.float64)
        if result.shape != (count,):
            raise ValueError(f"{name} must be scalar or have shape ({count},).")
        result = np.array(result, dtype=np.float64, copy=True)
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class ParameterFDIteration:
    """One accepted iterate; iteration zero is the evaluated initial state."""

    iteration: int
    parameter_names: tuple[str, ...]
    parameter_vector: np.ndarray
    physical_parameters: Mapping[str, float]
    loss: float
    relative_l2_error: float
    gradient: np.ndarray
    step: np.ndarray
    damping: float
    evaluation_count: int
    timings: Mapping[str, float]
    geometry_points: np.ndarray
    maximum_system_residual: float

    def __post_init__(self) -> None:
        parameter_names = tuple(str(name) for name in self.parameter_names)
        if not parameter_names or any(not name for name in parameter_names):
            raise ValueError("parameter_names must contain non-empty labels.")
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("parameter_names must be unique.")
        count = len(parameter_names)
        parameter_vector = _readonly_array(
            self.parameter_vector,
            dtype=np.float64,
            ndim=1,
        )
        gradient = _readonly_array(self.gradient, dtype=np.float64, ndim=1)
        step = _readonly_array(self.step, dtype=np.float64, ndim=1)
        if (
            parameter_vector.shape != (count,)
            or gradient.shape != (count,)
            or step.shape != (count,)
        ):
            raise ValueError("parameter_vector, gradient, and step must match names.")
        if not all(
            np.all(np.isfinite(values))
            for values in (parameter_vector, gradient, step)
        ):
            raise ValueError("iteration vectors must contain only finite values.")
        geometry = _readonly_array(self.geometry_points, dtype=np.float64, ndim=2)
        if geometry.shape[1:] != (2,) or not np.all(np.isfinite(geometry)):
            raise ValueError("geometry_points must be a finite array of shape (N, 2).")
        physical = {
            str(name): float(value) for name, value in self.physical_parameters.items()
        }
        timings = {str(name): float(value) for name, value in self.timings.items()}
        if not all(math.isfinite(value) for value in physical.values()):
            raise ValueError("physical_parameters must contain finite values.")
        if not all(math.isfinite(value) and value >= 0.0 for value in timings.values()):
            raise ValueError("timings must contain finite non-negative values.")
        for name in ("loss", "relative_l2_error", "damping"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        residual = float(self.maximum_system_residual)
        if not math.isfinite(residual) or residual < 0.0:
            raise ValueError(
                "maximum_system_residual must be finite and non-negative."
            )
        iteration = _positive_integer(
            self.iteration,
            name="iteration",
            allow_zero=True,
        )
        evaluation_count = _positive_integer(
            self.evaluation_count,
            name="evaluation_count",
            allow_zero=True,
        )
        object.__setattr__(self, "iteration", iteration)
        object.__setattr__(self, "evaluation_count", evaluation_count)
        object.__setattr__(self, "parameter_names", parameter_names)
        object.__setattr__(self, "parameter_vector", parameter_vector)
        object.__setattr__(self, "gradient", gradient)
        object.__setattr__(self, "step", step)
        object.__setattr__(self, "geometry_points", geometry)
        object.__setattr__(self, "physical_parameters", MappingProxyType(physical))
        object.__setattr__(self, "timings", MappingProxyType(timings))
        object.__setattr__(self, "maximum_system_residual", residual)


@dataclass(frozen=True)
class ParameterFDInverseResult:
    """Complete accepted trajectory of one solver's numerical inverse."""

    solver: str
    parameter_names: tuple[str, ...]
    iterations: tuple[ParameterFDIteration, ...]
    converged: bool
    stop_reason: str
    total_evaluation_count: int
    cache_hit_count: int
    maximum_system_residual: float
    total_forward_seconds: float
    total_seconds: float

    def __post_init__(self) -> None:
        if self.solver not in {"mod", "kress"}:
            raise ValueError("solver must be 'mod' or 'kress'.")
        parameter_names = tuple(str(name) for name in self.parameter_names)
        iterations = tuple(self.iterations)
        if not iterations or iterations[0].iteration != 0:
            raise ValueError("iterations must begin with the initial iteration zero.")
        expected_indices = tuple(range(len(iterations)))
        if tuple(record.iteration for record in iterations) != expected_indices:
            raise ValueError("accepted iteration indices must be consecutive.")
        if any(record.parameter_names != parameter_names for record in iterations):
            raise ValueError(
                "Every iteration must use the result's parameter_names."
            )
        losses = np.asarray([record.loss for record in iterations])
        if np.any(losses[1:] > losses[:-1] + 32.0 * np.finfo(float).eps):
            raise ValueError("accepted iteration losses must be monotone non-increasing.")
        if not isinstance(self.stop_reason, str) or not self.stop_reason:
            raise ValueError("stop_reason must be a non-empty string.")
        if not isinstance(self.converged, (bool, np.bool_)):
            raise TypeError("converged must be boolean.")
        total_evaluation_count = _positive_integer(
            self.total_evaluation_count,
            name="total_evaluation_count",
            allow_zero=True,
        )
        cache_hit_count = _positive_integer(
            self.cache_hit_count,
            name="cache_hit_count",
            allow_zero=True,
        )
        if total_evaluation_count < iterations[-1].evaluation_count:
            raise ValueError(
                "total_evaluation_count cannot precede the final iteration."
            )
        maximum_system_residual = float(self.maximum_system_residual)
        if not math.isfinite(maximum_system_residual) or maximum_system_residual < 0.0:
            raise ValueError(
                "maximum_system_residual must be finite and non-negative."
            )
        for name in ("total_forward_seconds", "total_seconds"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, value)
        object.__setattr__(self, "parameter_names", parameter_names)
        object.__setattr__(self, "iterations", iterations)
        object.__setattr__(self, "converged", bool(self.converged))
        object.__setattr__(
            self,
            "total_evaluation_count",
            total_evaluation_count,
        )
        object.__setattr__(self, "cache_hit_count", cache_hit_count)
        object.__setattr__(
            self, "maximum_system_residual", maximum_system_residual
        )

    @property
    def initial_iteration(self) -> ParameterFDIteration:
        return self.iterations[0]

    @property
    def final_iteration(self) -> ParameterFDIteration:
        return self.iterations[-1]


@dataclass(frozen=True)
class _ObjectiveEvaluation:
    parameters: np.ndarray
    residual: np.ndarray
    loss: float
    relative_l2_error: float
    forward_result: "PairedForwardResult"
    wall_seconds: float


class _ObjectiveEvaluator:
    def __init__(
        self,
        model: torch.nn.Module,
        controller: TorchParameterController,
        data: ComplexScatteredData,
        geometry_config: object,
        solver: str,
    ) -> None:
        self.model = model
        self.controller = controller
        self.data = data
        self.geometry_config = geometry_config
        self.solver = solver
        self.cache: dict[bytes, _ObjectiveEvaluation] = {}
        self.evaluation_count = 0
        self.cache_hit_count = 0
        self.total_forward_seconds = 0.0
        self.maximum_system_residual = 0.0

    @staticmethod
    def _key(parameters: np.ndarray) -> bytes:
        return np.ascontiguousarray(parameters, dtype=np.float64).tobytes()

    def evaluate(self, parameters: np.ndarray) -> _ObjectiveEvaluation:
        self.controller.assign(parameters)
        realized = self.controller.parameter_vector()
        key = self._key(realized)
        cached = self.cache.get(key)
        if cached is not None:
            self.cache_hit_count += 1
            return cached

        from .forward import predict_paired_response

        started = perf_counter()
        forward_result = predict_paired_response(
            self.model,
            self.data.forward_problem,
            self.geometry_config,
            solver=self.solver,
        )
        self.maximum_system_residual = max(
            self.maximum_system_residual,
            _maximum_system_residual(forward_result),
        )
        wall_seconds = float(perf_counter() - started)
        response = _finite_complex_matrix(
            forward_result.scattered_response,
            name="forward_result.scattered_response",
        )
        residual, relative_l2_error = normalized_complex_residual(
            response,
            self.data.observed_scattered_response,
            self.data.frequency_weights,
        )
        loss = 0.5 * float(np.dot(residual, residual))
        if not math.isfinite(loss):
            raise FloatingPointError("The normalized fixed objective is non-finite.")
        evaluation = _ObjectiveEvaluation(
            parameters=_readonly_array(realized, dtype=np.float64, ndim=1),
            residual=_readonly_array(residual, dtype=np.float64, ndim=1),
            loss=loss,
            relative_l2_error=relative_l2_error,
            forward_result=forward_result,
            wall_seconds=wall_seconds,
        )
        self.cache[key] = evaluation
        self.evaluation_count += 1
        self.total_forward_seconds += wall_seconds
        return evaluation


def _finite_difference_jacobian(
    evaluator: _ObjectiveEvaluator,
    base: _ObjectiveEvaluation,
    requested_steps: np.ndarray,
    lower_bounds: np.ndarray,
    upper_bounds: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Build the common numerical Jacobian, centrally when bounds permit.

    A second-order one-sided stencil is used only when an accepted parameter is
    exactly on a bound and a symmetric perturbation is impossible.
    """

    started = perf_counter()
    parameters = np.asarray(base.parameters, dtype=np.float64)
    jacobian = np.empty(
        (base.residual.size, parameters.size),
        dtype=np.float64,
    )
    for index, requested_step in enumerate(requested_steps):
        lower_room = parameters[index] - lower_bounds[index]
        upper_room = upper_bounds[index] - parameters[index]
        central_step = min(float(requested_step), lower_room, upper_room)
        resolution = 8.0 * np.finfo(np.float64).eps * max(
            1.0,
            abs(parameters[index]),
        )
        if central_step > resolution:
            plus = parameters.copy()
            minus = parameters.copy()
            plus[index] += central_step
            minus[index] -= central_step
            plus_evaluation = evaluator.evaluate(plus)
            minus_evaluation = evaluator.evaluate(minus)
            denominator = (
                plus_evaluation.parameters[index]
                - minus_evaluation.parameters[index]
            )
            if abs(denominator) <= resolution:
                raise ValueError(
                    f"finite_difference_steps[{index}] is not representable in "
                    "the controlled parameter dtype."
                )
            jacobian[:, index] = (
                plus_evaluation.residual - minus_evaluation.residual
            ) / denominator
            continue

        # Bound-active fallback: retain a deterministic second-order numerical
        # derivative rather than freezing a parameter that may move inward.
        if upper_room > resolution:
            step = min(float(requested_step), 0.5 * upper_room)
            first = parameters.copy()
            second = parameters.copy()
            first[index] += step
            second[index] += 2.0 * step
            first_evaluation = evaluator.evaluate(first)
            second_evaluation = evaluator.evaluate(second)
            actual_step = first_evaluation.parameters[index] - parameters[index]
            second_step = second_evaluation.parameters[index] - parameters[index]
            if (
                actual_step <= resolution
                or abs(second_step - 2.0 * actual_step) > 1.0e-5 * actual_step
            ):
                raise ValueError(
                    f"finite_difference_steps[{index}] is not representable near "
                    "the lower bound."
                )
            jacobian[:, index] = (
                -3.0 * base.residual
                + 4.0 * first_evaluation.residual
                - second_evaluation.residual
            ) / (2.0 * actual_step)
            continue
        if lower_room > resolution:
            step = min(float(requested_step), 0.5 * lower_room)
            first = parameters.copy()
            second = parameters.copy()
            first[index] -= step
            second[index] -= 2.0 * step
            first_evaluation = evaluator.evaluate(first)
            second_evaluation = evaluator.evaluate(second)
            actual_step = parameters[index] - first_evaluation.parameters[index]
            second_step = parameters[index] - second_evaluation.parameters[index]
            if (
                actual_step <= resolution
                or abs(second_step - 2.0 * actual_step) > 1.0e-5 * actual_step
            ):
                raise ValueError(
                    f"finite_difference_steps[{index}] is not representable near "
                    "the upper bound."
                )
            jacobian[:, index] = (
                3.0 * base.residual
                - 4.0 * first_evaluation.residual
                + second_evaluation.residual
            ) / (2.0 * actual_step)
            continue
        raise ValueError(
            f"Parameter {index} has no finite-difference room inside its bounds."
        )

    evaluator.evaluate(parameters)  # Restore the accepted model state; cache hit.
    return jacobian, float(perf_counter() - started)


def _geometry_points(forward_result: object) -> np.ndarray:
    geometry_build = getattr(forward_result, "geometry_build", None)
    curve = getattr(geometry_build, "curve", None)
    points = getattr(curve, "points", None)
    if points is None:
        points = getattr(geometry_build, "points", None)
    if points is None:
        points = getattr(forward_result, "geometry_points", None)
    if points is None:
        raise AttributeError(
            "PairedForwardResult must expose geometry_build.curve.points or "
            "geometry_points for inverse records."
        )
    result = np.asarray(points, dtype=np.float64)
    if result.ndim != 2 or result.shape[1] != 2 or not np.all(np.isfinite(result)):
        raise ValueError("Forward geometry points must have finite shape (N, 2).")
    return result


def _maximum_system_residual(forward_result: object) -> float:
    values = np.asarray(
        getattr(forward_result, "linear_system_relative_residuals"),
        dtype=np.float64,
    )
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError(
            "linear_system_relative_residuals must be a finite non-empty vector."
        )
    if np.any(values < 0.0):
        raise ValueError("linear_system_relative_residuals must be non-negative.")
    return float(np.max(values))


def _reported_forward_timings(forward_result: object) -> dict[str, float]:
    result: dict[str, float] = {}
    for name in (
        "geometry_seconds",
        "forward_seconds",
        "total_seconds",
    ):
        value = getattr(forward_result, name, None)
        if value is None:
            continue
        numeric = float(value)
        if not math.isfinite(numeric) or numeric < 0.0:
            raise ValueError(f"forward_result.{name} must be finite and non-negative.")
        result[f"reported_{name}"] = numeric
    return result


def _make_iteration_record(
    *,
    iteration: int,
    controller: TorchParameterController,
    evaluation: _ObjectiveEvaluation,
    gradient: np.ndarray,
    step: np.ndarray,
    damping: float,
    evaluator: _ObjectiveEvaluator,
    timings: Mapping[str, float],
) -> ParameterFDIteration:
    evaluator.evaluate(evaluation.parameters)
    combined_timings = dict(timings)
    combined_timings.update(_reported_forward_timings(evaluation.forward_result))
    combined_timings["accepted_forward_wall_seconds"] = evaluation.wall_seconds
    combined_timings["cumulative_forward_wall_seconds"] = (
        evaluator.total_forward_seconds
    )
    return ParameterFDIteration(
        iteration=iteration,
        parameter_names=controller.names,
        parameter_vector=evaluation.parameters,
        physical_parameters=controller.physical_parameter_dict(),
        loss=evaluation.loss,
        relative_l2_error=evaluation.relative_l2_error,
        gradient=gradient,
        step=step,
        damping=damping,
        evaluation_count=evaluator.evaluation_count,
        timings=combined_timings,
        geometry_points=_geometry_points(evaluation.forward_result),
        maximum_system_residual=_maximum_system_residual(
            evaluation.forward_result
        ),
    )


def run_parameter_fd_inverse(
    model: torch.nn.Module,
    controller: TorchParameterController,
    data: ComplexScatteredData,
    geometry_config: object,
    *,
    solver: str,
    config: ParameterFDConfig,
    progress_callback: ProgressCallback | None = None,
) -> ParameterFDInverseResult:
    """Run bounded LM iterations using the same numerical Jacobian per solver.

    Every stored record is an accepted state evaluated against the same fixed
    observation objective.  Trial steps must strictly decrease that objective;
    failures are reported as a stop reason rather than accepted into history.
    The model is restored to the final accepted parameters on all exits.
    """

    if not isinstance(model, torch.nn.Module):
        raise TypeError("model must be a torch.nn.Module.")
    if not isinstance(controller, TorchParameterController):
        raise TypeError("controller must be a TorchParameterController.")
    if controller.model is not model:
        raise ValueError("controller must own the same model passed to the inverse.")
    if not isinstance(data, ComplexScatteredData):
        raise TypeError("data must be ComplexScatteredData.")
    if not isinstance(config, ParameterFDConfig):
        raise TypeError("config must be ParameterFDConfig.")
    solver_name = str(solver)
    if solver_name not in {"mod", "kress"}:
        raise ValueError("solver must be exactly 'mod' or 'kress'.")
    if controller.num_parameters > config.max_parameters:
        raise ValueError(
            f"Controller has {controller.num_parameters} scalar parameters, "
            f"exceeding config.max_parameters={config.max_parameters}. Direct "
            "finite differences over a large random network are not scalable."
        )
    if progress_callback is not None and not callable(progress_callback):
        raise TypeError("progress_callback must be callable when supplied.")

    count = controller.num_parameters
    finite_difference_steps = config.resolved_finite_difference_steps(count)
    max_steps = config.resolved_max_steps(count)
    initial_parameters = controller.parameter_vector()
    evaluator = _ObjectiveEvaluator(
        model,
        controller,
        data,
        geometry_config,
        solver_name,
    )
    accepted_parameters = initial_parameters.copy()
    was_training = model.training
    records: list[ParameterFDIteration] = []
    converged = False
    stop_reason = "maximum_iterations"
    run_started = perf_counter()

    model.eval()
    try:
        initial_started = perf_counter()
        current = evaluator.evaluate(accepted_parameters)
        accepted_parameters = np.array(current.parameters, copy=True)
        jacobian, jacobian_seconds = _finite_difference_jacobian(
            evaluator,
            current,
            finite_difference_steps,
            controller.lower_bounds,
            controller.upper_bounds,
        )
        gradient = jacobian.T @ current.residual
        initial_record = _make_iteration_record(
            iteration=0,
            controller=controller,
            evaluation=current,
            gradient=gradient,
            step=np.zeros(count, dtype=np.float64),
            damping=config.initial_damping,
            evaluator=evaluator,
            timings={
                "iteration_seconds": perf_counter() - initial_started,
                "jacobian_seconds": jacobian_seconds,
                "line_search_seconds": 0.0,
            },
        )
        records.append(initial_record)
        if progress_callback is not None:
            progress_callback(initial_record)

        damping = config.initial_damping
        if current.loss <= config.loss_tolerance:
            converged = True
            stop_reason = "loss_tolerance"
        elif float(np.linalg.norm(gradient, ord=np.inf)) <= config.gradient_tolerance:
            converged = True
            stop_reason = "gradient_tolerance"

        for iteration in range(1, config.max_iterations + 1):
            if converged:
                break
            iteration_started = perf_counter()
            normal_matrix = jacobian.T @ jacobian
            scaling = np.maximum(np.diag(normal_matrix), 1.0)
            accepted: _ObjectiveEvaluation | None = None
            accepted_step: np.ndarray | None = None
            used_damping = damping
            line_search_started = perf_counter()
            candidate_relative_step = float("inf")

            trial_damping = damping
            for _damping_trial in range(config.max_damping_trials):
                damped_matrix = normal_matrix + trial_damping * np.diag(scaling)
                try:
                    proposed_step = np.linalg.solve(damped_matrix, -gradient)
                except np.linalg.LinAlgError:
                    trial_damping *= config.damping_increase
                    continue
                proposed_step = np.clip(proposed_step, -max_steps, max_steps)
                for backtrack in range(config.max_backtracks + 1):
                    scaled_step = (0.5**backtrack) * proposed_step
                    candidate_parameters = controller.project(
                        accepted_parameters + scaled_step
                    )
                    actual_step = candidate_parameters - accepted_parameters
                    candidate_relative_step = float(
                        np.linalg.norm(actual_step)
                        / max(np.linalg.norm(accepted_parameters), 1.0)
                    )
                    if candidate_relative_step <= config.relative_step_tolerance:
                        continue
                    candidate = evaluator.evaluate(candidate_parameters)
                    if candidate.loss < current.loss:
                        accepted = candidate
                        accepted_step = (
                            np.asarray(candidate.parameters)
                            - accepted_parameters
                        )
                        used_damping = trial_damping
                        break
                if accepted is not None:
                    break
                trial_damping *= config.damping_increase

            line_search_seconds = perf_counter() - line_search_started
            if accepted is None or accepted_step is None:
                if candidate_relative_step <= config.relative_step_tolerance:
                    converged = True
                    stop_reason = "relative_step_tolerance"
                else:
                    stop_reason = "no_decreasing_step"
                break

            previous_loss = current.loss
            current = accepted
            accepted_parameters = np.array(current.parameters, copy=True)
            damping = max(
                used_damping * config.damping_decrease,
                np.finfo(np.float64).tiny,
            )
            jacobian, jacobian_seconds = _finite_difference_jacobian(
                evaluator,
                current,
                finite_difference_steps,
                controller.lower_bounds,
                controller.upper_bounds,
            )
            gradient = jacobian.T @ current.residual
            record = _make_iteration_record(
                iteration=iteration,
                controller=controller,
                evaluation=current,
                gradient=gradient,
                step=accepted_step,
                damping=used_damping,
                evaluator=evaluator,
                timings={
                    "iteration_seconds": perf_counter() - iteration_started,
                    "jacobian_seconds": jacobian_seconds,
                    "line_search_seconds": line_search_seconds,
                },
            )
            records.append(record)
            if progress_callback is not None:
                progress_callback(record)

            if current.loss <= config.loss_tolerance:
                converged = True
                stop_reason = "loss_tolerance"
            elif previous_loss - current.loss <= config.loss_tolerance:
                converged = True
                stop_reason = "loss_change_tolerance"
            elif (
                float(np.linalg.norm(gradient, ord=np.inf))
                <= config.gradient_tolerance
            ):
                converged = True
                stop_reason = "gradient_tolerance"
            elif (
                float(np.linalg.norm(accepted_step))
                / max(np.linalg.norm(accepted_parameters), 1.0)
                <= config.relative_step_tolerance
            ):
                converged = True
                stop_reason = "relative_step_tolerance"

        return ParameterFDInverseResult(
            solver=solver_name,
            parameter_names=controller.names,
            iterations=tuple(records),
            converged=converged,
            stop_reason=stop_reason,
            total_evaluation_count=evaluator.evaluation_count,
            cache_hit_count=evaluator.cache_hit_count,
            maximum_system_residual=evaluator.maximum_system_residual,
            total_forward_seconds=evaluator.total_forward_seconds,
            total_seconds=float(perf_counter() - run_started),
        )
    finally:
        controller.assign(accepted_parameters)
        model.train(was_training)


__all__ = [
    "ComplexScatteredData",
    "ParameterFDConfig",
    "ParameterFDInverseResult",
    "ParameterFDIteration",
    "normalized_complex_residual",
    "run_parameter_fd_inverse",
]
