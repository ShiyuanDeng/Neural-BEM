"""Baseline generation for the 17 November 2026 run.

Run from the repository root with the EMNerf Python:

    python -m experiments.comparison list
    python -m experiments.comparison run bem/default_clean_uc_fc

It sets its own import paths and single-threaded BLAS, so no environment
variables are needed. README.md in this folder lists every command in order.
"""
import os
import sys
from pathlib import Path

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
_ROOT = Path(__file__).resolve().parents[2]
for _extra in (Path(os.environ.get('GAUGAL_SRC', Path.home()/'Gau-Gal/src')), _ROOT/'solvers'):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

import argparse
import csv
import shutil
import subprocess
import traceback

import numpy as np

from bem_inverse.io import read, write

from . import runs as R

SUCCESS_AREA = .05   # provisional cut-off; used only for the counts that ``list`` prints

COLUMNS = ('family', 'run', 'variant', 'data', 'contrast_mode', 'frequency', 'case', 'scene', 'contrast_true',
           'noise_percent', 'noise_draw', 'outcome', 'area_error', 'missing_area', 'excess_area', 'components',
           'holes', 'material_l2', 'boundary_rms_mm', 'chamfer_mm', 'hausdorff_mm', 'hausdorff_upper_mm',
           'centroid_mm', 'rrmse', 'psnr', 'ssim', 'contrast_snr_db', 'contrast_estimate',
           'contrast_relative_error', 'maximum_residual', 'residual_over_limit', 'fit_seconds', 'setup_seconds',
           'work_units', 'forward_solves', 'derivative_batches', 'iterations', 'last_stage', 'tg002_rms_mm',
           'tg002_hausdorff_upper_mm', 'empty_region', 'protocol_version')


def family_module(run):
    if run.family == 'bem':
        from . import bem
        return bem
    from . import gaugal
    return gaugal


def save_fit(folder, record, arrays):
    """fit.npz first, then fit.json: the JSON file marks a finished fit."""
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder/'fit.tmp.npz'
    np.savez_compressed(temporary, **arrays)
    temporary.replace(folder/'fit.npz')
    write(folder/'fit.json', dict(record, **R.commit()))


def load_fit(folder):
    with np.load(folder/'fit.npz') as saved:
        arrays = {k: saved[k] for k in saved.files}
    return read(folder/'fit.json'), arrays


def score_case(run, case, root):
    from . import scoring
    folder = run.folder(root)/case
    fit, arrays = load_fit(folder)
    row = scoring.score(run, case, fit, arrays, root)
    write(folder/'score.json', row)
    return row


def fit_child(run, case, root):
    """One GauGal case in its own process, so a hang or device fault cannot stop the run."""
    from . import gaugal
    folder = run.folder(root)/case
    folder.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-u', '-m', 'experiments.comparison', '--root', str(root), 'fit-case', run.key, case]
    failure = None
    try:
        code = subprocess.run(command, cwd=R.ROOT, timeout=None if run.variant == 'converged' else gaugal.OUTER_SECONDS).returncode
        if code:
            failure = f'child exited with code {code}'
    except subprocess.TimeoutExpired:
        failure = f'child stopped after {gaugal.OUTER_SECONDS:g} s'
    if not (folder/'fit.json').exists():
        save_fit(folder, *gaugal.from_checkpoint(run, case, root, folder/'checkpoint.npz', failure))
    (folder/'checkpoint.npz').unlink(missing_ok=True)


def fit_case(run, case, root):
    module = family_module(run)
    folder = run.folder(root)/case
    if run.family == 'gaugal':
        folder.mkdir(parents=True, exist_ok=True)
        record, arrays = module.fit_case(run, case, root, folder/'checkpoint.npz')
    else:
        record, arrays = module.fit_case(run, case, root)
    save_fit(folder, record, arrays)
    return record


