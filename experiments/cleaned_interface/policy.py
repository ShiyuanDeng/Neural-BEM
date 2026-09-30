"""The executable, versioned CI-001 policy. Plan and decisions share this source.

v1 carries MA-005 DF's noiseless path, SC-044 whitening/discrepancy stopping,
and recurrent cleanup for declared noisy observations. The noise rules are a
shared algorithm change relative to DF and need the all-36 retention run.
"""
from dataclasses import dataclass, asdict, replace
import numpy as np

from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, stage_record


@dataclass(frozen=True)
class LocalizationRule:
    frequencies: int = 3
    center_min_m: float = .28
    center_max_m: float = .72
    center_step_m: float = .004
    radius_min_m: float = .015
    radius_max_m: float = .075
    radius_step_m: float = .001
    batch_centers: int = 800
    max_ranked: int = 5000
    max_starts: int = 5
    distinct_center_m: float = .008
    distinct_radius_m: float = .004
    refinement_steps_m: tuple = (.004, .004, .001)
    refinement_iterations: int = 12
    qualification_tolerance: float = 1e-7
    cutoff_padding: int = 30


@dataclass(frozen=True)
class Operation:
    kind: str
    label: str
    purpose: str
    entry: str
    transition: str
    stage: object = None
    optimizer: object = None
    cleanup_band: object = None
    details: object = None

    def record(self):
        row = dict(operation=self.kind, label=self.label, purpose=self.purpose,
                   entry=self.entry, transition=self.transition, details=self.details)
        if self.stage is not None:
            stage = stage_record(self.stage)
            stage.update(M=self.stage.update_modes, K_geometry=self.stage.curve_modes,
                         frequencies_hz=[o.frequency_hz for o in self.stage.observations],
                         damping=[complex(o.wavenumber).imag / complex(o.wavenumber).real
                                  for o in self.stage.observations])
            row.update(stage=stage, optimizer=asdict(self.optimizer), cleanup_band=self.cleanup_band,
                       geometry_update='z + P_K[A(z+h*n)-A(z)], derivative of the complete trial',
                       cleanup='crop coefficients then pad; no arclength refit' if self.cleanup_band else 'none')
        return row


