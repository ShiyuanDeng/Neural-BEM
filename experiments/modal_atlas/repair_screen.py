"""MA-003: exterior-band (B) and dense exact-Mie localization (L) repairs, separately and together.

Plan: docs/iterations/modal_atlas/iteration_03/03_plan.md. Run from the
repository root with PYTHONPATH=solvers:. and one BLAS thread:

    python -m experiments.modal_atlas.repair_screen prepare
    python -m experiments.modal_atlas.repair_screen replay            # frozen arm must equal MA-002
    python -m experiments.modal_atlas.repair_screen development --workers 4
    python -m experiments.modal_atlas.repair_screen gate
    python -m experiments.modal_atlas.repair_screen generate           # transfer inputs
    python -m experiments.modal_atlas.repair_screen transfer --workers 4

The attempt logic is MA-002's `contrast_screen.attempt` (itself SC-050's),
with the arm selecting the localization and the prefix band only.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import (SC050, SCENES, OUT as MA002, digest, sc050, set_contrast,
                                                     tag, write)

ROOT = sc.ROOT
OUT = ROOT / 'results/validation/modal_atlas/MA-003'
ARMS = ('frozen', 'band', 'mie', 'both')
DEVELOPMENT = [(a, c, s) for a in ('band',) for c in (2.0, 4.0, 13.3) for s in SCENES] + \
              [(a, c, s) for a in ('mie', 'both') for c in (0.5, 2.0, 4.0, 13.3) for s in SCENES]
TRANSFER_SCENES = ('opposite_c', 'shifted_rotated_c', 'new_thin_c', 'noisy_asymmetric')
TRANSFER = [(a, c, s) for c in (4.0, 13.3) for s in TRANSFER_SCENES for a in ('frozen', 'both')]


# ------------------------------------------------------------------ repairs

def exterior_band(stages):
    """B: prefix stages 1-4 use M = floor(3 k_e) at their highest frequency and K = 2M + 2."""
    out = []
    for stage in stages:
        if stage.label.startswith('stage_'):
            k = max(o.wavenumber for o in stage.observations)
            m = int(np.floor(3 * k))
            stage = replace(stage, update_modes=m, curve_modes=2 * m + 2)
        out.append(stage)
    return out


def localize_mie(catalog, folder, contrast, s):
    """L: SC-050's objective on a dense exact-Mie grid, SC-050's coordinate search, then BIE qualification."""
    from experiments.modal_atlas import mie_localize as ml
    from experiments.modal_atlas.diagnose import dense_landscape
    started = time.perf_counter()
    obs = catalog[:3]
    observed = np.column_stack([o.scattered for o in obs])
    norms = np.linalg.norm(observed, axis=0)
    centers_m, radii_m, L = dense_landscape(obs, contrast)
    grid_seconds = time.perf_counter() - started

    def admissible(x):
        return .015 <= x[2] <= .075 and np.all(x[:2] - x[2] >= .2) and np.all(x[:2] + x[2] <= .8)

    def mie(x):
        if not admissible(x):
            return np.inf
        centre = (complex(*x[:2]) - sc.CENTER) / sc.LENGTH
        return float(ml.landscape(obs, contrast, [centre], [x[2] / sc.LENGTH])[0, 0])

    def refine(x):
        value, steps = mie(x), np.array([.004, .004, .001])
        for _ in range(12):
            neighbours = [(mie(x + sign * steps[j] * np.eye(3)[j]), x + sign * steps[j] * np.eye(3)[j])
                          for j in range(3) for sign in (-1, 1)]
            candidate, p = min(neighbours, key=lambda row: row[0])
            if candidate < value:
                value, x = candidate, p
            else:
                steps = steps / 2
        return x, value

    # Distinct grid minima, best first (at least 8 mm or 4 mm radius apart).
    flat = np.argsort(L, axis=None)
    starts = []
    for index in flat[:5000]:
        i, j = np.unravel_index(index, L.shape)
        if not np.isfinite(L[i, j]):
            break
        x = np.array([centers_m[i].real, centers_m[i].imag, radii_m[j]])
        if all(np.hypot(*(x[:2] - y[:2])) > .008 or abs(x[2] - y[2]) > .004 for y in starts):
            starts.append(x)
        if len(starts) == 5:
            break
    units, records = 0, []
    for rank, x0 in enumerate(starts):
        x, value = refine(x0)
        curve = ast_circle(x)
        a, b = [s.predictions(curve, obs, n) for n in (512, 1024)]
        units += 2 * len(obs)
        disc = ac.relative(a, b)
        bie = .5 * float(np.mean((np.linalg.norm(b - observed, axis=0) / norms) ** 2))
        passed = bool(np.all(np.isfinite(disc)) and max(disc) <= 1e-7)
        records.append(dict(rank=rank, grid_start=x0, parameters_m=x, mie_loss=value, bie_loss=bie,
                            field_relative=disc, qualified=passed))
        if passed:
            break
    else:
        raise RuntimeError('No qualified Mie localization candidate')
    row = dict(method='dense exact-Mie grid + SC-050 coordinate search', parameters_m=x, loss=bie, mie_loss=value,
               units=units, seconds=time.perf_counter() - started, grid_seconds=grid_seconds,
               grid=dict(centres_m=[.28, .72, .004], radii_m=[.015, .075, .001]), candidates=records,
               frequencies_hz=ac.CATALOG_HZ[:3])
    write(folder / 'localization.json', row)
    print('LOCALIZED', folder.parent.name, folder.name, np.round(x, 5).tolist(), 'units', units, flush=True)
    return curve, row


def ast_circle(x):
    from experiments.shape_continuation.geometry import FourierCurve
    return FourierCurve.circle(x[2] / sc.LENGTH, (complex(*x[:2]) - sc.CENTER) / sc.LENGTH)


# ------------------------------------------------------------------ inputs

def input_folder(contrast, scene):
    if scene in SCENES:
        return MA002 / 'inputs' / tag(contrast) / scene
    return OUT / 'inputs' / tag(contrast) / scene


def fitting_data(contrast, scene):
    # Deliberately no truth path in this entry point.
    d = sc.read(input_folder(contrast, scene) / 'observations.json')
    return (ac.observations(np.array(d['observed_real']) + 1j * np.array(d['observed_imag'])),
            ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'initial.json')))


def generate_one(contrast):
    set_contrast(contrast)
    s = sc050()
    template = ast.catalog_only('circle_to_c')
    for scene in ('opposite_c', 'shifted_rotated_c', 'new_thin_c', 'new_asymmetric_source'):
        name = 'noisy_asymmetric' if scene == 'new_asymmetric_source' else scene
        folder = OUT / 'inputs' / tag(contrast) / name
        if (folder / 'qualification.json').exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        if name == 'noisy_asymmetric':
            # SC-050's noisy scene: the clean asymmetric data plus its fixed 1% noise draw.
            src = sc.read(MA002 / 'inputs' / tag(contrast) / 'new_asymmetric' / 'observations.json')
            clean = np.array(src['clean_real']) + 1j * np.array(src['clean_imag'])
            qualification = sc.read(MA002 / 'inputs' / tag(contrast) / 'new_asymmetric' / 'qualification.json')
            check = dict(passed=qualification['passed'], contrast=contrast, units=0, reused='MA-002 new_asymmetric')
            d = s.SCENES['noisy_asymmetric']
            sigma = d['noise'] * np.linalg.norm(clean, axis=0) / np.sqrt(2 * len(clean))
            rng = np.random.default_rng(d['seed'])
            data = clean + sigma[None, :] * (rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape))
        else:
            truth = ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'truth.json'))
            a, b = [s.predictions(truth, template, n) for n in (1024, 2048)]
            disc = ac.relative(a, b)
            check = dict(passed=bool(max(disc) <= 1e-8), contrast=contrast, refinement_relative=disc, units=38)
            clean = data = b
        check['seconds'] = time.perf_counter() - started
        write(folder / 'observations.json', dict(observed_real=data.real, observed_imag=data.imag,
                                                 clean_real=clean.real, clean_imag=clean.imag,
                                                 frequencies_hz=ac.CATALOG_HZ,
                                                 realized_noise_relative=ac.relative(data, clean)))
        write(folder / 'qualification.json', check)
        print('INPUT', contrast, name, check['passed'], flush=True)


def generate():
    verify()
    for contrast in (4.0, 13.3):
        subprocess.run([sys.executable, '-c', f'from experiments.modal_atlas.repair_screen import generate_one; '
                        f'generate_one({contrast!r})'], check=True, cwd=ROOT)
    m = sc.read(OUT / 'manifest.json')
    m['transfer_inputs'] = {str(p.relative_to(ROOT)): digest(p) for p in sorted((OUT / 'inputs').rglob('*.json'))}
    write(OUT / 'manifest.json', m)


# ------------------------------------------------------------------ attempts

def source_paths():
    from experiments.modal_atlas import contrast_screen
    paths = set(contrast_screen.source_paths())
    here = ROOT / 'experiments/modal_atlas'
    paths.update(here / f for f in ('repair_screen.py', 'mie_localize.py', 'diagnose.py', 'circle.py'))
    paths.add(ROOT / 'docs/iterations/modal_atlas/iteration_03/03_plan.md')
    return sorted(paths)


def prepare():
    if (OUT / 'manifest.json').exists():
        raise FileExistsError('Preserve the existing MA-003 manifest')
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip()
    write(OUT / 'manifest.json', dict(experiment='MA-003', parent_commit=head, arms=ARMS,
                                      development=DEVELOPMENT, transfer=TRANSFER,
                                      sources={str(p.relative_to(ROOT)): digest(p) for p in source_paths()},
                                      sc050_inputs={f'{s}/{n}': digest(SC050 / 'inputs' / s / n)
                                                    for s in (*SCENES, *TRANSFER_SCENES)
                                                    for n in ('truth.json', 'initial.json')}))
    print('FROZEN', len(source_paths()), 'sources at', head, flush=True)


def verify():
    m = sc.read(OUT / 'manifest.json')
    for path, value in {**m['sources'], **m.get('transfer_inputs', {})}.items():
        assert digest(ROOT / path) == value, 'Frozen file changed: ' + path
    for key, value in m['sc050_inputs'].items():
        assert digest(SC050 / 'inputs' / key) == value, 'SC-050 input changed: ' + key


def attempt(arm, contrast, scene, root=None):
    """MA-002's attempt with the arm's localization and prefix band."""
    verify()
    set_contrast(contrast)
    s = sc050()
    old, c = s.old, s.c
    from experiments.shape_continuation.lm_backend import Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record
    from experiments.spd014_geometry.runtime import geometry_acceleration
    from ordered_boundary.validation_cache import geometry_validation
    folder = (root or OUT / 'runs') / arm / tag(contrast) / scene
    if (folder / 'result.json').exists():
        return sc.read(folder / 'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    if not sc.read(input_folder(contrast, scene) / 'qualification.json')['passed']:
        row = dict(scene=scene, contrast=contrast, arm=arm, outcome='WITHHELD_INPUT', recovered=False)
        write(folder / 'result.json', row)
        return row
    catalog, initial = fitting_data(contrast, scene)
    stages, config = s.setup(catalog, 'localize_low')
    if arm in ('band', 'both'):
        stages = exterior_band(stages)
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
            if arm in ('mie', 'both'):
                curve, loc = localize_mie(catalog, folder, contrast, s)
            else:
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
                print('STAGE', arm, contrast, scene, stage.label, result.outcome, result.final_loss, ledger.units,
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
            noise = np.array(sc.read(input_folder(contrast, scene) / 'observations.json')['realized_noise_relative'])
            noisy = bool(s.SCENES[scene].get('noise'))
            limits = np.maximum(.003, 3 * noise) if noisy else np.full(len(ac.CATALOG_HZ), .003)
            recovered = bool(final['passed'] and metrics['rms_mm'] <= 1. and metrics['hausdorff_upper_mm'] <= 2.
                             and np.all(residual <= limits))
            row = dict(scene=scene, contrast=contrast, arm=arm, outcome=outcome, recovered=recovered, noisy=noisy,
                       metrics=metrics, final_curve=ast.curve_record(curve), initial_audit_passed=pre['passed'],
                       final_audit_passed=final['passed'], relative_residual=residual, residual_limits=limits,
                       maximum_residual=float(max(residual)),
                       localization={k: v for k, v in loc.items() if k not in ('rows', 'candidates')},
                       fit_work=ledger.snapshot(), fit_and_localization_units=loc['units'] + ledger.units,
                       fit_and_localization_seconds=fit_seconds, endpoint_seconds=endpoint_seconds,
                       seconds=time.perf_counter() - started, stages=rows)
        except Exception:
            row = dict(scene=scene, contrast=contrast, arm=arm, outcome='EXCEPTION', recovered=False,
                       traceback=traceback.format_exc(), last_curve=ast.curve_record(curve), stages=rows,
                       work=None if ledger is None else ledger.snapshot(),
                       localization={k: v for k, v in loc.items() if k not in ('rows', 'candidates')},
                       seconds=time.perf_counter() - started)
    write(folder / 'result.json', row)
    print('RESULT', arm, contrast, scene, row['outcome'], row['recovered'], row.get('metrics'), flush=True)
    return row


def replay():
    """The frozen arm must reproduce MA-002's contrast-4 C accepted states exactly."""
    root = OUT / 'replay'
    attempt('frozen', 4.0, 'development_c', root=root)
    mine = sc.read(root / 'frozen/c4/development_c/accepted.json')['states']
    theirs = sc.read(MA002 / 'runs/c4/development_c/accepted.json')['states']
    keys = ('stage', 'iteration', 'M', 'loss', 'units', 'curve')
    same = len(mine) == len(theirs) and all(all(a[k] == b[k] for k in keys) for a, b in zip(mine, theirs))
    write(OUT / 'replay.json', dict(identical=same, states=len(mine), reference=len(theirs)))
    print('REPLAY identical' if same else 'REPLAY DIFFERS', flush=True)
    if not same:
        raise SystemExit(1)


