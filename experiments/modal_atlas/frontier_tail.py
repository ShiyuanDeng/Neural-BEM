"""MA-005: MA-004's damped start (D), then a band tail up to the observable frontier (DF).

Plan: docs/iterations/modal_atlas/iteration_05/03_plan.md. From the repository
root with PYTHONPATH=solvers:. and one BLAS thread:

    python -m experiments.modal_atlas.frontier_tail prepare
    python -m experiments.modal_atlas.frontier_tail replay       # D reproduces MA-004's c4 C, state for state
    python -m experiments.modal_atlas.frontier_tail development --workers 3
    python -m experiments.modal_atlas.frontier_tail gate
    python -m experiments.modal_atlas.frontier_tail transfer --workers 3

DF changes one thing in D. SC-050's schedule stops at the fixed M = 37 stage,
a band chosen for contrast 0.5. After it, DF measures the 1% observable
frontier (MA-001's column-norm definition) at the current iterate and the
highest catalog frequency. While the released band is below the frontier it
appends fixed stages M = 43, 49, ... (SC-050's fixed-stage step, quota and
settings), stopping at the first M at or above the frontier (at most M = 95,
the K = 192 storage limit). The frontier needs no truth: one solve and one
Jacobian at the iterate, charged 2 work units. Where the frontier is at most
37, DF is D.

DF continues from D's saved endpoint and work ledger; D is deterministic
(`replay` checks this before anything counts). A D attempt that did not
complete its schedule gets no tail, and DF inherits its verdict.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
import subprocess
import sys
import time
import traceback
import warnings

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.modal_atlas.contrast_screen import OUT as MA002, SC050, SCENES, digest, sc050, set_contrast, tag
from experiments.modal_atlas import damped_screen as ds

ROOT = sc.ROOT
OUT = ROOT / 'results/validation/modal_atlas/MA-005'
TAU, STEP, LAST, TOP = 1e-2, 6, 37, 95
DEVELOPMENT = [(c, s) for c in (0.5, 2.0, 4.0, 13.3) for s in SCENES]
TRANSFER = [(c, s) for c in (4.0, 13.3) for s in ds.TRANSFER_SCENES]


def frontier(curve, observation, contrast, nodes=1024):
    """Highest arclength harmonic whose paired-Jacobian column norm is >= TAU of the strongest (p <= TOP)."""
    from experiments.shape_continuation import forward as F
    from experiments.shape_continuation.atlas import orthonormal_normal_basis
    state = F.solve(curve, observation.wavenumber, contrast, observation.acquisition, nodes)
    J = F.shape_jacobian(state, orthonormal_normal_basis(state.curve, TOP))
    norms = np.linalg.norm(J, axis=0)
    per_p = np.r_[norms[0], np.hypot(norms[1::2], norms[2::2])]
    return int(np.nonzero(per_p >= TAU * per_p.max())[0].max()), per_p


def tail_bands(front):
    bands, M = [], LAST
    while M < front and M + STEP <= TOP:
        M += STEP
        bands.append(M)
    return bands


def tail(contrast, scene, parent, root):
    """DF from the D attempt saved under `parent`; writes under `root`/DF."""
    verify()
    set_contrast(contrast)
    ds.install_damped_solve()
    s = sc050()
    from experiments.shape_continuation.lm_backend import Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA
    from experiments.spd014_geometry.runtime import geometry_acceleration
    from ordered_boundary.validation_cache import geometry_validation
    c = s.c
    folder = root / 'DF' / tag(contrast) / scene
    if (folder / 'result.json').exists():
        return sc.read(folder / 'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    source = parent / 'D' / tag(contrast) / scene / 'result.json'
    d = sc.read(source)
    info = dict(parent=str(source.relative_to(ROOT)), parent_digest=digest(source), parent_outcome=d['outcome'])
    if d['outcome'] != 'COMPLETED_SCHEDULE':
        row = dict(d, arm='DF', tail=dict(info, applied=False, reason='D did not complete its schedule'))
        ds.write(folder / 'result.json', row)
        print('RESULT DF', contrast, scene, row['outcome'], row['recovered'], 'no tail', flush=True)
        return row
    real, damped, _ = ds.fitting_data(contrast, scene)
    stages, config = ds.schedule('D', real, damped, s)
    last = stages[-1]
    assert last.label == f'fixed_M{LAST}' and last.update_modes == LAST
    curve = ast.curve_from(d['final_curve'])
    started = time.perf_counter()
    with geometry_acceleration('both'):
        front, profile = frontier(curve, real[-1], contrast)
    bands = tail_bands(front)
    info.update(frontier=front, frontier_k=float(real[-1].wavenumber), column_profile=profile, bands=bands,
                frontier_units=2, frontier_seconds=time.perf_counter() - started)
    ds.write(folder / 'configuration.json', dict(scene=scene, arm='DF', contrast=contrast, tail=info,
                                                 d_units=d['fit_and_localization_units'],
                                                 d_seconds=d['fit_and_localization_seconds']))
    print('FRONTIER', contrast, scene, front, bands, flush=True)
    if not bands:
        row = dict(d, arm='DF', tail=dict(info, applied=False, reason='frontier at or below M = 37'))
        ds.write(folder / 'result.json', row)
        print('RESULT DF', contrast, scene, row['outcome'], row['recovered'], 'no tail', flush=True)
        return row
    units0 = d['fit_and_localization_units'] + 2
    seconds0 = d['fit_and_localization_seconds'] + info['frontier_seconds']
    accepted, rows, ledger = [], [], None
    last_stage = last
    with geometry_acceleration('both'):
        try:
            ledger = Ledger(cap=s.FIT_CAP - units0, seconds=max(0., s.FIT_SECONDS - seconds0))
            update = c.reference.ProjectedUpdate(sc.LENGTH)
            outcome = 'COMPLETED_SCHEDULE'
            fit_started = time.perf_counter()
            for M in bands:
                stage = replace(last, label=f'fixed_M{M}', update_modes=M)
                last_stage = stage
                curve = c.resize(curve, stage.curve_modes)
                try:
                    ledger.begin_stage(stage.label, stage.quota)
                except Stop as exc:
                    outcome = exc.code
                    break

                def checkpoint(iteration, evaluation, stage=stage):
                    accepted.append(dict(stage=stage.label, iteration=iteration, M=stage.update_modes,
                                         loss=evaluation.loss, units=units0 + ledger.units,
                                         curve=ast.curve_record(evaluation.curve)))
                    ds.write(folder / 'accepted.json', dict(states=accepted))
                with geometry_validation('cache'):
                    result = fit_stage(curve, stage, ac.contrast(), update, config, ledger, on_accept=checkpoint)
                curve = result.curve
                row = dict(stage=stage.label, M=M, K=stage.curve_modes, outcome=result.outcome,
                           stop=result.stop_reason, detail=result.detail, accepted_steps=result.accepted_steps,
                           initial_loss=result.initial_loss, final_loss=result.final_loss, work=ledger.snapshot(),
                           seconds=result.seconds, curve=ast.curve_record(curve))
                rows.append(row)
                ds.write(folder / f'{stage.label}.json', dict(row, history=result.history, trials=result.trials,
                                                             acceptance_checks=result.acceptance_checks))
                print('STAGE DF', contrast, scene, stage.label, result.outcome, result.final_loss, ledger.units,
                      flush=True)
                if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                    outcome = result.outcome
                    break
            fit_seconds = time.perf_counter() - fit_started
            final = s.audit(curve, last_stage, config, real, folder, 'final')
            pred = s.predictions(curve, real, last_stage.refined_nodes)
            observed = np.column_stack([o.scattered for o in real])
            residual = ac.relative(pred, observed)
            # Truth loaded only after the fit and independent audit have returned.
            truth = ast.curve_from(sc.read(SC050 / 'inputs' / ('new_asymmetric' if scene == 'noisy_asymmetric'
                                                               else scene) / 'truth.json'))
            metrics = s.old.score(curve, truth)
            noise = np.array(sc.read(ds.real_input(contrast, scene) / 'observations.json')['realized_noise_relative'])
            noisy = bool(s.SCENES[scene].get('noise'))
            limits = np.maximum(.003, 3 * noise) if noisy else np.full(len(ac.CATALOG_HZ), .003)
            recovered = bool(final['passed'] and metrics['rms_mm'] <= 1. and metrics['hausdorff_upper_mm'] <= 2.
                             and np.all(residual <= limits))
            row = dict(scene=scene, contrast=contrast, arm='DF', outcome=outcome, recovered=recovered, noisy=noisy,
                       metrics=metrics, final_curve=ast.curve_record(curve), initial_audit_passed=d['initial_audit_passed'],
                       final_audit_passed=final['passed'], relative_residual=residual, residual_limits=limits,
                       maximum_residual=float(max(residual)), localization=d['localization'],
                       tail=dict(info, applied=True, work=ledger.snapshot(), seconds=fit_seconds),
                       fit_and_localization_units=units0 + ledger.units,
                       fit_and_localization_seconds=seconds0 + fit_seconds,
                       stages=d['stages'] + rows, d_recovered=d['recovered'], d_metrics=d['metrics'])
        except Exception:
            row = dict(scene=scene, contrast=contrast, arm='DF', outcome='EXCEPTION', recovered=False,
                       traceback=traceback.format_exc(), last_curve=ast.curve_record(curve),
                       stages=d['stages'] + rows, tail=dict(info, applied=True,
                                                            work=None if ledger is None else ledger.snapshot()))
    ds.write(folder / 'result.json', row)
    print('RESULT DF', contrast, scene, row['outcome'], row['recovered'], row.get('metrics'), flush=True)
    return row


# ------------------------------------------------------------------ provenance, replay, gates

def source_paths():
    paths = set(ds.source_paths())
    paths.add(ROOT / 'experiments/modal_atlas/frontier_tail.py')
    paths.add(ROOT / 'docs/iterations/modal_atlas/iteration_05/03_plan.md')
    return sorted(paths)


def parents():
    return sorted((ds.OUT / 'runs/D').glob('*/*/result.json'))


def prepare():
    if (OUT / 'manifest.json').exists():
        raise FileExistsError('Preserve the existing MA-005 manifest')
    ds.verify()
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True, cwd=ROOT).strip()
    m4 = ds.OUT / 'manifest.json'
    ds.write(OUT / 'manifest.json', dict(
        experiment='MA-005', parent_commit=head, tau=TAU, step=STEP, last=LAST, top=TOP,
        development=DEVELOPMENT, transfer=TRANSFER, ma004_manifest=digest(m4),
        sources={str(p.relative_to(ROOT)): digest(p) for p in source_paths()},
        d_parents={str(p.relative_to(ROOT)): digest(p) for p in parents()}))
    print('FROZEN', len(source_paths()), 'sources and', len(parents()), 'D parents at', head, flush=True)


def verify():
    ds.verify()
    m = sc.read(OUT / 'manifest.json')
    assert digest(ds.OUT / 'manifest.json') == m['ma004_manifest'], 'MA-004 manifest changed'
    for group in ('sources', 'd_parents'):
        for path, value in m[group].items():
            assert digest(ROOT / path) == value, 'Frozen file changed: ' + path


def replay():
    """D, rerun from scratch, must equal MA-004's contrast-4 C state for state."""
    verify()
    root = OUT / 'replay'
    ds.attempt('D', 4.0, 'development_c', root=root)
    keys = ('stage', 'iteration', 'M', 'loss', 'units', 'curve')
    mine = sc.read(root / 'D/c4/development_c/accepted.json')['states']
    theirs = sc.read(ds.OUT / 'runs/D/c4/development_c/accepted.json')['states']
    same = len(mine) == len(theirs) and all(all(a[k] == b[k] for k in keys) for a, b in zip(mine, theirs))
    ds.write(OUT / 'replay.json', dict(D=same, states=len(mine)))
    print('REPLAY', same, len(mine), flush=True)
    if not same:
        raise SystemExit(1)


