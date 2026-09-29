"""MA-004: damped (complex-frequency) localization and prefix for denser-than-host targets.

Plan: docs/iterations/modal_atlas/iteration_04/03_plan.md. From the repository
root with PYTHONPATH=solvers:. and one BLAS thread:

    python -m experiments.modal_atlas.damped_screen check        # damped solver against Mie
    python -m experiments.modal_atlas.damped_screen prepare
    python -m experiments.modal_atlas.damped_screen generate     # damped (and transfer) observations
    python -m experiments.modal_atlas.damped_screen replay       # frozen = MA-002, LB = MA-003 both
    python -m experiments.modal_atlas.damped_screen development --workers 4
    python -m experiments.modal_atlas.damped_screen gate
    python -m experiments.modal_atlas.damped_screen transfer --workers 4

A complex wavenumber k(1 + i gamma) is the Fourier transform at omega of the
time-domain trace damped by exp(-gamma omega t). Both media scale by the same
complex factor, so the known contrast k_i^2 / k_e^2 is unchanged.

Arms (each adds one principal change to the previous row, and all use MA-003's
exterior band except `frozen`):
  frozen  SC-050 localization, borges band (MA-002's policy)
  LB      dense exact-Mie localization, exterior band (MA-003 `both`)
  R       LB plus one extra undamped stage-4 pass (extra-work control)
  DP      LB, but warm-up and stages 1-4 at damped frequencies, then the
          undamped stage-4 pass, then the unchanged releases
  D       DP with the Mie localization also at damped frequencies
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import warnings

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.inverse import Observation
from experiments.modal_atlas.contrast_screen import SC050, SCENES, OUT as MA002, digest, sc050, set_contrast, tag
from experiments.modal_atlas import repair_screen as ma003

ROOT = sc.ROOT
OUT = ROOT / 'results/validation/modal_atlas/MA-004'
GAMMA = 0.25
ARMS = ('frozen', 'LB', 'R', 'DP', 'D')
TRANSFER_SCENES = ('opposite_c', 'shifted_rotated_c', 'new_thin_c', 'noisy_asymmetric')
DEVELOPMENT = ([('D', c, s) for c in (0.5, 2.0, 4.0, 13.3) for s in SCENES]
               + [(a, c, s) for a in ('DP', 'R') for c in (4.0, 13.3) for s in SCENES])
TRANSFER = [(a, c, s) for c in (4.0, 13.3) for s in TRANSFER_SCENES for a in ('frozen', 'D')]


def write(path, value):
    def portable(item):
        if isinstance(item, (complex, np.complexfloating)):
            return dict(real=float(np.real(item)), imag=float(np.imag(item)))
        if isinstance(item, dict):
            return {k: portable(v) for k, v in item.items()}
        if isinstance(item, (list, tuple)):
            return [portable(v) for v in item]
        if isinstance(item, np.ndarray) and np.iscomplexobj(item):
            return dict(real=item.real, imag=item.imag)
        return item
    sc.write(Path(path), portable(value))


@dataclass(frozen=True)
class DampedObservation(Observation):
    """An observation at a complex wavenumber with positive real and imaginary parts."""

    def __post_init__(self):
        data = np.array(self.scattered, complex, copy=True)
        if data.shape != self.acquisition.data_shape or not np.isfinite(data).all():
            raise ValueError('Scattered data must match the acquisition and be finite.')
        k = complex(self.wavenumber)
        if not (np.isfinite(k.real) and np.isfinite(k.imag) and k.real > 0 and k.imag > 0):
            raise ValueError('Damped wavenumber must have positive real and imaginary parts.')
        data.setflags(write=False)
        object.__setattr__(self, 'scattered', data)


def install_damped_solve():
    """Route the fit loop's solves through the complex-capable solve, with geometry validation kept.

    Real wavenumbers still go to the unchanged `forward.solve` (CUDA default).
    """
    from experiments.shape_continuation import forward as F, lm_backend
    from experiments.shape_continuation.geometry_runtime import geometry_validated
    from experiments.modal_atlas import damped
    original = F.solve
    validated = geometry_validated(damped.solve)

    def dispatch(shape, wavenumber, contrast, acquisition, nodes, *, work=None):
        if complex(wavenumber).imag == 0:
            return original(shape, wavenumber, contrast, acquisition, nodes, work=work)
        return validated(shape, wavenumber, contrast, acquisition, nodes, work=work)
    lm_backend.solve = dispatch
    return dispatch


# ------------------------------------------------------------------ inputs

def real_input(contrast, scene):
    if scene in SCENES:
        return MA002 / 'inputs' / tag(contrast) / scene
    return OUT / 'inputs' / tag(contrast) / scene


def damped_input(contrast, scene):
    return OUT / 'inputs' / tag(contrast) / scene / f'damped_{GAMMA:g}'


def read_data(folder):
    d = sc.read(folder / 'observations.json')
    return np.array(d['observed_real']) + 1j * np.array(d['observed_imag'])


def fitting_data(contrast, scene):
    # Deliberately no truth path in this entry point.
    real = ac.observations(read_data(real_input(contrast, scene)))
    values = read_data(damped_input(contrast, scene))
    damped = tuple(DampedObservation(o.wavenumber * (1 + 1j * GAMMA), o.acquisition, values[:, j])
                   for j, o in enumerate(real))
    return real, damped, ast.curve_from(sc.read(SC050 / 'inputs' / scene / 'initial.json'))


def generate_one(contrast):
    from experiments.modal_atlas import damped
    set_contrast(contrast)
    s = sc050()
    template = ast.catalog_only('circle_to_c')
    noise = s.SCENES['noisy_asymmetric']
    for scene in (*SCENES, *TRANSFER_SCENES):
        if contrast not in (4.0, 13.3) and scene in TRANSFER_SCENES:
            continue
        source = 'new_asymmetric' if scene == 'noisy_asymmetric' else scene
        truth = ast.curve_from(sc.read(SC050 / 'inputs' / source / 'truth.json'))
        # Real-frequency transfer data (development data are MA-002's).
        if scene in TRANSFER_SCENES:
            folder = OUT / 'inputs' / tag(contrast) / scene
            if not (folder / 'qualification.json').exists():
                folder.mkdir(parents=True, exist_ok=True)
                if scene == 'noisy_asymmetric':
                    clean = read_data(MA002 / 'inputs' / tag(contrast) / 'new_asymmetric')
                    check = dict(passed=sc.read(MA002 / 'inputs' / tag(contrast) / 'new_asymmetric' /
                                                'qualification.json')['passed'], reused='MA-002 new_asymmetric')
                    sigma = noise['noise'] * np.linalg.norm(clean, axis=0) / np.sqrt(2 * len(clean))
                    rng = np.random.default_rng(noise['seed'])
                    data = clean + sigma[None, :] * (rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape))
                else:
                    a, b = [s.predictions(truth, template, n) for n in (1024, 2048)]
                    disc = ac.relative(a, b)
                    check = dict(passed=bool(max(disc) <= 1e-8), refinement_relative=disc)
                    clean = data = b
                write(folder / 'observations.json', dict(observed_real=data.real, observed_imag=data.imag,
                                                         clean_real=clean.real, clean_imag=clean.imag,
                                                         frequencies_hz=ac.CATALOG_HZ,
                                                         realized_noise_relative=ac.relative(data, clean)))
                write(folder / 'qualification.json', dict(check, contrast=contrast))
                print('INPUT', contrast, scene, check['passed'], flush=True)
        # Damped data at k (1 + i gamma), every catalog frequency.
        folder = damped_input(contrast, scene)
        if (folder / 'qualification.json').exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        ks = [o.wavenumber * (1 + 1j * GAMMA) for o in template]
        a, b = [np.column_stack([damped.solve(truth, k, contrast, o.acquisition, n).prediction
                                 for k, o in zip(ks, template)]) for n in (1024, 2048)]
        disc = ac.relative(a, b)
        clean = data = b
        if scene == 'noisy_asymmetric':
            # Same relative noise model as SC-050, independent draw for the damped transform.
            sigma = noise['noise'] * np.linalg.norm(clean, axis=0) / np.sqrt(2 * len(clean))
            rng = np.random.default_rng(noise['seed'] + 1)
            data = clean + sigma[None, :] * (rng.normal(size=clean.shape) + 1j * rng.normal(size=clean.shape))
        write(folder / 'observations.json', dict(observed_real=data.real, observed_imag=data.imag,
                                                 clean_real=clean.real, clean_imag=clean.imag, gamma=GAMMA,
                                                 wavenumbers_real=np.real(ks), wavenumbers_imag=np.imag(ks),
                                                 realized_noise_relative=ac.relative(data, clean)))
        write(folder / 'qualification.json', dict(passed=bool(max(disc) <= 1e-8), refinement_relative=disc,
                                                  contrast=contrast, gamma=GAMMA))
        print('DAMPED INPUT', contrast, scene, bool(max(disc) <= 1e-8), f'{max(disc):.1e}', flush=True)


def generate():
    verify(inputs=False)
    for contrast in (0.5, 2.0, 4.0, 13.3):
        subprocess.run([sys.executable, '-c', f'from experiments.modal_atlas.damped_screen import generate_one; '
                        f'generate_one({contrast!r})'], check=True, cwd=ROOT)
    m = sc.read(OUT / 'manifest.json')
    m['inputs'] = {str(p.relative_to(ROOT)): digest(p) for p in sorted((OUT / 'inputs').rglob('*.json'))}
    write(OUT / 'manifest.json', m)


def check():
    """The damped Kress solve against exact Mie series on the 5 cm disk, every contrast and frequency."""
    from experiments.modal_atlas import circle, damped
    from experiments.shape_continuation.geometry import FourierCurve
    warnings.simplefilter('ignore')
    disk = FourierCurve.circle(1.0)
    rows = []
    for contrast in (0.5, 2.0, 4.0, 13.3):
        for o in ast.catalog_only('circle_to_c'):
            k = o.wavenumber * (1 + 1j * GAMMA)
            kress = damped.solve(disk, k, contrast, o.acquisition, 1024).prediction / o.acquisition.strength
            s, r = o.acquisition.sources, o.acquisition.receivers
            exact = np.array([circle.scattered(k, contrast, np.hypot(*a), np.arctan2(a[1], a[0]),
                                               np.hypot(*b), np.arctan2(b[1], b[0]), 80)[0] for a, b in zip(s, r)])
            rows.append(dict(contrast=contrast, k=[k.real, k.imag],
                             relative=float(np.linalg.norm(kress - exact) / np.linalg.norm(exact))))
    worst = max(r['relative'] for r in rows)
    OUT.mkdir(parents=True, exist_ok=True)
    write(OUT / 'damped_mie_check.json', dict(gamma=GAMMA, nodes=1024, worst_relative=worst,
                                             passed=bool(worst <= 1e-8), rows=rows))
    print('DAMPED MIE CHECK worst', worst, flush=True)


# ------------------------------------------------------------------ localization

def localize_damped_mie(damped_obs, folder, contrast):
    """MA-003's dense Mie localization, on the damped data; BIE qualification at the damped frequencies."""
    from experiments.modal_atlas import damped, mie_localize as ml
    from experiments.modal_atlas.diagnose import dense_grid
    started = time.perf_counter()
    obs = damped_obs[:3]
    observed = np.column_stack([o.scattered for o in obs])
    norms = np.linalg.norm(observed, axis=0)
    centers_m, radii_m, centers, radii, inside = dense_grid()
    cut = int(np.ceil(max(abs(o.wavenumber) for o in obs) * np.sqrt(max(contrast, 1)) * radii.max() + 30))
    L = np.concatenate([ml.landscape(obs, contrast, centers[i:i + 800], radii, cutoff=cut)
                        for i in range(0, len(centers), 800)])
    L = np.where(inside, L, np.inf)
    grid_seconds = time.perf_counter() - started

    def mie(x):
        if not (.015 <= x[2] <= .075 and np.all(x[:2] - x[2] >= .2) and np.all(x[:2] + x[2] <= .8)):
            return np.inf
        centre = (complex(*x[:2]) - sc.CENTER) / sc.LENGTH
        return float(ml.landscape(obs, contrast, [centre], [x[2] / sc.LENGTH], cutoff=cut)[0, 0])

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

    starts = []
    for index in np.argsort(L, axis=None)[:5000]:
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
        curve = ma003.ast_circle(x)
        a, b = [np.column_stack([damped.solve(curve, o.wavenumber, contrast, o.acquisition, n).prediction
                                 for o in obs]) for n in (512, 1024)]
        units += 2 * len(obs)
        disc = ac.relative(a, b)
        bie = .5 * float(np.mean((np.linalg.norm(b - observed, axis=0) / norms) ** 2))
        passed = bool(np.all(np.isfinite(disc)) and max(disc) <= 1e-7)
        records.append(dict(rank=rank, grid_start=x0, parameters_m=x, mie_loss=value, bie_loss=bie,
                            field_relative=disc, qualified=passed))
        if passed:
            break
    else:
        raise RuntimeError('No qualified damped Mie localization candidate')
    row = dict(method=f'dense exact-Mie grid on damped data (gamma {GAMMA}) + SC-050 coordinate search',
               parameters_m=x, loss=bie, mie_loss=value, units=units, seconds=time.perf_counter() - started,
               grid_seconds=grid_seconds, candidates=records, gamma=GAMMA)
    write(folder / 'localization.json', row)
    print('LOCALIZED', folder.name, np.round(x, 5).tolist(), 'units', units, flush=True)
    return curve, row


