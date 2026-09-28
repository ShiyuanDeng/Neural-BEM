"""SC-050 frozen, observation-only localization and full-path ablations."""
import argparse
from dataclasses import asdict, replace
import importlib.util
from pathlib import Path
import subprocess
import tarfile
import time
import traceback
import numpy as np

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.forward import solve, ordered_calls
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import Ledger, Stop, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record
from experiments.spd014_geometry.runtime import geometry_acceleration
from experiments.spd014_geometry.run import environment
from ordered_boundary.validation_cache import validation_cache, geometry_validation

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sc050_parent', HERE.parent/'SC-049-far-circle-to-c/run.py')
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
c = old.c
write = c.write
ARMS = ('baseline','low','localize','localize_low','small_steps','refined')
SCENES = {
    'development_c': dict(start=[.32,.62], kind='original_c', center=[.5,.5], rotation=0.),
    'opposite_c': dict(start=[.68,.36], kind='original_c', center=[.5,.5], rotation=0.),
    'shifted_rotated_c': dict(start=[.31,.65], kind='c', center=[.537,.466], rotation=.87),
    'shifted_star': dict(start=[.68,.32], kind='star', center=[.467,.537], rotation=.41),
    'new_asymmetric': dict(start=[.31,.32], kind='asymmetric', center=[.543,.551], rotation=-.32),
    'new_thin_c': dict(start=[.69,.66], kind='thin_c', center=[.465,.473], rotation=-.55),
    'noisy_asymmetric': dict(start=[.31,.32], kind='asymmetric', center=[.543,.551], rotation=-.32, noise=.01, seed=50061),
}
TRANSFER = tuple(k for k in SCENES if k != 'development_c')
FIT_CAP, FIT_SECONDS = 13412, 1800


def transform(curve, center, rotation):
    coef = curve.coefficients.copy()*np.exp(1j*rotation)
    coef[curve.band] += (complex(*center)-sc.CENTER)/sc.LENGTH
    return FourierCurve(coef)


def truth_fixture(scene):
    d = SCENES[scene]
    t = 2*np.pi*np.arange(8192)/8192
    if d['kind'] in ('c','original_c'):
        curve = ac.truth_curve('circle_to_c')
    elif d['kind'] == 'star':
        curve = ac.truth_curve('circle_to_star')
    elif d['kind'] == 'asymmetric':
        r = .92+.16*np.cos(3*t)+.12*np.sin(4*t)+.055*np.cos(7*t+.4)
        curve = FourierCurve.from_samples(r*np.exp(1j*t),8)
    else:
        R,w,alpha=.84,.23,np.radians(122.)
        cap=np.linspace(0,np.pi,800)
        p=np.concatenate(((R+w)*np.exp(1j*np.linspace(-alpha,alpha,2400)),
            R*np.exp(1j*alpha)+w*np.exp(1j*(alpha+cap)),
            (R-w)*np.exp(1j*np.linspace(alpha,-alpha,2400)),
            R*np.exp(-1j*alpha)+w*np.exp(1j*(-alpha+np.pi+cap))))
        s=np.r_[0,np.cumsum(np.abs(np.diff(np.r_[p,p[0]])))]
        u=np.linspace(0,s[-1],8192,endpoint=False)
        z=np.interp(u,s,np.r_[p.real,p[0].real])+1j*np.interp(u,s,np.r_[p.imag,p[0].imag])
        curve=FourierCurve.from_samples(z,16)
    return transform(curve,d['center'],d['rotation'])


def source_paths():
    paths={sc.ROOT/p for p in sc.source_hashes()}
    paths.update(sc.ROOT/p for p in c.sources())
    paths.update((Path(__file__).resolve(),HERE/'plan.md',Path(old.__file__)))
    paths.update((sc.ROOT/'experiments/spd014_geometry').glob('*.py'))
    return sorted(paths)


def verify(require_inputs=True):
    m=sc.read(HERE/'manifest.json')
    current=m['amendments'][-1] if m.get('amendments') else m
    for mapping in (current['sources'],m.get('inputs',{})):
        for path,digest in mapping.items():
            assert sc.digest(sc.ROOT/path)==digest, 'Frozen file changed: '+path
    assert sc.digest(HERE/'sources.tar.gz')==m['archive_sha256']
    for amendment in m.get('amendments',[]):
        assert sc.digest(HERE/amendment['archive'])==amendment['archive_sha256']
    if require_inputs:
        assert m.get('inputs_sealed'), 'Inputs not sealed'