def _job(args):
    arm, contrast, scene = args
    log = OUT / 'logs' / f'{arm}_{tag(contrast)}_{scene}.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a') as handle:
        code = subprocess.run([sys.executable, '-m', 'experiments.modal_atlas.repair_screen', 'attempt', '--arm', arm,
                               '--contrast', repr(contrast), '--scene', scene], cwd=ROOT,
                              stdout=handle, stderr=subprocess.STDOUT).returncode
    return arm, contrast, scene, code


def run(jobs, workers):
    verify()
    with ProcessPoolExecutor(workers) as pool:
        for arm, contrast, scene, code in pool.map(_job, jobs):
            print('DONE', arm, contrast, scene, code, flush=True)


def gate():
    """G1: LB recovers >= 2 of the 4 frozen failures, and all 8 frozen recoveries still recover."""
    rows = []
    for contrast in (0.5, 2.0, 4.0, 13.3):
        for scene in SCENES:
            frozen = sc.read(MA002 / 'runs' / tag(contrast) / scene / 'result.json')['recovered']
            both = sc.read(OUT / 'runs/both' / tag(contrast) / scene / 'result.json')['recovered']
            rows.append(dict(contrast=contrast, scene=scene, frozen=frozen, both=both))
    repaired = sum(r['both'] and not r['frozen'] for r in rows)
    kept = all(r['both'] for r in rows if r['frozen'])
    passed = repaired >= 2 and kept
    write(OUT / 'gate_G1.json', dict(passed=passed, repaired=repaired, kept_all_frozen_recoveries=kept, rows=rows))
    print('G1', 'PASS' if passed else 'FAIL', repaired, kept, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'replay', 'development', 'gate', 'generate', 'transfer',
                                          'attempt', 'verify'))
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--contrast', type=float)
    parser.add_argument('--scene')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.phase == 'attempt':
        attempt(args.arm, args.contrast, args.scene)
    elif args.phase == 'development':
        run(DEVELOPMENT, args.workers)
    elif args.phase == 'transfer':
        assert sc.read(OUT / 'gate_G1.json')['passed'], 'G1 did not pass; transfer withheld'
        run(TRANSFER, args.workers)
    else:
        globals()[args.phase]()


if __name__ == '__main__':
    main()
