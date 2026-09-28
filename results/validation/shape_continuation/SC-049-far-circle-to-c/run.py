"""One frozen, full far-circle-to-C reconstruction; no fitting retuning."""
import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
import importlib.util
import json
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time

import numpy as np
from scipy.spatial import cKDTree

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.forward import Work, ordered_calls, solve, shape_jacobian
from experiments.shape_continuation.geometry import FourierCurve, normal_basis
from experiments.shape_continuation.lm_backend import Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record
from experiments.shape_continuation.metrics import boundary_distance
from experiments.spd014_geometry.runtime import geometry_acceleration
from experiments.spd014_geometry.run import environment
from ordered_boundary.validation_cache import geometry_validation, validation_cache

HERE = Path(__file__).resolve().parent
PLAN = sc.ROOT/'docs/iterations/shape_frequency_continuation/iteration_28/03_sc049_plan.md'
INPUT = ast.source_folder('circle_to_c')
spec = importlib.util.spec_from_file_location('sc049_common', HERE.parent/'SC-042-state-strategies/run.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def write(path, value):
    c.write(path, value)


@contextmanager
def deadline(seconds):
    def expired(*_):
        raise TimeoutError('SC-049 phase wall budget exhausted')
    previous = signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def setup():
    catalog = ast.catalog_only('circle_to_c')
    prefix, config = ast.schedules(catalog, 'baseline')
    prefix = [replace(s, curve_modes=2*s.update_modes+2) for s in prefix]
    full = dict(observations=tuple(catalog), weights=tuple(np.ones(19)/19),
                discrepancy_tolerances=tuple(1e-5 if f <= .5e9 else 1e-7 for f in ac.CATALOG_HZ))
    stages = prefix + [replace(prefix[-1], label=f'release_M{m}', update_modes=m,
                              curve_modes=192, quota=1500, **full) for m in (11, 15, 19)]
    stages += [replace(stages[-1], label=f'fixed_M{m}', update_modes=m, quota=304)
               for m in (25, 31, 37)]
    initial = FourierCurve.circle(.065/sc.LENGTH, (complex(.32,.62)-sc.CENTER)/sc.LENGTH)
    return catalog, stages, config, c.resize(initial, stages[0].curve_modes)


def prepare():
    if (HERE/'manifest.json').exists():
        raise FileExistsError('A frozen SC-049 run already exists')
    catalog, stages, config, initial = setup()
    initial.validate()
    assert sc.read(INPUT/'oracle_check.json')['passed']
    truth = ast.curve_from(sc.read(INPUT/'truth.json'))
    a, b = initial.values(8192), truth.values(8192)
    gap = float(np.min(cKDTree(np.column_stack((b.real,b.imag))).query(
        np.column_stack((a.real,a.imag)))[0]))*sc.LENGTH
    # A stronger x-axis separation proves these filled objects are disjoint.
    gap_x = float(np.min(b.real)-np.max(a.real))*sc.LENGTH
    assert gap_x > 0
    paths = {sc.ROOT/p for p in sc.source_hashes()}
    paths.update((sc.ROOT/p for p in c.sources()))
    paths.add(Path(__file__))
    paths.update((sc.ROOT/'experiments/spd014_geometry').glob('*.py'))
    sources = {str(p.relative_to(sc.ROOT)):sc.digest(p) for p in sorted(paths)}
    with tarfile.open(HERE/'sources.tar.gz','w:gz') as archive:
        for p in sorted(paths):
            archive.add(p, arcname=str(p.relative_to(sc.ROOT)), recursive=False)
    (HERE/'approved_plan.md').write_bytes(PLAN.read_bytes())
    inputs = {str((INPUT/n).relative_to(sc.ROOT)):sc.digest(INPUT/n)
              for n in ('observations.json','truth.json','oracle_check.json')}
    write(HERE/'configuration.json', dict(experiment='SC-049', initial=ast.curve_record(initial),
        center_m=[.32,.62], radius_m=.065, target='SC-022 circle_to_c, unchanged',
        initial_sampled_boundary_gap_mm=1000*gap, initial_x_separation_mm=1000*gap_x,
        stages=[stage_record(s) for s in stages], backend=asdict(config),
        cleanup_before='fixed_M25', physical_work_cap=13824, fit_seconds_cap=1800,
        audit_seconds_cap_each=300, atlas_seconds_cap_total=600,
        recovery_limits=dict(rms_mm=1., hausdorff_mm=2., maximum_catalog_relative_residual=.003),
        environment=environment()))
    write(HERE/'manifest.json', dict(sources=sources, inputs=inputs,
        configuration_sha256=sc.digest(HERE/'configuration.json'),
        source_archive_sha256=sc.digest(HERE/'sources.tar.gz'),
        approved_plan_sha256=sc.digest(HERE/'approved_plan.md')))
    print('FROZEN',len(sources),'sources; initial gap',gap*1000,'mm',flush=True)


def verify():
    manifest = sc.read(HERE/'manifest.json')
    for kind in ('sources','inputs'):
        for p,digest in manifest[kind].items():
            assert sc.digest(sc.ROOT/p) == digest, 'Frozen file changed: '+p
    for name,key in [('configuration.json','configuration_sha256'),
                     ('sources.tar.gz','source_archive_sha256'),('approved_plan.md','approved_plan_sha256')]:
        assert sc.digest(HERE/name) == manifest[key]


def all_frequency_stage(stage, catalog):
    return replace(stage, observations=tuple(catalog), weights=tuple(np.ones(19)/19),
                   discrepancy_tolerances=tuple(1e-5 if f <= .5e9 else 1e-7 for f in ac.CATALOG_HZ))


def audit(curve, stage, config, label):
    started = time.perf_counter()
    with deadline(300), validation_cache('cache'):
        row = c.audit(curve, stage, config)
    row['seconds'] = time.perf_counter()-started
    write(HERE/f'{label}_audit.json',row)
    print('AUDIT',label,row['passed'],round(row['seconds'],3),flush=True)
    return row


def atlas(curve, catalog, label):
    started = time.perf_counter()
    grids, work = {}, []
    for nodes in (512,1024):
        def one(observation):
            counter = Work(max_forwards=1,max_seconds=300)
            state = solve(curve,observation.wavenumber,ac.contrast(),observation.acquisition,nodes,work=counter)
            derivative = shape_jacobian(state,normal_basis(state.curve,48)/sc.LENGTH,work=counter)
            scale = np.linalg.norm(observation.scattered)
            return state.prediction, derivative/scale, counter.summary()
        with validation_cache('cache'), ordered_calls(one,catalog) as calls:
            rows = [call() for call in calls]
        grids[nodes] = dict(prediction=np.stack([r[0] for r in rows]),
                            jacobian=np.stack([r[1] for r in rows]))
        work.extend(r[2] for r in rows)
    coarse,fine = grids[512],grids[1024]
    fields = np.linalg.norm(coarse['prediction']-fine['prediction'],axis=1)/np.linalg.norm(fine['prediction'],axis=1)
    derivative = np.linalg.norm(coarse['jacobian']-fine['jacobian'],axis=1)/np.maximum(np.linalg.norm(fine['jacobian'],axis=1),1e-30)
    observed = np.stack([o.scattered for o in catalog])
    residual = np.linalg.norm(fine['prediction']-observed,axis=1)/np.linalg.norm(observed,axis=1)
    sensitivity = np.linalg.norm(fine['jacobian'],axis=1)
    # Merge cosine/sine columns into a norm for each order, including order 0.
    harmonic = np.column_stack((sensitivity[:,0],np.sqrt(sensitivity[:,1:49]**2+sensitivity[:,49:]**2)))
    np.savez_compressed(HERE/f'{label}_atlas.npz', **{f'{k}_{n}':v for n,d in grids.items() for k,v in d.items()},
                        harmonic_sensitivity_per_m=harmonic, relative_residual=residual)
    row = dict(passed=bool(np.all(fields <= np.array([1e-5 if f<=.5e9 else 1e-7 for f in ac.CATALOG_HZ]))
                           and np.max(derivative)<=1e-3),
        band=48,nodes=[512,1024],field_relative=fields,jacobian_column_relative=derivative,
        relative_residual=residual,units=sum(w['attempted']+w['jacobians'] for w in work),
        work=work,seconds=time.perf_counter()-started,
        convention='norm of relative-data Jacobian column pair per metre of normal-harmonic amplitude; not an observability threshold')
    write(HERE/f'{label}_atlas.json',row)
    print('ATLAS',label,row['passed'],round(row['seconds'],3),flush=True)
    return row


def score(curve, truth):
    distance,bound = boundary_distance(truth,curve)
    return dict(rms_mm=1000*symmetric_rms_distance(curve,truth.values(16384),sc.LENGTH),
                hausdorff_mm=1000*sc.LENGTH*distance,hausdorff_upper_mm=1000*sc.LENGTH*(distance+bound))


def run():
    if (HERE/'accepted.json').exists() or (HERE/'result.json').exists():
        raise FileExistsError('Do not overwrite a trajectory')
    verify()
    catalog,stages,config,initial = setup()
    began = time.perf_counter()
    with geometry_acceleration('both'):
        preflight = audit(initial,all_frequency_stage(stages[0],catalog),config,'initial')
        if not preflight['passed']:
            raise RuntimeError('Initial numerical qualification failed; inverse withheld')
        curve,rows,accepted = initial,[],[]
        ledger = Ledger(cap=13412,seconds=1800)
        update = c.reference.ProjectedUpdate(sc.LENGTH)
        outcome = 'COMPLETED_SCHEDULE'
        last_stage = stages[0]
        fit_started = time.perf_counter()
        for stage in stages:
            if stage.label == 'fixed_M25':
                curve,_ = c.treatment(curve,'once',0)
            else:
                curve = c.resize(curve,stage.curve_modes)
            try:
                ledger.begin_stage(stage.label,stage.quota)
            except Stop as exc:
                outcome=exc.code
                break
            def checkpoint(iteration,value):
                accepted.append(dict(stage=stage.label,M=stage.update_modes,iteration=iteration,
                    loss=value.loss,units=ledger.units,curve=ast.curve_record(value.curve)))
                write(HERE/'accepted.json',dict(states=accepted))
            with geometry_validation('cache'):
                result = fit_stage(curve,stage,ac.contrast(),update,config,ledger,on_accept=checkpoint)
            curve = result.curve
            last_stage = stage
            row = dict(stage=stage.label,M=stage.update_modes,K=stage.curve_modes,
                outcome=result.outcome,stop=result.stop_reason,detail=result.detail,
                accepted_steps=result.accepted_steps,initial_loss=result.initial_loss,final_loss=result.final_loss,
                work=ledger.snapshot(),seconds=result.seconds,curve=ast.curve_record(curve))
            rows.append(row)
            write(HERE/f'{stage.label}.json',dict(row,history=result.history,trials=result.trials,
                                                acceptance_checks=result.acceptance_checks))
            write(HERE/'checkpoint.json',dict(curve=ast.curve_record(curve),stages=rows,work=ledger.snapshot()))
            print('STAGE',stage.label,result.outcome,result.stop_reason,'loss',result.final_loss,'units',ledger.units,flush=True)
            if result.outcome not in (NORMAL_RETURN,STAGE_QUOTA):
                outcome=result.outcome
                break
        fit_seconds = time.perf_counter()-fit_started
        final_audit = audit(curve,all_frequency_stage(last_stage,catalog),config,'final')
        with deadline(600):
            initial_atlas = atlas(initial,catalog,'initial')
            final_atlas = atlas(curve,catalog,'final')
    # Truth-based metrics are computed only after the trajectory is fixed.
    truth = ast.curve_from(sc.read(INPUT/'truth.json'))
    initial_score,final_score = score(initial,truth),score(curve,truth)
    recovery = dict(rms=final_score['rms_mm']<=1.,hausdorff=final_score['hausdorff_mm']<=2.,
        data=max(final_atlas['relative_residual'])<=.003,audit=final_audit['passed'])
    monotone = all(all(b['loss'] < a['loss'] for a,b in zip(ss,ss[1:]))
        for stage in stages for ss in [[r for r in accepted if r['stage']==stage.label]])
    units = ledger.units+preflight['work']['work_units']+final_audit['work']['work_units']+initial_atlas['units']+final_atlas['units']
    assert units<=13824
    verify()
    write(HERE/'result.json',dict(outcome=outcome,recovered=all(recovery.values()),recovery_checks=recovery,
        initial_score=initial_score,score=final_score,curve=ast.curve_record(curve),stages=rows,
        fit_seconds=fit_seconds,seconds=time.perf_counter()-began,total_units=units,fit_work=ledger.snapshot(),
        accepted_steps=sum(r['accepted_steps'] for r in rows),accepted_losses_strictly_decrease_per_stage=monotone,
        final_maximum_catalog_relative_residual=max(final_atlas['relative_residual']),
        atlas_qualified=initial_atlas['passed'] and final_atlas['passed'],integrity_passed=True,
        environment=environment()))
    print('DONE',outcome,'recovered',all(recovery.values()),final_score,'fit seconds',fit_seconds,'units',units,flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=('prepare','verify','run'))
    args=parser.parse_args()
    if args.mode=='prepare': prepare()
    elif args.mode=='verify': verify()
    else:
        try: run()
        except Exception:
            import traceback
            write(HERE/'failure.json',dict(traceback=traceback.format_exc(),environment=environment()))
            raise


if __name__=='__main__':
    main()
