"""Single-frequency GN/SD normal updates and explicit continuation handoffs."""
from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from .forward import Acquisition, BudgetExceeded, ForwardState, Work, solve, shape_jacobian, timed, same_acquisition
from .geometry import FourierCurve, displaced, gaussian_filter, normal_basis, curvature_tail, integer
from .schedule import Stage


@dataclass(frozen=True)
class Observation:
    wavenumber: float
    acquisition: Acquisition
    scattered: np.ndarray

    def __post_init__(self):
        data = np.array(self.scattered, complex, copy=True)
        expected = self.acquisition.data_shape
        if data.shape != expected or not np.isfinite(data).all():
            raise ValueError(f"Scattered data must have shape {expected} and be finite.")
        if not np.isfinite(self.wavenumber) or self.wavenumber <= 0:
            raise ValueError("Observation wavenumber must be positive.")
        data.setflags(write=False)
        object.__setattr__(self, "scattered", data)


DIRECTIONS = ("gauss_newton", "steepest_descent")


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
    # Which proposals the search may use, in the reference's `optim_type` sense:
    # ('gauss_newton',) is 'gn', ('steepest_descent',) is 'sd' — what the
    # transmission driver uses — and both is 'min(gn,sd)'. The reference's
    # 'sd-min(gn,sd)' phase, steepest descent for the first sd_iter updates of a
    # frequency, is expressed by a strategy issuing two decisions rather than by
    # a counter here: a counter would depend on how updates are grouped into
    # chunks, so the same trajectory driven one update at a time would differ.
    directions: tuple = ("gauss_newton", "steepest_descent")

    def __post_init__(self):
        for name in ("max_iterations", "backtracks", "filter_steps"):
            integer(getattr(self, name), name, minimum=0)
        chosen = tuple(self.directions)
        if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(DIRECTIONS):
            raise ValueError(f"directions must be a non-repeating subset of {DIRECTIONS}.")
        object.__setattr__(self, "directions", chosen)
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


@dataclass(frozen=True)
class OptimizerState:
    """One physical state. Retune through prepare_state; never mutate its arrays."""
    shape: FourierCurve
    observation: Observation
    stage: Stage
    contrast: float
    forward: ForwardState = field(repr=False)
    relative_residual: float

    @property
    def data_scale(self):
        return float(np.linalg.norm(self.observation.scattered)) or 1.0


@dataclass(frozen=True)
class StepResult:
    state: OptimizerState
    accepted: bool
    stop_reason: Optional[str]  # None means another update is allowed.
    diagnostics: dict  # Evaluated at the INPUT state, not the accepted endpoint.
    trials: list
    accepted_record: Optional[dict] = None


def _pad_shape(shape, stage):
    if shape.band > stage.curve_modes:
        raise ValueError("A stage may not silently discard stored shape modes.")
    padding = stage.curve_modes - shape.band
    return FourierCurve(np.pad(shape.coefficients, (padding, padding))) if padding else shape


def _same_curve(first, second):
    band = max(first.band, second.band)
    return np.array_equal(np.pad(first.coefficients, (band-first.band,) * 2),
                          np.pad(second.coefficients, (band-second.band,) * 2))


def prepare_state(shape, observation, stage, contrast, *, cached=None, work=None):
    """Prepare or reuse physics; M/C/K-padding changes alone need no new solve.

    Geometry is supplied in its current gauge. The continuation drivers refit
    their initial curve once; accepted updates already refit by arclength.
    Cache matching is exact and includes shape, k, contrast, acquisition and N.
    Data-only changes reuse the prediction but recompute its residual.
    """
    if stage.wavenumber != observation.wavenumber:
        raise ValueError("Stage and observation wavenumbers differ.")
    if not np.isfinite(contrast) or contrast <= 0:
        raise ValueError("Contrast must be positive.")
    if (cached is not None and shape is cached.shape and observation is cached.observation
            and stage == cached.stage and contrast == cached.contrast):
        return cached
    shape = _pad_shape(shape, stage)
    with timed(work, "initial_geometry"):
        shape.validate()
    reuse = (cached is not None and stage.wavenumber == cached.stage.wavenumber
        and stage.nodes == cached.stage.nodes and contrast == cached.contrast
        and _same_curve(shape, cached.shape)
        and same_acquisition(observation.acquisition, cached.observation.acquisition))
    forward = cached.forward if reuse else solve(shape, stage.wavenumber, contrast,
                                                observation.acquisition, stage.nodes, work=work)
    scale = float(np.linalg.norm(observation.scattered)) or 1.0
    error = float(np.linalg.norm(forward.prediction - observation.scattered) / scale)
    return OptimizerState(shape, observation, stage, float(contrast), forward, error)


