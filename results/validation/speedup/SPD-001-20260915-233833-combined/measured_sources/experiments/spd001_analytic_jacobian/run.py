"""SPD-001: sequential, bounded six-arm numerical and optimizer timings."""
from __future__ import annotations
import argparse
from dataclasses import replace, asdict
from pathlib import Path
from collections import Counter
from contextlib import contextmanager
import hashlib,json,os,platform,resource,shutil,signal,sys,time,traceback
import numpy as np
import scipy
import torch
import run_top016_preflight as p
from sdf_inverse import radial_topology as rt
from sdf_inverse.analytic_jacobian import cartesian_residual_jacobian
from sdf_inverse.work_accounting import collect_work
from gpr_bem_kress.execution import execution

ROOT=Path(__file__).resolve().parents[2]
INPUT=ROOT/'results/validation/topology/TOP-023-20260915-181302-terminal-model'
ARMS=[('fd_cpu','fd','reference','cpu'),('analytic_cpu','analytic','reference','cpu'),
      ('fd_fast_cpu','fd','real_bessel','cpu'),('analytic_fast_cpu','analytic','real_bessel','cpu'),
      ('fd_fast_cuda','fd','real_bessel','cuda'),('analytic_fast_cuda','analytic','real_bessel','cuda')]
PLAN=ROOT/'docs/iterations/speedup/iteration_01/03_plan.md'
CAPS=dict(assembly_equivalents=8000,derivative_assemblies=4000,factorizations=5000)


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=lambda x:x.tolist() if hasattr(x,'tolist') else str(x)))


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def workers():
    result=[]
    for folder in Path('/proc').iterdir():
        if not folder.name.isdigit() or int(folder.name)==os.getpid():continue
        try:
            args=(folder/'cmdline').read_bytes().split(b'\0')
            if not args or not args[0]:continue
            cmd=b' '.join(args).decode(errors='replace')
            executable=Path(args[0].decode(errors='replace')).name
            cwd=str((folder/'cwd').resolve())
            if (executable.startswith('python') and (cwd==str(ROOT) or str(ROOT) in cmd)
                    and any(v in cmd for v in ('.py','pytest','experiments.'))) or executable=='ffmpeg':
                result.append(dict(pid=int(folder.name),command=cmd))
        except (OSError,PermissionError):pass
    return result


def sources():
    paths=[*sorted((ROOT/'solvers').rglob('*.py')),Path(__file__),
           ROOT/'run_top016_preflight.py', ROOT/'run_top017.py', ROOT/'run_top016_pilot.py',
           ROOT/'run_fourier_topology_controller.py',
           ROOT/'run_radial_fourier_topology_inverse.py']
    return {str(x.relative_to(ROOT)):sha(x) for x in paths}


def environment():
    return dict(platform=platform.platform(),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
        torch=torch.__version__,gpu=torch.cuda.get_device_name(0),blas_threads=1,workers=workers(),
        load=list(os.getloadavg()),cpu='Intel Core Ultra 9 285K',pid=os.getpid())


def charge(counts):
    dense=counts.get('dense_factor_and_solve',0)
    fact=counts.get('factorization',0)
    deriv=counts.get('derivative_assembly',0)
    return dict(assembly_equivalents=dense+fact+deriv,derivative_assemblies=deriv,factorizations=dense+fact)


class Budget:
    def __init__(self,bundle):
        self.bundle=bundle;self.path=bundle/'budget.json'
        self.data=read(self.path) if self.path.exists() else dict(counts=dict.fromkeys(CAPS,0),seconds={})
    @contextmanager
    def stage(self,name):
        start=time.perf_counter();remaining=3600-self.data['seconds'].get(name,0.)
        if remaining<=0:raise RuntimeError('Stage wall budget exhausted: '+name)
        previous=signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('SPD-001 stage wall ceiling')))
        signal.setitimer(signal.ITIMER_REAL,remaining)
        try:yield
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
            self.data['seconds'][name]=self.data['seconds'].get(name,0.)+time.perf_counter()-start
            write(self.path,self.data)
    def add(self,context):
        for key,value in charge(context.counts).items():self.data['counts'][key]+=value
        write(self.path,self.data)
        if any(self.data['counts'][k]>v for k,v in CAPS.items()):raise RuntimeError('SPD-001 work ceiling')


def inputs():
    frozen=read(INPUT/'inputs.json');state=p.driver.deserialize_state(frozen['state'])
    observed=np.array(frozen['training']['observed_real'])+1j*np.array(frozen['training']['observed_imag'])
    return frozen,state,observed


