"""Fresh shapes, fixed noise draws, common-circle prefix and state-control suffixes."""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace, asdict
import importlib.util
from pathlib import Path
import time
import traceback
import numpy as np

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation.forward import solve
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.metrics import boundary_distance
from experiments.shape_continuation.lm_backend import Ledger, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc044_common', HERE.parent/'SC-042-state-strategies/run.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
CASES = ('asymmetric_lobes', 'deep_c')
PROFILES = ('clean', 'noise_seed_0', 'noise_seed_1')
ARMS = ('none', 'boundary', 'cap')
PLAN = HERE/'plan.md'


def truth(case):
    t = 2*np.pi*np.arange(8192)/8192
    if case == 'asymmetric_lobes':
        radius = 1+.17*np.cos(3*t)+.11*np.sin(5*t)+.045*np.cos(7*t)
        return FourierCurve.from_samples(radius*np.exp(1j*(t+.21)), 8)
    if case != 'deep_c':
        raise ValueError(case)
    R, w, alpha = .8, .22, np.radians(125.)
    cap = np.linspace(0,np.pi,800)
    p = np.concatenate(((R+w)*np.exp(1j*np.linspace(-alpha,alpha,2400)),
        R*np.exp(1j*alpha)+w*np.exp(1j*(alpha+cap)),
        (R-w)*np.exp(1j*np.linspace(alpha,-alpha,2400)),
        R*np.exp(-1j*alpha)+w*np.exp(1j*(-alpha+np.pi+cap))))
    s = np.r_[0,np.cumsum(np.abs(np.diff(np.r_[p,p[0]])))]
    u = np.linspace(0,s[-1],8192,endpoint=False)
    z = np.interp(u,s,np.r_[p.real,p[0].real])+1j*np.interp(u,s,np.r_[p.imag,p[0].imag])
    return FourierCurve.from_samples(z*np.exp(-.4j),16)


def perturb(clean, relative, seed):
    """Independent real/imag noise; complex RMS is relative to each frequency RMS."""
    sigma = relative*np.linalg.norm(clean,axis=0)/np.sqrt(2*clean.shape[0])
    rng = np.random.default_rng(seed)
    noise = sigma[None,:]*(rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape))
    return clean+noise, sigma


def whitened_weights(observations, sigma):
    norms = np.array([np.linalg.norm(o.scattered) for o in observations])
    raw = (norms/np.asarray(sigma))**2
    weights = raw/raw.sum()
    # Existing normalize then equals a whitened residual divided by sqrt(sum raw).
    expected_loss = sum(o.scattered.size for o in observations)/raw.sum()
    return tuple(weights), float(expected_loss)


def sources():
    return dict(c.sources(), **{str(p.relative_to(c.sc.ROOT)):c.sc.digest(p) for p in (Path(__file__),PLAN)})


def verify():
    manifest = c.sc.read(HERE/'manifest.json')
    assert manifest['sources'] == sources(), 'Frozen code changed'
    for path, digest in manifest.get('inputs',{}).items():
        assert c.sc.digest(c.sc.ROOT/path) == digest, 'Frozen data changed'


