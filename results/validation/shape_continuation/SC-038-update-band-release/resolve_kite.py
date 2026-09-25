"""One 768/1536-node rerun of kite's last two M-release stages."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from pathlib import Path
import importlib.util
import os
import sys
import time
import traceback
import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc038_original', HERE / 'run.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
ac, ast, sc = base.ac, base.ast, base.sc
from experiments.shape_continuation.forward import solve
from experiments.shape_continuation.lm_backend import Ledger, Objective, Stop, relative_columns, stage_record

OUT = HERE / 'dense_kite'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_19/04_resolution_followup.md'


def hashes():
    return dict(base.hashes(), **{str(p.relative_to(sc.ROOT)): sc.digest(p)
                for p in (Path(__file__).resolve(), PLAN)})


def start(arm):
    folder = HERE / 'runs/kite' / arm
    curve = ast.curve_from(sc.read(folder / 'release_1_history.json')['history'][-1]['coefficients'])
    record = sc.read(folder / 'result.json')
    first = record['stages'][0]['work']['work_units']
    return curve, record['prefix_units'] + first


def schedules(arm):
    stages, config, catalog = base.schedules('kite', arm)
    stages = [replace(s, label=f'dense_{i}', nodes=768, refined_nodes=1536)
              for i, s in enumerate(stages[1:], 2)]
    return stages, config, catalog


def audit(arm, final=False):
    curve = ast.curve_from(sc.read(OUT / 'runs' / arm / 'result.json')['curve']) if final else start(arm)[0]
    stages, config, catalog = schedules(arm)
    # Qualification deliberately includes all modes through M=19, even for the control.
    modes = stages[-1].update_modes if final else 19
    stage = replace(stages[-1], observations=(catalog[-1],), weights=(1.,),
                    discrepancy_tolerances=(1e-7,), update_modes=modes)
    ledger = Ledger(cap=44, seconds=600, endpoint_reserve=0)
    update = base.ProjectedUpdate(sc.LENGTH)
    space = update.prepare(curve, modes, 192)
    coarse = Objective(stage, ac.contrast(), config, ledger)
    fine = Objective(replace(stage, nodes=1536, refined_nodes=3072), ac.contrast(), config, ledger)
    a, b = coarse.production(curve, 'audit_base'), fine.production(curve, 'audit_base')
    ja, jb = coarse.jacobian(a, update, space), fine.jacobian(b, update, space)
    relative = np.linalg.norm(ja - jb, axis=0) / np.maximum(np.linalg.norm(jb, axis=0), 1e-30)
    fields = [float(relative_columns(a.prediction, b.prediction)[0])]
    direction = np.random.default_rng(38020).normal(size=jb.shape[1])
    direction /= np.linalg.norm(direction)
    fd_error, refusal = None, None
    try:
        plus, minus = [fine.production(update.trial(space, s * 1e-7 * direction)[0], 'audit_fd').residual for s in (1, -1)]
        fd = (plus - minus) / 2e-7
        fd_error = float(np.linalg.norm(fd - jb @ direction) / np.linalg.norm(fd))
    except ValueError as exc:
        refusal = str(exc)
    frequencies = [ac.CATALOG_HZ[-1]]
    if final:
        for f, obs in zip(ac.CATALOG_HZ[:-1], catalog[:-1]):
            predictions = []
            for n in (768, 1536):
                ledger.reserve(1)
                ledger.charge('solve', 'all_frequency_refinement')
                predictions.append(solve(curve, obs.wavenumber, ac.contrast(), obs.acquisition, n).prediction)
            fields.append(float(np.linalg.norm(predictions[0] - predictions[1]) / np.linalg.norm(predictions[1])))
            frequencies.append(f)
    passed = (all(e <= (1e-5 if f <= .5e9 else 1e-7) for f, e in zip(frequencies, fields))
              and max(relative) <= 1e-3 and fd_error is not None and fd_error <= 1e-3)
    row = dict(arm=arm, final=final, M=modes, nodes=[768, 1536], frequencies_hz=frequencies,
               field_refinement_relative=fields, jacobian_refinement_relative=relative,
               full_trial_fd_relative=fd_error, fd_refusal=refusal, passed=bool(passed), work=ledger.snapshot())
    print('DENSE AUDIT', arm, final, bool(passed), 'field', max(fields), 'J', max(relative), 'FD', fd_error, flush=True)
    return row


def worker(arm):
    folder = OUT / 'runs' / arm
    folder.mkdir(parents=True, exist_ok=False)
    ledger = Ledger(cap=3000, seconds=1800)
    try:
        curve, prefix_units = start(arm)
        stages, config, catalog = schedules(arm)
        update = base.ProjectedUpdate(sc.LENGTH)
        frozen = hashes()
        sc.write(folder / 'configuration.json', dict(arm=arm, stages=[stage_record(s) for s in stages],
                 backend=asdict(config), update=update.settings(), initial=ast.curve_record(curve), prefix_units=prefix_units))
        begun = time.perf_counter()
        try:
            curve, rows, status, reason = base.old.run_stages(curve, stages, update, config, ledger, folder)
        except Stop as exc:
            checkpoint = folder / 'checkpoint.json'
            d = sc.read(checkpoint) if checkpoint.exists() else None
            if d:
                curve, rows = ast.curve_from(d['curve']), d['stages']
            else:
                rows = []
            status, reason = 'HARD_STOP', exc.code
        result = dict(case='kite', arm=arm, curve=ast.curve_record(curve), stages=rows, status=status, reason=reason,
                      work=ledger.snapshot(), seconds=time.perf_counter() - begun, prefix_units=prefix_units,
                      complete_path_units=prefix_units + ledger.units, geometry_work=update.counts,
                      score=ast.score('kite', curve, catalog))
        assert hashes() == frozen
        sc.write(folder / 'result.json', result)
        print('DENSE DONE', arm, status, result['score']['symmetric_rms_mm'], ledger.units, flush=True)
        return {k: result[k] for k in ('arm', 'status', 'reason', 'score', 'work', 'prefix_units', 'complete_path_units')}
    except Exception:
        row = dict(arm=arm, status='EXCEPTION', traceback=traceback.format_exc(), work=ledger.snapshot())
        sc.write(folder / 'failure.json', row)
        print(row, flush=True)
        return row


def main():
    assert sc.read(HERE / 'completion.json')['status'] == 'COMPLETE'
    assert sc.read(HERE / 'runs/kite/release_m/result.json')['reason'] == 'NUMERICAL_FAILURE'
    OUT.mkdir(exist_ok=False)
    inputs = [HERE / 'manifest.json', HERE / 'completion.json'] + [HERE / 'runs/kite' / a / name
              for a in base.ARMS for name in ('release_1_history.json', 'result.json')]
    frozen = hashes()
    sc.write(OUT / 'manifest.json', dict(experiment='SC-038-dense-kite', sources=frozen,
             inputs={str(p.relative_to(sc.ROOT)): sc.digest(p) for p in inputs},
             command=sys.argv, threads={k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},
             workers=2, new_inverse_cap=6000, audit_cap=100, evaluation_fields=38))
    with ProcessPoolExecutor(max_workers=2) as pool:
        qualified = list(pool.map(audit, base.ARMS))
    passed = all(r['passed'] for r in qualified)
    sc.write(OUT / 'qualification.json', dict(rows=qualified, passed=passed))
    if not passed:
        sc.write(OUT / 'completion.json', dict(status='QUALIFICATION_FAILED'))
        return
    rows = []
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(worker, a) for a in base.ARMS]):
            rows.append(future.result())
            sc.write(OUT / 'summary.json', dict(rows=rows))
    audits = []
    if all(r['status'] != 'EXCEPTION' for r in rows):
        with ProcessPoolExecutor(max_workers=2) as pool:
            for future in as_completed([pool.submit(audit, a, True) for a in base.ARMS]):
                audits.append(future.result())
                sc.write(OUT / 'final_audit.json', dict(rows=audits, passed=all(r['passed'] for r in audits)))
    assert hashes() == frozen
    manifest = sc.read(OUT / 'manifest.json')
    assert all(sc.digest(sc.ROOT / p) == h for p, h in manifest['inputs'].items())
    sc.write(OUT / 'completion.json', dict(status='COMPLETE' if len(audits) == 2 else 'FAILED',
             audits_passed=len(audits) == 2 and all(r['passed'] for r in audits), sources_unchanged=True,
             new_inverse_units=sum(r['work']['work_units'] for r in rows),
             audit_units=sum(r['work']['work_units'] for r in qualified + audits)))


if __name__ == '__main__':
    main()