def prepare():
    if (HERE/'manifest.json').exists():
        raise FileExistsError('Preserve existing campaign')
    paths=source_paths()
    with tarfile.open(HERE/'sources.tar.gz','w:gz') as archive:
        for p in paths:
            archive.add(p,arcname=str(p.relative_to(sc.ROOT)),recursive=False)
    write(HERE/'manifest.json',dict(experiment='SC-050',sources={str(p.relative_to(sc.ROOT)):sc.digest(p) for p in paths},
        archive_sha256=sc.digest(HERE/'sources.tar.gz'),scenes=SCENES,development_arms=ARMS,
        maximum_attempts=18,fit_units_cap=FIT_CAP,fit_seconds_cap=FIT_SECONDS,
        parent_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),environment=environment()))
    for scene in SCENES:
        folder=HERE/'inputs'/scene
        folder.mkdir(parents=True,exist_ok=False)
        target=truth_fixture(scene)
        target.validate()
        initial=FourierCurve.circle(.065/sc.LENGTH,(complex(*SCENES[scene]['start'])-sc.CENTER)/sc.LENGTH)
        initial.validate()
        write(folder/'truth.json',ast.curve_record(target))
        write(folder/'initial.json',ast.curve_record(initial))
    print('FROZEN',len(paths),'sources; seven scenes, six transfer',flush=True)


def predictions(curve, catalog, nodes):
    with validation_cache('cache'), ordered_calls(lambda o: solve(curve,o.wavenumber,ac.contrast(),o.acquisition,nodes).prediction,catalog) as calls:
        return np.column_stack([call() for call in calls])


def generate():
    verify(False)
    template=ast.catalog_only('circle_to_c')
    for scene,d in SCENES.items():
        folder=HERE/'inputs'/scene
        if (folder/'qualification.json').exists():
            continue
        started=time.perf_counter()
        target=ast.curve_from(sc.read(folder/'truth.json'))
        if d['kind']=='original_c':
            source=ast.source_folder('circle_to_c')
            source_data=sc.read(source/'observations.json')
            clean=np.array(source_data['observed_real'])+1j*np.array(source_data['observed_imag'])
            check=dict(passed=bool(sc.read(source/'oracle_check.json')['passed']), units=0,
                reused={str((source/n).relative_to(sc.ROOT)):sc.digest(source/n) for n in ('observations.json','truth.json','oracle_check.json')})
        elif scene=='noisy_asymmetric':
            src=sc.read(HERE/'inputs/new_asymmetric/observations.json')
            clean=np.array(src['clean_real'])+1j*np.array(src['clean_imag'])
            check=dict(passed=sc.read(HERE/'inputs/new_asymmetric/qualification.json')['passed'],units=0,reused='new_asymmetric')
        else:
            a,b=[predictions(target,template,n) for n in (1024,2048)]
            disc=ac.relative(a,b)
            ids=[0,8,18]
            kress=ac.kress_predictions(target,[ac.CATALOG_HZ[i] for i in ids],1024)
            cross=ac.relative(kress,b[:,ids])
            clean=b
            check=dict(passed=bool(max(disc)<=1e-8 and max(cross)<=1e-8),units=41,
                refinement_relative=disc,cross_kress_relative=cross,cross_frequencies_hz=[ac.CATALOG_HZ[i] for i in ids])
        data=clean.copy()
        if d.get('noise'):
            sigma=d['noise']*np.linalg.norm(clean,axis=0)/np.sqrt(2*len(clean))
            rng=np.random.default_rng(d['seed'])
            data+=sigma[None,:]*(rng.normal(size=data.shape)+1j*rng.normal(size=data.shape))
        check['seconds']=time.perf_counter()-started
        write(folder/'observations.json',dict(observed_real=data.real,observed_imag=data.imag,
            clean_real=clean.real,clean_imag=clean.imag,frequencies_hz=ac.CATALOG_HZ,
            realized_noise_relative=ac.relative(data,clean)))
        write(folder/'qualification.json',check)
        print('INPUT',scene,check['passed'],round(check['seconds'],2),flush=True)
    m=sc.read(HERE/'manifest.json')
    m.update(inputs_sealed=True,inputs={str(p.relative_to(sc.ROOT)):sc.digest(p) for p in sorted((HERE/'inputs').rglob('*.json'))})
    for scene in ('development_c','opposite_c'):
        m['inputs'].update(sc.read(HERE/'inputs'/scene/'qualification.json')['reused'])
    write(HERE/'manifest.json',m)


