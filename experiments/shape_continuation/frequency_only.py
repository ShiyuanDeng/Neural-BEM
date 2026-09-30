"""SC-051: full-discretization Fourier bands; only frequencies are continued.

Run with PYTHONPATH=solvers:. and single-thread BLAS. Existing input and
comparison artifacts are read-only. Truth is accessed only for final scoring.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.inverse import Observation
from experiments.shape_continuation.lm_backend import (
    BackendConfig, Ledger, Objective, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record)
from experiments.shape_continuation.multi_object import MultiCurve, MultiUpdate
from experiments.modal_atlas.contrast_screen import sc050, set_contrast, tag

ROOT = sc.ROOT
BASE = ROOT / 'results/validation/shape_continuation'
OUT = BASE / 'SC-051-frequency-only'
MA = ROOT / 'results/validation/modal_atlas'
NODES = 512
BAND = NODES // 2 - 1
CAP, SECONDS, ITERATIONS = 13412, 1800, 44


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    sc.write(tmp, value)
    tmp.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).relative_to(ROOT))


def descriptors():
    """The current paired-source reconstruction panels, including all saved noise draws."""
    rows = []
    for case in ast.CASES:
        folder = ast.source_folder(case)
        rows.append(dict(id='core__' + case, panel='core', case=case, contrast=.5,
            data=relative(folder/'observations.json'), truth=relative(folder/'truth.json'),
            qualification=relative(folder/'oracle_check.json'),
            reference=relative(BASE/'SC-043-prospective-band/runs'/case/'fixed/result.json'),
            adaptive_reference=relative(BASE/'SC-043-prospective-band/runs'/case/'stagnation/result.json'),
            reference_name='SC-043 fixed release (best aggregate control; full predecessor path)',
            cost_scope='suffix_only'))
    for case in ('asymmetric_lobes', 'deep_c'):
        folder = BASE/'SC-044-noisy-fresh-cases/inputs'/case
        for profile in ('clean', 'noise_seed_0', 'noise_seed_1'):
            rows.append(dict(id=f'fresh__{case}__{profile}', panel='fresh', case=case,
                profile=profile, contrast=.5, data=relative(folder/f'{profile}.json'),
                clean=relative(folder/'clean.json'), truth=relative(folder/'truth.json'),
                qualification=relative(folder/'observations.json'),
                reference=relative(BASE/'SC-044-noisy-fresh-cases/runs'/case/profile/'boundary/result.json'),
                reference_name='SC-044 recurrent cleanup', cost_scope='suffix_only'))
    s = sc050()
    for scene in s.SCENES:
        folder = s.HERE/'inputs'/scene
        rows.append(dict(id='far__'+scene, panel='far', case=scene, contrast=.5,
            data=relative(folder/'observations.json'), initial=relative(folder/'initial.json'),
            truth=relative(folder/'truth.json'), qualification=relative(folder/'qualification.json'),
            reference=relative(s.HERE/'runs'/scene/'localize_low/result.json'),
            reference_name='SC-050 localization + warm-up + band releases', cost_scope='full_fit'))
    from experiments.modal_atlas import damped_screen as ds, frontier_tail as ft
    for contrast, scene in ft.DEVELOPMENT + ft.TRANSFER:
        # Contrast-0.5 development cells already occur in the SC-050 panel.
        if contrast == .5:
            continue
        folder = ds.real_input(contrast, scene)
        rows.append(dict(id=f'modal__{tag(contrast)}__{scene}', panel='modal', case=scene,
            contrast=contrast, data=relative(folder/'observations.json'),
            initial=relative(s.HERE/'inputs'/scene/'initial.json'),
            truth=relative(s.HERE/'inputs'/('new_asymmetric' if scene == 'noisy_asymmetric' else scene)/'truth.json'),
            qualification=relative(folder/'qualification.json'),
            reference=relative(ft.OUT/'runs/DF'/tag(contrast)/scene/'result.json'),
            reference_name='MA-005 damped localization/prefix + adaptive frontier tail', cost_scope='full_fit'))
    for sep in (.14, .20):
        for noisy in (False, True):
            case = f'sep{sep:.2f}_{"noise" if noisy else "clean"}'
            rows.append(dict(id='coupled__'+case, panel='coupled', case=case, contrast=.5,
                data=relative(BASE/f'SC-047-coupled-continuation/inputs/separation_{sep:.2f}/input.json'),
                noisy=noisy, reference=relative(BASE/'SC-047-coupled-continuation/runs'/case/'joint/result.json'),
                reference_name='SC-047 joint M3→M5', cost_scope='full_fit'))
    case = 'sep0.14_clean'
    rows.append(dict(id='intrinsic__'+case, panel='intrinsic', case=case, contrast=.5,
        data=relative(BASE/'SC-048-global-motion-directions/inputs'/f'{case}.json'), noisy=False,
        reference=relative(BASE/'SC-048-global-motion-directions/runs'/case/'normal_m5/result.json'),
        reference_name='SC-048 compact M5 (best qualified control)', cost_scope='full_fit'))
    return rows


def record(curve):
    if isinstance(curve, MultiCurve):
        return dict(ids=curve.ids, components=[ast.curve_record(c) for c in curve.components])
    return ast.curve_record(curve)


def restore(row):
    if 'components' in row:
        return MultiCurve(tuple(ast.curve_from(c) for c in row['components']), tuple(row['ids']))
    return ast.curve_from(row)


def resize(curve, band=BAND):
    if isinstance(curve, MultiCurve):
        return MultiCurve(tuple(resize(c, band) for c in curve.components), curve.ids)
    if curve.band > band:
        raise ValueError('No truncation permitted')
    return FourierCurve(np.pad(curve.coefficients, (band-curve.band,)*2))


def data_only(row):
    d = sc.read(ROOT/row['data'])
    frequencies = ac.CATALOG_HZ
    if row['panel'] in ('coupled', 'intrinsic'):
        frequencies = (.25e9, .5e9, 1e9, 1.5e9)
        if row['panel'] == 'coupled':
            values = np.array(d['clean_real']) + 1j*np.array(d['clean_imag'])
            noise = np.array(d['noise_real']) + 1j*np.array(d['noise_imag'])
            if row['noisy']:
                values += noise
        else:
            values = np.array(d['observed_real']) + 1j*np.array(d['observed_imag'])
        initial = restore(d['initial'])
    else:
        values = np.array(d['observed_real']) + 1j*np.array(d['observed_imag'])
        initial = restore(sc.read(ROOT/row['initial'])) if 'initial' in row else ac.start_curve()
    return tuple(ac.observations(values, frequencies)), initial, frequencies


def schedule(catalog, frequencies, config, nodes=NODES):
    """Cumulative dense frequency ladder, fixed full mesh bands from stage one."""
    from experiments.shape_continuation.lm_backend import FitStage
    band = nodes//2 - 1
    quota = CAP//len(catalog)
    return [FitStage(f'f{i+1:02d}', tuple(catalog[:i+1]), tuple(np.ones(i+1)/(i+1)),
        tuple(1e-5 if f <= .5e9 else 1e-7 for f in frequencies[:i+1]),
        band, band, nodes, 2*nodes, ITERATIONS, quota) for i in range(len(catalog))]


def audit(curve, stage, config, update, contrast, folder):
    """Unchanged SC field/column-Jacobian/complete-trial FD gates, including all M columns."""
    ledger = Ledger(cap=6*len(stage.observations)+12, seconds=300, endpoint_reserve=0)
    started = time.perf_counter()
    try:
        a = Objective(stage, contrast, config, ledger)
        b = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=2*stage.refined_nodes),
                      contrast, config, ledger)
        low, high = a.production(curve, 'audit_base'), b.production(curve, 'audit_fine')
        if low is None or high is None:
            raise ValueError('Endpoint forward evaluation failed')
        space = update.prepare(curve, stage.update_modes, stage.curve_modes)
        ja, jb = a.jacobian(low, update, space), b.jacobian(high, update, space)
        fields = ac.relative(low.prediction, high.prediction)
        colnorm = np.linalg.norm(jb, axis=0)
        derivative = np.linalg.norm(ja-jb, axis=0)/np.maximum(colnorm, 1e-30)
        direction = np.random.default_rng(42001).normal(size=ja.shape[1])
        direction /= np.linalg.norm(direction)
        plus, minus = [b.production(update.trial(space, sign*1e-7*direction)[0], 'audit_fd') for sign in (1,-1)]
        if plus is None or minus is None:
            raise ValueError('FD forward evaluation failed')
        fd = (plus.residual-minus.residual)/2e-7
        error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
        row = dict(passed=bool(np.all(fields<=stage.discrepancy_tolerances) and max(derivative)<=1e-3 and error<=1e-3),
            field_relative=fields, jacobian_relative=derivative, jacobian_column_norm=colnorm,
            full_trial_fd_relative=error, fine_loss=high.loss,
            relative_residual=ac.relative(high.prediction, b.observed))
    except Exception:
        row = dict(passed=False, traceback=traceback.format_exc())
    row.update(work=ledger.snapshot(), seconds=time.perf_counter()-started)
    write(folder/'final_audit.json', row)
    return row


def score(row, curve):
    s = sc050()
    if row['panel'] in ('coupled', 'intrinsic'):
        truth = restore(sc.read(ROOT/row['data'])['truth'])
        scores = [s.old.score(c,t) for c,t in zip(curve.components, truth.components)]
        return dict(rms_mm=max(r['rms_mm'] for r in scores),
                    hausdorff_upper_mm=max(r['hausdorff_upper_mm'] for r in scores), objects=scores)
    return s.old.score(curve, restore(sc.read(ROOT/row['truth'])))


def residual_limits(row, catalog):
    data = sc.read(ROOT/row['data'])
    observed = np.column_stack([o.scattered for o in catalog])
    if 'realized_noise_relative' in data:
        noise = np.array(data['realized_noise_relative'])
    elif row['panel'] == 'fresh':
        clean = sc.read(ROOT/row['clean'])
        clean = np.array(clean['observed_real'])+1j*np.array(clean['observed_imag'])
        noise = ac.relative(observed, clean)
    elif row.get('noisy'):
        clean = np.array(data['clean_real'])+1j*np.array(data['clean_imag'])
        noise = ac.relative(observed, clean)
    else:
        noise = np.zeros(len(catalog))
    return np.maximum(.003, 3*noise), bool(np.max(noise) > 1e-10)


def prepare():
    if (OUT/'manifest.json').exists():
        raise FileExistsError('Existing campaign is immutable')
    rows = descriptors()
    paths = {Path(__file__), OUT/'plan.md'}
    paths.update(ROOT/p for p in sc.source_hashes())
    paths.update(sc050().source_paths())
    inputs = set()
    for row in rows:
        for key in ('data','initial','truth','clean','qualification','reference','adaptive_reference'):
            if key in row:
                p = ROOT/row[key]
                if not p.exists():
                    raise FileNotFoundError(p)
                inputs.add(p)
        if 'qualification' in row:
            q = sc.read(ROOT/row['qualification'])
            assert q.get('passed', q.get('qualified')), row['id']
    write(OUT/'manifest.json', dict(experiment='SC-051', cases=rows,
        nodes=NODES, M=BAND, K=BAND, cap=CAP, seconds=SECONDS, iterations=ITERATIONS,
        frequency_rule='cumulative all available frequencies ascending; no localization or band schedule',
        sources={relative(p):digest(p) for p in sorted(paths)},
        inputs={relative(p):digest(p) for p in sorted(inputs)},
        commit=subprocess.check_output(['git','rev-parse','HEAD'], text=True).strip(),
        original_status=subprocess.check_output(['git','status','--short'], text=True),
        python=sys.version, environment={k:os.getenv(k) for k in ('SC_FORWARD_BACKEND','SC_FREQUENCY_THREADS',
            'OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}))
    print('FROZEN',len(rows),'cases',flush=True)


def verify():
    manifest = sc.read(OUT/'manifest.json')
    for mapping in ('sources','inputs'):
        for path, expected in manifest[mapping].items():
            if digest(ROOT/path) != expected:
                raise RuntimeError('Frozen file changed: '+path)
    return manifest


def attempt(row):
    verify()
    folder = OUT/'runs'/row['id']
    if (folder/'result.json').exists():
        return sc.read(folder/'result.json')
    folder.mkdir(parents=True, exist_ok=False)
    set_contrast(row['contrast'])
    catalog, initial, frequencies = data_only(row)
    s = sc050()
    _, config = ast.schedules(catalog if len(catalog)==19 else ast.catalog_only('wrong_circle'), 'baseline')
    if row['panel'] in ('coupled','intrinsic'):
        config = BackendConfig(step_control='physical', physical_step_bound_m=.002,
                               gradient_tolerance=1e-10, log_model=True)
    # SC-044's discrepancy stopping was part of its backend, and is retained.
    stages = schedule(catalog, frequencies, config)
    configs = []
    for stage in stages:
        local = config
        if row['panel']=='fresh' and row['profile']!='clean':
            d=sc.read(ROOT/row['data'])
            sigma=np.array(d['sigma_real_imag'])[:len(stage.observations)]
            raw=(np.array([np.linalg.norm(o.scattered) for o in stage.observations])/sigma)**2
            stage=replace(stage, weights=tuple(raw/raw.sum()))
            local=replace(config, loss_tolerance=max(config.loss_tolerance,
                1.1**2*sum(o.scattered.size for o in stage.observations)/raw.sum()))
        configs.append((stage,local))
    curve = resize(initial)
    base_update = s.c.reference.ProjectedUpdate(sc.LENGTH)
    update = MultiUpdate(base_update) if isinstance(curve, MultiCurve) else base_update
    write(folder/'configuration.json', dict(case=row, initial=record(curve),
        schedule=[dict(stage=stage_record(st), backend=asdict(cfg)) for st,cfg in configs],
        update=base_update.settings(), cap=CAP, seconds=SECONDS))
    ledger = Ledger(cap=CAP, seconds=SECONDS)
    started = time.perf_counter()
    accepted, records, outcome = [], [], 'COMPLETED_SCHEDULE'
    try:
        for stage, cfg in configs:
            ledger.begin_stage(stage.label, stage.quota)
            def checkpoint(iteration, evaluation):
                accepted.append(dict(stage=stage.label, iteration=iteration,
                    loss=evaluation.loss, units=ledger.units, curve=record(evaluation.curve)))
                write(folder/'accepted.json', dict(states=accepted))
            result = fit_stage(curve,stage,row['contrast'],update,cfg,ledger,on_accept=checkpoint)
            curve = result.curve
            receipt = dict(stage=stage.label, highest_frequency_hz=frequencies[len(records)],
                M=stage.update_modes, K=stage.curve_modes, outcome=result.outcome, stop=result.stop_reason,
                detail=result.detail, accepted=result.accepted_steps, initial_loss=result.initial_loss,
                final_loss=result.final_loss, seconds=result.seconds, work=ledger.snapshot())
            records.append(receipt)
            write(folder/f'{stage.label}.json', dict(receipt, history=result.history,
                trials=result.trials, checks=result.acceptance_checks))
            write(folder/'checkpoint.json', dict(curve=record(curve), stages=records, work=ledger.snapshot()))
            print('STAGE',row['id'],stage.label,result.outcome,result.accepted_steps,ledger.units,flush=True)
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                outcome = result.outcome
                break
    except Stop as exc:
        outcome = exc.code
    except Exception:
        outcome = 'EXCEPTION'
        write(folder/'fit_exception.json',dict(traceback=traceback.format_exc()))
    fit_seconds = time.perf_counter()-started
    # Record the returned endpoint before any evaluation can fail.
    result = dict(case=row, outcome=outcome, stages=records, final_curve=record(curve),
        fit_work=ledger.snapshot(), fit_seconds=fit_seconds, accepted=sum(r['accepted'] for r in records))
    write(folder/'unscored.json', result)
    with s.old.deadline(300):
        final = audit(curve, configs[-1][0], configs[-1][1], update, row['contrast'], folder)
    result.update(final_audit_passed=final['passed'], audit_units=final['work']['work_units'])
    result['metrics'] = score(row,curve)
    limits,noisy = residual_limits(row,catalog)
    result.update(noisy=noisy, residual_limits=limits, relative_residual=final.get('relative_residual'),
        maximum_residual=max(final['relative_residual']) if 'relative_residual' in final else None)
    result['recovered']=bool(final['passed'] and result['metrics']['rms_mm']<=1 and
        result['metrics']['hausdorff_upper_mm']<=2 and result['relative_residual'] is not None and
        np.all(np.array(result['relative_residual'])<=limits))
    result['total_seconds']=time.perf_counter()-started
    write(folder/'result.json',result)
    print('RESULT',row['id'],outcome,result['recovered'],result['metrics']['rms_mm'],flush=True)
    return result


def run_case(row):
    try:
        return attempt(row)
    except Exception:
        failure=dict(case=row, outcome='WORKER_EXCEPTION', traceback=traceback.format_exc())
        write(OUT/'runs'/row['id']/'failure.json', failure)
        print('FAILURE',row['id'],failure['traceback'],flush=True)
        return failure


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare','run','verify'))
    parser.add_argument('--cases',nargs='+')
    parser.add_argument('--workers',type=int,default=3)
    args=parser.parse_args()
    if args.mode=='prepare':
        prepare()
    elif args.mode=='verify':
        print('VERIFIED',len(verify()['cases']))
    else:
        manifest=verify()
        rows=[r for r in manifest['cases'] if args.cases is None or r['id'] in args.cases]
        if args.workers==1:
            for row in rows:
                run_case(row)
        else:
            with ProcessPoolExecutor(args.workers) as pool:
                futures=[pool.submit(run_case,r) for r in rows]
                for future in as_completed(futures):
                    future.result()
        verify()


if __name__=='__main__':
    main()
