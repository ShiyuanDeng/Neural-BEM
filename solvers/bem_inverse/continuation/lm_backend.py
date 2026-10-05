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
from dataclasses import dataclass, field, asdict, replace
from copy import deepcopy
import hashlib
import pickle
from threading import RLock
from time import perf_counter
from typing import Optional

import numpy as np
from ordered_boundary.validation_cache import fit_geometry_validation

from .forward import ordered_calls, solve, shape_jacobian
from .geometry import FourierCurve, grid_size, integer
from .geometry_runtime import geometry_validated
from .updates import UpdateRefused
from .globalization import damping_floor, accepted_damping, shortened_stagnation

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


class GeometryProposalCap(Stop):
    code = 'GEOMETRY_PROPOSAL_CAP'


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
    # ON-001 opt-in; sampled reach is a proxy, never an admissibility certificate.
    reach_fraction: float = 0.0
    resolution_gate: str = "absolute"
    # CI-SPD feedback is opt-in until recovery retention is measured.
    damping_floor_relative: float = 1e-6
    geometry_proposal_cap: int = 2000
    progress_window: int = 5
    minimum_relative_progress: float = .01
    avoid_terminal_linearization: bool = False

    def __post_init__(self):
        if self.resolution_gate not in ("absolute", "decision"):
            raise ValueError("resolution_gate must be 'absolute' or 'decision'")
        if not 0 <= self.reach_fraction <= 1:
            raise ValueError("reach_fraction must lie in [0, 1]")
        if self.damping_rule not in ("schedule", "hanke", "agreement"):
            raise ValueError(f"Unknown damping rule {self.damping_rule!r}.")
        if self.metric not in ("marquardt", "mass", "curvature"):
            raise ValueError(f"Unknown step metric {self.metric!r}.")
        if not 0 < self.hanke_ratio < 1 or not self.detectability_factor > 0:
            raise ValueError("hanke_ratio must lie in (0, 1) and detectability_factor must be positive.")
        if not np.isfinite(self.damping_floor_relative) or not 0 < self.damping_floor_relative < 1:
            raise ValueError('Damping floor must be a finite relative curvature in (0,1).')
        integer(self.geometry_proposal_cap, 'geometry_proposal_cap')
        integer(self.progress_window, 'progress_window')
        if not np.isfinite(self.minimum_relative_progress) or not 0 <= self.minimum_relative_progress < 1:
            raise ValueError('Minimum progress must lie in [0,1).')

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

    def __init__(self, cap=8012, seconds=7200.0, clock=perf_counter, endpoint_reserve=12,
                 strict_dispatch=False):
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
        self.strict_dispatch = strict_dispatch
        self._lock = RLock()

    @contextmanager
    def calls(self, calls_for, function, items, kind, category):
        """Opt-in accounting at dispatch; default retains historical SPD receipts."""
        items = tuple(items)
        if not self.strict_dispatch:
            with calls_for(function, items) as calls:
                def consume(call):
                    self.reserve(1)
                    self.charge(kind, category)
                    return call()
                yield [lambda call=call: consume(call) for call in calls]
            return
        self.reserve(len(items))  # complete batch, before a pool starts any work
        def dispatched(item):
            with self._lock:
                self.reserve(1)
                self.charge(kind, category)
            try:
                return function(item)
            except Exception:
                with self._lock:
                    self.fail(category)
                raise
        with calls_for(dispatched, items) as calls:
            yield calls

    def begin_stage(self, label, quota):
        if self.clock() - self.started >= self.seconds:
            raise TrialWallLimit("hard wall limit at stage boundary")
        if self.units >= self.cap:
            raise TrialSolveCap("hard work cap at stage boundary")
        self.stage, self.stage_start, self.stage_quota = label, self.units, quota

    @classmethod
    def restore(cls, snapshot, *, seconds, endpoint_reserve=12, strict_dispatch=False):
        """Restore consumed fitting work/time without granting a new stage quota."""
        ledger = cls(cap=snapshot['cap'], seconds=seconds, endpoint_reserve=endpoint_reserve,
                     strict_dispatch=strict_dispatch)
        ledger.units = snapshot['work_units']
        ledger.stage = snapshot['stage']
        ledger.stage_start = ledger.units-snapshot['stage_units']
        ledger.stage_quota = snapshot['stage_quota']
        ledger.solves = dict(snapshot['solves'])
        ledger.reciprocal = dict(snapshot['reciprocal_batches'])
        ledger.failed = dict(snapshot['failed'])
        ledger.started -= snapshot['seconds']
        return ledger

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


