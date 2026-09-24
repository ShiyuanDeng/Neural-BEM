"""Policy-controlled continuation; no truth, fixtures or legacy inverse imports."""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .forward import BudgetExceeded, Work, solve, shape_jacobian, timed
from .geometry import FourierCurve, integer, normal_basis, reparameterize
from .inverse import FitConfig, FitResult, prepare_state, fit_prepared
from .schedule import Stage


@dataclass(frozen=True)
class Decision:
    stage: Stage
    config: FitConfig = field(default_factory=FitConfig)
    reason: str = ""


@dataclass(frozen=True)
class Qualification:
    passed: bool
    diagnostics: dict = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionRecord:
    index: int
    decision: Decision
    result: FitResult
    committed: bool
    qualification: Optional[Qualification]
    work_before: dict
    work_after: dict


@dataclass(frozen=True)
class PolicyContext:
    shape: FourierCurve  # Last committed curve, including after a rejected decision.
    history: tuple  # All DecisionRecords, without dense physics caches.
    available_wavenumbers: tuple
    work: dict


@dataclass(frozen=True)
class ContinuationResult:
    shape: FourierCurve
    stop_reason: str
    history: tuple


@dataclass(frozen=True)
class FixedSchedule:
    """Minimal policy example. max_iterations=1 gives one update per decision."""
    stages: tuple
    config: FitConfig = field(default_factory=FitConfig)

    def __call__(self, context):
        index = len(context.history)
        return (Decision(self.stages[index], self.config, "fixed schedule")
                if index < len(self.stages) else None)


@dataclass(frozen=True)
class ResolutionGate:
    """Require convergence of both fields and the full normal Jacobian at N/2N.

    Reuses the candidate's N-node factorization, adds one 2N solve and two
    Jacobians, and charges all checks to the same explicit work budget.
    """
    tolerance: float = 1e-6

    def __post_init__(self):
        if not np.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("Resolution tolerance must be positive.")

    def __call__(self, state, work):
        stage = state.stage
        fine = solve(state.shape, stage.wavenumber, state.contrast,
                     state.observation.acquisition, 2 * stage.nodes, work=work)
        coarse_j = shape_jacobian(state.forward,
            normal_basis(state.forward.curve, stage.update_modes), work=work)
        fine_j = shape_jacobian(fine,
            normal_basis(fine.curve, stage.update_modes), work=work)
        def relative(first, second):
            return float(np.linalg.norm(first - second)
                         / max(np.linalg.norm(second), np.finfo(float).tiny))
        field_error = relative(state.forward.prediction, fine.prediction)
        jacobian_error = relative(coarse_j, fine_j)
        return Qualification(max(field_error, jacobian_error) <= self.tolerance,
            dict(nodes=stage.nodes, fine_nodes=2 * stage.nodes,
                 field_relative=field_error, jacobian_relative=jacobian_error,
                 tolerance=self.tolerance))


def run_adaptive(initial, observations, contrast, strategy, *, work=None,
                 max_decisions=1000, qualify=None, on_decision=None):
    """Let strategy(context) return the next Decision, or None to stop.

    A decision may repeat, advance or revisit an available frequency, retune
    M/C/K/N and FitConfig, and request one update or a fixed-stage chunk.
    Stored geometry may be zero-padded but cannot be silently truncated.
    Inputs/history are read-only by convention. Policies receive neither
    truth nor held-out data. Only the live state retains dense forward arrays.

    Optional qualify(candidate_state, work) returns Qualification. A failed
    check rolls back the entire decision, retaining the previous curve/cache;
    rejected trajectories and checks remain in history. If checking runs out
    of budget, the unqualified candidate is also rolled back. Without a gate,
    partial progress before budget exhaustion is committed.
    """
    integer(max_decisions, "max_decisions")
    if not np.isfinite(contrast) or contrast <= 0:
        raise ValueError("Contrast must be positive.")
    observations = tuple(observations)
    catalog = {o.wavenumber: o for o in observations}
    if not observations or len(catalog) != len(observations):
        raise ValueError("Provide nonempty observations with unique wavenumbers.")
    work = Work() if work is None else work
    shape, state, history = initial, None, []
    initialized = False
    while True:
        context = PolicyContext(shape, tuple(history), tuple(sorted(catalog)), work.summary())
        decision = strategy(context)
        if decision is None:
            reason = "policy_stop"
            break
        if len(history) >= max_decisions:
            reason = "decision_limit"
            break
        stage = decision.stage
        if stage.wavenumber not in catalog:
            raise ValueError("Strategy selected a wavenumber without an observation.")
        if stage.curve_modes < shape.band:
            raise ValueError("Strategy may not discard stored geometry modes.")
        before = work.summary()
        if not initialized:
            with timed(work, "initial_geometry"):
                shape, _ = reparameterize(shape, stage.curve_modes,
                                         tolerance=decision.config.projection_tolerance)
            initialized = True
        check = None
        committed = False
        try:
            prepared = prepare_state(shape, catalog[stage.wavenumber], stage, contrast,
                                     cached=state, work=work)
        except BudgetExceeded:
            report = FitResult(shape, stage, "budget_exhausted", float("nan"), states=[shape])
            exhausted = True
        else:
            candidate, report = fit_prepared(prepared, config=decision.config, work=work)
            exhausted = report.stop_reason == "budget_exhausted"
            if qualify is not None:
                if exhausted:
                    check = Qualification(False, dict(status="budget_exhausted_before_qualification"))
                else:
                    try:
                        check = qualify(candidate, work)
                    except BudgetExceeded:
                        exhausted = True
                        check = Qualification(False, dict(status="budget_exhausted_during_qualification"))
            committed = check is None or check.passed
            if committed:
                shape, state = candidate.shape, candidate
        record = DecisionRecord(len(history), decision, report, committed,
                                check, before, work.summary())
        history.append(record)
        if on_decision is not None:
            on_decision(record)
        if exhausted:
            reason = "budget_exhausted"
            break
    return ContinuationResult(shape, reason, tuple(history))
