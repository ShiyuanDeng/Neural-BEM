"""The GauGal family: one reconstruction of one case, saved as ``fit.json`` and ``fit.npz``.

``default`` is the setting GGB-002 ended with, used here with no further tuning:
lattice 51, width 0.7, TV weight 0.5, step 0.05, susceptibility limit 15,
80 iterations, a 400 s optimization limit, all 19 real frequencies at once.
It was chosen on clean data, so these numbers are a reference, not a fair baseline.

The case handed to GauGal carries the observations and acquisition only: the
truth boundary and contrast that ``tg002_data.load`` attaches are replaced by
the start circle and contrast 1 before the adapter sees them.
"""
from dataclasses import asdict, replace
from time import perf_counter
import traceback

import numpy as np

from experiments.benchmark import scenes as S
from experiments.gaugal_comparison import tg002_data as D

from . import noise as N

SETTINGS = dict(grid=51, sigma_scale=.7, lambda_scale=.5, step_size=.05, contrast_max=15., num_iter=80)
MAX_SECONDS = 400.
OUTER_SECONDS = 600.     # the parent stops a hung child after this long
FREQUENCIES = 19


def settings(run):
    if run.variant != 'default' or run.contrast != 'uc' or run.frequency != 'fs' or run.damped:
        raise ValueError('GauGal runs here are default_<data>_uc_fs: untuned, unknown contrast, all frequencies at once.')
    return dict(method='GauGal collocation, FISTA + TV, one coefficient vector over all frequencies',
                adapter='experiments/gaugal_comparison/gaugal_arm.py', **SETTINGS,
                max_seconds=MAX_SECONDS, outer_seconds=OUTER_SECONDS, frequencies=FREQUENCIES,
                tuning='none here; settings are those GGB-002 chose on clean circle cases',
                data='sealed TG-002 real catalog' if run.noise is None else f'results/_shared/noise/{run.data}/<case>.npz',
                timing='fit_seconds is the optimization loop; setup_seconds builds the operators')


def blind_case(run, case, root):
    """Observations and acquisition for ``case`` with every truth field replaced."""
    loaded = D.load(case)
    observed = loaded.observed
    if run.noise is not None:
        observed = N.load(*run.noise, case, root)['observed'].T
    circle = S.LENGTH*S.start_fixture().values(4096)
    return replace(loaded, contrast=1., boundary=circle, observed=observed)


def record_from(case, run, fit, observed, outcome=None, detail=None):
    """(fit.json record, fit.npz arrays) from the adapter's result or last checkpoint."""
    used = list(fit['frequencies'])
    residual = D.relative_error(np.asarray(fit['predictions']), observed[used])
    record = dict(case=case, scene=case.split('__')[0], family=run.family, run=run.name, representation='image',
                  outcome=outcome or ('COMPLETED' if fit.get('stop_reason') == 'iteration_limit' else 'STOPPED_EARLY'),
                  stop_reason=fit.get('stop_reason'), detail=detail, settings=fit['settings'],
                  frequencies_hz=[float(D.ci.FREQUENCIES[i]) for i in used], residual=residual,
                  maximum_residual=float(residual.max()), fit_seconds=fit['optimize_seconds'],
                  setup_seconds=fit['build_seconds'], history=fit['history'][::10]+fit['history'][-1:],
                  linear_solves=fit.get('linear_solves'),
                  work=dict(iterations=fit.get('iterations', len(fit['history'])),
                            linear_solve_calls=sum(r['calls'] for r in fit.get('linear_solves') or []),
                            linear_solves_unconverged=sum(r['unconverged'] for r in fit.get('linear_solves') or [])))
    arrays = dict(image=np.asarray(fit['image'], np.float32), coefficients=np.asarray(fit['coefficients']),
                  predicted=np.asarray(fit['predictions']))
    return record, arrays


def fit_case(run, case, root, checkpoint_path=None):
    """Reconstruct one case. Returns (record for fit.json, arrays for fit.npz)."""
    started = perf_counter()
    try:
        from experiments.gaugal_comparison import gaugal_arm
        blind = blind_case(run, case, root)
        last = {}

        def checkpoint(state):
            last.clear()
            last.update(state)
            if checkpoint_path is not None:
                temporary = checkpoint_path.with_name('checkpoint.tmp.npz')
                np.savez_compressed(temporary, image=state['image'], coefficients=state['coefficients'],
                                    predictions=state['predictions'], frequencies=state['frequencies'],
                                    iterations=state['iterations'], build_seconds=state['build_seconds'],
                                    optimize_seconds=state['optimize_seconds'])
                temporary.replace(checkpoint_path)

        chosen = gaugal_arm.settings(SETTINGS['grid'], **{k: v for k, v in SETTINGS.items() if k != 'grid'})
        try:
            fit = gaugal_arm.reconstruct(blind, chosen, frequencies=list(range(FREQUENCIES)), verbose=True,
                                         max_seconds=MAX_SECONDS, checkpoint=checkpoint)
            record, arrays = record_from(case, run, fit, blind.observed)
        except Exception:
            if not last:
                raise
            record, arrays = record_from(case, run, dict(last, stop_reason='exception'), blind.observed,
                                         outcome='EXCEPTION_PARTIAL', detail=traceback.format_exc())
    except Exception:
        record, arrays = dict(case=case, scene=case.split('__')[0], family=run.family, run=run.name,
                              representation='image', outcome='WORKER_EXCEPTION',
                              detail=traceback.format_exc()), {}
    record['case_seconds'] = perf_counter()-started
    return record, arrays


def from_checkpoint(run, case, root, checkpoint_path, reason):
    """The last saved state of a child that was stopped from outside."""
    from experiments.gaugal_comparison import gaugal_arm
    base = dict(case=case, scene=case.split('__')[0], family=run.family, run=run.name, representation='image')
    if not checkpoint_path.exists():
        return dict(base, outcome='TIMEOUT', detail=reason), {}
    with np.load(checkpoint_path) as saved:
        state = {k: saved[k] for k in saved.files}
    chosen = gaugal_arm.settings(SETTINGS['grid'], **{k: v for k, v in SETTINGS.items() if k != 'grid'})
    fit = dict(state, frequencies=[int(i) for i in state['frequencies']], iterations=int(state['iterations']),
               build_seconds=float(state['build_seconds']), optimize_seconds=float(state['optimize_seconds']),
               settings=asdict(chosen), history=[dict(iteration=int(state['iterations']))], stop_reason='outer_timeout')
    return record_from(case, run, fit, blind_case(run, case, root).observed, outcome='TIMEOUT_PARTIAL', detail=reason)
