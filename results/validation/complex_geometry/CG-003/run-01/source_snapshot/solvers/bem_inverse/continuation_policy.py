"""Opt-in four-phase continuation with a circle-preserving initialization."""
from dataclasses import dataclass, replace

from .policy import CumulativePolicy


@dataclass(frozen=True)
class ShapeFrequencyPolicy(CumulativePolicy):
    """Keep the frequency ladder, then grow both normal and storage bands.

    Stage-local similarity changes only the initial fitting subspace. The
    runner retains its selected ordinary geometry update for numerical audits.
    Full release means the configured validated ceiling, with all gates active.
    """
    name: str = 'shape_frequency_continuation'
    version: str = '0.1.0'
    shape_bands: tuple = (11, 15, 19, 25)
    full_release_band: int = 95
    shape_quota: int = 1500

    def operations(self, problem, physics):
        if self.release_storage != 'fixed':
            raise ValueError('The four added shape stages set their own storage; release_storage does not apply.')
        prior = super().operations(problem, physics)
        warmup = next(op for op in prior if op.label == 'warmup_025_damped')
        initialization = replace(warmup, label='initialize_translation_scale',
            purpose='Fit centre and size at the lowest damped frequency, preserving circular shape',
            stage=replace(warmup.stage, label='initialize_translation_scale', update_modes=0),
            fit_geometry_update='similarity',
            details=dict(warmup.details, coordinates=['translation_x_m', 'translation_y_m', 'radius_change_m'],
                         normal_shape_modes=False, geometry_update='exact translation and uniform scaling'))
        prefix = [op for op in prior if op.label.startswith('stage_')]
        endpoint = prefix[-1].stage
        if len(self.shape_bands) != 4:
            raise ValueError('Exactly four additional shape bands are required.')
        bands = (endpoint.update_modes, *self.shape_bands, self.full_release_band)
        if any(isinstance(m, bool) or not isinstance(m, int) or m < 1 for m in bands):
            raise ValueError('Shape bands must be positive integers.')
        if any(b <= a for a, b in zip(bands, bands[1:])):
            raise ValueError('Shape bands must increase strictly from the frequency-ladder endpoint.')
        storages = (endpoint.curve_modes, *(2*m+2 for m in self.shape_bands), self.storage_band)
        if any(b <= a for a, b in zip(storages, storages[1:])) or self.storage_band < self.full_release_band:
            raise ValueError('Storage bands must grow strictly and contain the full update band.')
        shapes = [self._fit(problem, physics, f'shape_{i}_M{m}', problem.real, m, 2*m+2,
            self.shape_quota, purpose='Additional shape release at the complete real-frequency catalog')
            for i, m in enumerate(self.shape_bands, 1)]
        final = self._fit(problem, physics, f'full_release_M{self.full_release_band}', problem.real,
            self.full_release_band, self.storage_band, self.shape_quota,
            purpose='Release the full configured validated shape bandwidth')
        return (prior[0], prior[1], initialization, *prefix, *shapes, final, prior[-1])

    def plan(self, problem, physics):
        plan = super().plan(problem, physics)
        plan['changes_from_DF'] = [
            'circle-preserving lowest-frequency translation/scale initialization',
            'unchanged damped frequency ladder and explicit real return',
            'four increasing full-catalog shape/storage stages then full configured release',
            'ordinary selected geometry update retained for all independent audits']
        return plan
