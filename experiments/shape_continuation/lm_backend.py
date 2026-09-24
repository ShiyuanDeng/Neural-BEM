"""SPD-style Levenberg-Marquardt backend over a replaceable geometry update.

The step rules reproduce `sdf_inverse.radial_topology.run_multiradial_fd_inverse`
as the SPD continuation calls it (loss-change stopping off, strict production
decrease plus the refined cross-resolution acceptance of `run_top016_pilot`,
hard stop when a candidate leaves the frozen numerical regime). Only the
coordinates, directions, finite trial construction and physics change:

- the update strategy supplies them (default: Borges normal move + refit);
- fields and Hadamard derivatives come from this package's nodal Müller solver.

A policy chooses each `FitStage`; the backend never sees truth or evaluation
data. Work is charged in SPD units: one frequency system solve, or one
reciprocal right-hand-side batch for a Jacobian at one frequency.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from time import perf_counter
from typing import Optional

import numpy as np
from ordered_boundary.validation_cache import fit_geometry_validation

from .forward import solve, shape_jacobian
from .geometry import FourierCurve, grid_size, integer
from .updates import UpdateRefused

NORMAL_RETURN = "NORMAL_OPTIMIZER_RETURN"
STAGE_QUOTA = "STAGE_QUOTA_REACHED"


class Stop(RuntimeError):
    code = "IMPLEMENTATION_ERROR"


class StageQuota(Stop):
    code = STAGE_QUOTA


class TrialSolveCap(Stop):
    code = "TRIAL_SOLVE_CAP"


class TrialWallLimit(Stop):
    code = "TRIAL_WALL_LIMIT"


class NumericalFailure(Stop):
    code = "NUMERICAL_FAILURE"


@dataclass(frozen=True)
class FitStage:
    """One policy decision: the objective, the shape space and the work allowed."""
    label: str
    observations: tuple  # inverse.Observation, one per active frequency (F)
    weights: tuple  # objective weight per active frequency
    discrepancy_tolerances: tuple  # production/refined agreement per frequency
    update_modes: int  # M
    curve_modes: int  # K
    nodes: int  # N for the objective and Jacobian
    refined_nodes: int  # acceptance and numerical-regime check
    iterations: int  # LM iteration cap
    quota: Optional[int] = None  # work units for this stage

    def __post_init__(self):
        count = len(self.observations)
        if not count or len(self.weights) != count or len(self.discrepancy_tolerances) != count:
            raise ValueError("One weight and tolerance is required per active observation.")
        if any(not np.isfinite(w) or w < 0 for w in self.weights) or not any(self.weights):
            raise ValueError("Weights must be finite, nonnegative and not all zero.")
        for name in ("curve_modes", "nodes", "refined_nodes"):
            integer(getattr(self, name), name)
        integer(self.update_modes, "update_modes", minimum=0)
        integer(self.iterations, "iterations", minimum=0)
        if self.nodes <= 2 * self.curve_modes or self.refined_nodes <= self.nodes:
            raise ValueError("Nodes must resolve the curve band and refine strictly.")
        if self.quota is not None:
            integer(self.quota, "quota")


@dataclass(frozen=True)
class BackendConfig:
    """SPD continuation LM settings; bounds apply by harmonic order 0, 1, >=2."""
    initial_damping: float = 1e-3
    damping_increase: float = 10.0
    damping_decrease: float = 0.3
    max_damping_trials: int = 5
    max_backtracks: int = 7
    gradient_tolerance: float = 1e-7
    loss_tolerance: float = 1e-14
    relative_step_tolerance: float = 1e-7
    scaling_floor: float = 1.0
    step_bounds_m: tuple = (0.012, 0.018, 0.006)
    acceptance_absolute_margin: float = 1e-14
    acceptance_relative_margin: float = 1e-8
    cross_resolution_factor: float = 5.0
    residual_floor: float = 1e-12
    domain_box: Optional[tuple] = None  # ((xmin, ymin), (xmax, ymax)) in package units
    # "coefficient" clips each coordinate to `step_bounds_m` (SPD's rule, the
    # default). "physical" instead scales the whole proposal so its maximum
    # normal move is at most `physical_step_bound_m`, keeping its direction and
    # a bound that does not grow with the band M. A shared-backend option,
    # added after the 2026-09-24 review; runs before it used "coefficient".
    step_control: str = "coefficient"
    physical_step_bound_m: float = 0.006
    # SC-031 opt-in regularizing LM (defaults reproduce V2 bitwise).
    # damping_rule "schedule": first damping of an iteration carries over
    # (initial_damping, then x damping_decrease after success). "hanke": it
    # solves ||r + J d(lam)|| = hanke_ratio ||r|| each iteration (Hanke 1997),
    # falling back to a Gauss-Newton floor when unattainable. metric
    # "marquardt": max(diag G, scaling_floor); "mass"/"curvature": the
    # update's physical step metric, with smoothing length
    # 1 / (detectability_factor * exterior wavenumber of the stage's highest
    # frequency). log_model adds pred = -g.d - d.G.d/2 to every trial record.
    damping_rule: str = "schedule"
    hanke_ratio: float = 0.7
    metric: str = "marquardt"
    detectability_factor: float = 2.5
    log_model: bool = False

    def __post_init__(self):
        if self.damping_rule not in ("schedule", "hanke"):
            raise ValueError(f"Unknown damping rule {self.damping_rule!r}.")
        if self.metric not in ("marquardt", "mass", "curvature"):
            raise ValueError(f"Unknown step metric {self.metric!r}.")
        if not 0 < self.hanke_ratio < 1 or not self.detectability_factor > 0:
            raise ValueError("hanke_ratio must lie in (0, 1) and detectability_factor must be positive.")

    def bounds(self, orders):
        order = np.asarray(orders)
        return np.where(order == 0, self.step_bounds_m[0],
                        np.where(order == 1, self.step_bounds_m[1], self.step_bounds_m[2]))


def control_step(proposed, space, update, config):
    """Apply the configured step control to an LM proposal (before halving)."""
    if config.step_control == "coefficient":
        bound = config.bounds(space.orders)
        return np.clip(proposed, -bound, bound)
    if config.step_control == "physical":
        size = update.measure(space, proposed)["maximum_normal_m"]
        return proposed * min(1.0, config.physical_step_bound_m / size) if size > 0 else proposed
    raise ValueError(f"Unknown step control {config.step_control!r}.")


def hanke_damping(matrix, residual, metric, ratio, floor=1e-12):
    """Hanke's regularizing-LM parameter in the metric R (Inverse Problems 13, 1997).

    Returns (lam, attainable) with ||r + J d(lam)|| = ratio ||r|| for
    d(lam) = -(J^T J + lam R)^{-1} J^T r. The linearized residual rises
    monotonically from its Gauss-Newton value (lam = 0) to ||r||; if the
    Gauss-Newton value already exceeds ratio ||r||, return the floor
    ``floor`` x the mean eigenvalue of the R-scaled Gauss-Newton matrix.
    """
    from scipy.optimize import brentq
    factor = np.linalg.cholesky(metric)
    scaled = np.linalg.solve(factor, np.asarray(matrix).T).T  # J C^{-T}, R = C C^T
    u, singular, _ = np.linalg.svd(scaled, full_matrices=False)
    projection = u.T @ residual
    total = float(residual @ residual)
    outside = max(total - float(projection @ projection), 0.0)
    power = singular**2
    lowest = floor * float(np.mean(power)) if power.size and np.mean(power) > 0 else floor
    target = ratio**2 * total

    def excess(log_lam):
        lam = np.exp(log_lam)
        return outside + float(np.sum((lam / (power + lam))**2 * projection**2)) - target

    if excess(np.log(lowest)) >= 0:
        return lowest, False
    high = max(float(np.max(power)), lowest) * 10
    while excess(np.log(high)) < 0:
        high *= 10
    return float(np.exp(brentq(excess, np.log(lowest), np.log(high), xtol=1e-13, rtol=1e-15))), True


class Ledger:
    """Work units, stage quotas and hard limits with the SPD reservation rule.

    A reservation raises before a batch whose declared maximum would cross
    the stage quota (a normal stage end) or the total cap/wall (a hard stop).
    """

    def __init__(self, cap=8012, seconds=7200.0, clock=perf_counter, endpoint_reserve=12):
        self.cap, self.seconds, self.clock = int(cap), float(seconds), clock
        self.endpoint_reserve = int(endpoint_reserve)
        self.started = clock()
        self.units = 0
        self.stage = None
        self.stage_start = 0
        self.stage_quota = None
        self.endpoint = False
        self.solves = {}
        self.failed = {}
        self.reciprocal = {}

    def begin_stage(self, label, quota):
        if self.clock() - self.started >= self.seconds:
            raise TrialWallLimit("hard wall limit at stage boundary")
        if self.units >= self.cap:
            raise TrialSolveCap("hard work cap at stage boundary")
        self.stage, self.stage_start, self.stage_quota = label, self.units, quota

    def reserve(self, maximum):
        overhead = self.endpoint_reserve if self.stage is not None and not self.endpoint else 0
        spent = self.units - self.stage_start
        if self.clock() - self.started >= self.seconds:
            raise TrialWallLimit("hard wall limit")
        if self.units >= self.cap and maximum + overhead > 0:
            raise TrialSolveCap("total work cap reached")
        if (self.stage_quota is not None and spent + maximum + overhead > self.stage_quota
                and self.stage_quota - spent <= self.cap - self.units
                and self.units + overhead <= self.cap):
            raise StageQuota("next complete batch and endpoint reserve exceed the stage quota")
        if self.units + maximum + overhead > self.cap:
            raise TrialSolveCap("next complete batch and endpoint reserve exceed the total cap")

    @contextmanager
    def endpoint_scope(self):
        previous, self.endpoint = self.endpoint, True
        try:
            yield
        finally:
            self.endpoint = previous

    def charge(self, kind, category):
        store = self.solves if kind == "solve" else self.reciprocal
        key = f"{self.stage}:{category}"
        store[key] = store.get(key, 0) + 1
        self.units += 1

    def fail(self, category):
        key = f"{self.stage}:{category}"
        self.failed[key] = self.failed.get(key, 0) + 1

    def snapshot(self):
        return dict(work_units=self.units, stage=self.stage, stage_units=self.units - self.stage_start,
                    stage_quota=self.stage_quota, cap=self.cap, solves=dict(self.solves),
                    reciprocal_batches=dict(self.reciprocal), failed=dict(self.failed),
                    seconds=self.clock() - self.started)


def normalize(values, observed, weights, floor=1e-12):
    """Linear SPD residual map: per-frequency relative scale and sqrt weight.

    Matches `sdf_inverse.optimization.normalized_complex_residual`, including
    its floor and real/imaginary row order. `values` may carry trailing axes.
    """
    observed = np.asarray(observed)
    norms = np.linalg.norm(observed, axis=0)
    reference = max(float(np.max(norms)), float(np.linalg.norm(observed)) / np.sqrt(observed.shape[1]), 1.0)
    scales = np.maximum(norms, max(floor * reference, np.finfo(float).tiny))
    values = np.asarray(values)
    shape = (1, -1) + (1,) * (values.ndim - 2)
    scaled = values / scales.reshape(shape) * np.sqrt(np.asarray(weights, float)).reshape(shape)
    tail = values.shape[2:]
    return np.concatenate((scaled.real.reshape((-1,) + tail), scaled.imag.reshape((-1,) + tail)))


@dataclass(frozen=True)
class Evaluation:
    curve: FourierCurve
    loss: float
    relative_l2: float
    residual: np.ndarray = field(repr=False)
    prediction: np.ndarray = field(repr=False)  # (pairs, frequencies)
    forwards: tuple = field(repr=False, default=())


def acceptance(base, candidate, refined_base, refined_candidate, config):
    dp, dr = base - candidate, refined_base - refined_candidate
    margin = max(config.acceptance_absolute_margin + config.acceptance_relative_margin * base,
                 config.acceptance_absolute_margin + config.acceptance_relative_margin * refined_base)
    uncertainty = config.cross_resolution_factor * abs(dp - dr)
    return dict(production_gain=dp, refined_gain=dr, margin=margin,
                disagreement_allowance=uncertainty, accepted=bool(min(dp, dr) > margin + uncertainty))


def relative_columns(a, b):
    return np.linalg.norm(a - b, axis=0) / np.linalg.norm(b, axis=0)


def inside_box(curve, box):
    if box is None:
        return True
    z = curve.values(grid_size(curve.band))
    (x0, y0), (x1, y1) = box
    return bool(np.all(z.real > x0) and np.all(z.real < x1) and np.all(z.imag > y0) and np.all(z.imag < y1))


class Objective:
    """Stage objective at production and refined nodes; refined values cached."""

    def __init__(self, stage, contrast, config, ledger):
        self.stage, self.contrast, self.config, self.ledger = stage, float(contrast), config, ledger
        self.observed = np.column_stack([o.scattered for o in stage.observations])
        self.refined_cache = {}
        self.count = len(stage.observations)

    def _predict(self, curve, nodes, category, keep):
        self.ledger.reserve(self.count)
        forwards, columns = [], []
        for observation in self.stage.observations:
            self.ledger.reserve(1)
            self.ledger.charge("solve", category)
            try:
                state = solve(curve, observation.wavenumber, self.contrast, observation.acquisition, nodes)
            except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                self.ledger.fail(category)
                return None
            columns.append(state.prediction)
            if keep:
                forwards.append(state)
        prediction = np.column_stack(columns)
        residual = normalize(prediction - self.observed, self.observed, self.stage.weights,
                             self.config.residual_floor)
        relative = float(np.linalg.norm(prediction - self.observed) / np.linalg.norm(self.observed))
        return Evaluation(curve, 0.5 * float(residual @ residual), relative, residual, prediction, tuple(forwards))

    def production(self, curve, category):
        return self._predict(curve, self.stage.nodes, category, keep=True)

    def refined(self, curve):
        key = curve.coefficients.tobytes()
        if key not in self.refined_cache:
            self.refined_cache[key] = self._predict(curve, self.stage.refined_nodes, "acceptance_validation", keep=False)
        return self.refined_cache[key]

    def jacobian(self, evaluation, update, space):
        """Residual Jacobian (rows as `normalize`) with respect to update coordinates."""
        blocks = []
        for forward in evaluation.forwards:
            self.ledger.reserve(1)
            self.ledger.charge("reciprocal", "derivative")
            blocks.append(shape_jacobian(forward, update.velocities(space, forward.curve)))
        derivative = np.stack(blocks, axis=1)  # (pairs, frequencies, directions)
        return normalize(derivative, self.observed, self.stage.weights, self.config.residual_floor)


@dataclass
class StageResult:
    stage_label: str
    curve: FourierCurve
    outcome: str
    stop_reason: Optional[str]
    converged: bool
    accepted_steps: int
    initial_loss: float
    final_loss: float
    history: list
    trials: list
    acceptance_checks: list
    detail: Optional[str] = None
    work: dict = field(default_factory=dict)
    seconds: float = 0.0


@fit_geometry_validation
def fit_stage(curve, stage, contrast, update, config, ledger, *, on_accept=None):
    """Run one stage, optionally under a fit-local ``geometry_validation`` cache.

    The default is unchanged. Use ``geometry_validation('cache', on_fit=...)``
    for exact reuse of hybrid and shared forward-geometry predicates. The
    generic cache callback's ``num_nodes`` is unset for this stage interface;
    resolutions remain available in the caller's FitStage record.
    """
    started = perf_counter()
    if curve.band != stage.curve_modes:
        raise ValueError("Pass the curve at the stage storage band.")
    objective = Objective(stage, contrast, config, ledger)
    m = objective.count
    history, trials, checks = [], [], []
    accepted_steps, converged, stop_reason, outcome, detail = 0, False, "maximum_iterations", NORMAL_RETURN, None
    current = None
    initial_loss = float("nan")

    def admissible(candidate_curve):
        return inside_box(candidate_curve, config.domain_box)

    def validate(base, candidate):
        ledger.reserve(2 * m)
        rb, rc = objective.refined(base.curve), objective.refined(candidate.curve)
        if rb is None or rc is None:
            raise NumericalFailure("refined evaluation failed at an accepted or candidate state")
        discrepancy = relative_columns(candidate.prediction, rc.prediction)
        row = dict(acceptance(base.loss, candidate.loss, rb.loss, rc.loss, config),
                   prediction_discrepancy=discrepancy.tolist(),
                   refined_base_loss=rb.loss, refined_candidate_loss=rc.loss)
        checks.append(row)
        tolerances = np.asarray(stage.discrepancy_tolerances)
        if not np.all(np.isfinite(discrepancy)) or np.any(discrepancy > tolerances):
            row["accepted"] = False
            row["numerical_obstruction"] = True
            raise NumericalFailure("candidate leaves the frozen numerical-resolution regime")
        return row["accepted"]

    def gradient_frame(evaluation):
        space = update.prepare(evaluation.curve, stage.update_modes, stage.curve_modes)
        ledger.reserve(4 * m)  # Jacobian plus one production/refined step opportunity
        matrix = objective.jacobian(evaluation, update, space)
        return space, matrix, matrix.T @ evaluation.residual

    def record(iteration, evaluation, gradient, step, damping, next_damping, trial=None):
        row = dict(iteration=iteration, loss=evaluation.loss, relative_l2=evaluation.relative_l2,
                   gradient_inf=float(np.linalg.norm(gradient, ord=np.inf)),
                   step_norm_m=float(np.linalg.norm(step)), damping=float(damping),
                   next_damping=float(next_damping), step_m=np.asarray(step, float).tolist(),
                   coefficients=dict(real=evaluation.curve.coefficients.real.tolist(),
                                     imag=evaluation.curve.coefficients.imag.tolist()),
                   work=ledger.snapshot())
        if trial is not None:
            row.update({k: trial[k] for k in ("maximum_normal_m", "rms_normal_m", "projection_relative",
                                               "speed_ratio") if k in trial})
        history.append(row)

    scale = max(float(np.linalg.norm(curve.coefficients) * update.length_unit_m), 1.0)
    smoothing = None
    if config.metric == "curvature":
        smoothing = update.length_unit_m / (config.detectability_factor *
                                            max(o.wavenumber for o in stage.observations))

    def damping_matrix(space, normal):
        if config.metric == "marquardt":
            return np.diag(np.maximum(np.diag(normal), config.scaling_floor))
        return update.metric(space, config.metric, smoothing)
    try:
        if not admissible(curve):
            raise NumericalFailure("initial state leaves the geometry domain")
        current = objective.production(curve, "initial_objective")
        if current is None:
            raise NumericalFailure("initial state is not solver-ready")
        initial_loss = current.loss
        if on_accept is not None:
            on_accept(0, current)
        space, matrix, gradient = gradient_frame(current)
        damping = config.initial_damping
        record(0, current, gradient, np.zeros(matrix.shape[1]), damping, damping)
        if current.loss <= config.loss_tolerance:
            converged, stop_reason = True, "loss_tolerance"
        elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
            converged, stop_reason = True, "gradient_tolerance"
        for iteration in range(1, stage.iterations + 1):
            if converged:
                break
            normal = matrix.T @ matrix
            damped = damping_matrix(space, normal)
            accepted = None
            trial_damping = damping
            rule = None
            if config.damping_rule == "hanke":
                trial_damping, attainable = hanke_damping(matrix, current.residual, damped, config.hanke_ratio)
                rule = dict(hanke_lambda=float(trial_damping), hanke_attainable=bool(attainable))
            for _ in range(config.max_damping_trials):
                try:
                    proposed = np.linalg.solve(normal + trial_damping * damped, -gradient)
                except np.linalg.LinAlgError:
                    trial_damping *= config.damping_increase
                    continue
                proposed = control_step(proposed, space, update, config)
                for backtrack in range(config.max_backtracks + 1):
                    step = 0.5 ** backtrack * proposed
                    if np.linalg.norm(step) / scale <= config.relative_step_tolerance:
                        continue
                    trial = dict(iteration=iteration, damping=float(trial_damping), backtrack=backtrack,
                                 step_norm_m=float(np.linalg.norm(step)))
                    if config.log_model:
                        trial.update(predicted_decrease=float(-(gradient @ step) - 0.5 * step @ normal @ step),
                                     **(rule or {}))
                    trials.append(trial)
                    try:
                        candidate_curve, geometry = update.trial(space, step)
                        trial.update(geometry)
                    except UpdateRefused as exc:
                        trial.update(status="refused", reason=exc.reason, detail=exc.detail)
                        continue
                    if not admissible(candidate_curve):
                        trial.update(status="refused", reason="outside_domain")
                        continue
                    candidate = objective.production(candidate_curve, "candidate")
                    if candidate is None:
                        trial.update(status="refused", reason="physics_failed")
                        continue
                    trial.update(loss=candidate.loss)
                    if candidate.loss >= current.loss:
                        trial["status"] = "nondecreasing"
                        continue
                    if not validate(current, candidate):
                        trial["status"] = "acceptance_margin"
                        continue
                    trial["status"] = "accepted"
                    accepted = (candidate, step, trial_damping, trial)
                    break
                if accepted is not None:
                    break
                trial_damping *= config.damping_increase
            if accepted is None:
                stop_reason = "no_decreasing_step"
                break
            current, step, used_damping, trial = accepted
            accepted_steps = iteration
            damping = max(used_damping * config.damping_decrease, np.finfo(float).tiny)
            if on_accept is not None:
                on_accept(iteration, current)
            space, matrix, gradient = gradient_frame(current)
            record(iteration, current, gradient, step, used_damping, damping, trial)
            if current.loss <= config.loss_tolerance:
                converged, stop_reason = True, "loss_tolerance"
            elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
                converged, stop_reason = True, "gradient_tolerance"
            elif np.linalg.norm(step) / scale <= config.relative_step_tolerance:
                converged, stop_reason = True, "relative_step_tolerance"
    except StageQuota as exc:
        outcome, stop_reason, detail = STAGE_QUOTA, None, str(exc)
    except Stop as exc:
        outcome, stop_reason, detail = exc.code, None, str(exc)
    final = curve if current is None else current.curve
    return StageResult(stage.label, final, outcome, stop_reason, converged, accepted_steps, initial_loss,
                       float("nan") if current is None else current.loss, history, trials, checks,
                       detail, ledger.snapshot(), perf_counter() - started)


class FixedSchedule:
    """The simplest policy: a declared list of stages, ignoring history."""

    def __init__(self, stages, name="fixed schedule"):
        self.stages, self.name = tuple(stages), name

    def next_stage(self, history):
        return self.stages[len(history)] if len(history) < len(self.stages) else None


@dataclass
class ScheduleResult:
    status: str
    curve: FourierCurve
    stages: list
    regauge_error: float
    reason: Optional[str] = None
    detail: Optional[str] = None


def run_policy(initial, policy, contrast, update, config, ledger, *, on_stage=None, on_accept=None):
    """Policy loop. `on_stage(stage, result)` is the external endpoint hook.

    The hook may raise `Stop` (for example a failed endpoint numerical check);
    its return value is ignored, so evaluation cannot steer the policy.
    """
    history = []
    stage = policy.next_stage(history)
    if stage is None:
        return ScheduleResult("NO_STAGE", initial, history, 0.0)
    curve, regauge_error = update.regauge(initial, stage.curve_modes)
    status, reason, detail = "COMPLETED_SCHEDULE", None, None
    try:
        while stage is not None:
            if curve.band < stage.curve_modes:
                pad = stage.curve_modes - curve.band
                curve = FourierCurve(np.pad(curve.coefficients, (pad, pad)))
            elif curve.band > stage.curve_modes:
                curve, _ = update.regauge(curve, stage.curve_modes)
            ledger.begin_stage(stage.label, stage.quota)
            result = fit_stage(curve, stage, contrast, update, config, ledger,
                               on_accept=None if on_accept is None else
                               (lambda i, e, s=stage: on_accept(s, i, e)))
            history.append(result)
            curve = result.curve
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                status, reason, detail = "HARD_STOP", result.outcome, result.detail
                break
            if on_stage is not None:
                on_stage(stage, result)
            stage = policy.next_stage(history)
    except Stop as exc:
        status, reason, detail = "HARD_STOP", exc.code, str(exc)
    return ScheduleResult(status, curve, history, regauge_error, reason, detail)


def stage_record(stage):
    """Portable description of a stage without observation arrays."""
    record = {k: v for k, v in asdict(stage).items() if k != "observations"}
    record["wavenumbers"] = [o.wavenumber for o in stage.observations]
    return record