def resolution_check(base, candidate, refined_base, refined_candidate, stage, config):
    """Gain decision and field qualification, retaining the pre-gate decision."""
    states = (base, candidate, refined_base, refined_candidate)
    if any(s is None for s in states):
        raise NumericalFailure("production or refined evaluation failed")
    if any(not np.isfinite(s.loss) or not np.isfinite(s.prediction).all() for s in states):
        raise NumericalFailure("non-finite production or refined evaluation")
    discrepancy = relative_columns(candidate.prediction, refined_candidate.prediction)
    if not np.isfinite(discrepancy).all():
        raise NumericalFailure("non-finite prediction discrepancy")
    row = dict(acceptance(*(s.loss for s in states), config),
               prediction_discrepancy=discrepancy.tolist(),
               refined_base_loss=refined_base.loss, refined_candidate_loss=refined_candidate.loss,
               gate=config.resolution_gate,
               prediction_discrepancy_ratios=(discrepancy/np.asarray(stage.discrepancy_tolerances)).tolist())
    accurate = bool(np.all(discrepancy <= stage.discrepancy_tolerances))
    if not accurate:
        row['numerical_obstruction'] = True
        if config.resolution_gate == 'absolute':
            row['accepted'] = False
    return row, accurate


def inside_box(curve, box):
    if box is None:
        return True
    z = curve.values(grid_size(curve.band))
    (x0, y0), (x1, y1) = box
    return bool(np.all(z.real > x0) and np.all(z.real < x1) and np.all(z.imag > y0) and np.all(z.imag < y1))


class Objective:
    """Stage objective at production and refined nodes; refined values cached."""

    def __init__(self, stage, contrast, config, ledger, *, physics=None):
        self.stage, self.contrast, self.config, self.ledger = stage, float(contrast), config, ledger
        self.physics = physics
        self.observed = np.column_stack([o.scattered.reshape(-1) for o in stage.observations])
        self.refined_cache = {}
        self.count = len(stage.observations)
        self.failures = []

    @geometry_validated
    def _predict(self, curve, nodes, category, keep):
        self.ledger.reserve(self.count)
        forwards, columns = [], []

        def predict(observation):
            try:
                state = (solve(curve, observation.wavenumber, self.contrast, observation.acquisition, nodes)
                         if self.physics is None else
                         self.physics.evaluate(curve, observation, self.contrast, nodes))
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as exc:
                failure = dict(exception_type=type(exc).__name__, message=str(exc),
                    category=category, resolution=nodes,
                    frequency_hz=getattr(observation, 'frequency_hz', None),
                    wavenumber=dict(real=float(complex(observation.wavenumber).real),
                                    imag=float(complex(observation.wavenumber).imag)),
                    candidate_sha256=hashlib.sha256(curve.coefficients.tobytes()).hexdigest(),
                    candidate_coefficients=dict(real=curve.coefficients.real.tolist(),
                                                imag=curve.coefficients.imag.tolist()))
                with self.ledger._lock:
                    self.failures.append(failure)
                raise
            return state if keep else state.prediction  # release discarded systems early

        calls_for = ordered_calls if self.physics is None else self.physics.ordered_calls
        with self.ledger.calls(calls_for, predict, self.stage.observations, "solve", category) as calls:
            for call in calls:
                try:
                    value = call()
                except (ValueError, FloatingPointError, np.linalg.LinAlgError):
                    if not self.ledger.strict_dispatch:
                        self.ledger.fail(category)
                    return None
                columns.append(np.asarray(value.prediction if keep else value).reshape(-1))
                if keep:
                    forwards.append(value)
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

    @geometry_validated
    def jacobian(self, evaluation, update, space):
        """Residual Jacobian (rows as `normalize`) with respect to update coordinates."""
        blocks = []
        derivative_for = (lambda forward: shape_jacobian(forward, update.velocities(space, forward.curve))
                          if self.physics is None else self.physics.derivative(forward, update, space))
        calls_for = ordered_calls if self.physics is None else self.physics.ordered_calls
        with self.ledger.calls(calls_for, derivative_for, evaluation.forwards,
                               "reciprocal", "derivative") as calls:
            for call in calls:
                block = call()
                blocks.append(block.reshape(-1, block.shape[-1]))
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
    checkpoint: object = field(default=None, repr=False)
    resolution_events: list = field(default_factory=list)
    final_nodes: Optional[int] = None
    final_refined_nodes: Optional[int] = None
    physics_failures: list = field(default_factory=list)
    geometry_proposals: int = 0