def run_command(args):
    run, root = R.parse(args.run), args.root
    module = family_module(run)
    cases = tuple(args.cases) if args.cases else R.cases_for(run)
    unknown = set(cases)-set(R.CASES_ALL)
    if unknown:
        raise SystemExit(f'Unknown cases: {sorted(unknown)}')
    if run.noise is not None:
        from . import noise
        noise.make(run.noise[0], [run.noise[1]], root=root)
    R.open_run(run, module.settings(run), cases, root)
    pending = [c for c in cases if not (run.folder(root)/c/'fit.json').exists()]
    print(f'{run.key}: {len(cases)-len(pending)} of {len(cases)} fits already saved', flush=True)
    if pending and run.family == 'bem':
        module.warm_up(run)
    unscored = []
    for case in cases:
        folder = run.folder(root)/case
        if case in pending:
            if run.family == 'gaugal':
                fit_child(run, case, root)
            else:
                fit_case(run, case, root)
        if not (folder/'score.json').exists() or case in pending:
            try:
                row = score_case(run, case, root)
                fit = read(folder/'fit.json')
                print(f"RESULT {run.key} {case}: {fit.get('outcome')}, area error {row['area_error']:.4f}, "
                      f"components {row['components']}, material error {row['material_l2']:.4f}, "
                      f"{fit.get('fit_seconds') or float('nan'):.1f} s", flush=True)
            except Exception:
                unscored.append(case)
                print(f'SCORE FAILED {run.key} {case}\n{traceback.format_exc()}', flush=True)
    metrics_command(args)
    summary(root, [run.key])
    if unscored:
        raise SystemExit(f'Fits are saved, but scoring failed for: {unscored}')


def fit_case_command(args):
    run = R.parse(args.run)
    record = fit_case(run, args.case, args.root)
    print(f"FIT {run.key} {args.case}: {record.get('outcome')}", flush=True)


def score_command(args):
    wanted = None if args.run is None else R.parse(args.run).key
    failed = []
    for run_folder, case_folder in R.fits(args.root):
        run = R.parse(f'{run_folder.parent.name}/{run_folder.name}')
        if wanted in (None, run.key):
            try:
                score_case(run, case_folder.name, args.root)
            except Exception:
                failed.append(f'{run.key}/{case_folder.name}')
                print(f'SCORE FAILED {failed[-1]}\n{traceback.format_exc()}', flush=True)
    metrics_command(args)
    if failed:
        raise SystemExit(f'Scoring failed for: {failed}')


def rows(root):
    for run_folder, case_folder in R.fits(root):
        run = R.parse(f'{run_folder.parent.name}/{run_folder.name}')
        fit = read(case_folder/'fit.json')
        score = read(case_folder/'score.json') if (case_folder/'score.json').exists() else {}
        work = fit.get('work') or {}
        noise = run.noise or (0., None)
        row = dict(score, family=run.family, run=run.name, variant=run.variant, data=run.data,
                   contrast_mode=run.contrast, frequency=run.frequency, case=case_folder.name,
                   scene=case_folder.name.split('__')[0], noise_percent=noise[0], noise_draw=noise[1],
                   outcome=fit.get('outcome'), maximum_residual=fit.get('maximum_residual'),
                   fit_seconds=fit.get('fit_seconds'), setup_seconds=fit.get('setup_seconds'),
                   work_units=work.get('units'), forward_solves=work.get('forward_solves'),
                   derivative_batches=work.get('derivative_batches'), iterations=work.get('iterations'),
                   last_stage=(fit.get('final_stage') or {}).get('label'),
                   protocol_version=(score.get('protocol') or {}).get('version'))
        yield {k: row.get(k) for k in COLUMNS}


def metrics_command(args):
    table = list(rows(args.root))
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root/'metrics.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        writer.writerows(table)
    print(f'metrics.csv: {len(table)} fits', flush=True)


def summary(root, keys=None):
    """Counts per run. The 5% cut-off is provisional and is not stored anywhere."""
    table = list(rows(root))
    planned = {key: (number, label) for number, label, keys_ in R.PLAN for key in keys_}
    found = sorted({f"{r['family']}/{r['run']}" for r in table}, key=lambda k: (planned.get(k, (99, ''))[0], k))
    listed = keys or [key for _, _, keys_ in R.PLAN for key in keys_]+[k for k in found if k not in planned]
    print(f'{"run":34} {"fits":>7} {"area<=5%":>9} {"old count":>10} {"median area":>12} {"median s":>9}')
    for key in listed:
        mine = [r for r in table if f"{r['family']}/{r['run']}" == key]
        total = len(R.cases_for(R.parse(key))) if key in planned else len(mine)
        scored = [r for r in mine if r['area_error'] is not None]
        good = sum(r['area_error'] <= SUCCESS_AREA for r in scored)
        old = sum(r['boundary_rms_mm'] is not None and r['boundary_rms_mm'] <= 1 and r['hausdorff_upper_mm'] <= 2
                  and r['residual_over_limit'] is not None and r['residual_over_limit'] <= 1 for r in scored)
        seconds = [r['fit_seconds'] for r in mine if r['fit_seconds'] is not None]
        middle = lambda v: f'{np.median(v):.4g}' if v else '-'
        print(f'{key:34} {len(mine):>3}/{total:<3} {good:>9} {old:>10} '
              f'{middle([r["area_error"] for r in scored]):>12} {middle(seconds):>9}')