def optimise_step(state, *, config=None, work=None, iteration=1):
    """Attempt at most ONE accepted update, retaining its computed forward state.

    All rejected trials and input-state diagnostics are returned. A small-step,
    data-fit or other local stop is a report to the caller, not a prohibition on
    retuning the state/configuration and trying another strategy.
    """
    config = FitConfig() if config is None else config
    work = Work() if work is None else work
    integer(iteration, "iteration")
    shape, observation, stage = state.shape, state.observation, state.stage
    current, error, scale = state.forward, state.relative_residual, state.data_scale
    diagnostics, trials = {}, []
    def stopped(reason):
        return StepResult(state, False, reason, diagnostics, trials)
    if error <= config.residual_tolerance:
        return stopped("data_fit")
    try:
        basis = normal_basis(current.curve, stage.update_modes)
        complex_j = shape_jacobian(current, basis, work=work).reshape(-1, basis.shape[1])
        matrix = real_stack(complex_j) / scale
        residual = real_stack((current.prediction - observation.scattered).ravel()) / scale
        gradient = matrix.T @ residual
        gradient_norm = float(np.linalg.norm(gradient, ord=np.inf))
        with timed(work, "least_squares"):
            gn, _, rank, singular = np.linalg.lstsq(matrix, -residual, rcond=config.rank_tolerance)
        with timed(work, "curvature_checks"):
            base_tail = curvature_tail(shape, stage.curvature_modes)
        diagnostics.update(gradient_inf=gradient_norm, jacobian_rank=int(rank),
                           singular_values=singular.tolist(), base_curvature_tail=base_tail)
        if gradient_norm <= config.gradient_tolerance:
            return stopped("stationary")
        # Eq.18 names only the direction J*(u_meas - F). The reference code
        # scales it to the Cauchy point, t = |J*r|^2 / |J J*r|^2, which is
        # invariant to the residual normalization applied above; the unscaled
        # adjoint has arbitrary magnitude and is not a usable step.
        curvature_along = float(np.linalg.norm(matrix @ gradient))
        sd = -gradient * (np.linalg.norm(gradient) / curvature_along) ** 2 if curvature_along else -gradient
        proposals = dict(gauss_newton=gn, steepest_descent=sd)

        def search(label):
            """Weaken this one direction until it is admissible and decreasing.

            The reference filters each direction to admissibility on its own and
            only then compares the survivors' residuals, so a direction needing
            a stronger filter is still reachable when the other succeeds early.
            """
            direction = proposals[label]
            weakened = None
            for filtering in range(config.filter_steps + 1):
                # Eq.19 damps each harmonic monotonically in the level, so once
                # a level leaves the update unchanged every later one does too
                # and would rebuild the identical candidate. Stopping there is
                # exact, not a tolerance: the reference simply pays for the
                # repeats. It matters when a direction is hopeless, where the
                # sweep would otherwise re-solve the same geometry ~6 times.
                previous, weakened = weakened, gaussian_filter(direction, filtering)
                if previous is not None and np.array_equal(weakened, previous):
                    break
                for backtrack in range(config.backtracks + 1):
                    work.check()
                    step = 0.5 ** backtrack
                    trial = dict(iteration=iteration, direction=label,
                                 filter_index=filtering, step=step)
                    trials.append(trial)
                    try:
                        with timed(work, "geometry_proposals"):
                            proposal = displaced(shape, direction, stage.curve_modes,
                                filter_index=filtering, step=step, projection_tolerance=config.projection_tolerance)
                        candidate = proposal.shape
                        trial.update(projection_error=proposal.projection_error,
                            rms_displacement=proposal.rms_displacement,
                            maximum_displacement=proposal.maximum_displacement,
                            update_norm=proposal.update_norm,
                            coefficient_step_norm=float(np.linalg.norm(step * direction)))
                        with timed(work, "curvature_checks"):
                            tail = curvature_tail(candidate, stage.curvature_modes)
                        trial.update(curvature_tail=tail)
                        if tail > config.curvature_tail_tolerance:
                            trial["status"] = "curvature_refused"
                            continue
                        forward = solve(candidate, stage.wavenumber, state.contrast,
                                        observation.acquisition, stage.nodes, work=work)
                        candidate_error = float(np.linalg.norm(forward.prediction - observation.scattered) / scale)
                        trial["relative_residual"] = candidate_error
                        trial["status"] = "decreasing" if candidate_error < error else "nondecreasing"
                        if candidate_error < error:
                            return candidate_error, candidate, forward, trial
                    except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                        trial.update(status="invalid", detail=str(exc))
            return None

        candidates = [found for found in map(search, config.directions) if found]
        if not candidates:
            return stopped("no_acceptable_step")
        accepted = min(candidates, key=lambda item: item[0])
        error, shape, current, trial = accepted
        trial["status"] = "accepted"
        record = dict(iteration=iteration, relative_residual=error,
            direction=trial["direction"], step=trial["step"], filter_index=trial["filter_index"],
            curvature_tail=trial["curvature_tail"], projection_error=trial["projection_error"],
            coefficient_step_norm=trial["coefficient_step_norm"], update_norm=trial["update_norm"],
            rms_displacement=trial["rms_displacement"], maximum_displacement=trial["maximum_displacement"],
            system_residual=current.system_residual)
        updated = OptimizerState(shape, observation, stage, state.contrast, current, error)
        reason = "data_fit" if error <= config.residual_tolerance else (
            "small_step" if trial["rms_displacement"] <= config.step_tolerance else None)
        return StepResult(updated, True, reason, diagnostics, trials, record)
    except BudgetExceeded:
        if trials and "status" not in trials[-1]:
            trials[-1]["status"] = "budget_exhausted"
        return stopped("budget_exhausted")


