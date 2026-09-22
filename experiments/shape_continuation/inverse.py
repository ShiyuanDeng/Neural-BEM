"""Single-frequency GN/SD normal updates and explicit continuation handoffs."""
from dataclasses import dataclass, field
import numpy as np

from .forward import Acquisition, BudgetExceeded, Work, solve, shape_jacobian, timed
from .geometry import FourierCurve, displaced, normal_basis, curvature_tail, reparameterize, integer
from .schedule import Stage


@dataclass(frozen=True)
class Observation:
    wavenumber: float
    acquisition: Acquisition
    scattered: np.ndarray

    def __post_init__(self):
        data = np.array(self.scattered, complex, copy=True)
        expected = (len(self.acquisition.directions), len(self.acquisition.receivers))
        if data.shape != expected or not np.isfinite(data).all():
            raise ValueError(f"Scattered data must have shape {expected} and be finite.")
        if not np.isfinite(self.wavenumber) or self.wavenumber <= 0:
            raise ValueError("Observation wavenumber must be positive.")
        data.setflags(write=False)
        object.__setattr__(self, "scattered", data)


@dataclass(frozen=True)
class FitConfig:
    max_iterations: int = 50
    residual_tolerance: float = 1e-5
    step_tolerance: float = 1e-5
    gradient_tolerance: float = 1e-10
    curvature_tail_tolerance: float = 0.1
    projection_tolerance: float = 1e-7
    backtracks: int = 8
    filter_steps: int = 10
    rank_tolerance: float = 1e-10

    def __post_init__(self):
        for name in ("max_iterations", "backtracks", "filter_steps"):
            integer(getattr(self, name), name, minimum=0)
        for name in ("residual_tolerance", "step_tolerance", "gradient_tolerance", "projection_tolerance", "rank_tolerance"):
            value = getattr(self, name)
            if not np.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be positive.")
        if not 0 <= self.curvature_tail_tolerance < 1:
            raise ValueError("Curvature tail tolerance must lie in [0,1).")


@dataclass
class FitResult:
    shape: FourierCurve
    stage: Stage
    stop_reason: str
    relative_residual: float
    history: list = field(default_factory=list)
    trials: list = field(default_factory=list)
    states: list = field(default_factory=list)


def real_stack(array):
    return np.concatenate((array.real, array.imag), axis=0)