def fitting_data(scene):
    # Deliberately no truth path in this entry point.
    folder=HERE/'inputs'/scene
    d=sc.read(folder/'observations.json')
    return ac.observations(np.array(d['observed_real'])+1j*np.array(d['observed_imag'])), ast.curve_from(sc.read(folder/'initial.json'))


def setup(catalog,arm):
    prefix,config=ast.schedules(catalog,'baseline')
    stages=[replace(s,curve_modes=2*s.update_modes+2) for s in prefix]
    full=dict(observations=tuple(catalog),weights=tuple(np.ones(19)/19),
        discrepancy_tolerances=tuple(1e-5 if f<=.5e9 else 1e-7 for f in ac.CATALOG_HZ))
    stages += [replace(stages[-1],label=f'release_M{m}',update_modes=m,curve_modes=192,quota=1500,**full) for m in (11,15,19)]
    stages += [replace(stages[-1],label=f'fixed_M{m}',update_modes=m,quota=304) for m in (25,31,37)]
    if arm in ('low','localize_low'):
        stages.insert(0,replace(stages[0],label='warmup_025',observations=(catalog[0],),weights=(1.,),
            discrepancy_tolerances=(1e-5,),update_modes=1,curve_modes=4,iterations=44,quota=600))
    if arm=='small_steps':
        config=replace(config,step_bounds_m=tuple(x/4 for x in config.step_bounds_m))
    if arm=='refined':
        stages=[replace(s,nodes=1024,refined_nodes=2048) for s in stages]
    return stages,config


def circle_exterior_clearance(parameters_m,catalog):
    """Exact circular-domain precheck using known acquisition coordinates only."""
    points=np.concatenate([getattr(o.acquisition,key) for o in catalog for key in ('sources','receivers')])
    physical=points*sc.LENGTH+np.array([sc.CENTER.real,sc.CENTER.imag])
    return float(np.min(np.linalg.norm(physical-parameters_m[:2],axis=1))-parameters_m[2])


def localize(catalog,folder):
    started=time.perf_counter()
    obs=catalog[:3]
    observed=np.column_stack([o.scattered for o in obs])
    norms=np.linalg.norm(observed,axis=0)
    records=[]
    units=0
    cache={}
    def evaluate(x,grid=False):
        nonlocal units
        key=tuple(np.round(x,12))+(grid,)
        if key in cache:
            return cache[key]
        x=np.asarray(x)
        if not (.015<=x[2]<=.075 and np.all(x[:2]-x[2]>=.2) and np.all(x[:2]+x[2]<=.8)):
            return np.inf
        if units+6>2000 or time.perf_counter()-started>600:
            raise RuntimeError('Localization budget exhausted')
        nodes=(128,256) if grid else (512,1024)
        clearance=circle_exterior_clearance(x,obs)
        record=dict(parameters_m=x,loss=None,qualified=False,nodes=nodes,exterior_clearance_m=clearance)
        loss=np.inf
        if clearance<=32*np.finfo(float).eps:
            record.update(reason='source_or_receiver_not_exterior',attempted_units=0)
        else:
            curve=FourierCurve.circle(x[2]/sc.LENGTH,(complex(*x[:2])-sc.CENTER)/sc.LENGTH)
            before=units
            try:
                values=[]
                for n in nodes:
                    units+=len(obs)  # charge dispatched batches, including failures
                    values.append(predictions(curve,obs,n))
                a,b=values
                disc=ac.relative(a,b)
                passed=bool(np.all(np.isfinite(disc)) and max(disc)<=1e-7)
                value=.5*float(np.mean((np.linalg.norm(b-observed,axis=0)/norms)**2))
                record.update(loss=value,qualified=passed,field_relative=disc,
                              reason='qualified' if passed else 'resolution_disagreement')
                if passed:
                    loss=value
            except (ValueError,FloatingPointError,np.linalg.LinAlgError) as exc:
                record.update(reason='forward_refused',detail=str(exc))
            record['attempted_units']=units-before
        record['units']=units
        records.append(record)
        write(folder/'localization_progress.json',dict(rows=records,units=units,seconds=time.perf_counter()-started))
        cache[key]=loss
        return loss
    grid=[]
    for x in np.linspace(.28,.72,9):
        for y in np.linspace(.28,.72,9):
            for r in (.025,.045,.065):
                p=np.array([x,y,r]);grid.append((evaluate(p,True),p))
    grid_loss,best=min(grid,key=lambda row:row[0])
    if not np.isfinite(grid_loss):
        raise RuntimeError('No admissible, qualified grid candidate')
    value=evaluate(best)
    if not np.isfinite(value):
        raise RuntimeError('Selected grid candidate failed 512/1024 qualification')
    steps=np.array([.02,.02,.0075])
    for iteration in range(12):
        neighbors=[(evaluate(best+sign*steps[j]*np.eye(3)[j]),best+sign*steps[j]*np.eye(3)[j])
                   for j in range(3) for sign in (-1,1)]
        candidate,p=min(neighbors,key=lambda row:row[0])
        if candidate<value:
            value,best=candidate,p
        else:
            steps/=2
    row=dict(rows=records,parameters_m=best,loss=value,units=units,seconds=time.perf_counter()-started,
        grid_shape=[9,9,3],frequencies_hz=ac.CATALOG_HZ[:3])
    write(folder/'localization.json',row)
    print('LOCALIZED',folder.parent.name,folder.name,best.tolist(),'units',units,flush=True)
    return FourierCurve.circle(best[2]/sc.LENGTH,(complex(*best[:2])-sc.CENTER)/sc.LENGTH),row


