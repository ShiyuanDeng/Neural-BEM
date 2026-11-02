"""MR-001: TG-002 fits that recover the contrast together with the boundary.

Same cases, inputs, settings, endpoint check and recovery limits as the
known-contrast control (R1), whose manifest settings are reused exactly. Two
differences: the fit receives a ``MaterialUnknown`` and starts from an
estimated contrast instead of the true one.

Start rules (recorded before fitting):
- ``weak`` (R2): solve the centred start circle once at contrast 1 + 1e-3 at
  the lowest damped frequency and scale that response to best fit the data.
  This uses no truth. A separate physics context does this solve, so the fit's
  caches and ledger are untouched; its time is recorded separately.
- ``near_truth`` (R3): 1.2 x the true contrast, only to diagnose R2 failures.

The final field residual is computed at the recovered contrast. Truth is read
only to score after the fit and its residual have returned. The final
two-resolution check no longer runs (user decision D11, 2026-11-02).

    PYTHONPATH=solvers:. OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        python -m experiments.gaugal_comparison.mr001 --cases all --start weak \
        --settings-from results/validation/cleaned_interfaces/MR-001/R1_known_contrast \
        --run-dir results/validation/cleaned_interfaces/MR-001/R2_material_weak_start
"""
import argparse
from dataclasses import replace
from pathlib import Path
from time import perf_counter
import traceback

import numpy as np

from bem_inverse.io import read, write, curve_from
from bem_inverse.material import MaterialUnknown
from bem_inverse.physics import Execution
from bem_inverse.policy import CumulativePolicy
from bem_inverse.runner import fit
from experiments.benchmark import campaign as C, scenes as S
from experiments.cleaned_interface import benchmark as ci

EPSILON = 1e-3
NEAR_TRUTH_FACTOR = 1.2
MINIMUM_START = .05


def weak_scatterer_start(problem, settings, execution):
    physics, forward_solve = C._physics(settings['solver'], execution)
    observation = problem.damped[0]
    nodes = physics.resolution_profile(problem.initial.band)['production']
    started = perf_counter()
    state = forward_solve(problem.initial, observation, 1.+EPSILON, nodes)
    seconds = perf_counter()-started
    if hasattr(physics, 'close'):
        physics.close()
    p = np.asarray(state.prediction).reshape(-1)
    d = np.asarray(observation.scattered).reshape(-1)
    susceptibility = EPSILON*float(np.real(np.vdot(p, d))/np.real(np.vdot(p, p)))
    return max(1.+susceptibility, MINIMUM_START), dict(
        rule='weak', epsilon=EPSILON, frequency_hz=getattr(observation, 'frequency_hz', None),
        wavenumber=str(observation.wavenumber), nodes=nodes, estimated_susceptibility=susceptibility,
        clipped=1.+susceptibility < MINIMUM_START, seconds=seconds)


def run_case(run_dir, case_row, settings, start_rule, material):
    folder = Path(run_dir)/'runs'/case_row['id']
    if (folder/'result.json').exists():
        return read(folder/'result.json')
    if folder.exists():
        raise FileExistsError(f'Incomplete run preserved at {folder}; use a fresh run directory')
    folder.mkdir(parents=True)
    execution = Execution(**settings['execution'])
    started = perf_counter()
    try:
        problem = ci.fitting_problem(case_row, run_dir)
        if start_rule == 'weak':
            start, start_record = weak_scatterer_start(problem, settings, execution)
        else:
            start = NEAR_TRUTH_FACTOR*problem.contrast
            start_record = dict(rule='near_truth', factor=NEAR_TRUTH_FACTOR, seconds=0.)
        start_record['start_contrast'] = start
        write(folder/'contrast_start.json', start_record)
        physics, forward_solve = C._physics(settings['solver'], execution)
        result = fit(replace(problem, contrast=start), solver=settings['solver'], execution=execution,
                     physics=physics, forward_solve=forward_solve, output=folder,
                     geometry_update=settings['geometry_update'], localization_adapter=C.keep_start,
                     on_event=lambda e: print(case_row['id'], e['operation']['label'], e['reason'], flush=True),
                     policy=CumulativePolicy(**settings.get('cumulative_options', {})), material=material)
        final_contrast = float(result['final_contrast'])
        checked = C.final_residual(replace(problem, contrast=final_contrast), result, settings)
        result.update(relative_residual=checked['relative_residual'], residual_seconds=checked['seconds'],
                      residual_resolution=checked['resolution'], total_units=result['fit_and_localization_units'],
                      total_seconds=result['total_seconds']+checked['seconds']+start_record['seconds'])
        result['output_seconds'] = perf_counter()-started
        # The fit and its residual have returned; truth is read from here on.
        metrics = ci.score(case_row, curve_from(result['final_curve']))
        limits = ci.residual_limits(case_row)
        residual = result['relative_residual']
        true = float(case_row['contrast'])
        result.update(case=case_row, settings=settings, metrics=metrics, residual_limits=limits,
            contrast_start=start, contrast_start_record=start_record, contrast_true=true,
            contrast_final=final_contrast, contrast_relative_error=final_contrast/true-1.,
            recovered=C.recovered(metrics, residual, limits), maximum_residual=float(max(residual)))
    except Exception:
        result = dict(case=case_row, settings=settings, outcome='WORKER_EXCEPTION', recovered=False,
                      traceback=traceback.format_exc())
    write(folder/'result.json', result)
    print('RESULT', case_row['id'], result.get('outcome'), result['recovered'],
          result.get('contrast_start'), result.get('contrast_final'), result.get('metrics'), flush=True)
    return result


def summarize(run_dir):
    rows = []
    for path in sorted((Path(run_dir)/'runs').glob('*/result.json')):
        r = read(path)
        m = r.get('metrics') or {}
        rows.append(dict(id=r['case']['id'], contrast=r['case']['contrast'], outcome=r.get('outcome'),
                         recovered=r['recovered'], rms_mm=m.get('rms_mm'),
                         hausdorff_upper_mm=m.get('hausdorff_upper_mm'), maximum_residual=r.get('maximum_residual'),
                         contrast_start=r.get('contrast_start'), contrast_final=r.get('contrast_final'),
                         contrast_relative_error=r.get('contrast_relative_error'), seconds=r.get('total_seconds')))
    summary = dict(completed=len(rows), recovered=sum(r['recovered'] for r in rows),
                   by_contrast={S.tag(c): sum(r['recovered'] for r in rows if r['contrast'] == c) for c in S.CONTRASTS},
                   cases=rows)
    write(Path(run_dir)/'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cases', nargs='+', default=['all'])
    parser.add_argument('--start', choices=('weak', 'near_truth'), required=True)
    parser.add_argument('--settings-from', type=Path, required=True, help='known-contrast control run directory')
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--hold-warmup', action='store_true',
                        help='R4: keep the start contrast fixed in warmup_025_damped')
    args = parser.parse_args()
    cases = list(S.CASES) if args.cases == ['all'] else args.cases
    settings = read(args.settings_from/'manifest.json')['settings']
    material = MaterialUnknown(held_stages=('warmup_025_damped',) if args.hold_warmup else ())
    C.verify(C.INPUTS, require_inputs=True)
    rows = [C.row(c, C.INPUTS) for c in cases]
    manifest = dict(settings, material=material.settings(), contrast_start_rule=args.start,
                    settings_from=str(args.settings_from))
    C.open_run(args.run_dir, cases, manifest, experiment='MR-001')
    for r in rows:
        run_case(args.run_dir, r, settings, args.start, material)
    print(summarize(args.run_dir)['recovered'], 'recovered', flush=True)


if __name__ == '__main__':
    main()