@dataclass
class StageCheckpoint:
    """Accepted-state restart, retaining the exact linearization and next damping.

    No LU factors are needed until the next accepted candidate. Cached refined
    values are part of the state so pause/resume does not add solves or reset
    quotas. The caller must restore the matching ledger before resuming.
    """
    signature: str
    stage: FitStage
    current: Evaluation
    matrix: np.ndarray
    gradient: np.ndarray
    iteration: int
    damping: float
    initial_loss: float
    scale: float
    work: dict
    history: list
    trials: list
    checks: list
    refined_cache: dict


def checkpoint_signature(stage, contrast, config, update):
    # Hashing pickle bytes does not deserialize or execute any external input.
    return hashlib.sha256(pickle.dumps((stage, float(contrast), config, update.settings()),
                                      protocol=5)).hexdigest()


@dataclass(frozen=True)
class ResolutionResponse:
    """One opt-in promotion followed by ordinary backtracking at the upper pair.

    The caller supplies the same physics service at the finer execution profile
    (RB-001 uses one frequency worker). This mechanism is for ordinary losses.
    """
    production_nodes: int = 1024
    refined_nodes: int = 2048
    physics: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.production_nodes <= 0 or self.refined_nodes <= self.production_nodes:
            raise ValueError('Resolution response must refine strictly')


class _PromoteBase(Exception):
    pass