def audit(curve,stage,config,catalog,folder,label):
    started=time.perf_counter()
    full=old.all_frequency_stage(stage,catalog)
    with old.deadline(300),validation_cache('cache'):
        row=c.audit(curve,full,config)
    row['seconds']=time.perf_counter()-started
    write(folder/f'{label}_audit.json',row)
    return row


def attempt(scene,arm):
    verify()
    folder=HERE/'runs'/scene/arm
    if (folder/'result.json').exists():
        return sc.read(folder/'result.json')
    folder.mkdir(parents=True,exist_ok=False)
    if not sc.read(HERE/'inputs'/scene/'qualification.json')['passed']:
        row=dict(scene=scene,arm=arm,outcome='WITHHELD_INPUT',recovered=False)
        write(folder/'result.json',row);return row
    catalog,initial=fitting_data(scene)
    stages,config=setup(catalog,arm)
    curve=c.resize(initial,stages[0].curve_modes)
    write(folder/'configuration.json',dict(scene=scene,arm=arm,initial=ast.curve_record(curve),
        stages=[stage_record(s) for s in stages],backend=asdict(config),fit_cap=FIT_CAP,fit_seconds=FIT_SECONDS))
    started=time.perf_counter()
    last_stage=stages[0]
    accepted=[];rows=[];loc=dict(units=0,seconds=0.)
    ledger=None
    try:
        pre=audit(curve,last_stage,config,catalog,folder,'initial')
        if not pre['passed']:
            raise RuntimeError('Initial full-catalog audit failed')
        fit_started=time.perf_counter()
        if arm.startswith('localize'):
            curve,loc=localize(catalog,folder)
        ledger=Ledger(cap=FIT_CAP-loc['units'],seconds=max(0.,FIT_SECONDS-loc['seconds']))
        update=c.reference.ProjectedUpdate(sc.LENGTH)
        outcome='COMPLETED_SCHEDULE'
        for stage in stages:
            last_stage=stage
            if stage.label=='fixed_M25':
                curve,_=c.treatment(curve,'once',0)
            else:
                curve=c.resize(curve,stage.curve_modes)
            try:
                ledger.begin_stage(stage.label,stage.quota)
            except Stop as exc:
                outcome=exc.code;break
            def checkpoint(iteration,evaluation):
                accepted.append(dict(stage=stage.label,iteration=iteration,M=stage.update_modes,
                    loss=evaluation.loss,units=loc['units']+ledger.units,curve=ast.curve_record(evaluation.curve)))
                write(folder/'accepted.json',dict(states=accepted))
            with geometry_validation('cache'):
                result=fit_stage(curve,stage,ac.contrast(),update,config,ledger,on_accept=checkpoint)
            curve=result.curve
            row=dict(stage=stage.label,M=stage.update_modes,K=stage.curve_modes,outcome=result.outcome,
                stop=result.stop_reason,detail=result.detail,accepted_steps=result.accepted_steps,
                initial_loss=result.initial_loss,final_loss=result.final_loss,work=ledger.snapshot(),
                seconds=result.seconds,curve=ast.curve_record(curve))
            rows.append(row)
            write(folder/f'{stage.label}.json',dict(row,history=result.history,trials=result.trials,acceptance_checks=result.acceptance_checks))
            write(folder/'checkpoint.json',dict(stages=rows,curve=ast.curve_record(curve),work=ledger.snapshot()))
            print('STAGE',scene,arm,stage.label,result.outcome,result.final_loss,ledger.units,flush=True)
            if result.outcome not in (NORMAL_RETURN,STAGE_QUOTA):
                outcome=result.outcome;break
        fit_seconds=time.perf_counter()-fit_started
        final=audit(curve,last_stage,config,catalog,folder,'final')
        # Extra endpoint data evaluation is charged separately, never feeds fitting.
        endpoint_started=time.perf_counter()
        pred=predictions(curve,catalog,last_stage.refined_nodes)
        observed=np.column_stack([o.scattered for o in catalog])
        residual=ac.relative(pred,observed)
        endpoint_seconds=time.perf_counter()-endpoint_started
        # Truth loaded only after the fit and independent audit have returned.
        truth=ast.curve_from(sc.read(HERE/'inputs'/scene/'truth.json'))
        metrics=old.score(curve,truth)
        noise=np.array(sc.read(HERE/'inputs'/scene/'observations.json')['realized_noise_relative'])
        is_noisy=bool(SCENES[scene].get('noise'))
        residual_limits=np.maximum(.003,3*noise) if is_noisy else np.full(19,.003)
        recovered=bool(final['passed'] and metrics['rms_mm']<=1. and metrics['hausdorff_upper_mm']<=2.
                       and np.all(residual<=residual_limits))
        total_units=loc['units']+ledger.units+pre['work']['work_units']+final['work']['work_units']+19
        row=dict(scene=scene,arm=arm,outcome=outcome,recovered=recovered,noisy=is_noisy,metrics=metrics,
            final_curve=ast.curve_record(curve),initial_audit_passed=pre['passed'],final_audit_passed=final['passed'],
            relative_residual=residual,maximum_residual=float(max(residual)),residual_limits=residual_limits,
            localization={k:v for k,v in loc.items() if k!='rows'},fit_work=ledger.snapshot(),
            fit_and_localization_units=loc['units']+ledger.units,total_units=total_units,
            fit_and_localization_seconds=fit_seconds,endpoint_seconds=endpoint_seconds,
            seconds=time.perf_counter()-started,stages=rows)
    except Exception:
        row=dict(scene=scene,arm=arm,outcome='EXCEPTION',recovered=False,traceback=traceback.format_exc(),
            last_curve=ast.curve_record(curve),stages=rows,work=None if ledger is None else ledger.snapshot(),
            localization={k:v for k,v in loc.items() if k!='rows'},seconds=time.perf_counter()-started)
    write(folder/'result.json',row)
    print('RESULT',scene,arm,row['outcome'],row['recovered'],row.get('metrics'),flush=True)
    return row