# ------------------------------------------------------------------ schedule and attempts

def schedule(arm, real, damped, s):
    stages, config = s.setup(real, 'localize_low')
    if arm == 'frozen':
        return stages, config
    stages = ma003.exterior_band(stages)
    prefix, rest = stages[:5], stages[5:]          # warm-up and stages 1-4; releases and fixed stages
    assert [x.label for x in prefix] == ['warmup_025', 'stage_1', 'stage_2', 'stage_3', 'stage_4']
    undamp = replace(prefix[-1], label='stage_4_undamped')
    if arm == 'LB':
        return prefix + rest, config
    if arm == 'R':
        return prefix + [undamp] + rest, config
    lookup = {round(o.wavenumber, 9): d for o, d in zip(real, damped)}
    damped_prefix = [replace(x, label=f'{x.label}_damped',
                             observations=tuple(lookup[round(o.wavenumber, 9)] for o in x.observations))
                     for x in prefix]
    return damped_prefix + [undamp] + rest, config


def attempt(arm, contrast, scene, root=None):
    verify()
    set_contrast(contrast)
    install_damped_solve()
    s = sc050()
    old, c = s.old, s.c
    from experiments.shape_continuation.lm_backend import Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record
    from experiments.spd014_geometry.runtime import geometry_acceleration
    from ordered_boundary.validation_cache import geometry_validation
    folder = (root or OUT / 'runs') / arm / tag(contrast) / scene
    if (folder / 'result.json').exists():
        return sc.read(folder / 'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    passed = sc.read(real_input(contrast, scene) / 'qualification.json')['passed'] and \
        sc.read(damped_input(contrast, scene) / 'qualification.json')['passed']
    if not passed:
        row = dict(scene=scene, contrast=contrast, arm=arm, outcome='WITHHELD_INPUT', recovered=False)
        write(folder / 'result.json', row)
        return row
    real, damped, initial = fitting_data(contrast, scene)
    stages, config = schedule(arm, real, damped, s)
    curve = c.resize(initial, stages[0].curve_modes)
    write(folder / 'configuration.json', dict(scene=scene, arm=arm, contrast=contrast, gamma=GAMMA,
                                              initial=ast.curve_record(curve),
                                              stages=[stage_record(x) for x in stages], backend=asdict(config),
                                              fit_cap=s.FIT_CAP, fit_seconds=s.FIT_SECONDS))
    started = time.perf_counter()
    last_stage = stages[0]
    accepted, rows, loc, ledger = [], [], dict(units=0, seconds=0.), None
    with geometry_acceleration('both'):
        try:
            # Initial audit exactly as MA-002/MA-003: SC-049's all-frequency stage built from the real warm-up.
            template = s.setup(real, 'localize_low')[0][0]
            pre = s.audit(curve, template, config, real, folder, 'initial')
            if not pre['passed']:
                raise RuntimeError('Initial full-catalog audit failed')
            fit_started = time.perf_counter()
            if arm == 'D':
                curve, loc = localize_damped_mie(damped, folder, contrast)
            elif arm == 'frozen':
                curve, loc = s.localize(real, folder)
            else:
                curve, loc = ma003.localize_mie(real, folder, contrast, s)
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
            final = s.audit(curve, last_stage, config, real, folder, 'final')
            endpoint_started = time.perf_counter()
            pred = s.predictions(curve, real, last_stage.refined_nodes)
            observed = np.column_stack([o.scattered for o in real])
            residual = ac.relative(pred, observed)
            endpoint_seconds = time.perf_counter() - endpoint_started
            # Truth loaded only after the fit and independent audit have returned.
            source = 'new_asymmetric' if scene == 'noisy_asymmetric' else scene
            truth = ast.curve_from(sc.read(SC050 / 'inputs' / source / 'truth.json'))
            metrics = old.score(curve, truth)
            noise = np.array(sc.read(real_input(contrast, scene) / 'observations.json')['realized_noise_relative'])
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


# ------------------------------------------------------------------ provenance, replay, gates

def source_paths():
    paths = set(ma003.source_paths())
    here = ROOT / 'experiments/modal_atlas'
    paths.update(here / f for f in ('damped_screen.py', 'damped.py', 'repair_screen.py'))
    paths.add(ROOT / 'docs/iterations/modal_atlas/iteration_04/03_plan.md')
    return sorted(paths)


def prepare():
    if (OUT / 'manifest.json').exists():
        raise FileExistsError('Preserve the existing MA-004 manifest')
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip()
    write(OUT / 'manifest.json', dict(experiment='MA-004', parent_commit=head, gamma=GAMMA, arms=ARMS,
                                      development=DEVELOPMENT, transfer=TRANSFER,
                                      sources={str(p.relative_to(ROOT)): digest(p) for p in source_paths()}))
    print('FROZEN', len(source_paths()), 'sources at', head, flush=True)


def verify(inputs=True):
    m = sc.read(OUT / 'manifest.json')
    for path, value in m['sources'].items():
        assert digest(ROOT / path) == value, 'Frozen source changed: ' + path
    if inputs:
        assert m.get('inputs'), 'Inputs not generated'
        for path, value in m['inputs'].items():
            assert digest(ROOT / path) == value, 'Frozen input changed: ' + path


def replay():
    """frozen must equal MA-002's c4 C and LB must equal MA-003's `both` c4 C, state for state."""
    root = OUT / 'replay'
    keys = ('stage', 'iteration', 'M', 'loss', 'units', 'curve')
    out = {}
    for arm, reference in (('frozen', MA002 / 'runs/c4/development_c'), ('LB', ma003.OUT / 'runs/both/c4/development_c')):
        attempt(arm, 4.0, 'development_c', root=root)
        mine = sc.read(root / arm / 'c4/development_c/accepted.json')['states']
        theirs = sc.read(reference / 'accepted.json')['states']
        out[arm] = len(mine) == len(theirs) and all(all(a[k] == b[k] for k in keys) for a, b in zip(mine, theirs))
    write(OUT / 'replay.json', out)
    print('REPLAY', out, flush=True)
    if not all(out.values()):
        raise SystemExit(1)


def _job(args):
    arm, contrast, scene = args
    log = OUT / 'logs' / f'{arm}_{tag(contrast)}_{scene}.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a') as handle:
        code = subprocess.run([sys.executable, '-m', 'experiments.modal_atlas.damped_screen', 'attempt',
                               '--arm', arm, '--contrast', repr(contrast), '--scene', scene], cwd=ROOT,
                              stdout=handle, stderr=subprocess.STDOUT).returncode
    return arm, contrast, scene, code