@fit_geometry_validation
@geometry_validated
def fit_stage(curve, stage, contrast, update, config, ledger, *, on_accept=None, physics=None,
              objective_factory=None, resume=None, pause_after=None, resolution_response=None):
    """Run one stage, optionally under a fit-local ``geometry_validation`` cache.

    Exact reuse and spatial intersection checks are enabled by default. Use
    ``SC_GEOMETRY_RUNTIME=reference`` for pre-integration execution, or
    ``geometry_validation('cache', on_fit=...)`` to collect cache diagnostics. The
    generic cache callback's ``num_nodes`` is unset for this stage interface;
    resolutions remain available in the caller's FitStage record.
    """
    started = perf_counter()
    if curve.band != stage.curve_modes:
        raise ValueError("Pass the curve at the stage storage band.")
    if resolution_response is not None:
        if objective_factory not in (None, Objective) or getattr(stage, 'relaxed_tau', None) is not None:
            raise ValueError('Resolution response is qualified only for the ordinary objective')
        if stage.nodes > resolution_response.production_nodes or stage.refined_nodes > resolution_response.refined_nodes:
            raise ValueError('Starting resolution exceeds the response ceiling')
        ledger.strict_dispatch = True
    signature = checkpoint_signature(stage, contrast, config, update) if resume is not None or pause_after is not None else None
    if resume is not None:
        if resume.signature != signature or not np.array_equal(curve.coefficients, resume.current.curve.coefficients):
            raise ValueError('Resume state does not match the stage, objective, update or curve')
        for key in ('work_units', 'stage', 'stage_units', 'stage_quota', 'cap', 'solves', 'reciprocal_batches', 'failed'):
            if ledger.snapshot()[key] != resume.work[key]:
                raise ValueError('Resume ledger mismatch: '+key)
    objective = (objective_factory or Objective)(stage, contrast, config, ledger, physics=physics)
    if hasattr(objective, "model_residual") and (resume is not None or pause_after is not None):
        raise ValueError("Working-frequency checkpointing requires separately qualified W2 state")
    m = objective.count
    history, trials, checks = [], [], []
    accepted_steps, converged, stop_reason, outcome, detail = 0, False, "maximum_iterations", NORMAL_RETURN, None
    current = None
    initial_loss = float("nan")
    checkpoint = None
    resolution_events = []
    promotion_objective = None
    reach_cache = {}
    resume_iteration = 0
    geometry_proposals = 0

    def admissible(candidate_curve):
        return inside_box(candidate_curve, config.domain_box)

    def checked_pair(base, candidate, rb, rc, active_stage, *, check_base=False):
        row, accurate = resolution_check(base, candidate, rb, rc, active_stage, config)
        discrepancy = np.asarray(row['prediction_discrepancy'])
        checks.append(row)
        tolerances = np.asarray(active_stage.discrepancy_tolerances)
        base_accurate = True
        if check_base:
            bd = relative_columns(base.prediction, rb.prediction)
            base_accurate = bool(np.all(np.isfinite(bd)) and np.all(bd <= tolerances))
            row.update(base_prediction_discrepancy=bd.tolist(), base_qualified=base_accurate,
                       candidate_qualified=accurate, nodes=active_stage.nodes,
                       refined_nodes=active_stage.refined_nodes,
                       threshold_distance=(tolerances-discrepancy).tolist())
        if (not accurate and config.resolution_gate == 'absolute') or not base_accurate:
            row.update(accepted=False, numerical_obstruction=True)
        return row, base_accurate, accurate

    def finer_objective():
        nonlocal promotion_objective
        if promotion_objective is None:
            finer = replace(stage, nodes=resolution_response.production_nodes,
                            refined_nodes=resolution_response.refined_nodes)
            promotion_objective = Objective(finer, contrast, config, ledger,
                                            physics=resolution_response.physics or physics)
        return promotion_objective

    def promote(fine):
        nonlocal stage, objective, physics
        stage, objective, physics = fine.stage, fine, fine.physics
        resolution_events.append(dict(action='promoted', nodes=stage.nodes, refined_nodes=stage.refined_nodes,
                                      work=ledger.snapshot()))

    def validate(base, candidate):
        ledger.reserve(2 * m)
        rb, rc = objective.refined(base.curve), objective.refined(candidate.curve)
        row, base_ok, candidate_ok = checked_pair(base, candidate, rb, rc, stage,
                                                  check_base=resolution_response is not None)
        if resolution_response is None:
            if not candidate_ok and config.resolution_gate == 'absolute':
                raise NumericalFailure("candidate leaves the frozen numerical-resolution regime")
            return candidate if row['accepted'] else None
        if base_ok and candidate_ok:
            return candidate if row['accepted'] else None
        if stage.nodes == resolution_response.production_nodes:
            if not base_ok:
                raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
            resolution_events.append(dict(action='reject_inaccurate_candidate', check=deepcopy(row),
                                          work=ledger.snapshot()))
            return None
        fine = finer_objective()
        ledger.reserve(2*m)
        rrb, rrc = fine.refined(base.curve), fine.refined(candidate.curve)
        finer_row, fine_base_ok, fine_candidate_ok = checked_pair(rb, rc, rrb, rrc, fine.stage, check_base=True)
        resolution_events.append(dict(action='refinement_attempt', check=deepcopy(finer_row),
                                      work=ledger.snapshot()))
        if not fine_base_ok:
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        if finer_row['accepted'] and fine_candidate_ok:
            # Rebuild the factorized production evaluation at the promoted N.
            # Its refined counterpart remains in the fine objective's cache.
            rebuilt = fine.production(candidate.curve, 'promotion_candidate')
            if rebuilt is None:
                raise NumericalFailure('promoted candidate factorization failed')
            repeat, _, _ = checked_pair(rb, rebuilt, rrb, rrc, fine.stage, check_base=True)
            if not repeat['accepted']:
                raise NumericalFailure('promoted candidate changed during factorization rebuild')
            promote(fine)
            return rebuilt
        if not base_ok:
            promote(fine)
            raise _PromoteBase()
        return None

    def qualified_base(evaluation):
        """No retry may start from an unresolved retained state."""
        refined = objective.refined(evaluation.curve)
        if refined is None:
            raise NumericalFailure('retained base refinement failed')
        discrepancy = relative_columns(evaluation.prediction, refined.prediction)
        if np.all(np.isfinite(discrepancy)) and np.all(discrepancy <= stage.discrepancy_tolerances):
            return evaluation, False
        if stage.nodes == resolution_response.production_nodes:
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        fine = finer_objective()
        finer = fine.refined(evaluation.curve)
        if finer is None:
            raise NumericalFailure('retained base finer solve failed')
        discrepancy = relative_columns(refined.prediction, finer.prediction)
        if not np.all(np.isfinite(discrepancy)) or np.any(discrepancy > stage.discrepancy_tolerances):
            raise NumericalFailure('unresolved accepted base at maximum permitted resolution')
        rebuilt = fine.production(evaluation.curve, 'promotion_base')
        if rebuilt is None:
            raise NumericalFailure('promoted base factorization failed')
        promote(fine)
        return rebuilt, True

    def gradient_frame(evaluation):
        space = update.prepare(evaluation.curve, stage.update_modes, stage.curve_modes)
        ledger.reserve(4 * m)  # Jacobian plus one production/refined step opportunity
        matrix = objective.jacobian(evaluation, update, space)
        model_residual = (objective.model_residual(evaluation) if hasattr(objective, 'model_residual')
                          else evaluation.residual)
        gradient = (objective.gradient(evaluation, update, space, matrix)
                    if hasattr(objective, 'gradient') else matrix.T @ model_residual)
        if gradient.shape != (matrix.shape[1],) or not np.isfinite(gradient).all():
            raise FloatingPointError('Invalid objective gradient')
        return space, matrix, gradient

    def record(iteration, evaluation, gradient, step, damping, next_damping, trial=None):
        row = dict(iteration=iteration, loss=evaluation.loss, relative_l2=evaluation.relative_l2,
                   gradient_inf=None if gradient is None else float(np.linalg.norm(gradient, ord=np.inf)),
                   step_norm_m=float(np.linalg.norm(step)), damping=float(damping),
                   next_damping=float(next_damping), step_m=np.asarray(step, float).tolist(),
                   coefficients=dict(real=evaluation.curve.coefficients.real.tolist(),
                                     imag=evaluation.curve.coefficients.imag.tolist()),
                   work=ledger.snapshot())
        if hasattr(objective, "indices"):
            row.update(active_frequencies=objective.indices,
                       maximum_full_residual=float(objective.relative_residuals(evaluation).max()),
                       working_events=deepcopy(objective.events))
        if trial is not None:
            row.update({k: trial[k] for k in ("maximum_normal_m", "rms_normal_m", "projection_relative",
                                               "speed_ratio", "accepted_fraction", "gain_ratio",
                                               "damping_feedback", "damping_floor") if k in trial})
        if gradient is None:
            row['terminal_linearization_skipped'] = True
        if resolution_response is not None:
            row.update(nodes=stage.nodes, refined_nodes=stage.refined_nodes)
        history.append(row)

    def capture():
        nonlocal checkpoint
        if resume is None and pause_after is None:
            return
        checkpoint = StageCheckpoint(checkpoint_signature(stage, contrast, config, update), stage,
            replace(current, forwards=()), matrix.copy(), gradient.copy(), accepted_steps, damping,
            initial_loss, scale, deepcopy(ledger.snapshot()), deepcopy(history), deepcopy(trials),
            deepcopy(checks), dict(objective.refined_cache))

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
        if resume is None:
            current = objective.production(curve, "initial_objective")
            if current is None:
                raise NumericalFailure("initial state is not solver-ready")
            initial_loss = current.loss
            if on_accept is not None:
                on_accept(0, current)
            if resolution_response is not None:
                current, _ = qualified_base(current)
            space, matrix, gradient = gradient_frame(current)
            damping = config.initial_damping
            record(0, current, gradient, np.zeros(matrix.shape[1]), damping, damping)
        else:
            current, matrix, gradient = resume.current, resume.matrix.copy(), resume.gradient.copy()
            history, trials, checks = deepcopy((resume.history, resume.trials, resume.checks))
            geometry_proposals = sum(t.get('geometry_constructed', True) for t in trials)
            accepted_steps, resume_iteration = resume.iteration, resume.iteration
            damping, initial_loss, scale = resume.damping, resume.initial_loss, resume.scale
            objective.refined_cache = dict(resume.refined_cache)
            space = update.prepare(current.curve, stage.update_modes, stage.curve_modes)
            if resolution_response is not None:
                current, changed = qualified_base(current)
                if changed:
                    space, matrix, gradient = gradient_frame(current)
        capture()
        if current.loss <= config.loss_tolerance:
            converged, stop_reason = True, "loss_tolerance"
        elif np.linalg.norm(gradient, ord=np.inf) <= config.gradient_tolerance:
            converged, stop_reason = True, "gradient_tolerance"
        iteration = resume_iteration
        while iteration < stage.iterations:
            if converged:
                break
            if pause_after is not None and accepted_steps >= pause_after:
                outcome, stop_reason = 'PAUSED', 'accepted_state_pause'
                break
            iteration += 1
            normal = matrix.T @ matrix
            damped = damping_matrix(space, normal)
            accepted = None
            trial_damping = damping
            rule = None
            restart = False
            accuracy_limited = False
            seen_steps = set()
            floor = damping_floor(normal, damped, config.damping_floor_relative) if config.damping_rule == 'agreement' else 0.
            if floor:
                trial_damping = max(trial_damping, floor)
            if config.damping_rule == "hanke":
                trial_damping, attainable = hanke_damping(matrix, current.residual, damped, config.hanke_ratio)
                rule = dict(hanke_lambda=float(trial_damping), hanke_attainable=bool(attainable))
            for _ in range(config.max_damping_trials):
                try:
                    proposed = np.linalg.solve(normal + trial_damping * damped, -gradient)
                except np.linalg.LinAlgError:
                    trial_damping *= config.damping_increase
                    continue
                raw_norm = float(np.linalg.norm(proposed))
                proposed = control_step(proposed, space, update, config)
                clipping = {}
                if config.reach_fraction:
                    from bem_inverse.reach import clip_direction
                    proposed, clipping = clip_direction(proposed, space.curve, update.length_unit_m,
                                                        config.reach_fraction, reach_cache)
                for backtrack in range(config.max_backtracks + 1):
                    if config.damping_rule == 'agreement':
                        ledger.reserve(0)  # deadline/work check before geometry, even after pure refusals
                        if geometry_proposals >= config.geometry_proposal_cap:
                            raise GeometryProposalCap('stage geometry proposal cap reached')
                    step = 0.5 ** backtrack * proposed
                    if np.linalg.norm(step) / scale <= config.relative_step_tolerance:
                        continue
                    trial = dict(iteration=iteration, damping=float(trial_damping), backtrack=backtrack,
                                 step_norm_m=float(np.linalg.norm(step)), **clipping)
                    feedback = config.damping_rule == 'agreement'
                    if feedback:
                        fraction = float(np.linalg.norm(step)/max(raw_norm, np.finfo(float).tiny))
                        trial.update(accepted_fraction=fraction, damping_floor=floor,
                                     clipping_fraction=float(np.linalg.norm(proposed)/max(raw_norm, np.finfo(float).tiny)))
                    if config.log_model or feedback:
                        trial["step_m"] = step.tolist()
                    if config.log_model or feedback:
                        trial.update(predicted_decrease=float(-(gradient @ step) - 0.5 * step @ normal @ step),
                                     **(rule or {}))
                    if resolution_response is not None:
                        trial.update(proposal_nodes=stage.nodes, proposal_refined_nodes=stage.refined_nodes)
                    trials.append(trial)
                    if feedback:
                        key = np.ascontiguousarray(step).tobytes()
                        if key in seen_steps:
                            trial.update(status='refused', reason='repeated_clipped_proposal', geometry_constructed=False)
                            continue
                        seen_steps.add(key)
                    geometry_proposals += 1
                    trial['geometry_constructed'] = True
                    geometry_started = perf_counter()
                    try:
                        candidate_curve, geometry = update.trial(space, step)
                        trial.update(geometry)
                        if 'a_used' in geometry:
                            step = np.asarray(geometry['a_used'], float)
                            trial['step_m'] = step.tolist()
                            trial['step_norm_m'] = float(np.linalg.norm(step))
                            if feedback:
                                trial['accepted_fraction'] = float(np.linalg.norm(step)/max(raw_norm, np.finfo(float).tiny))
                            if config.log_model or feedback:
                                trial['predicted_decrease'] = float(-gradient@step-.5*step@normal@step)
                    except UpdateRefused as exc:
                        trial.update(getattr(update, "last_trial", {}))
                        trial.update(status="refused", reason=exc.reason, detail=exc.detail)
                        if config.log_model:
                            trial["geometry_seconds"] = perf_counter()-geometry_started
                        continue
                    if config.log_model:
                        trial["geometry_seconds"] = perf_counter()-geometry_started
                    if not admissible(candidate_curve):
                        trial.update(status="refused", reason="outside_domain")
                        continue
                    if hasattr(objective, 'candidate'):
                        from bem_inverse.working_frequency import WorkingSetChanged
                        try:
                            candidate = objective.candidate(current, candidate_curve)
                        except WorkingSetChanged:
                            trial.update(status='working_model_rebuild', **objective.last_trial)
                            space, matrix, gradient = gradient_frame(current)
                            restart = True
                            break
                        trial.update(objective.last_trial)
                    else:
                        candidate = objective.production(candidate_curve, "candidate")
                    if candidate is None:
                        trial.update(status='physics_failed', reason='production_evaluation_failed',
                                     physics_failures=deepcopy(getattr(objective, 'failures', [])))
                        raise NumericalFailure("production evaluation failed at candidate state")
                    if not np.isfinite(candidate.loss) or not np.isfinite(candidate.prediction).all():
                        raise NumericalFailure("non-finite production evaluation at candidate state")
                    trial.update(loss=candidate.loss)
                    if candidate.loss >= current.loss:
                        trial["status"] = "nondecreasing"
                        continue
                    before_checks = len(checks)
                    try:
                        qualified = validate(current, candidate)
                    except _PromoteBase:
                        trial.update(status='base_promotion_retry', nodes=stage.nodes)
                        current = objective.production(current.curve, 'promotion_base')
                        if current is None:
                            raise NumericalFailure('promoted base factorization failed')
                        space, matrix, gradient = gradient_frame(current)
                        restart = True
                        break
                    if qualified is None:
                        inaccurate = any(c.get('numerical_obstruction', False) for c in checks[before_checks:])
                        accuracy_limited |= inaccurate
                        trial["status"] = "numerical_rejection" if inaccurate else "acceptance_margin"
                        if hasattr(objective, 'reject'):
                            from bem_inverse.working_frequency import WorkingSetChanged
                            try:
                                objective.reject(current, candidate)
                            except WorkingSetChanged:
                                trial.update(status='working_model_rebuild', **objective.last_trial)
                                space, matrix, gradient = gradient_frame(current)
                                restart = True
                                break
                        continue
                    candidate = qualified
                    if resolution_response is not None:
                        trial.update(original_production_loss=trial['loss'], loss=candidate.loss,
                                     nodes=stage.nodes, refined_nodes=stage.refined_nodes)
                    if config.log_model or feedback:
                        trial["actual_decrease"] = current.loss-candidate.loss
                        pred = trial["predicted_decrease"]
                        trial["gain_ratio"] = trial["actual_decrease"]/pred if pred > 0 else None
                    trial["status"] = "accepted"
                    accepted = (candidate, step, trial_damping, trial)
                    break
                if accepted is not None or restart:
                    break
                trial_damping *= config.damping_increase
            if restart:
                iteration -= 1  # same iteration, original quota and damping
                continue
            if accepted is None:
                stop_reason = "accuracy_limited_trials_exhausted" if accuracy_limited else "no_decreasing_step"
                if accuracy_limited:
                    outcome = 'ACCURACY_LIMITED_TRIALS'
                break
            current, step, used_damping, trial = accepted
            accepted_steps = iteration
            if config.damping_rule == 'agreement':
                damping, trial['damping_feedback'] = accepted_damping(used_damping, floor,
                    trial['accepted_fraction'], trial['gain_ratio'], config)
            else:
                damping = max(used_damping * config.damping_decrease, np.finfo(float).tiny)
            if on_accept is not None:
                on_accept(iteration, current)
            terminal = current.loss <= config.loss_tolerance or iteration >= stage.iterations
            if (config.avoid_terminal_linearization and terminal and pause_after is None and
                    resume is None and resolution_response is None):
                # on_accept has already observed the current evaluation; no callback
                # receives a tangent. Checkpoint/resolution-response paths retain it.
                record(iteration, current, None, step, used_damping, damping, trial)
                if current.loss <= config.loss_tolerance:
                    converged, stop_reason = True, 'loss_tolerance'
                break
            space, matrix, gradient = gradient_frame(current)
            record(iteration, current, gradient, step, used_damping, damping, trial)
            capture()
            if (config.damping_rule == 'agreement' and not current.loss <= config.loss_tolerance and
                    shortened_stagnation(history, config.progress_window, config.minimum_relative_progress)):
                stop_reason = 'shortened_step_stagnation'
                break
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
    if resolution_response is not None and trials and 'status' not in trials[-1]:
        trials[-1].update(status=outcome, reason=detail)
    final = curve if current is None else current.curve
    return StageResult(stage.label, final, outcome, stop_reason, converged, accepted_steps, initial_loss,
                       float("nan") if current is None else current.loss, history, trials, checks,
                       detail, ledger.snapshot(), perf_counter() - started, checkpoint,
                       resolution_events, stage.nodes, stage.refined_nodes,
                       deepcopy(getattr(objective, 'failures', [])), geometry_proposals)


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