def develop():
    verify()
    results=[attempt('development_c',arm) for arm in ARMS]
    eligible=[r for r in results if r['arm']!='baseline' and 'maximum_residual' in r]
    if not eligible:
        raise RuntimeError('No development endpoint to select')
    def rank(r):
        group=0 if r['outcome']=='COMPLETED_SCHEDULE' and r['final_audit_passed'] else 1 if r['final_audit_passed'] else 2
        return (group,r['maximum_residual'],r['fit_and_localization_units'],r['arm'])
    best=min(eligible,key=rank)
    selection=dict(arm=best['arm'],development_only=True,rank=rank(best),
        qualified=best['final_audit_passed'],rule='complete+audit, audit, other; max residual, units, name',
        candidates=[dict(arm=r['arm'],rank=rank(r)) for r in eligible],
        development_hashes={r['arm']:sc.digest(HERE/'runs/development_c'/r['arm']/'result.json') for r in results})
    write(HERE/'selection.json',selection)
    print('SELECTED',selection['arm'],selection['rank'],flush=True)


def transfer():
    verify()
    selection=sc.read(HERE/'selection.json')
    for arm,digest in selection['development_hashes'].items():
        assert sc.digest(HERE/'runs/development_c'/arm/'result.json')==digest
    for i,scene in enumerate(TRANSFER):
        arms=('baseline',selection['arm']) if i%2==0 else (selection['arm'],'baseline')
        for arm in arms:
            attempt(scene,arm)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('prepare','generate','develop','transfer','verify'))
    args=parser.parse_args()
    with geometry_acceleration('both'):
        globals()[args.phase]()
