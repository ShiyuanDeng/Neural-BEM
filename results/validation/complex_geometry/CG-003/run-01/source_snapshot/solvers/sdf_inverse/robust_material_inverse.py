"""Training-only continuation and bounded restart selection for the K2 inverse.

This is an opt-in orchestration layer, not a new geometry or forward solver.
It keeps the D material/shape bounds, exact E derivatives and immutable data.
Low-frequency scores may screen starts but never select the delivered result:
every eligible candidate is scored on the same original full-band objective.
Forward and analytic-direction attempt caps include failed and ranking work.
Neither geometry truth nor held-out data is accepted by this API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
from time import perf_counter

import numpy as np

from gpr_bem_kress.shape_derivative import linearize_kress_forward
from .forward import PairedForwardProblem
from .material_inverse import (
    MaterialCurveEvaluator, PHYSICAL_LOWER, PHYSICAL_UPPER, PARAMETER_SCALES,
    PARAMETER_ORIGIN, candidate_state, fit_material_curve, scaled_direction,
    scaled_parameters,
)


def _readonly(value, *, dtype=float):
    array = np.array(value, dtype=dtype, copy=True)
    if not np.all(np.isfinite(array)):
        raise ValueError("Expected finite numeric data.")
    array.setflags(write=False)
    return array


def _digest(array):
    values = np.asarray(array)
    return hashlib.sha256(str((values.shape, values.dtype.str)).encode()+values.tobytes()).hexdigest()


@dataclass(frozen=True)
class RobustMaterialConfig:
    policy: str = "multistart"
    nodes: int = 64
    stage_max_evaluations: tuple[int, int] = (40, 40)
    maximum_forward_solves: int = 400
    maximum_direction_evaluations: int = 2400
    screening_keep: int = 2
    stationarity_tolerance: float = 1e-7
    near_bound_scaled_tolerance: float = 1e-6

    def __post_init__(self):
        if self.policy not in ("full_band", "continuation", "multistart"):
            raise ValueError("policy must be full_band, continuation or multistart.")
        for name in ("nodes", "maximum_forward_solves", "maximum_direction_evaluations", "screening_keep"):
            value = getattr(self, name)
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                raise ValueError(f"{name} must be an integer.")
            if value < (1 if name == "screening_keep" else 0):
                raise ValueError(f"{name} is outside its supported range.")
        if self.nodes < 16 or self.nodes % 2:
            raise ValueError("nodes must be even and at least sixteen.")
        budgets = tuple(self.stage_max_evaluations)
        if len(budgets) != 2 or any(isinstance(value, (bool, np.bool_)) or
                not isinstance(value, (int, np.integer)) or value < 1 for value in budgets):
            raise ValueError("stage_max_evaluations requires two positive integers.")
        object.__setattr__(self, "stage_max_evaluations", budgets)
        for name in ("stationarity_tolerance", "near_bound_scaled_tolerance"):
            if not np.isfinite(getattr(self, name)) or getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive and finite.")


def cumulative_frequency_indices(problem):
    """Low-to-high prefixes; the final objective retains original column order."""
    if not isinstance(problem, PairedForwardProblem):
        raise TypeError("Expected PairedForwardProblem.")
    frequencies = problem.angular_frequencies
    if np.unique(frequencies).size != frequencies.size:
        raise ValueError("Continuation requires distinct frequency columns.")
    ordered = tuple(int(index) for index in np.argsort(frequencies, kind="stable"))
    return tuple(ordered[:count] for count in range(1, len(ordered))) + (tuple(range(len(ordered))),)


def subset_problem(problem, indices):
    if not isinstance(problem, PairedForwardProblem):
        raise TypeError("Expected PairedForwardProblem.")
    indices = tuple(indices)
    if not indices or any(isinstance(index, (bool, np.bool_)) or
            not isinstance(index, (int, np.integer)) or not 0 <= index < problem.num_frequencies
            for index in indices) or len(set(indices)) != len(indices):
        raise ValueError("indices must be nonempty distinct valid frequency integers.")
    positions = list(indices)
    return replace(problem, angular_frequencies=problem.angular_frequencies[positions],
                   source_strengths=problem.source_strengths[positions])


def make_restart_candidates(initial_physical, *, joint_shape):
    """Bound-derived material quartiles, optionally also a box-midpoint circle.

    No exact target, observed field or held-out quantity determines these
    seeds. With fixed shape all five geometry entries are copied unchanged.
    """
    if not isinstance(joint_shape, (bool, np.bool_)):
        raise ValueError("joint_shape must be boolean.")
    candidate_state(scaled_parameters(initial_physical))
    initial = np.asarray(initial_physical, dtype=float)
    epsilon = PHYSICAL_LOWER[5] + np.array([.25, .75])*(PHYSICAL_UPPER[5]-PHYSICAL_LOWER[5])
    candidates = [initial.copy()]
    for value in epsilon:
        candidate = initial.copy()
        candidate[5] = value
        candidates.append(candidate)
    if joint_shape:
        for value in epsilon:
            candidate = .5*(PHYSICAL_LOWER+PHYSICAL_UPPER)
            candidate[5] = value
            candidates.append(candidate)
    unique = []
    for candidate in candidates:
        if not any(np.array_equal(candidate, previous) for previous in unique):
            candidate_state(scaled_parameters(candidate))
            unique.append(_readonly(candidate))
    return tuple(unique)


class BudgetExhausted(RuntimeError):
    pass


class _Budget:
    def __init__(self, config):
        self.config = config
        self.exhausted = False
        self.work = dict(forward_solves=0, analytic_direction_evaluations=0,
                         candidate_builds=0, cache_hits=0, invalid_candidate_probes=0,
                         failed_forward_solves=0, failed_direction_evaluations=0,
                         forward_seconds=0., jacobian_seconds=0.)

    def require(self, *, forwards=0, directions=0):
        if (self.work["forward_solves"]+forwards > self.config.maximum_forward_solves or
                self.work["analytic_direction_evaluations"]+directions > self.config.maximum_direction_evaluations):
            self.exhausted = True
            raise BudgetExhausted("The global forward/directional-attempt budget is exhausted.")


class _BudgetedEvaluator(MaterialCurveEvaluator):
    def __init__(self, problem, observed, *, budget, nodes=64, on_evaluation=None, frequency_scales=None):
        super().__init__(problem, observed, nodes=nodes)
        if frequency_scales is not None:
            scales = _readonly(frequency_scales)
            if scales.shape != (problem.num_frequencies,) or np.any(scales <= 0):
                raise ValueError("Frozen stage scales must be positive and match frequency columns.")
            self.frequency_scales = scales
            self.normalization_hash = hashlib.sha256(scales.tobytes()).hexdigest()
        self._frozen_observation_identity = _digest(self.observed)
        self._frozen_normalization_identity = _digest(self.frequency_scales)
        self.budget = budget
        self.on_evaluation = on_evaluation
        self.best = None
        self.work["failed_direction_evaluations"] = 0
        self._accounted = {key: 0 for key in self.work}

    def _assert_frozen(self):
        super()._assert_frozen()
        if (_digest(self.observed) != self._frozen_observation_identity or
                _digest(self.frequency_scales) != self._frozen_normalization_identity):
            raise RuntimeError("Immutable observation/normalization shape or dtype changed.")

    def _sync(self):
        for key, value in self.work.items():
            self.budget.work[key] = self.budget.work.get(key, 0) + value-self._accounted[key]
            self._accounted[key] = value

    def pin_audited_candidate(self, candidate):
        """Reuse an already-paid immutable primal for the final Jacobian audit."""
        self._assert_frozen()
        key = hashlib.sha256((self.scene_hash+self.observation_hash+self.normalization_hash).encode()
                             +candidate.scaled.tobytes()).hexdigest()
        if candidate.cache_key != key:
            raise ValueError("The audited candidate belongs to another experiment identity.")
        if self._cached is None or self._cached.cache_key != candidate.cache_key:
            self._jacobian_cache = {}
        self._cached = candidate

    def evaluate(self, scaled):
        self._assert_frozen()
        # Validate before budget/cache checks; an invalid probe cannot masquerade
        # as a valid cached candidate or a scientific budget failure.
        try:
            candidate_state(scaled)
        except (TypeError, ValueError):
            self.work["invalid_candidate_probes"] += 1
            self._sync()
            raise
        # Match the base cache's float64 byte identity, including signed zero.
        # Numeric equality alone could skip this guard but miss the base cache.
        cached = (self._cached is not None and
                  self._cached.scaled.tobytes() == np.asarray(scaled, dtype=np.float64).tobytes())
        if not cached:
            self.budget.require(forwards=self.problem.num_frequencies)
        try:
            result = super().evaluate(scaled)
        finally:
            self._sync()
        with np.errstate(over="ignore", invalid="ignore"):
            loss = float(.5*np.dot(result.residual, result.residual))
        if not np.isfinite(loss):
            # Finite residual entries do not guarantee a representable squared
            # norm. The base evaluator has already logged this paid primal;
            # retain its failure honestly without an ineligible inf incumbent
            # or a non-JSON scalar in the stage history.
            reason = "The weighted training objective is non-finite."
            if self.history and self.history[-1]["cache_key"] == result.cache_key:
                self.history[-1].update(loss=None, failure_reason=reason)
            self._cached = None
            self._jacobian_cache = {}
            raise FloatingPointError(reason)
        if self.best is None or loss < .5*np.dot(self.best.residual, self.best.residual):
            self.best = result
        if self.on_evaluation is not None:
            self.on_evaluation(result, self)
        return result

    def jacobian(self, scaled, *, active_indices=tuple(range(6))):
        active = tuple(active_indices)
        if not active or len(set(active)) != len(active) or any(
                isinstance(index, (bool, np.bool_)) or not isinstance(index, (int, np.integer))
                or not 0 <= index < 6 for index in active):
            raise ValueError("active_indices must be distinct valid parameter integers.")
        base = self.evaluate(scaled)
        missing = [index for index in active if index not in self._jacobian_cache]
        self.budget.require(directions=len(missing)*self.problem.num_frequencies)
        started = perf_counter()
        try:
            for index in missing:
                direction = scaled_direction(base.forward_results[0].system.geometry.parameters, index)
                columns = []
                for forward in base.forward_results:
                    self.work["analytic_direction_evaluations"] += 1
                    try:
                        jvp = linearize_kress_forward(forward, direction)
                    except (FloatingPointError, np.linalg.LinAlgError):
                        self.work["failed_direction_evaluations"] += 1
                        raise
                    columns.append(np.diag(jvp.d_scattered_receiver))
                weighted = np.column_stack(columns)/self.frequency_scales[None, :]
                self._jacobian_cache[index] = _readonly(np.r_[weighted.real.ravel(), weighted.imag.ravel()])
            return np.column_stack([self._jacobian_cache[index] for index in active])
        finally:
            self.work["jacobian_seconds"] += perf_counter()-started
            self._sync()


def _select_screened(screening, *, keep, exterior_epsr):
    """Retain low-score contrast-side representatives, then fill by low score."""
    ranked = sorted((row for row in screening if row["loss"] is not None),
                    key=lambda row: (row["loss"], row["seed_index"]))
    chosen = []
    if keep >= 2:
        for side in (-1, 1):
            available = [row for row in ranked if np.sign(row["physical"][5]-exterior_epsr) == side]
            if available:
                chosen.append(available[0]["seed_index"])
    for row in ranked:
        if len(chosen) >= keep:
            break
        if row["seed_index"] not in chosen:
            chosen.append(row["seed_index"])
    return tuple(chosen)


def solve_robust_material(problem, observed, initial_physical, *, joint_shape=False, config=None):
    """Return best fully scored candidate and a truthful training-only report.

    ``verified_stationarity`` certifies only the declared projected-gradient
    tolerance, not data fit, physical recovery, global identifiability or
    completion of all restart work. Budget/failed branches retain the lowest
    finite fully audited candidate encountered, including valid trial points.
    """
    settings = RobustMaterialConfig() if config is None else config
    if not isinstance(settings, RobustMaterialConfig):
        raise TypeError("Expected RobustMaterialConfig.")
    if not isinstance(joint_shape, (bool, np.bool_)):
        raise ValueError("joint_shape must be boolean.")
    schedule = cumulative_frequency_indices(problem)
    data = _readonly(observed, dtype=np.complex128)
    if data.shape != (problem.num_pairs, problem.num_frequencies):
        raise ValueError("Observed data shape disagrees with the training acquisition.")
    candidate_state(scaled_parameters(initial_physical))
    initial = _readonly(initial_physical)
    data_hash = _digest(data)
    started = perf_counter()
    ledger = _Budget(settings)
    candidate_records, stages, screening, skipped_stages = [], [], [], []
    incumbent, owner = None, None
    scored_keys = set()

    def observe_full(candidate, evaluator):
        nonlocal incumbent, owner
        loss = float(.5*np.dot(candidate.residual, candidate.residual))
        if candidate.cache_key not in scored_keys:
            candidate_records.append(dict(physical=candidate.physical.tolist(), training_loss=loss,
                cache_key=candidate.cache_key, forward_solves_at_score=ledger.work["forward_solves"]))
            scored_keys.add(candidate.cache_key)
        if incumbent is None or loss < .5*np.dot(incumbent.residual, incumbent.residual):
            incumbent, owner = candidate, evaluator

    full = _BudgetedEvaluator(problem, data, budget=ledger, nodes=settings.nodes, on_evaluation=observe_full)
    all_indices = tuple(range(problem.num_frequencies))
    seeds = make_restart_candidates(initial, joint_shape=joint_shape) if settings.policy == "multistart" else (initial,)
    selected_seed_indices = (0,)
    search_completed = True
    initial_failure = None
    try:
        full.evaluate(scaled_parameters(initial))
    except BudgetExhausted as error:
        search_completed, initial_failure = False, str(error)
    except (FloatingPointError, np.linalg.LinAlgError) as error:
        initial_failure = f"{type(error).__name__}: {error}"
        search_completed = False
    initial_audit_work = dict(ledger.work)
    before_screening = dict(ledger.work)

    if settings.policy == "multistart" and not ledger.exhausted:
        low_indices = schedule[0]
        low = _BudgetedEvaluator(subset_problem(problem, low_indices), data[:, list(low_indices)],
            budget=ledger, nodes=settings.nodes,
            frequency_scales=full.frequency_scales[list(low_indices)],
            on_evaluation=observe_full if low_indices == all_indices else None)
        for index, seed in enumerate(seeds):
            row = dict(seed_index=index, physical=seed.tolist(), frequency_indices=list(low_indices),
                       loss=None, failure_reason=None, selected=False)
            try:
                value = low.evaluate(scaled_parameters(seed))
                row["loss"] = float(.5*np.dot(value.residual, value.residual))
            except BudgetExhausted as error:
                row["failure_reason"] = str(error)
                search_completed = False
            except (FloatingPointError, np.linalg.LinAlgError) as error:
                row["failure_reason"] = f"{type(error).__name__}: {error}"
                search_completed = False
            screening.append(row)
            if ledger.exhausted:
                break
        selected_seed_indices = _select_screened(screening, keep=settings.screening_keep,
                                                exterior_epsr=problem.exterior.epsr)
        if not selected_seed_indices:
            search_completed = False
            skipped_stages.append(dict(reason="no_valid_screened_seed", seed_index=None, frequency_indices=None))
        for row in screening:
            row["selected"] = row["seed_index"] in selected_seed_indices
    screening_work = {key: ledger.work[key]-before_screening[key] for key in before_screening}

    active = tuple(range(6)) if joint_shape else (5,)
    run_schedule = (all_indices,) if settings.policy == "full_band" else schedule
    if not ledger.exhausted:
        for seed_index in selected_seed_indices:
            physical = seeds[seed_index]
            for stage_index, indices in enumerate(run_schedule):
                is_full = indices == all_indices
                evaluator = (_BudgetedEvaluator(problem, data, budget=ledger, nodes=settings.nodes,
                              frequency_scales=full.frequency_scales, on_evaluation=observe_full) if is_full else
                    _BudgetedEvaluator(subset_problem(problem, indices), data[:, list(indices)],
                                       budget=ledger, nodes=settings.nodes,
                                       frequency_scales=full.frequency_scales[list(indices)]))
                maximum = (sum(settings.stage_max_evaluations) if settings.policy == "full_band" else
                           settings.stage_max_evaluations[1 if is_full else 0])
                before = dict(ledger.work)
                row = dict(seed_index=seed_index, stage_index=stage_index, frequency_indices=list(indices),
                    is_full_band=is_full, initial_physical=physical.tolist(), max_evaluations=maximum,
                    status="started", fit=None, failure_reason=None)
                try:
                    terminal, fit = fit_material_curve(evaluator, physical, joint_shape=joint_shape,
                                                       max_evaluations=maximum)
                    fit.pop("scaled_weighted_real_jacobian", None)
                    row.update(status="completed", fit=fit, terminal_physical=terminal.physical.tolist())
                except BudgetExhausted as error:
                    row.update(status="budget_exhausted", failure_reason=str(error))
                    search_completed = False
                except (FloatingPointError, np.linalg.LinAlgError) as error:
                    row.update(status="numerical_failure", failure_reason=f"{type(error).__name__}: {error}")
                    search_completed = False
                best = evaluator.best
                if best is not None:
                    physical = best.physical
                    row.update(best_seen_physical=physical.tolist(), best_seen_stage_loss=float(.5*np.dot(best.residual, best.residual)))
                row["work"] = {key: ledger.work[key]-before[key] for key in before}
                row["candidate_history"] = list(evaluator.history)
                stages.append(row)
                if ledger.exhausted:
                    break
                if best is None:
                    search_completed = False
                    for skipped in run_schedule[stage_index+1:]:
                        skipped_stages.append(dict(seed_index=seed_index, frequency_indices=list(skipped),
                                                  reason="no_valid_previous_stage_candidate"))
                    break
            if ledger.exhausted:
                break

    if ledger.exhausted:
        recorded = {(row["seed_index"], tuple(row["frequency_indices"])) for row in stages}
        skipped = {(row["seed_index"], tuple(row["frequency_indices"]))
                   for row in skipped_stages if row["frequency_indices"] is not None}
        for seed_index in selected_seed_indices:
            for indices in run_schedule:
                if (seed_index, indices) not in recorded | skipped:
                    skipped_stages.append(dict(seed_index=seed_index, frequency_indices=list(indices),
                                              reason="global_budget_exhausted"))

    # Never rank a low-only result against a full-band score. This audit uses
    # the stored owner/data identity; all additional work still counts.
    before_selected_audit = dict(ledger.work)
    selected_diagnostics = dict(verified_stationarity=False, stationarity_evaluated=False,
                               failure_reason=None, projected_gradient_inf=None)
    if incumbent is not None:
        audit_candidate = incumbent
        scaled = audit_candidate.scaled.copy()
        lo = (PHYSICAL_LOWER-PARAMETER_ORIGIN)/PARAMETER_SCALES
        hi = (PHYSICAL_UPPER-PARAMETER_ORIGIN)/PARAMETER_SCALES
        selected_diagnostics.update(
            scaled_distance_to_lower=(scaled-lo).tolist(), scaled_distance_to_upper=(hi-scaled).tolist(),
            physical_distance_to_lower=(incumbent.physical-PHYSICAL_LOWER).tolist(),
            physical_distance_to_upper=(PHYSICAL_UPPER-incumbent.physical).tolist(),
            near_lower_bounds=((scaled-lo) <= settings.near_bound_scaled_tolerance).tolist(),
            near_upper_bounds=((hi-scaled) <= settings.near_bound_scaled_tolerance).tolist(),
            near_bound_scaled_tolerance=settings.near_bound_scaled_tolerance)
        try:
            owner.pin_audited_candidate(audit_candidate)
            selected_diagnostics["reused_saved_forward_for_audit"] = True
            jacobian = owner.jacobian(scaled, active_indices=active)
            gradient = jacobian.T @ audit_candidate.residual
            projected = scaled[list(active)]-np.clip(scaled[list(active)]-gradient, lo[list(active)], hi[list(active)])
            norm = float(np.max(np.abs(projected)))
            singular = np.linalg.svd(jacobian, compute_uv=False)
            colnorm = np.linalg.norm(jacobian, axis=0)
            correlations = jacobian.T@jacobian/np.maximum(colnorm[:, None]*colnorm[None, :], 1e-300)
            if not all(np.all(np.isfinite(value)) for value in (gradient, projected, singular, correlations)):
                raise FloatingPointError("Selected-state sensitivity audit is non-finite.")
            selected_diagnostics.update(stationarity_evaluated=True,
                verified_stationarity=norm <= settings.stationarity_tolerance,
                projected_gradient_inf=norm, scaled_gradient=gradient.tolist(),
                scaled_projected_gradient=projected.tolist(), jacobian_singular_values=singular.tolist(),
                jacobian_column_correlations=correlations.tolist(), active_indices=list(active),
                stationarity_tolerance=settings.stationarity_tolerance)
        except BudgetExhausted as error:
            selected_diagnostics["failure_reason"] = str(error)
        except (FloatingPointError, np.linalg.LinAlgError) as error:
            selected_diagnostics["failure_reason"] = f"{type(error).__name__}: {error}"
    selected_audit_work = {key: ledger.work[key]-before_selected_audit[key] for key in before_selected_audit}

    full._assert_frozen()
    if _digest(data) != data_hash:
        raise RuntimeError("Full immutable training data changed.")
    if incumbent is not None and not joint_shape:
        initial_scaled = scaled_parameters(initial)
        roundoff = 8*np.finfo(float).eps*np.maximum(1., np.abs(initial_scaled[:5]))
        if np.any(np.abs(incumbent.scaled[:5]-initial_scaled[:5]) > roundoff):
            raise RuntimeError("A fixed-shape solve changed geometry beyond scaling roundoff.")
    report = dict(configuration=asdict(settings), policy=settings.policy, joint_shape=bool(joint_shape),
        initial_physical=initial.tolist(), initial_sha256=_digest(initial), observation_sha256=data_hash,
        normalization_sha256=full.normalization_hash, scene_sha256=full.scene_hash,
        frequency_normalization=full.frequency_scales.tolist(), schedule=[list(indices) for indices in run_schedule],
        seeds=[seed.tolist() for seed in seeds], selected_seed_indices=list(selected_seed_indices),
        initial_audit_failure=initial_failure, selected_physical=None if incumbent is None else incumbent.physical.tolist(),
        selected_training_loss=None if incumbent is None else float(.5*np.dot(incumbent.residual, incumbent.residual)),
        verified_stationarity=bool(selected_diagnostics["verified_stationarity"]),
        selected_diagnostics=selected_diagnostics, search_completed=bool(search_completed and not ledger.exhausted),
        budget_exhausted=ledger.exhausted, status=("budget_limited" if ledger.exhausted else
                                                "selected" if incumbent is not None else "no_valid_fullband_candidate"),
        screening=screening, stages=stages, skipped_stages=skipped_stages,
        candidates=candidate_records, work=dict(ledger.work),
        phase_work=dict(initial_fullband_audit=initial_audit_work, screening=screening_work,
                        stages={key: sum(row["work"][key] for row in stages) for key in ledger.work},
                        selected_stationarity_audit=selected_audit_work),
        seconds=perf_counter()-started, observations_unchanged=True,
        ranking="minimum common full-band immutable weighted training loss over valid evaluated candidates; no stationarity/heldout/truth preference",
        screening_policy="low-band best per available contrast sign about known exterior, then low-loss remaining slots",
        stationarity_contract="full-band scaled projected gradient; not physical recovery or global optimality")
    return incumbent, report


__all__ = ["RobustMaterialConfig", "BudgetExhausted", "make_restart_candidates",
           "cumulative_frequency_indices", "subset_problem", "solve_robust_material"]