def fit_frequency(initial, observation, stage, contrast, *, config=None, work=None):
    """Optimizer sees one observation, never truth or evaluation observations."""
    config = FitConfig() if config is None else config
    work = Work() if work is None else work
    if stage.wavenumber != observation.wavenumber:
        raise ValueError("Stage and observation wavenumbers differ.")
    if initial.band > stage.curve_modes:
        raise ValueError("A stage may not silently discard stored shape modes.")
    padding = stage.curve_modes - initial.band
    shape = FourierCurve(np.pad(initial.coefficients, (padding, padding)))
    with timed(work, "initial_geometry"):
        shape.validate()
    scale = float(np.linalg.norm(observation.scattered)) or 1.0
    history, trials = [], []
    states = [shape]
    reason, error = "iteration_limit", float("nan")
    try:
        current = solve(shape, stage.wavenumber, contrast, observation.acquisition, stage.nodes, work=work)
        error = float(np.linalg.norm(current.prediction - observation.scattered) / scale)
        history.append(dict(iteration=0, relative_residual=error, system_residual=current.system_residual))
        for iteration in range(1, config.max_iterations + 1):
            if error <= config.residual_tolerance:
                reason = "data_fit"
                break
            basis = normal_basis(current.curve, stage.update_modes)
            complex_j = shape_jacobian(current, basis, work=work).reshape(-1, basis.shape[1])
            matrix = real_stack(complex_j) / scale
            residual = real_stack((current.prediction - observation.scattered).ravel()) / scale
            gradient = matrix.T @ residual
            gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
            with timed(work, "least_squares"):
                gn, _, rank, singular = np.linalg.lstsq(matrix, -residual, rcond=config.rank_tolerance)
            history[-1].update(gradient_inf=gradient_norm, jacobian_rank=int(rank),
                               singular_values=singular.tolist())
            if gradient_norm <= config.gradient_tolerance:
                reason = "stationary"
                break
            # Paper eq.18 is unscaled J* residual. Evaluate in the same raw-data
            # coordinates; normalized gradient above is only for diagnostics.
            sd = -gradient * scale ** 2
            accepted = None
            for filtering in range(config.filter_steps + 1):
                for backtrack in range(config.backtracks + 1):
                    candidates = []
                    for label, direction in (("gauss_newton", gn), ("steepest_descent", sd)):
                        work.check()
                        step = 0.5 ** backtrack
                        trial = dict(iteration=iteration, direction=label, filter_index=filtering, step=step)
                        trials.append(trial)
                        try:
                            with timed(work, "geometry_proposals"):
                                candidate, projection = displaced(shape, direction, stage.curve_modes,
                                    filter_index=filtering, step=step, projection_tolerance=config.projection_tolerance)
                            with timed(work, "curvature_checks"):
                                tail = curvature_tail(candidate, stage.curvature_modes)
                            trial.update(curvature_tail=tail, projection_error=projection)
                            if tail > config.curvature_tail_tolerance:
                                trial["status"] = "curvature_refused"
                                continue
                            forward = solve(candidate, stage.wavenumber, contrast,
                                            observation.acquisition, stage.nodes, work=work)
                            candidate_error = float(np.linalg.norm(forward.prediction - observation.scattered) / scale)
                            trial["relative_residual"] = candidate_error
                            trial["status"] = "decreasing" if candidate_error < error else "nondecreasing"
                            if candidate_error < error:
                                candidates.append((candidate_error, candidate, forward, trial, step * direction))
                        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                            trial.update(status="invalid", detail=str(exc))
                    if candidates:
                        accepted = min(candidates, key=lambda item: item[0])
                        break
                if accepted is not None:
                    break
            if accepted is None:
                reason = "no_acceptable_step"
                break
            error, shape, current, trial, coefficient_step = accepted
            states.append(shape)
            trial["status"] = "accepted"
            history.append(dict(iteration=iteration, relative_residual=error,
                direction=trial["direction"], step=trial["step"], filter_index=trial["filter_index"],
                curvature_tail=trial["curvature_tail"], projection_error=trial["projection_error"],
                coefficient_step_norm=float(np.linalg.norm(coefficient_step)),
                system_residual=current.system_residual))
            if error <= config.residual_tolerance:
                reason = "data_fit"
                break
            # A filtered coefficient norm would not describe the actual update.
            if trial["filter_index"] == 0 and np.linalg.norm(coefficient_step) <= config.step_tolerance:
                reason = "small_step"
                break
    except BudgetExceeded:
        reason = "budget_exhausted"
    return FitResult(shape, stage, reason, error, history, trials, states)


def run_continuation(initial, observations, stages, contrast, *, config=None, work=None, on_stage=None):
    """Warm-start ordered single-frequency objectives; no hidden cumulative fit."""
    observations, stages = tuple(observations), tuple(stages)
    if len(observations) != len(stages) or not stages:
        raise ValueError("One observation is required per nonempty stage list.")
    if any(b.wavenumber <= a.wavenumber for a, b in zip(stages, stages[1:])):
        raise ValueError("Baseline continuation requires strictly increasing wavenumbers.")
    if any(a.wavenumber != b.wavenumber for a, b in zip(observations, stages)):
        raise ValueError("Observations must match the stage order.")
    if any(b.curve_modes < a.curve_modes for a, b in zip(stages, stages[1:])):
        raise ValueError("Stored curve bandwidth cannot decrease in this baseline.")
    config = FitConfig() if config is None else config
    work = Work() if work is None else work
    with timed(work, "initial_geometry"):
        shape, _ = reparameterize(initial, stages[0].curve_modes, tolerance=config.projection_tolerance)
    results = []
    for observation, stage in zip(observations, stages):
        result = fit_frequency(shape, observation, stage, contrast, config=config, work=work)
        results.append(result)
        shape = result.shape
        if on_stage is not None:
            on_stage(len(results) - 1, result)
        if result.stop_reason == "budget_exhausted":
            break
    return results