def import_command(args):
    """Bring the saved clean GauGal endpoints from 2 November 2026 into this layout and score them."""
    from . import gaugal
    legacy_results = R.ROOT.parent/'Neural_SDF_BEM_AD/development_results'
    source = legacy_results/'GGB-002/G2_all'
    run = R.parse('gaugal/default_clean_uc_fs')
    manifest = read(legacy_results/'GGB-002/overnight_manifest.json')
    settings = dict(gaugal.settings(run), imported_from='development_results/GGB-002/G2_all',
                    original_commit=manifest['commit'], note='GGB-002 fits copied without refitting')
    cases = [c for c in R.CASES_ALL if (source/f'{c}.json').exists() and (source/f'{c}.npz').exists()]
    R.open_run(run, settings, cases, args.root)
    for case in cases:
        folder = run.folder(args.root)/case
        if not (folder/'fit.json').exists():
            old = read(source/f'{case}.json')
            record = dict(case=case, scene=case.split('__')[0], family=run.family, run=run.name,
                          representation='image',
                          outcome='COMPLETED' if old.get('status') == 'completed' else 'STOPPED_EARLY',
                          stop_reason=old.get('stop_reason'), detail=old.get('failure'), settings=old['settings'],
                          frequencies_hz=old['frequencies_hz'], residual=old['residual'],
                          maximum_residual=old['maximum_residual'], fit_seconds=old['optimize_seconds'],
                          setup_seconds=old['build_seconds'], history=old['history'],
                          linear_solves=old.get('linear_solves'),
                          work=dict(iterations=old['iterations'],
                                    linear_solve_calls=sum(r['calls'] for r in old.get('linear_solves') or []),
                                    linear_solves_unconverged=sum(r['unconverged'] for r in old.get('linear_solves') or [])),
                          imported_from=f'development_results/GGB-002/G2_all/{case}.json')
            with np.load(source/f'{case}.npz') as saved:
                arrays = dict(image=saved['image'], coefficients=saved['coefficients'], predicted=saved['predictions'])
            save_fit(folder, record, arrays)
        score_case(run, case, args.root)
    metrics_command(args)
    summary(args.root, [run.key])


def noise_command(args):
    from . import noise
    written = noise.make(args.percent, args.draws, root=args.root)
    print(f'noise {args.percent:g}%: {written} files written, draws {args.draws}', flush=True)


def clean_command(args):
    """Remove case folders that hold no finished fit (left by an interrupted run)."""
    for family in sorted(p for p in args.root.glob('*') if p.is_dir() and not p.name.startswith('_')):
        for folder in sorted(family.glob('*/*')):
            if folder.is_dir() and not (folder/'fit.json').exists():
                print('removing unfinished', folder.relative_to(args.root), flush=True)
                shutil.rmtree(folder)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', type=Path, default=R.RESULTS, help='storage root (default: results/)')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('list', help='planned runs and how far each has got')
    p.set_defaults(call=lambda a: summary(a.root))
    p = sub.add_parser('noise', help='write the shared noisy data')
    p.add_argument('--percent', type=float, default=1.)
    p.add_argument('--draws', type=int, nargs='+', default=[0, 1, 2])
    p.set_defaults(call=noise_command)
    p = sub.add_parser('run', help='fit and score the remaining cases of one run')
    p.add_argument('run', help='<family>/<variant>_<data>_<contrast>_<frequency>')
    p.add_argument('--cases', nargs='+', help='default: the planned cases of that run')
    p.set_defaults(call=run_command)
    p = sub.add_parser('fit-case', help='fit one case without scoring (used for GauGal child processes)')
    p.add_argument('run')
    p.add_argument('case')
    p.set_defaults(call=fit_case_command)
    p = sub.add_parser('score', help='rescore saved fits (all, or one run) and rebuild metrics.csv')
    p.add_argument('run', nargs='?')
    p.set_defaults(call=score_command)
    p = sub.add_parser('metrics', help='rebuild metrics.csv from the saved fits and scores')
    p.set_defaults(call=metrics_command)
    p = sub.add_parser('import-gaugal-2026-11-02', help='copy the saved clean GauGal fits into this layout and score them')
    p.set_defaults(call=import_command)
    p = sub.add_parser('clean', help='remove case folders left unfinished by an interrupted run')
    p.set_defaults(call=clean_command)
    p = sub.add_parser('forward-check', help='compare one sealed field with an independent forward solver')
    p.set_defaults(call=lambda a: __import__('experiments.comparison.forward_check', fromlist=['main']).main(a))
    args = parser.parse_args()
    args.root = args.root.resolve()
    args.call(args)


if __name__ == '__main__':
    main()
