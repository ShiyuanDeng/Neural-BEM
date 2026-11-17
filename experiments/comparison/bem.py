"""The BEM family: one fit of one case, saved as ``fit.json`` and ``fit.npz``.

This module never opens a truth file. It reads the observations, the start
curve and, only for a known-contrast run, the supplied contrast.

| Tag | What this module does |
|---|---|
| ``default`` / ``nodal`` | ``modal_muller`` / ``nodal_kress`` physics, both with the ``slider`` geometry update |
| ``fixedband<M>`` | ``RealOnlyPolicy(fixed_band=M)`` |
| ``clean`` / ``n<p>d<k>`` | real catalog only: ``Problem(damped=None)`` and ``RealOnlyPolicy`` |
| ``cleandamped`` | real and damped catalogs under the unchanged ``CumulativePolicy``, start kept |
| ``uc`` | ``MaterialUnknown`` from the weak-scatterer start; ``kc`` supplies the contrast |
| ``fc`` / ``fs`` / ``sf<GHz>`` | ``frequency_schedule`` continuation / simultaneous / single |

Unknown-contrast start (MR-001's weak rule): solve the start circle once at
contrast 1 + 1e-3 at the lowest frequency the fit may read, and scale that
response to best fit the data. Real-only runs use the lowest real frequency of
their catalog; the damped run uses the lowest damped frequency, as MR-001 did.

Noisy runs declare the per-frequency noise standard deviation to the fit, which
then whitens the loss and stops at the noise discrepancy (existing policy rules).
"""
from dataclasses import asdict, replace
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.continuation.geometry_runtime import geometry_runtime
from bem_inverse.io import read, curve_from, curve_record
from bem_inverse.material import MaterialUnknown
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.problem import Problem
from bem_inverse.real_only_policy import RealOnlyPolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign as C, scenes as S
from experiments.cleaned_interface import benchmark as ci
from experiments.gaugal_comparison import tg002_data as D

from . import noise as N

GEOMETRY_UPDATE = 'slider'
EXECUTION = Execution('auto', 4)
EPSILON, MINIMUM_START = 1e-3, .05      # MR-001's weak-scatterer start
GRID = 201                              # shared material-field grid, see scoring.py
# Wall limit of one fit, checked between solver batches. It is the TG-002 benchmark
# contract value (bem_inverse.policies.BENCHMARK_CONTRACT); the schedule default is 1800 s.
FIT_SECONDS = 120.


def solver(run):
    return 'nodal_kress' if run.variant == 'nodal' else 'modal_muller'


def policy(run):
    if run.damped:
        return CumulativePolicy(fit_seconds=FIT_SECONDS)
    schedule = ('single' if run.single_frequency_hz is not None else
                'simultaneous' if run.frequency == 'fs' else 'continuation')
    return RealOnlyPolicy(frequency_schedule=schedule, fixed_band=run.fixed_band, fit_seconds=FIT_SECONDS)


def settings(run):
    """Everything that defines the run, for ``run.json``."""
    if run.damped and (run.frequency != 'fc' or run.fixed_band is not None):
        raise ValueError('The damped run keeps the old schedule unchanged.')
    if run.damped and run.noise is not None:
        raise ValueError('Noisy data and damped data never appear together.')
    chosen = policy(run)
    return dict(
        solver=solver(run), geometry_update=GEOMETRY_UPDATE, localization='none',
        start='centred 65 mm circle (TG-002 start.json)',
        policy=dict(type=type(chosen).__name__, **asdict(chosen)),
        material=None if run.contrast == 'kc' else MaterialUnknown().settings(),
        contrast=('supplied (true value)' if run.contrast == 'kc' else
                  f'weak-scatterer start, epsilon {EPSILON}, at the lowest '
                  f'{"damped" if run.damped else "real"} frequency of the fit catalog; floor {MINIMUM_START}'),
        data=dict(real='sealed TG-002 real catalog' if run.noise is None else
                       f'results/_shared/noise/{run.data}/<case>.npz',
                  damped='sealed TG-002 damped catalog' if run.damped else None,
                  single_frequency_hz=run.single_frequency_hz,
                  noise_declared_to_fit=run.noise is not None),
        execution=asdict(EXECUTION), shared_grid=GRID,
        fit_wall_limit_seconds=FIT_SECONDS,
        timing='fit_seconds is the fit ledger wall time on one process; the contrast start solve, '
               'the final residual solve and scoring are timed separately')


def observations(run, row, root):
    """The real catalog this run may read, and the damped one for the damped run only."""
    data = read(ci.ROOT/row['data'])
    if run.noise is not None:
        saved = N.load(*run.noise, row['id'], root)
        data = dict(observed_real=saved['observed'].real, observed_imag=saved['observed'].imag,
                    sigma_real_imag=saved['sigma_real_imag'], frequencies_hz=data['frequencies_hz'])
    real = ci.observations(data, row)
    if run.single_frequency_hz is not None:
        real = tuple(o for o in real if o.frequency_hz == run.single_frequency_hz)
    damped = ci.observations(read(ci.ROOT/row['damped']), row, damped=True) if run.damped else None
    return real, damped