def prepare():
    if (HERE/'manifest.json').exists():
        verify()
        return
    if not PLAN.exists():
        raise RuntimeError('Freeze the contract before generating observations')
    c.write(HERE/'manifest.json', dict(experiment='SC-044', sources=sources(), cases=CASES,
        profiles=PROFILES, arms=ARMS, noise_relative=.01, seeds=[44000,44001],
        geometry_generation='closed formulas in run.py, no recovery-based selection',
        prepared=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    (HERE/'inputs').mkdir(exist_ok=False)
    for case in CASES:
        curve = truth(case)
        with geometry_validation('cache'):
            curve.validate()
        folder = HERE/'inputs'/case
        folder.mkdir(exist_ok=False)
        c.write(folder/'truth.json',c.ast.curve_record(curve))


def generate(case):
    folder = HERE/'inputs'/case
    if (folder/'observations.json').exists():
        return c.sc.read(folder/'observations.json')['qualified']
    verify()
    curve = c.ast.curve_from(c.sc.read(folder/'truth.json'))
    acquisition = c.ast.catalog_only('kite')
    started = time.perf_counter()
    columns = {1024:[],2048:[]}
    work = 0
    with geometry_validation('cache'):
        for nodes in columns:
            for i,o in enumerate(acquisition):
                columns[nodes].append(solve(curve,o.wavenumber,c.ac.contrast(),o.acquisition,nodes).prediction)
                work += 1
                print('DATA',case,nodes,i+1,flush=True)
    coarse, fine = [np.column_stack(columns[n]) for n in (1024,2048)]
    relative = c.reference.relative_columns(coarse,fine)
    qualified = bool(np.all(relative<=1e-8))
    c.write(folder/'observations.json',dict(observed_real=fine.real,observed_imag=fine.imag,
        qualified=qualified,refinement_relative=relative,work_units=work,seconds=time.perf_counter()-started))
    if qualified:
        for profile in PROFILES:
            data,sigma = (fine,np.zeros(fine.shape[1])) if profile == 'clean' else perturb(fine,.01,44000+int(profile[-1]))
            c.write(folder/f'{profile}.json',dict(observed_real=data.real,observed_imag=data.imag,
                sigma_real_imag=sigma,profile=profile,relative_complex_rms=.0 if profile=='clean' else .01))
    return qualified


def seal_inputs():
    verify()
    manifest = c.sc.read(HERE/'manifest.json')
    assert all(c.sc.read(HERE/'inputs'/case/'observations.json')['qualified'] for case in CASES)
    manifest['inputs'] = {str(p.relative_to(c.sc.ROOT)):c.sc.digest(p) for p in sorted((HERE/'inputs').rglob('*.json'))}
    c.write(HERE/'manifest.json',manifest)


def catalog(case,profile):
    d=c.sc.read(HERE/'inputs'/case/f'{profile}.json')
    values=np.array(d['observed_real'])+1j*np.array(d['observed_imag'])
    return c.ac.observations(values),np.array(d['sigma_real_imag'])


def make_stages(case,profile,arm):
    observations,sigma=catalog(case,profile)
    prefix,config=c.ast.schedules(observations,'baseline')
    prefix=[replace(s,curve_modes=2*s.update_modes+2,nodes=512,refined_nodes=1024,
                    iterations=30,quota=q) for s,q in zip(prefix,(600,800,1000,1000))]
    suffix=[replace(prefix[-1],label=f'release_M{m}',observations=tuple(observations),
        weights=tuple(np.ones(19)/19),discrepancy_tolerances=tuple(1e-5 if f<=.5e9 else 1e-7 for f in c.ac.CATALOG_HZ),
        update_modes=m,curve_modes=64 if arm=='cap' else 192,iterations=22,quota=380) for m in (11,19,31)]
    configs=[]
    stages=[]
    for s in prefix+suffix:
        noise_loss=0.
        if profile!='clean':
            ids=[int(np.argmin(abs(np.array([o.wavenumber for o in observations])-o.wavenumber))) for o in s.observations]
            weights,noise_loss=whitened_weights(s.observations,sigma[ids])
            s=replace(s,weights=weights)
        configs.append(replace(config,log_model=True,loss_tolerance=max(config.loss_tolerance,1.1**2*noise_loss)))
        stages.append(s)
    return stages,configs


def score(case,curve):
    target=c.ast.curve_from(c.sc.read(HERE/'inputs'/case/'truth.json'))
    distance,bound=boundary_distance(target,curve)
    return dict(rms_mm=1e3*symmetric_rms_distance(curve,target.values(16384),c.sc.LENGTH),
        hausdorff_mm=1e3*c.sc.LENGTH*distance,hausdorff_upper_mm=1e3*c.sc.LENGTH*(distance+bound),
        tightest_radius_mm=float(1e3*c.sc.LENGTH/np.max(abs(curve.nodes(16384).curvatures))))


def fit_path(case,profile,arm,prefix=False):
    folder=HERE/'runs'/case/profile/('prefix' if prefix else arm)
    folder.mkdir(parents=True,exist_ok=False)
    records,accepted=[],[]
    total=0
    try:
        verify()
        stages,configs=make_stages(case,profile,arm)
        if prefix:
            curve=c.ac.start_curve()
            curve=c.resize(curve,stages[0].curve_modes)
            stages,configs=stages[:4],configs[:4]
        else:
            previous=c.sc.read(HERE/'runs'/case/profile/'prefix'/'result.json')
            if previous['outcome']!='COMPLETED_SCHEDULE' or not previous.get('audit_passed'):
                row=dict(case=case,profile=profile,arm=arm,outcome='PREFIX_FAILED',prefix_outcome=previous['outcome'],
                         prefix_audit_passed=previous.get('audit_passed'),total_units=0)
                c.write(folder/'result.json',row)
                return row
            curve=c.ast.curve_from(previous['curve'])
            stages,configs=stages[4:],configs[4:]
        initial=curve
        c.write(folder/'configuration.json',dict(case=case,profile=profile,arm=arm,prefix=prefix,
            initial=c.ast.curve_record(curve),stages=[stage_record(s) for s in stages],configs=[asdict(k) for k in configs]))
        outcome='COMPLETED_SCHEDULE'
        last_stage,last_config=stages[0],configs[0]
        update=c.reference.ProjectedUpdate(c.sc.LENGTH)
        for i,(stage,config) in enumerate(zip(stages,configs)):
            curve=c.resize(curve,stage.curve_modes) if prefix else c.treatment(curve,arm,i)[0]
            curve.validate()
            ledger=Ledger(cap=stage.quota+1,seconds=3600)
            ledger.begin_stage(stage.label,stage.quota)
            base_units=total
            def checkpoint(iteration,evaluation):
                accepted.append(dict(stage=stage.label,M=stage.update_modes,iteration=iteration,
                    loss=evaluation.loss,total_units=base_units+ledger.units,curve=c.ast.curve_record(evaluation.curve)))
                c.write(folder/'accepted.json',dict(states=accepted))
            with geometry_validation('cache'):
                result=fit_stage(curve,stage,c.ac.contrast(),update,config,ledger,on_accept=checkpoint)
            curve=result.curve
            last_stage,last_config=stage,config
            total+=ledger.units
            row=dict(stage=stage.label,M=stage.update_modes,K=stage.curve_modes,outcome=result.outcome,stop=result.stop_reason,
                initial_loss=result.initial_loss,final_loss=result.final_loss,discrepancy_target=config.loss_tolerance,
                units=ledger.units,total_units=total,detail=result.detail)
            records.append(row)
            c.write(folder/f'{stage.label}.json',dict(row,history=result.history,trials=result.trials,acceptance_checks=result.acceptance_checks))
            c.write(folder/'checkpoint.json',dict(stages=records,curve=c.ast.curve_record(curve),total_units=total))
            print('STAGE',case,profile,'prefix' if prefix else arm,stage.label,result.outcome,result.final_loss,flush=True)
            if result.outcome not in (NORMAL_RETURN,STAGE_QUOTA):
                outcome=result.outcome
                break
            if not prefix and result.final_loss<=config.loss_tolerance:
                outcome='DISCREPANCY_REACHED' if profile!='clean' else 'LOSS_TOLERANCE_REACHED'
                break
        final_audit=c.audit(curve,last_stage,last_config)
        c.write(folder/'audit.json',final_audit)
        row=dict(case=case,profile=profile,arm='prefix' if prefix else arm,outcome=outcome,stages=records,total_units=total,
            curve=c.ast.curve_record(curve),score=score(case,curve),audit_passed=final_audit['passed'],
            audit_units=final_audit['work']['work_units'])
        c.write(folder/'result.json',row)
        verify()
        print('DONE',case,profile,row['arm'],outcome,row['score'],flush=True)
        return row
    except Exception:
        row=dict(case=case,profile=profile,arm='prefix' if prefix else arm,outcome='EXCEPTION',traceback=traceback.format_exc(),
                 total_units=total,stages=records)
        c.write(folder/'failure.json',row)
        print('FAILED',row,flush=True)
        return row


def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=('prepare','generate','prefix','suffix'))
    p.add_argument('--workers',type=int,default=6)
    a=p.parse_args()
    assert 1<=a.workers<=6
    if a.mode=='prepare':
        prepare()
    elif a.mode=='generate':
        with ProcessPoolExecutor(min(2,a.workers)) as pool:
            qualified=list(pool.map(generate,CASES))
        if all(qualified): seal_inputs()
    else:
        verify()
        assert c.sc.read(HERE/'manifest.json').get('inputs'),'Input generation/qualification incomplete'
        jobs=[(case,profile,arm,a.mode=='prefix') for case in CASES for profile in PROFILES
              for arm in (('none',) if a.mode=='prefix' else ARMS)
              if not (HERE/'runs'/case/profile/('prefix' if a.mode=='prefix' else arm)).exists()]
        with ProcessPoolExecutor(a.workers) as pool:
            for f in as_completed([pool.submit(fit_path,*j) for j in jobs]):
                f.result()


if __name__=='__main__':
    main()