def check(bundle):
    manifest=read(bundle/'manifest.json')
    if sources()!=manifest['source_sha256']:raise RuntimeError('Measured source changed')
    for name,h in manifest['input_sha256'].items():
        if sha(ROOT/name)!=h:raise RuntimeError('Measured input changed: '+name)
    active=workers()
    if active:raise RuntimeError('Other numerical/render worker: '+str(active))


def relative(a,b):return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),np.finfo(float).tiny))

def jacobian_errors(actual,reference):
    errors=np.linalg.norm(actual-reference,axis=0)/np.maximum(np.linalg.norm(reference,axis=0),np.finfo(float).tiny)
    return dict(relative_error=relative(actual,reference),worst_column_relative_error=float(np.max(errors)))


def prepare(bundle):
    if (bundle/'manifest.json').exists():return
    assert not workers(),workers()
    assert all(os.environ.get(k)=='1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'))
    shutil.copyfile(PLAN,bundle/'approved_plan.md')
    paths=[INPUT/'inputs.json',INPUT/'model.json']
    write(bundle/'manifest.json',dict(source_sha256=sources(),input_sha256={str(x.relative_to(ROOT)):sha(x) for x in paths},environment=environment(),
        approvals='User: go ahead; concrete runtime numbers; check running terminals',arms=ARMS,
        scope='saved-state Jacobians and one fixed-topology LM update; no full reconstruction claim'))
    for name in sources():
        dest=bundle/'measured_sources'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    for path in paths:shutil.copyfile(path,bundle/path.name.replace('.json','_input.json'))
    if Path('/tmp/spd001_tests.log').exists():shutil.copyfile('/tmp/spd001_tests.log',bundle/'tests.log')


def qualify(bundle,budget):
    if (bundle/'qualification.json').exists():
        assert read(bundle/'qualification.json')['status']=='PASS';return
    frozen,state,observed=inputs();basis=state.gauge_tangent_basis();saved=read(INPUT/'model.json')
    np.testing.assert_allclose(basis,saved['basis'],atol=1e-14)
    data=p.training_data(p.TRAIN,observed);solve=p.driver.baseline.iteration01_solve_config()
    rows=[];reference=None
    for label,_,kernels,device in [ARMS[1],ARMS[3],ARMS[5]]:
        check(bundle);tick=time.perf_counter()
        with execution(kernels=kernels,device=device) as work:
            try:
                matrix,pred=cartesian_residual_jacobian(state,data,p.driver.baseline._geometry_config(256),solve_config=solve,directions=basis)
            finally:budget.add(work)
        if reference is None:reference=matrix
        errors=jacobian_errors(matrix,np.asarray(saved['jacobian']))
        parity=jacobian_errors(matrix,reference)
        passed=max(errors.values())<1e-4 and max(parity.values())<1e-9
        rows.append(dict(arm=label,seconds=time.perf_counter()-tick,against_saved_fd=errors,against_analytic_cpu=parity,passed=passed,work=work.counts))
        np.savez(bundle/f'qualification_{label}.npz',matrix=matrix,prediction=pred,basis=basis)
        write(bundle/'qualification_partial.json',rows);print('QUALIFY',label,json.dumps(rows[-1]),flush=True)
        if not passed:raise RuntimeError('Saved full Jacobian qualification failed')
    # Production/refined selected direction checks; no full refined Jacobian.
    selected=basis[[0,-1]]
    check(bundle)
    with execution(kernels='real_bessel') as work:
        try:refined,pred=cartesian_residual_jacobian(state,data,p.driver.baseline._geometry_config(512),solve_config=solve,directions=selected)
        finally:budget.add(work)
    errors=jacobian_errors(refined,reference[:,[0,-1]])
    rows.append(dict(check='selected_256_512_sensitivity',**errors,passed=max(errors.values())<2e-5,work=work.counts))
    if not rows[-1]['passed']:raise RuntimeError('Refined sensitivity qualification failed')
    write(bundle/'qualification.json',dict(status='PASS',rows=rows,permanent_tests='tests.log'))


