"""Drivers for FW-001 (forward check) and GGB-002 (GauGal on TG-002).

Run from the repository root in the EMNerf environment:

    PYTHONPATH=solvers:.:2D-MOM-ESI/src:$HOME/Gau-Gal/src \
        python -m experiments.gaugal_comparison fw-mom --cases all --out <dir>

See docs/iterations/gaugal_comparison/iteration_01/03_plan.md.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from experiments.benchmark import scenes as S

from . import tg002_data as D


def _cases(names):
    return list(S.CASES) if names == ['all'] else names


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(payload, indent=1, default=lambda v: v.tolist() if hasattr(v, 'tolist') else str(v)))
    temporary.replace(path)


def fw_mom(args):
    from . import mom_arm
    for case_id in _cases(args.cases):
        target = args.out/f'{case_id}.json'
        if target.exists():
            continue
        rows = mom_arm.run_case(D.load(case_id), args.cells)
        _write(target, dict(case=case_id, solver='mom_esi', rows=rows))
        worst = max(r['relative_error'] for r in rows if r['cells'] == max(args.cells))
        print(f'{case_id}: worst error at {max(args.cells)} cells {worst:.3e}', flush=True)


def fw_gaugal(args):
    from time import perf_counter
    from gaugal.paper2d.settings import SolverControls
    from . import gaugal_arm
    for case_id in _cases(args.cases):
        target = args.out/f'{case_id}.json'
        if target.exists():
            continue
        case = D.load(case_id)
        rows = []
        controls = SolverControls(pcg_max_iter=args.max_iterations)
        indices = range(len(case.frequencies_hz)) if args.frequency_indices is None else args.frequency_indices
        for grid, sigma in args.settings:
            for i in indices:
                start = perf_counter()
                predicted, seconds, stats = gaugal_arm.forward(case, i, grid, sigma_scale=sigma, controls=controls)
                rows.append(dict(grid=grid, spacing_mm=1e3*2*D.BOX_HALF_WIDTH_M/(grid-1),
                                 sigma_scale=sigma, frequency_hz=case.frequencies_hz[i],
                                 relative_error=float(D.relative_error(predicted, case.observed[i])),
                                 solve_seconds=seconds, total_seconds=perf_counter()-start,
                                 linear_solve=stats))
        _write(target, dict(case=case_id, solver='gaugal_operator', pixels=gaugal_arm.PIXELS, rows=rows))
        for grid, sigma in args.settings:
            worst = max(r['relative_error'] for r in rows if (r['grid'], r['sigma_scale']) == (grid, sigma))
            print(f'{case_id}: lattice {grid} width {sigma}: worst error {worst:.3e}', flush=True)


def gaugal_case(case_id, case_settings, frequencies, folder, max_seconds=None):
    """One GGB-002 GauGal fit, saved with its scores (truth read only after the fit)."""
    from . import gaugal_arm, ggb_scoring as G
    target = folder/f'{case_id}.json'
    if target.exists():
        return json.loads(target.read_text())
    case = D.load(case_id)
    def checkpoint(fit):
        folder.mkdir(parents=True, exist_ok=True)
        temporary = folder/f'{case_id}.progress.tmp.npz'
        np.savez_compressed(temporary, image=fit['image'], coefficients=fit['coefficients'],
                            predictions=fit['predictions'])
        temporary.replace(folder/f'{case_id}.progress.npz')
        _write(folder/f'{case_id}.progress.json', {k: v for k, v in fit.items()
                if k not in ('image', 'coefficients', 'predictions')})
    fit = gaugal_arm.reconstruct(case, case_settings, frequencies=frequencies, verbose=True,
                                 max_seconds=max_seconds, checkpoint=checkpoint)
    return save_gaugal_fit(case, fit, folder)


def save_gaugal_fit(case, fit, folder, failure=None):
    from . import gaugal_arm, ggb_scoring as G
    case_id = case.case_id
    target = folder/f'{case_id}.json'
    chi = fit['image']
    folder.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(folder/f'{case_id}.npz', image=chi, coefficients=fit['coefficients'],
                        predictions=fit['predictions'])
    residual = D.relative_error(fit['predictions'], case.observed[fit['frequencies']])
    curve, traced = G.trace(chi, gaugal_arm.PIXELS)
    row = dict(case=case_id, frequencies_hz=case.frequencies_hz[fit['frequencies']], residual=residual,
               maximum_residual=float(residual.max()), settings=fit['settings'], build_seconds=fit['build_seconds'],
               optimize_seconds=fit['optimize_seconds'], traced=traced,
               traced_curve=None if curve is None else dict(real=curve.coefficients.real, imag=curve.coefficients.imag),
               history=fit['history'][::10]+fit['history'][-1:],
               iterations=fit.get('iterations', len(fit['history'])),
               linear_solves=fit.get('linear_solves'),
               stop_reason=fit.get('stop_reason', 'iteration_limit'), failure=failure,
               status='partial' if failure or fit.get('stop_reason') != 'iteration_limit' else 'completed')
    # Scoring: truth is read from here on.
    row.update(image=G.image_scores(chi, G.truth_image(case, gaugal_arm.PIXELS)),
               boundary=G.boundary_scores(case_id, curve), contrast_true=case.contrast)
    _write(target, row)
    print(f"{case_id}: residual max {row['maximum_residual']:.3f}, RMS {row['boundary']['rms_mm']:.2f} mm, "
          f"RRMSE {row['image']['rrmse']:.4f}, traced contrast {traced.get('traced_contrast', float('nan')):.3g}, "
          f"{row['optimize_seconds']:.0f} s", flush=True)
    return row


def _gaugal_settings(args, **override):
    from . import gaugal_arm
    values = dict(sigma_scale=args.sigma_scale, lambda_scale=args.lambda_scale, step_size=args.step_size,
                  contrast_max=args.contrast_max, num_iter=args.num_iter)
    values.update(override)
    return gaugal_arm.settings(args.grid, **values)


def ggb_run(args):
    frequencies = list(range(args.frequencies))
    for case_id in _cases(args.cases):
        gaugal_case(case_id, _gaugal_settings(args), frequencies, args.out, args.max_seconds)


def ggb_tune(args):
    """G1: at most 12 settings on the three circle cases; choose by mean image RRMSE."""
    import itertools
    frequencies = list(range(args.frequencies))
    grid = list(itertools.product(args.lambda_values, args.step_values, args.sigma_values))
    if len(grid) > 12:
        raise ValueError('The plan allows at most 12 tuning settings')
    table = []
    for lam, step, sigma in grid:
        tag = f'lambda{lam:g}_step{step:g}_sigma{sigma:g}'
        rows = [gaugal_case(c, _gaugal_settings(args, lambda_scale=lam, step_size=step, sigma_scale=sigma),
                            frequencies, args.out/tag) for c in ('circle__c0.5', 'circle__c4', 'circle__c13.3')]
        table.append(dict(setting=tag, lambda_scale=lam, step_size=step, sigma_scale=sigma,
                          mean_rrmse=float(np.mean([r['image']['rrmse'] for r in rows])),
                          rows=[dict(case=r['case'], rrmse=r['image']['rrmse'], rms_mm=r['boundary']['rms_mm'],
                                     maximum_residual=r['maximum_residual']) for r in rows]))
    best = min(table, key=lambda r: r['mean_rrmse'])
    _write(args.out/'tuning.json', dict(table=table, chosen=best['setting'], rule='lowest mean image RRMSE'))
    print('chosen', best['setting'], f"mean RRMSE {best['mean_rrmse']:.4f}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('fw-mom', help='FW-001 MoM forward error against the sealed fields')
    p.add_argument('--cases', nargs='+', default=['all'])
    p.add_argument('--cells', nargs='+', type=int, default=[51, 101, 201])
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(run=fw_mom)
    p = sub.add_parser('fw-gaugal', help="FW-001 GauGal operator forward error")
    p.add_argument('--cases', nargs='+', default=['all'])
    p.add_argument('--settings', nargs='+', type=lambda v: (int(v.split(':')[0]), float(v.split(':')[1])),
                   default=[(51, .7), (51, 1.), (101, .7), (101, 1.), (201, .35)], help='lattice:width pairs')
    p.add_argument('--frequency-indices', nargs='+', type=int, default=None)
    p.add_argument('--max-iterations', type=int, default=2000)
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(run=fw_gaugal)
    def gaugal_options(p):
        p.add_argument('--grid', type=int, required=True, help='Gaussian lattice size per side (from FW-001)')
        p.add_argument('--frequencies', type=int, default=19, help='use the lowest N real frequencies')
        p.add_argument('--sigma-scale', type=float, default=.35)
        p.add_argument('--lambda-scale', type=float, default=.5)
        p.add_argument('--step-size', type=float, default=1.)
        p.add_argument('--contrast-max', type=float, default=15.)
        p.add_argument('--num-iter', type=int, default=300)
        p.add_argument('--max-seconds', type=float, help='optimization wall limit; save the last finite result')
        p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('ggb-run', help='GGB-002 GauGal fits with one frozen setting')
    p.add_argument('--cases', nargs='+', default=['all'])
    gaugal_options(p)
    p.set_defaults(run=ggb_run)
    p = sub.add_parser('ggb-tune', help='GGB-002 G1 tuning on the circle cases')
    gaugal_options(p)
    p.add_argument('--lambda-values', nargs='+', type=float, required=True)
    p.add_argument('--step-values', nargs='+', type=float, required=True)
    p.add_argument('--sigma-values', nargs='+', type=float, required=True)
    p.set_defaults(run=ggb_tune)
    args = parser.parse_args()
    args.run(args)


if __name__ == '__main__':
    main()
