"""MA-002: the frozen SC-050 policy on targets denser than the host.

Plan: docs/iterations/modal_atlas/iteration_02/03_plan.md. Phases, run from
the repository root with PYTHONPATH=solvers:. and one BLAS thread:

    python -m experiments.modal_atlas.contrast_screen census
    python -m experiments.modal_atlas.contrast_screen mie
    python -m experiments.modal_atlas.contrast_screen prepare
    python -m experiments.modal_atlas.contrast_screen generate
    python -m experiments.modal_atlas.contrast_screen attempt --contrast 4 --scene shifted_star
    python -m experiments.modal_atlas.contrast_screen campaign --workers 4

The only change from SC-050 is the interior permittivity. `atlas_cases.contrast`
is overridden once per process, before any solve, so data generation,
localization, fitting and audits all use the same known material. SC-050's
frozen `setup`, `localize`, `audit` and `predictions` are imported unchanged.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import warnings

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc

ROOT = sc.ROOT
OUT = ROOT / 'results/validation/modal_atlas/MA-002'
SC050 = ROOT / 'results/validation/shape_continuation/SC-050-localization-robustness'
CONTRASTS = (0.5, 2.0, 4.0, 13.3)
SCENES = ('development_c', 'shifted_star', 'new_asymmetric')
BASE_CONTRAST = 0.5  # plastic (3) in sand (6); asserted against the configuration below


def tag(contrast):
    return f'c{contrast:g}'


def set_contrast(contrast):
    """Override the benchmark material for this process (every frozen entry point calls ac.contrast())."""
    assert abs(ac.contrast() - BASE_CONTRAST) < 1e-15 or ac.contrast.__name__ == 'overridden'
    def overridden():
        return float(contrast)
    ac.contrast = overridden


def sc050():
    spec = importlib.util.spec_from_file_location('ma002_sc050', SC050 / 'run.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, value):
    sc.write(Path(path), value)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ census and Mie check

def census():
    from scipy.special import hankel1, h1vp, jv, jvp
    warnings.simplefilter('ignore')

    def D(n, k, c):
        ki = k * np.sqrt(c)
        return k * jv(n, ki) * h1vp(n, k) - ki * jvp(n, ki) * hankel1(n, k)

    def newton(n, k, c):
        for _ in range(200):
            step = D(n, k, c) / ((D(n, k + 1e-7, c) - D(n, k - 1e-7, c)) / 2e-7)
            k -= step
            if abs(step) < 1e-13:
                return k
        return None

    catalog = ast.catalog_only('circle_to_c')
    kr = [float(o.wavenumber) for o in catalog]   # package units: the 5 cm disk has radius 1
    out = dict(radius_m=sc.LENGTH, catalog_kR=kr, contrasts={})
    for c in (2.0, 4.0, 10.0, 13.3):
        poles = []
        for n in range(0, 40):
            for k0 in np.linspace(0.5, 7, 300):
                k = newton(n, complex(k0, -0.05), c)
                if k is not None and 0.6 <= k.real <= 6.5 and -3 < k.imag < 0:
                    if all(abs(k - p[1]) > 1e-6 for p in poles if p[0] == n):
                        poles.append((n, k))
        poles.sort(key=lambda p: p[1].real)
        Q = [p[1].real / (-2 * p[1].imag) for p in poles]
        out['contrasts'][f'{c:g}'] = dict(
            count=len(poles), q_above_10=int(sum(q > 10 for q in Q)), q_above_100=int(sum(q > 100 for q in Q)),
            q_above_1000=int(sum(q > 1000 for q in Q)),
            poles=[dict(order=n, real=k.real, imag=k.imag, quality=q) for (n, k), q in zip(poles, Q)])
        print(c, out['contrasts'][f'{c:g}']['count'], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / 'circle_pole_census.json', out)


def mie():
    """Kress solver against exact Mie series on the 5 cm disk at the scene centre, every contrast."""
    from experiments.modal_atlas import circle
    from experiments.shape_continuation.forward import solve
    from experiments.shape_continuation.geometry import FourierCurve
    warnings.simplefilter('ignore')
    catalog = ast.catalog_only('circle_to_c')
    disk = FourierCurve.circle(1.0)
    rows = []
    for contrast in CONTRASTS:
        for o in catalog:
            acq = o.acquisition
            kress = solve(disk, o.wavenumber, contrast, acq, 1024).prediction / acq.strength
            s, r = acq.sources, acq.receivers
            exact = np.array([circle.scattered(o.wavenumber, contrast, np.hypot(*a), np.arctan2(a[1], a[0]),
                                               np.hypot(*b), np.arctan2(b[1], b[0]), 80)[0] for a, b in zip(s, r)])
            rows.append(dict(contrast=contrast, wavenumber=float(o.wavenumber),
                             relative=float(np.linalg.norm(kress - exact) / np.linalg.norm(exact))))
    worst = {f'{c:g}': max(r['relative'] for r in rows if r['contrast'] == c) for c in CONTRASTS}
    write(OUT / 'mie_check.json', dict(nodes=1024, tolerance=1e-8, passed=bool(max(worst.values()) <= 1e-8),
                                       worst_relative=worst, rows=rows))
    print('MIE', worst, flush=True)


# ------------------------------------------------------------------ inputs

def source_paths():
    from experiments.shape_continuation import atlas_cases, atlas_strategy_tests, forward, geometry, lm_backend
    paths = {Path(__file__).resolve(), ROOT / 'docs/iterations/modal_atlas/iteration_02/03_plan.md',
             SC050 / 'run.py', ROOT / 'results/validation/shape_continuation/SC-049-far-circle-to-c/run.py',
             ROOT / 'results/validation/shape_continuation/SC-042-state-strategies/run.py'}
    paths.update(Path(m.__file__).resolve() for m in (atlas_cases, atlas_strategy_tests, forward, geometry, lm_backend))
    paths.update((ROOT / 'experiments/shape_continuation').glob('*.py'))
    return sorted(paths)


def prepare():
    if (OUT / 'manifest.json').exists():
        raise FileExistsError('Preserve the existing MA-002 manifest')
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip()
    write(OUT / 'manifest.json', dict(experiment='MA-002', parent_commit=head, contrasts=CONTRASTS, scenes=SCENES,
                                      sources={str(p.relative_to(ROOT)): digest(p) for p in source_paths()},
                                      sc050_inputs={f'{s}/{n}': digest(SC050 / 'inputs' / s / n)
                                                    for s in SCENES for n in ('truth.json', 'initial.json')}))
    print('FROZEN', len(source_paths()), 'sources at', head, flush=True)


def verify():
    m = sc.read(OUT / 'manifest.json')
    for path, value in m['sources'].items():
        assert digest(ROOT / path) == value, 'Frozen source changed: ' + path
    for key, value in m['sc050_inputs'].items():
        assert digest(SC050 / 'inputs' / key) == value, 'SC-050 input changed: ' + key


def generate_one(contrast):
    set_contrast(contrast)
    s = sc050()
    template = ast.catalog_only('circle_to_c')
    for scene in SCENES:
        folder = OUT / 'inputs' / tag(contrast) / scene
        if (folder / 'qualification.json').exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
        a, b = [s.predictions(truth, template, n) for n in (1024, 2048)]
        disc = ac.relative(a, b)
        check = dict(passed=bool(max(disc) <= 1e-8), contrast=contrast, refinement_relative=disc, units=38,
                     seconds=time.perf_counter() - started)
        write(folder / 'observations.json', dict(observed_real=b.real, observed_imag=b.imag, clean_real=b.real,
                                                 clean_imag=b.imag, frequencies_hz=ac.CATALOG_HZ,
                                                 realized_noise_relative=np.zeros(len(ac.CATALOG_HZ))))
        write(folder / 'qualification.json', check)
        print('INPUT', contrast, scene, check['passed'], f'{max(disc):.2e}', flush=True)


def generate():
    verify()
    for contrast in CONTRASTS:   # one process per contrast keeps the override process-local
        subprocess.run([sys.executable, '-c', f'from experiments.modal_atlas.contrast_screen import generate_one; '
                        f'generate_one({contrast!r})'], check=True, cwd=ROOT)


# ------------------------------------------------------------------ attempts

def fitting_data(contrast, scene):
    # Deliberately no truth path in this entry point.
    d = sc.read(OUT / 'inputs' / tag(contrast) / scene / 'observations.json')
    return (ac.observations(np.array(d['observed_real']) + 1j * np.array(d['observed_imag'])),
            ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'initial.json')))


def attempt(contrast, scene, arm='localize_low'):
    """SC-050's `attempt`, verbatim in logic, with MA-002 folders and the contrast override."""
    verify()
    set_contrast(contrast)
    s = sc050()
    old, c = s.old, s.c
    from experiments.shape_continuation.lm_backend import (Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA,
                                                            stage_record)
    from experiments.spd014_geometry.runtime import geometry_acceleration
    from ordered_boundary.validation_cache import geometry_validation
    folder = OUT / 'runs' / tag(contrast) / scene
    if (folder / 'result.json').exists():
        return sc.read(folder / 'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    if not sc.read(OUT / 'inputs' / tag(contrast) / scene / 'qualification.json')['passed']:
        row = dict(scene=scene, contrast=contrast, arm=arm, outcome='WITHHELD_INPUT', recovered=False)
        write(folder / 'result.json', row)
        return row
    catalog, initial = fitting_data(contrast, scene)
    stages, config = s.setup(catalog, arm)
    curve = c.resize(initial, stages[0].curve_modes)
    write(folder / 'configuration.json', dict(scene=scene, arm=arm, contrast=contrast,
                                              initial=ast.curve_record(curve),
                                              stages=[stage_record(x) for x in stages], backend=asdict(config),
                                              fit_cap=s.FIT_CAP, fit_seconds=s.FIT_SECONDS))
    started = time.perf_counter()
    last_stage = stages[0]
    accepted, rows, loc, ledger = [], [], dict(units=0, seconds=0.), None
    with geometry_acceleration('both'):
        try:
            pre = s.audit(curve, last_stage, config, catalog, folder, 'initial')
            if not pre['passed']:
                raise RuntimeError('Initial full-catalog audit failed')
            fit_started = time.perf_counter()
            curve, loc = s.localize(catalog, folder)
            ledger = Ledger(cap=s.FIT_CAP - loc['units'], seconds=max(0., s.FIT_SECONDS - loc['seconds']))
            update = c.reference.ProjectedUpdate(sc.LENGTH)
            outcome = 'COMPLETED_SCHEDULE'
            for stage in stages:
                last_stage = stage
                if stage.label == 'fixed_M25':
                    curve, _ = c.treatment(curve, 'once', 0)
                else:
                    curve = c.resize(curve, stage.curve_modes)
                try:
                    ledger.begin_stage(stage.label, stage.quota)
                except Stop as exc:
                    outcome = exc.code
                    break

                def checkpoint(iteration, evaluation, stage=stage):
                    accepted.append(dict(stage=stage.label, iteration=iteration, M=stage.update_modes,
                                         loss=evaluation.loss, units=loc['units'] + ledger.units,
                                         curve=ast.curve_record(evaluation.curve)))
                    write(folder / 'accepted.json', dict(states=accepted))
                with geometry_validation('cache'):
                    result = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
                curve = result.curve
                row = dict(stage=stage.label, M=stage.update_modes, K=stage.curve_modes, outcome=result.outcome,
                           stop=result.stop_reason, detail=result.detail, accepted_steps=result.accepted_steps,
                           initial_loss=result.initial_loss, final_loss=result.final_loss, work=ledger.snapshot(),
                           seconds=result.seconds, curve=ast.curve_record(curve))
                rows.append(row)
                write(folder / f'{stage.label}.json', dict(row, history=result.history, trials=result.trials,
                                                          acceptance_checks=result.acceptance_checks))
                write(folder / 'checkpoint.json', dict(stages=rows, curve=ast.curve_record(curve),
                                                       work=ledger.snapshot()))
                print('STAGE', contrast, scene, stage.label, result.outcome, result.final_loss, ledger.units,
                      flush=True)
                if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                    outcome = result.outcome
                    break
            fit_seconds = time.perf_counter() - fit_started
            final = s.audit(curve, last_stage, config, catalog, folder, 'final')
            endpoint_started = time.perf_counter()
            pred = s.predictions(curve, catalog, last_stage.refined_nodes)
            observed = np.column_stack([o.scattered for o in catalog])
            residual = ac.relative(pred, observed)
            endpoint_seconds = time.perf_counter() - endpoint_started
            # Truth loaded only after the fit and independent audit have returned.
            truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
            metrics = old.score(curve, truth)
            recovered = bool(final['passed'] and metrics['rms_mm'] <= 1. and metrics['hausdorff_upper_mm'] <= 2.
                             and np.all(residual <= .003))
            row = dict(scene=scene, contrast=contrast, arm=arm, outcome=outcome, recovered=recovered,
                       metrics=metrics, final_curve=ast.curve_record(curve), initial_audit_passed=pre['passed'],
                       final_audit_passed=final['passed'], relative_residual=residual,
                       maximum_residual=float(max(residual)),
                       localization={k: v for k, v in loc.items() if k != 'rows'}, fit_work=ledger.snapshot(),
                       fit_and_localization_units=loc['units'] + ledger.units,
                       fit_and_localization_seconds=fit_seconds, endpoint_seconds=endpoint_seconds,
                       seconds=time.perf_counter() - started, stages=rows)
        except Exception:
            row = dict(scene=scene, contrast=contrast, arm=arm, outcome='EXCEPTION', recovered=False,
                       traceback=traceback.format_exc(), last_curve=ast.curve_record(curve), stages=rows,
                       work=None if ledger is None else ledger.snapshot(),
                       localization={k: v for k, v in loc.items() if k != 'rows'},
                       seconds=time.perf_counter() - started)
    write(folder / 'result.json', row)
    print('RESULT', contrast, scene, row['outcome'], row['recovered'], row.get('metrics'), flush=True)
    return row


def _job(args):
    contrast, scene = args
    log = OUT / 'logs' / f'{tag(contrast)}_{scene}.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a') as handle:
        code = subprocess.run([sys.executable, '-m', 'experiments.modal_atlas.contrast_screen', 'attempt',
                               '--contrast', repr(contrast), '--scene', scene], cwd=ROOT,
                              stdout=handle, stderr=subprocess.STDOUT).returncode
    return contrast, scene, code


def campaign(workers):
    verify()
    jobs = [(c, s) for c in CONTRASTS for s in SCENES]
    with ProcessPoolExecutor(workers) as pool:
        for contrast, scene, code in pool.map(_job, jobs):
            print('DONE', contrast, scene, code, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('census', 'mie', 'prepare', 'generate', 'attempt', 'campaign', 'verify'))
    parser.add_argument('--contrast', type=float)
    parser.add_argument('--scene', choices=SCENES)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.phase == 'attempt':
        attempt(args.contrast, args.scene)
    elif args.phase == 'campaign':
        campaign(args.workers)
    else:
        globals()[args.phase]()


if __name__ == '__main__':
    main()