def run_arm(bundle,budget,arm,kind,repetition):
    label,mode,kernels,device=arm
    key=f'{kind}_{label}_{repetition}';destination=bundle/'arms'/key
    if (destination/'result.json').exists():return read(destination/'result.json')
    check(bundle);destination.mkdir(parents=True,exist_ok=False)
    frozen,state,observed=inputs();indices=[3] if kind=='jacobian' else [0,1,2,3]
    frequencies=np.asarray(p.TRAIN)[indices];data=p.training_data(frequencies,observed[:,indices])
    config=rt.ParameterFDConfig(**frozen['optimizer'])
    config=replace(config,max_iterations=1,gradient_tolerance=1e50 if kind=='jacobian' else config.gradient_tolerance)
    # An enormous stopping tolerance is used only for initial-Jacobian timing;
    # the actual one-update comparison uses the stored optimizer tolerances.
    frames=[];matrices=[];events=Counter();refined_cache={};acceptance=[]
    def diagnostic(event,payload):
        events[event]+=1
        if event=='jacobian_complete':matrices.append(np.array(payload['matrix']))
    def progress(frame):
        row=dict(iteration=frame.iteration,parameters=frame.parameter_vector,loss=frame.loss,
            gradient=frame.gradient,damping=frame.damping,evaluations=frame.evaluation_count)
        frames.append(row);write(destination/'trajectory.json',frames)
    # Match production/refined acceptance already used in TOP-017 continuation.
    import run_top017 as production
    def refined(evaluation):
        key=evaluation.state.parameter_vector().tobytes()
        if key not in refined_cache:
            refined_cache[key]=rt.evaluate_multiradial_objective(evaluation.state,data,
                p.driver.baseline._geometry_config(512),solve_config=p.driver.baseline.iteration01_solve_config())
        return refined_cache[key]
    def accept(base,candidate):
        rb,rc=refined(base),refined(candidate)
        row=production.old.acceptance(base.loss,candidate.loss,rb.loss,rc.loss)
        discrepancy=p.relative(candidate.prediction,rc.prediction)
        if np.any(discrepancy>np.where(frequencies>.5e9+1.,1e-7,1e-5)):
            raise RuntimeError('Production/refined candidate predictions disagree')
        acceptance.append(dict(**row,prediction_discrepancy=discrepancy));return row['accepted']
    before=environment();torch.cuda.synchronize();tick=time.perf_counter();result=None;error=None
    with execution(kernels=kernels,device=device) as work,collect_work() as passive:
        try:
            result=rt.run_multiradial_fd_inverse(state,data,p.driver.baseline._geometry_config(256),
                solve_config=p.driver.baseline.iteration01_solve_config(),config=config,
                cartesian_gauge=True,minimum_component_radius_m=.008,feasible_fd_jacobian=True,
                feasibility_geometry_configs=(p.driver.baseline._geometry_config(512),),
                loss_change_stopping=False,jacobian_mode=mode,analytic_constraint_policy='true',
                diagnostic_callback=diagnostic,progress_callback=progress,
                candidate_acceptance_callback=accept if kind=='optimizer' else None)
            torch.cuda.synchronize()
        except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
        finally:
            seconds=time.perf_counter()-tick;budget.add(work)
    after=environment();check(bundle)
    row=dict(kind=kind,arm=label,repetition=repetition,seconds=seconds,events=dict(events),
        execution_counts=work.counts,execution_seconds=work.seconds,work=passive.snapshot(),
        assembly_equivalents=charge(work.counts),environment_before=before,environment_after=after,
        status='PASS' if error is None else 'FAILED',error=error,optimizer_config=asdict(config),
        frequencies_hz=frequencies,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    if result is not None:row.update(stop_reason=result.stop_reason,accepted_updates=len(result.iterations)-1,
        initial_loss=frames[0]['loss'],final_loss=frames[-1]['loss'],final_parameters=result.final_state.parameter_vector(),
        one_sided_columns=result.one_sided_jacobian_column_count,unresolved_columns=result.unresolved_jacobian_column_count)
    for i,matrix in enumerate(matrices):np.save(destination/f'jacobian_{i}.npy',matrix)
    write(destination/'acceptance.json',acceptance);write(destination/'result.json',row)
    print('ARM',kind,label,repetition,seconds,row['status'],flush=True)
    if error is not None:raise RuntimeError(error['message'])
    return row


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--phase',choices=['qualification','jacobian','optimizer','all'],default='all')
    args=parser.parse_args();bundle=args.bundle.resolve();prepare(bundle);budget=Budget(bundle)
    torch.ones(2,device='cuda',dtype=torch.complex128);torch.cuda.synchronize()
    try:
        if args.phase in ('qualification','jacobian','all'):
            with budget.stage('qualification_and_jacobian'):
                qualify(bundle,budget)
                if args.phase in ('jacobian','all'):
                    for rep in range(3):
                        for arm in (ARMS if rep%2==0 else list(reversed(ARMS))):run_arm(bundle,budget,arm,'jacobian',rep)
        if args.phase in ('optimizer','all'):
            assert read(bundle/'qualification.json')['status']=='PASS'
            with budget.stage('optimizer'):
                for arm in ARMS:run_arm(bundle,budget,arm,'optimizer',0)
        write(bundle/'execution_status.json',dict(status='COMPLETE',phase=args.phase))
    except BaseException as exc:
        write(bundle/'execution_status.json',dict(status='STOPPED',phase=args.phase,error=repr(exc),traceback=traceback.format_exc()))
        raise


if __name__=='__main__':main()