@dataclass(frozen=True)
class CumulativePolicy:
    name: str = 'cumulative_sc_ma'
    version: str = '1.0.0'
    fit_units: int = 13412
    fit_seconds: float = 1800.
    audit_seconds: float = 300.
    gamma: float = .25
    prefix_frequencies_hz: tuple = (.5e9, .75e9, 1e9, 1.25e9)
    prefix_quotas: tuple = (1000, 1250, 1750, 4000)
    release_bands: tuple = (11, 15, 19)
    fixed_bands: tuple = (25, 31, 37)
    storage_band: int = 192
    cleanup_band: int = 64
    frontier_threshold: float = .01
    frontier_step: int = 6
    frontier_top: int = 95
    noise_factor: float = 1.1
    localization: LocalizationRule = LocalizationRule()

    def _config(self, problem, observations):
        config = BackendConfig(domain_box=problem.domain_box)
        count = len(observations)
        weights = tuple(np.ones(count)/count)
        expected = 0.
        if all(o.sigma_real_imag > 0 for o in observations):
            raw = np.asarray([(np.linalg.norm(o.scattered)/o.sigma_real_imag)**2 for o in observations])
            weights = tuple(raw/raw.sum())
            expected = sum(o.scattered.size for o in observations)/raw.sum()
            config = replace(config, loss_tolerance=max(config.loss_tolerance, self.noise_factor**2*expected))
        return config, weights, expected

    def _fit(self, problem, physics, label, observations, band, storage, quota, iterations=22,
             purpose='Release shape detail', cleanup=None):
        config, weights, expected = self._config(problem, observations)
        profile = physics.resolution_profile(storage)
        stage = FitStage(label, tuple(observations), weights,
            tuple(1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in observations),
            band, storage, profile['production'], profile['refined'], iterations, quota)
        return Operation('fit', label, purpose, 'previous operation completed or exhausted its stage quota',
            'advance on normal/quota return; any hard/numerical failure goes to final audit; '
            'full real catalog at declared noise discrepancy goes directly to final audit',
            stage, config, cleanup, dict(accuracy_profile=profile, expected_noise_loss=expected,
                noise_threshold=config.loss_tolerance if expected else None,
                weight_rule='(norm(data)/sigma)^2 normalized' if expected else 'equal frequency weights',
                stopping=['loss tolerance', 'gradient infinity norm', 'relative step', 'iteration cap',
                          'stage quota', 'global work/time cap', 'numerical refusal']))

    def operations(self, problem, physics):
        required = (.25e9, *self.prefix_frequencies_hz)
        for catalog in (problem.real, problem.damped):
            if not all(any(o.frequency_hz == f for o in catalog) for f in required):
                raise ValueError(f'{self.name} requires frequencies {required}')
        real = {o.frequency_hz: o for o in problem.real}
        damped = {o.frequency_hz: o for o in problem.damped}
        operations = [Operation('audit', 'initial_audit', 'Qualify the prescribed original start',
            'before localization', 'localize if qualified; otherwise final failure',
            details=dict(scope='all real frequencies, complete-trial Jacobian/FD', seconds=self.audit_seconds))]
        operations.append(Operation('localize', 'damped_localization',
            'Find a data-supported circle using low-frequency damped data',
            'original-start audit passed', 'warm-up at first qualified refined circle; failure goes to final audit',
            details=dict(asdict(self.localization), gamma=self.gamma,
                objective='0.5*mean((norm(pred-data)/norm(data))^2); equal frequency weights',
                cutoff='ceil(max(abs(k))*sqrt(max(contrast,1))*max(radius/length_unit)+30)',
                refinement='best of six coordinate neighbors; halve steps if none improves',
                qualification='selected backend, production/refined circle predictions; first qualified start',
                bounds_m=problem.bounds_m)))
        operations.append(self._fit(problem, physics, 'warmup_025_damped', (damped[.25e9],), 1, 4, 600, 44,
                                    'Warm up localized circle at 0.25 GHz'))
        for number, quota in enumerate(self.prefix_quotas, 1):
            obs = tuple(damped[f] for f in self.prefix_frequencies_hz[:number])
            band = int(np.floor(3*max(complex(o.wavenumber).real for o in obs)))
            operations.append(self._fit(problem, physics, f'stage_{number}_damped', obs, band, 2*band+2,
                quota, purpose='Damped frequency prefix; M=floor(3*max(real(k_exterior))), K_geometry=2*M+2'))
        last = operations[-1].stage
        operations.append(self._fit(problem, physics, 'stage_4_undamped',
            tuple(real[f] for f in self.prefix_frequencies_hz), last.update_modes, last.curve_modes,
            self.prefix_quotas[-1], purpose='Return explicitly to the measured real-frequency objective'))
        noisy = all(o.sigma_real_imag > 0 for o in problem.real)
        for band in self.release_bands + self.fixed_bands:
            release = band in self.release_bands
            clean = self.cleanup_band if noisy or band == self.fixed_bands[0] else None
            operations.append(self._fit(problem, physics, f'{"release" if release else "fixed"}_M{band}',
                problem.real, band, self.storage_band, 1500 if release else 304,
                cleanup=clean, purpose='Full real catalog with '+('recurrent noise cleanup' if noisy else
                    'one-time state cleanup' if clean else 'shape-band release')))
        operations.append(Operation('frontier', 'observable_frontier',
            'Measure the paired-Jacobian frontier at the current curve and highest real frequency',
            'fixed schedule completed and real-catalog noise discrepancy not reached',
            'append fixed stages up to frontier; otherwise final audit', details=dict(
                formula='max(p: paired_column_norm[p] >= threshold*max(paired_column_norm))',
                threshold=self.frontier_threshold, top=self.frontier_top, step=self.frontier_step,
                first=self.fixed_bands[-1]+self.frontier_step, K_geometry=self.storage_band,
                quota=304, iterations=22, work_units=2,
                noise_rule='stop releases/tail once full real-catalog loss <= 1.1^2*expected noise loss',
                possible_bands=list(range(self.fixed_bands[-1]+self.frontier_step,
                                          self.frontier_top+1, self.frontier_step)))))
        operations.append(Operation('audit', 'final_audit', 'Qualify the returned endpoint independently',
            'every exit, including a hard stop or refusal', 'return unscored curve and diagnostics',
            details=dict(scope='all real frequencies; last actual M; field/column Jacobian/complete-trial FD',
                         field_tolerances='1e-5 at <=0.5 GHz; 1e-7 otherwise',
                         jacobian_tolerance=1e-3, fd_tolerance=1e-3, fd_step_m=1e-7,
                         fd_seed=42001, seconds=self.audit_seconds, backend='selected solver')))
        return self._explicit_cleanup(operations)

    def _explicit_cleanup(self, operations):
        out = []
        for op in operations:
            if op.cleanup_band is not None:
                out.append(Operation('cleanup', op.label+'_cleanup',
                    'Remove stored high Cartesian harmonics before this release',
                    'enter '+op.label, 'fit '+op.label,
                    details=dict(retained_band=op.cleanup_band, storage_band=op.stage.curve_modes,
                                 construction='centered coefficient crop, then zero-pad; no refit')))
            out.append(op)
        return tuple(out)

    def tail(self, problem, physics, frontier):
        bands, band = [], self.fixed_bands[-1]
        while band < frontier and band+self.frontier_step <= self.frontier_top:
            band += self.frontier_step
            bands.append(band)
        noisy = all(o.sigma_real_imag > 0 for o in problem.real)
        return self._explicit_cleanup(tuple(self._fit(problem, physics, f'fixed_M{m}', problem.real, m, self.storage_band, 304,
            cleanup=self.cleanup_band if noisy else None,
            purpose='Adaptive release: measured frontier exceeds previous update band') for m in bands))

    def at_noise_discrepancy(self, operation, loss, problem):
        threshold = (operation.details or {}).get('noise_threshold')
        full_real = (operation.stage is not None and
                     len(operation.stage.observations) == len(problem.real) and
                     all(a is b for a, b in zip(operation.stage.observations, problem.real)))
        return bool(full_real and threshold is not None and np.isfinite(loss) and loss <= threshold)

    def plan(self, problem, physics):
        return dict(policy=self.name, version=self.version, fit_units=self.fit_units, fit_seconds=self.fit_seconds,
            definitions=dict(M='normal shape update band', K_geometry='Cartesian geometry storage band',
                             K_trace='backend-internal physics trace cutoff, never M or K_geometry',
                             resolution='backend-owned nodal/coefficient workspace profile'),
            changes_from_DF=['declared-noise whitening and discrepancy stop for every stage',
                             'recurrent cleanup before full-catalog releases when noise is declared'],
            operations=[op.record() for op in self.operations(problem, physics)])