def fit_prepared(state, *, config=None, work=None):
    """Run a fixed-stage chunk; return (live cached state, lightweight report).

    max_iterations=1 hands control back after every update. Reports contain
    coefficient histories, never dense forward matrices or factorizations.
    """
    config = FitConfig() if config is None else config
    work = Work() if work is None else work
    history = [dict(iteration=0, relative_residual=state.relative_residual,
                    system_residual=state.forward.system_residual)]
    trials, states = [], [state.shape]
    reason = "iteration_limit"
    for iteration in range(1, config.max_iterations + 1):
        step = optimise_step(state, config=config, work=work, iteration=iteration)
        history[-1].update(step.diagnostics)
        trials.extend(step.trials)
        state = step.state
        if step.accepted:
            history.append(step.accepted_record)
            states.append(state.shape)
        if step.stop_reason is not None:
            reason = step.stop_reason
            break
    return state, FitResult(state.shape, state.stage, reason, state.relative_residual,
                            history, trials, states)


def fit_frequency(initial, observation, stage, contrast, *, config=None, work=None):
    """Compatibility convenience for a fresh single-frequency fit."""
    work = Work() if work is None else work
    try:
        state = prepare_state(initial, observation, stage, contrast, work=work)
    except BudgetExceeded:
        shape = _pad_shape(initial, stage)
        return FitResult(shape, stage, "budget_exhausted", float("nan"), states=[shape])
    return fit_prepared(state, config=config, work=work)[1]


def run_continuation(initial, observations, stages, contrast, *, config=None, work=None, on_stage=None):
    """Compatibility adapter for a strictly increasing fixed frequency ladder.

    A stage callback receives (shape, next_wavenumber, previous_stage).
    General strategies use continuation.run_adaptive with full decision history.
    """
    from .continuation import Decision, run_adaptive

    observations = tuple(observations)
    policy = stages if callable(stages) else None
    stages = None if policy else tuple(stages)
    if not observations or (stages is not None and len(observations) != len(stages)):
        raise ValueError("One observation is required per nonempty stage list.")
    if any(b.wavenumber <= a.wavenumber for a, b in zip(observations, observations[1:])):
        raise ValueError("Baseline continuation requires strictly increasing wavenumbers.")
    if stages is not None and any(a.wavenumber != b.wavenumber for a, b in zip(observations, stages)):
        raise ValueError("Observations must match the stage order.")
    if stages is not None and any(b.curve_modes < a.curve_modes for a, b in zip(stages, stages[1:])):
        raise ValueError("Stored curve bandwidth cannot decrease in this baseline.")
    config = FitConfig() if config is None else config
    def strategy(context):
        index = len(context.history)
        if index == len(observations):
            return None
        k = observations[index].wavenumber
        previous = context.history[-1].result.stage if index else None
        stage = policy(context.shape, k, previous) if policy else stages[index]
        if stage.wavenumber != k:
            raise ValueError("Stage policy must preserve frequency.")
        return Decision(stage, config, "fixed frequency ladder")
    def checkpoint(record):
        if on_stage is not None:
            on_stage(record.index, record.result)
    result = run_adaptive(initial, observations, contrast, strategy, work=work,
                          max_decisions=len(observations), on_decision=checkpoint)
    return [record.result for record in result.history]
