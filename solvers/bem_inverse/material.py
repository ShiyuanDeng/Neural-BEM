"""Optional research variant: recover the contrast together with the boundary.

Off by default. When a ``MaterialUnknown`` is passed to ``runner.fit`` (and from
there to ``fit_stage``), the update vector gains one last entry, the change of
log(contrast). Its Jacobian column is a one-sided finite difference: one extra
forward solve per active frequency at contrast * exp(derivative_step), charged
to the ledger as ordinary solves. The damping metric gains the matching
Marquardt entry, and each proposed log step is clipped to +-log_step_bound.
Stages named in ``held_stages`` run as known-contrast stages at the current
contrast (MR-001 R4 holds it in the damped warm-up).
Known-contrast fits never construct this object, so their numbers are unchanged.
"""
from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class MaterialUnknown:
    log_step_bound: float = .25
    derivative_step: float = 1e-6
    held_stages: tuple = ()  # stage labels that keep the entry contrast fixed

    def __post_init__(self):
        if not (np.isfinite(self.log_step_bound) and self.log_step_bound > 0):
            raise ValueError('log_step_bound must be positive')
        if not (np.isfinite(self.derivative_step) and 0 < self.derivative_step < 1e-2):
            raise ValueError('derivative_step must be in (0, 1e-2)')

    def settings(self):
        return dict(name='log_contrast_finite_difference', **{k: list(v) if isinstance(v, tuple) else v
                                                            for k, v in asdict(self).items()})

    def bound(self, log_step):
        return float(np.clip(log_step, -self.log_step_bound, self.log_step_bound))
