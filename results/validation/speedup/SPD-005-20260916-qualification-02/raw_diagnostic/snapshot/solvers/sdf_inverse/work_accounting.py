"""Scoped, passive work accounting for topology experiments.

An evaluation is an uncached objective call (including an invalid boundary).
A forward evaluation is a completed paired BIE prediction across all frequencies.
TD solves are recorded separately. Counters never affect numerical decisions.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


COUNTERS = ('evaluation_count', 'forward_evaluation_count',
            'forward_frequency_solve_count', 'td_evaluation_count',
            'td_frequency_solve_count', 'analytic_base_frequency_solve_count',
            'factorization_count', 'derivative_assembly_count', 'tangent_solve_count',
            'analytic_primal_rhs_count', 'reciprocal_frequency_solve_count',
            'reciprocal_rhs_count', 'reciprocal_contraction_count')
_active = ContextVar('topology_work_accounting', default=None)
_stage = ContextVar('topology_work_stage', default='unscoped')
_analytic_observer = ContextVar('analytic_work_observer', default=None)


@contextmanager
def observe_analytic_work(observer):
    """Let a budget owner reserve and charge analytic work without patching solvers."""
    token = _analytic_observer.set(observer)
    try:
        yield
    finally:
        _analytic_observer.reset(token)


@contextmanager
def analytic_work(kind, angular_frequency):
    observer = _analytic_observer.get()
    if observer is not None:
        observer('attempt', kind, angular_frequency, None)
    try:
        yield
    except BaseException as error:
        if observer is not None:
            observer('failed', kind, angular_frequency, error)
        raise
    else:
        if observer is not None:
            observer('completed', kind, angular_frequency, None)


@dataclass
class WorkLedger:
    stages: dict = field(default_factory=dict)

    def snapshot(self):
        stages = {key: dict(value) for key, value in self.stages.items()}
        totals = {key: sum(row.get(key, 0) for row in stages.values()) for key in COUNTERS}
        totals['bie_frequency_solve_count'] = (totals['forward_frequency_solve_count']
                                              + totals['td_frequency_solve_count']
                                              + totals['analytic_base_frequency_solve_count'])
        return dict(totals=totals, stages=stages)


def record_work(**counts):
    ledger = _active.get()
    if ledger is not None:
        row = ledger.stages.setdefault(_stage.get(), {})
        for key, value in counts.items():
            if key not in COUNTERS:
                raise ValueError(f'Unknown work counter: {key}')
            row[key] = row.get(key, 0) + value


@contextmanager
def collect_work():
    ledger = WorkLedger()
    token = _active.set(ledger)
    try:
        yield ledger
    finally:
        _active.reset(token)


def current_work():
    ledger = _active.get()
    return (WorkLedger() if ledger is None else ledger).snapshot()


def work_delta(after, before):
    return dict(
        totals={key: value - before['totals'].get(key, 0)
                for key, value in after['totals'].items()},
        stages={stage: {key: value - before['stages'].get(stage, {}).get(key, 0)
                        for key, value in row.items()}
                for stage, row in after['stages'].items()})


def accounted_call(stage, function, *args, **kwargs):
    token = _stage.set(stage)
    try:
        return function(*args, **kwargs)
    finally:
        _stage.reset(token)