def weak_start(initial, observation, name, execution):
    physics, forward_solve = C._physics(name, execution)
    nodes = physics.resolution_profile(initial.band)['production']
    started = perf_counter()
    state = forward_solve(initial, observation, 1.+EPSILON, nodes)
    seconds = perf_counter()-started
    if hasattr(physics, 'close'):
        physics.close()
    p = np.asarray(state.prediction).reshape(-1)
    d = np.asarray(observation.scattered).reshape(-1)
    susceptibility = EPSILON*float(np.real(np.vdot(p, d))/np.real(np.vdot(p, p)))
    return max(1.+susceptibility, MINIMUM_START), dict(
        rule='weak', epsilon=EPSILON, frequency_hz=observation.frequency_hz, wavenumber=str(observation.wavenumber),
        nodes=nodes, estimated_susceptibility=susceptibility, clipped=1.+susceptibility < MINIMUM_START,
        seconds=seconds)


def final_fields(real, curve, contrast, name, execution):
    """Predicted fields and relative residuals of the returned curve, at the fit's own resolution."""
    physics, forward_solve = C._physics(name, execution)
    nodes = physics.resolution_profile(curve.band)['production']
    started = perf_counter()
    predicted = []
    with geometry_runtime(execution.geometry):
        for observation in real:
            predicted.append(np.asarray(forward_solve(curve, observation, contrast, nodes).prediction).reshape(-1))
    if hasattr(physics, 'close'):
        physics.close()
    predicted = np.array(predicted)
    observed = np.array([np.asarray(o.scattered).reshape(-1) for o in real])
    residual = np.linalg.norm(predicted-observed, axis=1)/np.linalg.norm(observed, axis=1)
    return predicted, residual, dict(seconds=perf_counter()-started, resolution=nodes)


def warm_up(run):
    """One untimed solve so the first fit of a process does not pay device start-up."""
    row = C.row(S.CASES[0])
    real, _ = observations(replace(run, data='clean'), row, None)
    weak_start(curve_from(read(ci.ROOT/row['initial'])), real[0], solver(run), EXECUTION)


def fit_case(run, case, root):
    """Fit one case. Returns (record for fit.json, arrays for fit.npz)."""
    row = C.row(case)
    started = perf_counter()
    record = dict(case=case, scene=row['case'], family=run.family, run=run.name, representation='curve')
    arrays = {}
    try:
        real, damped = observations(run, row, root)
        initial = curve_from(read(ci.ROOT/row['initial']))
        name = solver(run)
        if run.contrast == 'kc':
            contrast, start, material = float(row['contrast']), dict(rule='supplied', seconds=0.), None
        else:
            contrast, start = weak_start(initial, (damped or real)[0], name, EXECUTION)
            material = MaterialUnknown()
        start['start_contrast'] = contrast
        problem = Problem(initial, real, damped, contrast)
        physics, forward_solve = C._physics(name, EXECUTION)
        result = fit(problem, solver=name, execution=EXECUTION, physics=physics, forward_solve=forward_solve,
                     geometry_update=GEOMETRY_UPDATE, policy=policy(run), material=material,
                     localization_adapter=C.keep_start if run.damped else None,
                     on_event=lambda e: print(case, e['operation']['label'], e['reason'], flush=True))
        curve = curve_from(result['final_curve'])
        final_contrast = float(result.get('final_contrast', contrast))
        work = result['fit_work'] or {}
        record.update(
            outcome=result['outcome'], detail=result['detail'], contrast_start=start,
            contrast=final_contrast, final_curve=curve_record(curve), final_stage=result['final_stage'],
            stages=result['stages'], decisions=result['decisions'], fit_work=work,
            frequencies_hz=[o.frequency_hz for o in real],
            noise_sigma_declared=[o.sigma_real_imag for o in real],
            fit_seconds=result['fit_and_localization_seconds'], setup_seconds=start['seconds'],
            work=dict(units=result['fit_and_localization_units'],
                      forward_solves=sum(work.get('solves', {}).values()),
                      derivative_batches=sum(work.get('reciprocal_batches', {}).values()),
                      failed=sum(work.get('failed', {}).values()),
                      accepted_steps=sum(s['accepted_steps'] for s in result['stages']),
                      stages=len(result['stages'])),
            physics=result['physics'], geometry_work=result['geometry_work'])
        arrays.update(coefficients=curve.coefficients,
                      image=((final_contrast-1.)*D.fill_fraction(S.LENGTH*curve.values(4096),
                                                                  *D.pixel_grid(GRID))).astype(np.float32))
        try:
            predicted, residual, check = final_fields(real, curve, final_contrast, name, EXECUTION)
            record.update(residual=residual, maximum_residual=float(residual.max()),
                          residual_seconds=check['seconds'], residual_resolution=check['resolution'])
            arrays.update(predicted=predicted)
        except Exception:
            record.update(residual=None, maximum_residual=None, residual_failure=traceback.format_exc())
    except Exception:
        record.update(outcome='WORKER_EXCEPTION', detail=traceback.format_exc())
    record['case_seconds'] = perf_counter()-started
    return record, arrays