def _job(args):
    kind, arm, contrast, scene = args
    log = OUT / 'logs' / f"{'DF' if kind == 'tail' else arm}_{tag(contrast)}_{scene}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, 'a') as handle:
        if kind == 'tail':
            command = ['-m', 'experiments.modal_atlas.frontier_tail', 'tail', '--contrast', repr(contrast),
                       '--scene', scene, '--parent', arm]
        else:
            command = ['-m', 'experiments.modal_atlas.frontier_tail', 'attempt', '--arm', arm,
                       '--contrast', repr(contrast), '--scene', scene]
        code = subprocess.run([sys.executable] + command, cwd=ROOT, stdout=handle,
                              stderr=subprocess.STDOUT).returncode
    return kind, arm, contrast, scene, code


def run(jobs, workers):
    verify()
    with ProcessPoolExecutor(workers) as pool:
        for row in pool.map(_job, jobs):
            print('DONE', *row, flush=True)


def transfer_jobs(contrast, scene):
    """frozen and D from scratch (MA-004's driver, written under MA-005), then the DF tail on that D."""
    for arm in ('frozen', 'D'):
        _job(('attempt', arm, contrast, scene))
    return _job(('tail', 'transfer', contrast, scene))


def gate():
    """G1: DF recovers >= 3 of the 4 MA-002 failures and all 8 earlier recoveries."""
    rows = []
    for contrast in (0.5, 2.0, 4.0, 13.3):
        for scene in SCENES:
            frozen = sc.read(MA002 / 'runs' / tag(contrast) / scene / 'result.json')['recovered']
            d = sc.read(ds.OUT / 'runs/D' / tag(contrast) / scene / 'result.json')['recovered']
            df = sc.read(OUT / 'runs/DF' / tag(contrast) / scene / 'result.json')['recovered']
            rows.append(dict(contrast=contrast, scene=scene, frozen=frozen, D=d, DF=df))
    repaired = sum(r['DF'] and not r['frozen'] for r in rows)
    kept = all(r['DF'] for r in rows if r['frozen'])
    passed = repaired >= 3 and kept
    ds.write(OUT / 'gate_G1.json', dict(passed=passed, repaired=repaired, kept_all_frozen_recoveries=kept, rows=rows))
    print('G1', 'PASS' if passed else 'FAIL', repaired, kept, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'replay', 'development', 'gate', 'transfer', 'tail', 'attempt',
                                          'verify'))
    parser.add_argument('--arm', choices=('frozen', 'D'))
    parser.add_argument('--parent', choices=('development', 'transfer'))
    parser.add_argument('--contrast', type=float)
    parser.add_argument('--scene')
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    warnings.simplefilter('ignore')
    if args.phase == 'tail':
        parent = ds.OUT / 'runs' if args.parent == 'development' else OUT / 'runs'
        tail(args.contrast, args.scene, parent, OUT / 'runs')
    elif args.phase == 'attempt':
        verify()
        ds.attempt(args.arm, args.contrast, args.scene, root=OUT / 'runs')
    elif args.phase == 'development':
        run([('tail', 'development', c, s) for c, s in DEVELOPMENT], args.workers)
    elif args.phase == 'transfer':
        assert sc.read(OUT / 'gate_G1.json')['passed'], 'G1 did not pass; transfer withheld'
        verify()
        with ProcessPoolExecutor(args.workers) as pool:
            for row in pool.map(transfer_jobs, *zip(*TRANSFER)):
                print('DONE', *row, flush=True)
    else:
        globals()[args.phase]()


if __name__ == '__main__':
    main()