def readable_plan(plan):
    """Render the executable operation records; no separately maintained stage text."""
    lines=[f'# {plan["policy"]} v{plan["version"]}', '',
           f'Fitting budget: {plan["fit_units"]} SPD work units, {plan["fit_seconds"]:g} seconds including localization.',
           'Independent initial and final audits have separate budgets.', '',
           'M controls the normal update. K_geometry stores the Cartesian curve. '
           'K_trace and assembly workspace belong to the selected physics service.', '']
    for index,op in enumerate(plan['operations'],1):
        lines += [f'## {index}. {op["label"]} ({op["operation"]})', '',op['purpose'],
                  '',f'Entry: {op["entry"]}.',f'Next: {op["transition"]}.']
        if 'stage' in op:
            s=op['stage']
            lines += [f'Frequencies (GHz): {", ".join(f"{f/1e9:g}" for f in s["frequencies_hz"])}.',
                f'Wavenumbers: {s["wavenumbers"]}; damping Im(k)/Re(k): {s["damping"]}.',
                f'Weights: {s["weights"]}.',
                f'M={s["M"]}; K_geometry={s["K_geometry"]}; resolution profile: {op["details"]["accuracy_profile"]}.',
                f'Field agreement tolerances: {s["discrepancy_tolerances"]}.',
                f'Budget: {s["iterations"]} iterations, {s["quota"]} work units.',
                f'Update: {op["geometry_update"]}. Cleanup: {op["cleanup"]}.',
                f'Stopping: {op["details"]["stopping"]}.',
                f'Optimizer settings: {op["optimizer"]}.']
        else:
            lines.append(f'Controls and decision rules: {op["details"]}.')
        lines.append('')
    return '\n'.join(lines)+'\n'