def run(jobs, workers):
    verify()
    with ProcessPoolExecutor(workers) as pool:
        for arm, contrast, scene, code in pool.map(_job, jobs):
            print('DONE', arm, contrast, scene, code, flush=True)


def gate():
    """G1: D recovers >= 3 of the 4 MA-002 failures and all 8 earlier recoveries."""
    rows = []
    for contrast in (0.5, 2.0, 4.0, 13.3):
        for scene in SCENES:
            frozen = sc.read(MA002 / 'runs' / tag(contrast) / scene / 'result.json')['recovered']
            d = sc.read(OUT / 'runs/D' / tag(contrast) / scene / 'result.json')['recovered']
            rows.append(dict(contrast=contrast, scene=scene, frozen=frozen, D=d))
    repaired = sum(r['D'] and not r['frozen'] for r in rows)
    kept = all(r['D'] for r in rows if r['frozen'])
    passed = repaired >= 3 and kept
    write(OUT / 'gate_G1.json', dict(passed=passed, repaired=repaired, kept_all_frozen_recoveries=kept, rows=rows))
    print('G1', 'PASS' if passed else 'FAIL', repaired, kept, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('check', 'prepare', 'generate', 'replay', 'development', 'gate',
                                          'transfer', 'attempt', 'verify'))
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
