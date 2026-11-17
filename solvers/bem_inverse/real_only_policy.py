"""The real-only schedule used for baseline generation on 17 November 2026.

It refuses a ``Problem`` that carries a damped catalog, so no stage can read one.
There is no localization and no warm-up: the first fit stage starts from the
prescribed curve. Frequencies, shape bands, storage bands and work quotas are
those of ``CumulativePolicy``, with real observations in place of damped ones
and without its "return to real data" stage, which would repeat the last
ladder stage.

| ``frequency_schedule`` | Stages |
|---|---|
| ``continuation`` (default) | ladder 0.5, +0.75, +1.0, +1.25 GHz; then the whole catalog at bands 11..37; then the measured tail |
| ``simultaneous`` | no ladder: the whole catalog at bands 11..37 from the start; then the measured tail |
| ``single`` | a one-frequency catalog: one ladder stage, then the frontier is measured there and bands 11, 15, ... are released while the last band is below it |

``fixed_band`` holds the shape band at one value in every stage and drops the
frontier and tail. Stage count, frequencies, quotas and iteration caps stay the
same, so only the band differs from the adaptive schedule.
"""
from dataclasses import dataclass

import numpy as np

from .policy import CumulativePolicy, Operation

SCHEDULES = ('continuation', 'simultaneous', 'single')


@dataclass(frozen=True)
class RealOnlyPolicy(CumulativePolicy):
    name: str = 'real_only'
    version: str = '1.0.0'
    frequency_schedule: str = 'continuation'
    fixed_band: object = None

    def __post_init__(self):
        super().__post_init__()
        if self.frequency_schedule not in SCHEDULES:
            raise ValueError(f'frequency_schedule must be one of {SCHEDULES}')
        band = self.fixed_band
        if band is not None and (isinstance(band, bool) or not isinstance(band, int) or band < 1):
            raise ValueError('fixed_band must be a positive integer or None')
        if band is not None and self.frequency_schedule == 'single':
            raise ValueError('The single-frequency schedule grows its band from the measured frontier.')

    # Shape bands released on the whole catalog, in order, and their work quotas.
    def _release_sequence(self):
        tail = range(self.fixed_bands[-1]+self.frontier_step, self.frontier_top+1, self.frontier_step)
        return (*self.release_bands, *self.fixed_bands, *tail)

    def _quota(self, band):
        return 1500 if band in self.release_bands else 304

    def _ladder_band(self, observations):
        return self.fixed_band or int(np.floor(3*max(complex(o.wavenumber).real for o in observations)))

    def _release(self, problem, physics, index, band, noisy, purpose):
        used = self.fixed_band or band
        # Cleanup follows the schedule position, so a fixed band keeps the same cleanups.
        clean = self.cleanup_band if noisy or band == self.fixed_bands[0] else None
        return self._fit(problem, physics, f'full_{index}_M{used}', problem.real, used,
                         self.release_storage_band(used), self._quota(band), cleanup=clean, purpose=purpose)

    def _frontier(self, first, possible):
        return Operation('frontier', 'observable_frontier',
            'Measure the paired-Jacobian frontier at the current curve and highest real frequency',
            'scheduled stages completed and real-catalog noise discrepancy not reached',
            'append stages up to frontier; otherwise the fit returns', details=dict(
                formula='max(p: paired_column_norm[p] >= threshold*max(paired_column_norm))',
                threshold=self.frontier_threshold, top=self.frontier_top, step=self.frontier_step, first=first,
                K_geometry=self.storage_band if self.release_storage == 'fixed' else '2M+2',
                iterations=22, work_units=2,
                noise_rule='stop releases/tail once full real-catalog loss <= 1.1^2*expected noise loss',
                possible_bands=list(possible)))

    def operations(self, problem, physics):
        if problem.damped is not None:
            raise ValueError(f'{self.name} takes a real-only problem; pass damped=None.')
        real = {o.frequency_hz: o for o in problem.real}
        noisy = all(o.sigma_real_imag > 0 for o in problem.real)
        operations = []
        if self.frequency_schedule == 'single':
            if len(problem.real) != 1:
                raise ValueError('The single-frequency schedule takes a one-frequency real catalog.')
            band = self._ladder_band(problem.real)
            operations.append(self._fit(problem, physics, 'ladder_1_real', problem.real, band, 2*band+2,
                self.prefix_quotas[0], purpose='Single real frequency; M=floor(3*real(k_exterior)), K_geometry=2*M+2'))
            possible = [m for m in self._release_sequence() if m > band]
            operations.append(self._frontier(possible[0] if possible else None, possible))
            return self._explicit_cleanup(operations)
        if self.frequency_schedule == 'continuation':
            if not all(f in real for f in self.prefix_frequencies_hz):
                raise ValueError(f'{self.name} requires real frequencies {self.prefix_frequencies_hz}')
            for number, quota in enumerate(self.prefix_quotas, 1):
                obs = tuple(real[f] for f in self.prefix_frequencies_hz[:number])
                band = self._ladder_band(obs)
                operations.append(self._fit(problem, physics, f'ladder_{number}_real', obs, band, 2*band+2, quota,
                    purpose='Real frequency prefix; '+('M fixed' if self.fixed_band else
                            'M=floor(3*max(real(k_exterior)))')+', K_geometry=2*M+2'))
        for index, band in enumerate(self.release_bands+self.fixed_bands, 1):
            operations.append(self._release(problem, physics, index, band, noisy,
                'Full real catalog with '+('recurrent noise cleanup' if noisy else
                    'one-time state cleanup' if band == self.fixed_bands[0] else 'shape-band release')))
        if self.fixed_band is None:
            first = self.fixed_bands[-1]+self.frontier_step
            operations.append(self._frontier(first, range(first, self.frontier_top+1, self.frontier_step)))
        return self._explicit_cleanup(operations)

    def tail(self, problem, physics, frontier):
        noisy = all(o.sigma_real_imag > 0 for o in problem.real)
        single = self.frequency_schedule == 'single'
        band = self._ladder_band(problem.real) if single else self.fixed_bands[-1]
        index = 1 if single else len(self.release_bands+self.fixed_bands)+1
        stages = []
        for candidate in (m for m in self._release_sequence() if m > band):
            if band >= frontier:
                break
            stages.append(self._release(problem, physics, index, candidate, noisy,
                'Adaptive release: measured frontier exceeds previous update band'))
            band, index = candidate, index+1
        return self._explicit_cleanup(tuple(stages))

    def plan(self, problem, physics):
        plan = super().plan(problem, physics)
        plan['changes_from_DF'] = [
            'real observations only; a problem with a damped catalog is refused',
            'no localization and no 0.25 GHz warm-up; the first stage starts from the prescribed curve',
            f'frequency schedule: {self.frequency_schedule}; fixed shape band: {self.fixed_band}',
            'declared-noise whitening, discrepancy stop and recurrent cleanup as in CumulativePolicy']
        return plan
