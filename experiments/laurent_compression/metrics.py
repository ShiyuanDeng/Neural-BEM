"""Errors, residuals, gates and the work ledger for LAU-001.

Gate values are frozen by the plan and are not renegotiated after results.
"""
import numpy as np

from .adapters import lift, relative

GATES = dict(receiver=1e-6, data_derivative=1e-3, data_derivative_target=1e-4,
             objective_derivative=1e-3, lifted_residual=1e-6, retention=0.30)

CONTROL_GATES = dict(receiver=1e-7, lifted_residual=1e-7, data_derivative=1e-4,
                     oracle_receiver=1e-8, oracle_derivative=1e-5,
                     full_dft_equivalence=1e-10)


def paired(values):
    """The 24 paired source/receiver measurements used throughout the project."""
    return np.diagonal(values, axis1=0, axis2=1).T if values.ndim == 3 else np.diag(values)


def lifted_residual(state, reference, cutoff):
    physical = lift(state, reference['curves'], cutoff)
    return relative(reference['a'] @ physical, reference['b'])


def objective(y, observed, weight=1.0):
    residual = weight * (y - observed)
    return .5 * float(np.vdot(residual, residual).real), residual


def objective_derivative(residual, dy, weight=1.0):
    return float(np.real(np.vdot(residual, weight * dy)))


def cancellation_allowance(reference_residual, reference_dy, weight=1.0):
    """s_v = ||r_ref|| * ||W D_v Y_ref||, for the near-zero-derivative rule."""
    return float(np.linalg.norm(reference_residual) * np.linalg.norm(weight * reference_dy))


def objective_derivative_passes(candidate, reference, scale):
    absolute = abs(candidate - reference)
    allowed = GATES['objective_derivative'] * abs(reference) + 1e-6 * scale
    controlling = 'relative' if GATES['objective_derivative'] * abs(reference) >= 1e-6 * scale \
        else 'cancellation'
    return dict(absolute_error=float(absolute), allowed=float(allowed),
                passes=bool(absolute <= allowed), controlling_term=controlling,
                reference_value=float(reference), candidate_value=float(candidate),
                relative_error=float(absolute / max(abs(reference), 1e-300)))


class Ledger:
    """Hard-ceiling work accounting. Reserve before a batch, never overrun."""

    CEILINGS = dict(assemblies=500, factorizations=1200, rhs_batches=2500,
                    seconds=45 * 60, peak_gib=8.0)

    def __init__(self):
        self.counts = dict(assemblies=0, factorizations=0, rhs_batches=0, rhs_columns=0)
        self.seconds = dict()
        self.stopped = None

    def charge(self, **amounts):
        for key, value in amounts.items():
            self.counts[key] = self.counts.get(key, 0) + value
        for key in ('assemblies', 'factorizations', 'rhs_batches'):
            if self.counts.get(key, 0) > self.CEILINGS[key]:
                self.stopped = f'{key} ceiling exceeded'
                raise RuntimeError(f'LAU-001 budget ceiling: {key} '
                                   f'{self.counts[key]} > {self.CEILINGS[key]}')

    def can_afford(self, **amounts):
        return all(self.counts.get(k, 0) + v <= self.CEILINGS[k] for k, v in amounts.items())

    def time(self, stage, value):
        self.seconds[stage] = self.seconds.get(stage, 0.) + value

    def report(self, elapsed):
        peak = 0.0
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 2)
        except Exception:
            pass
        return dict(counts=dict(self.counts), seconds=dict(self.seconds),
                    numerical_wall_seconds=elapsed, ceilings=dict(self.CEILINGS),
                    peak_rss_gib=peak, stopped=self.stopped)
