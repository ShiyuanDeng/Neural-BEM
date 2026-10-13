"""MA-007 actual-hook qualification and maximum-dimension resource pilot.

This command never starts the comparison matrix before the required pilot gates.
All numerical work uses the frozen hook Problem or the two prescribed archived
hook states. The pilot is partial qualification, never policy/ceiling evidence.
"""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
import os
from pathlib import Path
import resource
import subprocess
import sys
import tarfile
import threading
from time import perf_counter
import traceback

import numpy as np
from bem_inverse.certified import CertifiedSpectralUpdate
from bem_inverse.geometry import resize
from bem_inverse.io import read, write, digest, curve_from
from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
from bem_inverse.physics import Execution
from . import campaign as c
from .ma007_retention import read, retain

CASE = 'hook__c13.3'
OUTPUT = c.ROOT/'results/validation/modal_atlas/MA-007'
PLAN = c.ROOT/'docs/iterations/modal_atlas/iteration_07/03_plan.md'
ARCHIVED = c.ROOT/'results/validation/cleaned_interfaces/DP-001/F_screen/runs'/CASE
COORD = Path('/tmp/neural-sdf-bem-ad-coordination')
EXECUTION = Execution(device='cuda', frequency_threads=4, audit_frequency_batch=2)
THREADS = dict(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
SCHEMA = 'MA007-pilot-1'


def sources():
    return sorted({*c.ROOT.glob('solvers/**/*.py'), Path(__file__).resolve(),
        *Path(__file__).parent.glob('ma007*.py'),
        Path(__file__).with_name('ma007_report.py'),
        *(Path(__file__).parent/n for n in ('__init__.py', 'campaign.py', 'scenes.py')),
        c.ROOT/'experiments/cleaned_interface/benchmark.py'})


def hashes():
    return {str(p.relative_to(c.ROOT)): digest(p) for p in sources() if p.is_file()}


def available_memory():
    values = {line.split(':')[0]:int(line.split()[1])*1024
              for line in Path('/proc/meminfo').read_text().splitlines()
              if line.startswith(('MemTotal:', 'MemAvailable:'))}
    return values


def monitor_gpu(stop, samples):
    while not stop.is_set():
        try:
            line=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.used',
                '--format=csv,noheader,nounits'],text=True,timeout=10).strip().splitlines()[0]
            total, used = [int(x.strip())*2**20 for x in line.split(',')]
            samples.append(dict(monotonic_seconds=perf_counter(),total_bytes=total,used_bytes=used))
        except Exception as exc:
            samples.append(dict(error=str(exc)))
        stop.wait(2)


def states(problem):
    return [('initial', problem.initial, c.start_path()),
            ('last_damped', curve_from(read(ARCHIVED/'stage_4_damped.json')['curve']),
             ARCHIVED/'stage_4_damped.json'),
            ('failed_endpoint', curve_from(read(ARCHIVED/'result.json')['final_curve']),
             ARCHIVED/'result.json')]


def prepare(folder):
    c.verify(require_inputs=True)
    folder.mkdir(parents=True, exist_ok=False)
    with tarfile.open(folder/'sources.tar.gz', 'w:gz') as archive:
        for p in sources():
            if p.is_file():
                archive.add(p, arcname=str(p.relative_to(c.ROOT)), recursive=False)
    paths = [c.start_path(), ARCHIVED/'stage_4_damped.json', ARCHIVED/'result.json']
    value = dict(experiment='MA-007', schema=SCHEMA, case=CASE,
        purpose='Phase A maximum-dimension pilot; NOT full fits or ceiling evidence',
        source_hashes=hashes(), source_archive_sha256=digest(folder/'sources.tar.gz'),
        plan_sha256=digest(PLAN), input_manifest_sha256=digest(c.INPUTS/'manifest.json'),
        state_inputs={str(p.relative_to(c.ROOT)):digest(p) for p in paths},
        execution=asdict(EXECUTION), environment=THREADS,
        memory_before=available_memory(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=c.ROOT, text=True).strip(),
        status=subprocess.check_output(['git','status','--short'], cwd=c.ROOT, text=True),
        limits=dict(wall_seconds=3600, artifact_bytes=10*2**30),
        expected_states=['initial','last_damped','failed_endpoint'],
        expected_maximum_cells_per_state=13, expected_subblock_checks_per_state=8,
        pending=['C0 recording/instrumentation pilot', 'complete atlas and local probes',
                 'initial/archived-state derivative qualification', 'Phase B retention decision',
                 'all cap, rung-exit, ordering, extension and confirmation fits'])
    write(folder/'manifest.json', value)
    return value


def control_worker(folder, enabled):
    """The actual historical feedback recipe; recording cannot supply decisions."""
    from bem_inverse import policies
    from bem_inverse.runner import fit
    from experiments.cleaned_interface import benchmark as ci
    from .ma007_recording import Recorder
    verify(folder)
    run=folder/('C0_recorded' if enabled else 'C0_disabled')
    run.mkdir(exist_ok=False)
    epoch=digest(folder/'manifest.json')
    recorder=Recorder(run/'recording',epoch) if enabled else None
    physics=ModalMuller(EXECUTION,observer=recorder)
    policy=policies.build('feedback',**policies.BENCHMARK_CONTRACT)
    problem=c.problem(CASE)
    started=perf_counter()
    def event(row):
        print(row['operation']['label'],row['reason'],flush=True)
    try:
        result=fit(problem,solver='modal_muller',physics=physics,execution=EXECUTION,
            policy=policy,output=run,geometry_update='certified_spectral',
            localization_adapter=c.keep_start,on_event=event)
        returned=perf_counter()
        metrics=ci.score(c.row(CASE),curve_from(result['final_curve']))
        residual=result.get('relative_residual')
        result.update(metrics=metrics,case=CASE,recovered=bool(result['final_audit_passed'] and
            metrics['rms_mm']<=1. and metrics['hausdorff_upper_mm']<=2. and residual is not None and
            np.all(np.asarray(residual)<=.003)),audited_output_seconds=returned-started,
            policy_spec=policies.settings('feedback',policies.BENCHMARK_CONTRACT),source_epoch=epoch)
    except Exception:
        result=dict(case=CASE,outcome='IMPLEMENTATION_FAILURE',traceback=traceback.format_exc(),recovered=False)
    finally:
        if recorder is not None:
            result['recording']=recorder.finish()
    result['recording_enabled']=enabled
    write(run/'result.json',result)
    print(result['outcome'],result['recovered'],flush=True)
    return result


def instrumentation_identity(folder):
    a,b=[folder/name for name in ('C0_recorded','C0_disabled')]
    result_a,result_b=read(a/'result.json'),read(b/'result.json')
    checks=dict(outcome=result_a['outcome']==result_b['outcome'],
        final_coefficients=np.array_equal(curve_from(result_a['final_curve']).coefficients,
                                         curve_from(result_b['final_curve']).coefficients))
    def accepted(path):
        return [{k:r[k] for k in ('stage','iteration','M','loss','units','curve')}
                for r in read(path/'accepted.json')['states']]
    checks['accepted_states']=accepted(a)==accepted(b)
    def trial_decisions(path):
        result=read(path/'result.json')
        return [[{k:t[k] for k in ('iteration','damping','backtrack','step_m','status','reason','loss',
                                   'gain_ratio','actual_decrease','predicted_decrease') if k in t}
                 for t in read(path/(stage['stage']+'.json'))['trials']]
                for stage in result['stages']]
    checks['trial_decisions']=trial_decisions(a)==trial_decisions(b)
    value=dict(passed=all(checks.values()),checks=checks,
        recorded_result_sha256=digest(a/'result.json'),disabled_result_sha256=digest(b/'result.json'),
        disabled_atlas_link='C0_recorded atlas, only after exact identity and full atlas qualification')
    write(folder/'instrumentation_identity.json',value)
    return value


def control(folder):
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
        fcntl.flock(compute,fcntl.LOCK_EX); fcntl.flock(source,fcntl.LOCK_SH)
        manifest=prepare(folder)
        manifest.update(purpose='Phase A C0 instrumentation pair; atlas not yet collected',
            user_authorization='2026-10-13 latest 19-fit plan, local array retention',
            expected_configurations=['C0_recorded','C0_disabled'])
        write(folder/'manifest.json',manifest)
        for enabled in (True,False):
            name='C0_recorded' if enabled else 'C0_disabled'
            env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
            with (folder/(name+'.log')).open('w') as log:
                done=subprocess.run([sys.executable,'-m','experiments.benchmark.ma007','control-worker',
                    '--folder',str(folder),'--recording','on' if enabled else 'off'],
                    cwd=c.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            if done.returncode:
                write(folder/(name+'_failure.json'),dict(returncode=done.returncode))
                raise RuntimeError(name+' failed; evidence retained')
        verify(folder)
        identity=instrumentation_identity(folder)
        write(OUTPUT/'state.json',dict(experiment='MA-007',phase='A',
            source_epoch=digest(folder/'manifest.json'),completed=['maximum-dimension pilot','C0 instrumentation pair'],
            instrumentation_passed=identity['passed'],full_study_complete=False,
            pending=['complete C0 atlas/probes and regeneration','derivative/workspace qualification',
                     'resource forecast/release','nine capacity fits','rung-exit fit','eight ordering fits',
                     'conditional extensions/confirmations','three-question final report']))
        print('INSTRUMENTATION_IDENTITY',identity['passed'],flush=True)


def verify(folder):
    c.verify(require_inputs=True)
    saved = read(folder/'manifest.json')
    if saved['source_hashes'] != hashes():
        raise ValueError('MA-007 source epoch changed; preserve this attempt and reseal')
    if digest(PLAN) != saved['plan_sha256'] or digest(folder/'sources.tar.gz') != saved['source_archive_sha256']:
        raise ValueError('MA-007 plan/source archive changed')
    if digest(c.INPUTS/'manifest.json') != saved['input_manifest_sha256']:
        raise ValueError('TG-002 input manifest changed')
    for p, sha in saved['state_inputs'].items():
        if digest(c.ROOT/p) != sha:
            raise ValueError('Archived pilot state changed: '+p)
    return saved


class Chunks:
    """Lossless independently retrievable chunks with exact read-back receipts."""
    def __init__(self, folder):
        self.folder = folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.rows = []
        self.seconds = 0.

    def save(self, name, arrays, identity, units=None):
        started = perf_counter()
        arrays = {key:np.asarray(value) for key,value in arrays.items()}
        if any(a.dtype.hasobject for a in arrays.values()):
            raise TypeError('Object arrays are not portable pilot evidence')
        path = self.folder/(name+'.npz')
        if path.exists():
            raise FileExistsError(path)
        np.savez_compressed(path, **arrays)
        metadata = {}
        with np.load(path, allow_pickle=False) as loaded:
            if set(loaded.files) != set(arrays):
                raise ValueError('Chunk keys changed on retrieval')
            for key, value in arrays.items():
                back = loaded[key]
                if back.shape != value.shape or back.dtype != value.dtype or back.tobytes() != value.tobytes():
                    raise ValueError('Lossless read-back defect: '+key)
                metadata[key] = dict(shape=list(value.shape), dtype=str(value.dtype),
                    bytes=value.nbytes, sha256=hashlib.sha256(value.tobytes()).hexdigest(),
                    units=(units or {}).get(key, 'see identity coordinate/trace conventions'))
        row = dict(schema=SCHEMA, path=str(path.relative_to(c.ROOT)), bytes=path.stat().st_size,
            sha256=digest(path), arrays=metadata, identity=identity, readback='bitwise_passed')
        self.rows.append(row)
        write(path.with_suffix('.json'), row)
        self.seconds += perf_counter()-started
        return row


class Capture:
    """Retain solver-owned arrays before the ephemeral handle is released."""
    def __init__(self):
        self.field = None
        self.reciprocal = None

    def __call__(self, kind, record):
        if kind == 'field':
            self.field = record
        elif kind == 'reciprocal':
            self.reciprocal = record


def permutation(band):
    return np.r_[0, np.column_stack((np.arange(1,band+1),np.arange(band+1,2*band+1))).ravel()]


def selected_observations(problem):
    return [(kind, o) for kind in ('real','damped') for o in getattr(problem, kind)
            if o.frequency_hz in (0.25e9, 2.5e9)]


def subblock_indices(small, large):
    width = 2*large+1
    first = np.arange(large-small, large+small+1)
    return np.r_[first, width+first]


def worker(folder, state_name):
    verify(folder)
    problem = c.problem(CASE)
    label, base, origin = next(s for s in states(problem) if s[0] == state_name)
    target = folder/label
    target.mkdir(exist_ok=False)
    chunks = Chunks(target/'chunks')
    started = perf_counter()
    curve = resize(base,384)
    update = CertifiedSpectralUpdate(problem.length_unit_m)
    prep = perf_counter()
    space = update.prepare(curve,159,384)
    prep_seconds = perf_counter()-prep
    perm = permutation(159)
    capture = Capture()
    physics = ModalMuller(EXECUTION, ModalSettings(coefficient_workspace=512,
                                                  cached_geometries=1), observer=capture)
    physics.validate(problem)
    identity = dict(state=label, source_sha256=read(folder/'manifest.json')['source_hashes'],
        state_input=str(origin.relative_to(c.ROOT)), state_sha256=digest(origin),
        parameterization='stored t; modes -K..K', trace='(u, |z_t| dn u), modes -Ku..Ku',
        derivative='complete certified_spectral Cartesian tangent per metre optimizer coordinate',
        channels='paired diagonal R @ X_s; source strength applied only to B_s',
        P=159, K=384, contrast=problem.contrast, length_unit_m=problem.length_unit_m,
        execution=asdict(EXECUTION), settings=asdict(physics.settings))
    chunks.save('state_and_directions', dict(coefficients=curve.coefficients,
        complete_cartesian_velocities=space.derivatives[:,perm], export_permutation=perm,
        sources=problem.real[0].acquisition.sources, receivers=problem.real[0].acquisition.receivers,
        source_strength=np.asarray(problem.real[0].acquisition.strength)), identity)
    cells, checks = [], []
    for kind, observation in selected_observations(problem):
        name = f'{kind}_{observation.frequency_hz/1e9:g}'
        top = None
        for cutoff in (320,352,384,64,192):
            begin = perf_counter()
            item = dict(catalog=kind, frequency_hz=observation.frequency_hz, K_u=cutoff, B_work=512)
            try:
                pred = physics.evaluate(curve,observation,problem.contrast,token(cutoff))
                jac = physics.derivative(pred,update,space)
                data = capture.field
                reciprocal = capture.reciprocal['X_r']
                record_identity = dict(identity, **item, wavenumber=observation.wavenumber)
                arrays = dict(prediction=pred.prediction, observed=observation.scattered,
                    residual=pred.prediction-observation.scattered, J_complete=jac[:,perm],
                    X_s=data['X_s'], X_r=reciprocal)
                if cutoff == 384:
                    arrays.update(A=data['A'],B_s=data['B_s'],B_r=data['B_r'],R=data['R'])
                    top = data['A'].copy()
                if cutoff in (64,192) and top is not None:
                    ids = subblock_indices(cutoff,384)
                    large = top[np.ix_(ids,ids)]
                    n = 2*cutoff+1
                    errors = {f'{i}{j}':float(np.linalg.norm(data['A'][i*n:(i+1)*n,j*n:(j+1)*n]-
                        large[i*n:(i+1)*n,j*n:(j+1)*n])/max(np.linalg.norm(large[i*n:(i+1)*n,j*n:(j+1)*n]),1e-30))
                        for i in range(2) for j in range(2)}
                    checks.append(dict(**item, witness=384, block_errors=errors,
                                       passed=all(e<=1e-12 for e in errors.values())))
                compute = perf_counter()-begin
                chunk = chunks.save(f'{name}_U{cutoff}',arrays,record_identity)
                item.update(status='computed', compute_seconds=compute,
                    system_residual=pred.diagnostics['system_residual'], artifact=chunk['path'],
                    artifact_bytes=chunk['bytes'], solver_diagnostics=pred.diagnostics)
            except Exception:
                item.update(status='failed', seconds=perf_counter()-begin, traceback=traceback.format_exc())
            cells.append(item)
            write(target/'progress.json', dict(state=label, cells=cells, subblock_checks=checks))
            print(label, name, cutoff, item['status'], flush=True)
        del top
    # Required B_work=1024 maximum workspace evaluation per prescribed state.
    big = ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=1024,cached_geometries=1),observer=capture)
    observation = problem.real[-1]
    begin = perf_counter()
    item = dict(catalog='real',frequency_hz=observation.frequency_hz,K_u=384,B_work=1024)
    try:
        pred = big.evaluate(curve,observation,problem.contrast,token(384))
        jac = big.derivative(pred,update,space)
        data = capture.field
        compute = perf_counter()-begin
        chunk = chunks.save('real_2.5_U384_B1024',dict(prediction=pred.prediction,
            observed=observation.scattered,J_complete=jac[:,perm],X_s=data['X_s'],
            X_r=capture.reciprocal['X_r']),dict(identity,**item,settings=asdict(big.settings)))
        item.update(status='computed',compute_seconds=compute,artifact=chunk['path'],
            artifact_bytes=chunk['bytes'],solver_diagnostics=pred.diagnostics)
    except Exception:
        item.update(status='failed',seconds=perf_counter()-begin,traceback=traceback.format_exc())
    cells.append(item)
    numerical_complete = len(cells)==21 and all(x['status']=='computed' for x in cells)
    value = dict(state=label,status='MEASURED' if numerical_complete else 'NUMERICAL_CELLS_UNRESOLVED',
        pilot_only=True,cells=cells,subblock_checks=checks,subblock_all_passed=len(checks)==8 and all(x['passed'] for x in checks),
        preparation_seconds=prep_seconds,io_seconds=chunks.seconds,elapsed_seconds=perf_counter()-started,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        physics=physics.receipt(),workspace1024_physics=big.receipt(),
        artifact_bytes=sum(x['bytes'] for x in chunks.rows),chunks=len(chunks.rows))
    write(target/'result.json',value)
    return value


def pilot(folder):
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
        fcntl.flock(compute,fcntl.LOCK_EX)
        fcntl.flock(source,fcntl.LOCK_SH)
        manifest = prepare(folder)
        started = perf_counter()
        completed = []
        status = 'RUNNING'
        gpu_samples=[]
        gpu_stop=threading.Event()
        gpu_thread=threading.Thread(target=monitor_gpu,args=(gpu_stop,gpu_samples),daemon=True)
        gpu_thread.start()
        for label in manifest['expected_states']:
            remaining = 3600-(perf_counter()-started)
            if remaining<=0:
                status='RESOURCE_BLOCKED';break
            if sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())>=10*2**30:
                status='RESOURCE_BLOCKED';break
            env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
            with (folder/f'{label}.log').open('w') as log:
                try:
                    done=subprocess.run([sys.executable,'-m','experiments.benchmark.ma007','worker',
                        '--folder',str(folder),'--state',label],cwd=c.ROOT,env=env,
                        stdout=log,stderr=subprocess.STDOUT,timeout=remaining)
                    path=folder/label/'result.json'
                    if done.returncode or not path.exists():
                        status='PILOT_PROCESS_FAILED'
                        write(folder/(label+'_failure.json'),dict(returncode=done.returncode,
                            log=str((folder/f'{label}.log').relative_to(c.ROOT))))
                        break
                    completed.append(read(path))
                except subprocess.TimeoutExpired:
                    status='RESOURCE_BLOCKED'
                    write(folder/(label+'_failure.json'),dict(outcome='WALL_TIME_LIMIT',
                        last_progress=str((folder/label/'progress.json').relative_to(c.ROOT))))
                    break
            write(folder/'state.json',dict(status=status,completed=[x['state'] for x in completed],
                pending=[x for x in manifest['expected_states'] if x not in [v['state'] for v in completed]]))
        verify(folder)
        gpu_stop.set()
        gpu_thread.join(timeout=12)
        if status=='RUNNING':
            status='MAXIMUM_PILOT_MEASURED' if all(x['status']=='MEASURED' for x in completed) else 'NUMERICAL_CELLS_UNRESOLVED'
        value=dict(status=status,full_study_complete=False,full_fits=0,
            elapsed_seconds=perf_counter()-started,states=completed,
            artifact_bytes=sum(p.stat().st_size for p in folder.rglob('*') if p.is_file()),
            resource_gate_released=False,next_required='C0 recording pilot and qualification; latest matrix/retention decision',
            outstanding=manifest['pending'])
        measured_gpu=[x for x in gpu_samples if 'used_bytes' in x]
        value['resources']=dict(memory_before=manifest['memory_before'],memory_after=available_memory(),
            peak_worker_rss_bytes=max((x['peak_rss_bytes'] for x in completed),default=None),
            peak_gpu_used_bytes=max((x['used_bytes'] for x in measured_gpu),default=None),
            gpu_capacity_bytes=measured_gpu[0]['total_bytes'] if measured_gpu else None)
        write(folder/'resource_samples.json',dict(samples=gpu_samples))
        write(folder/'pilot.json',value)
        write(OUTPUT/'state.json',dict(experiment='MA-007',**value,attempt=str(folder.relative_to(c.ROOT))))
        print(status,flush=True)
        return value


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('pilot','worker','verify','control','control-worker'))
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--state',choices=('initial','last_damped','failed_endpoint'))
    parser.add_argument('--recording',choices=('on','off'))
    args=parser.parse_args()
    if args.command=='pilot':
        pilot(args.folder.resolve())
    elif args.command=='worker':
        if args.state is None:
            parser.error('worker needs --state')
        worker(args.folder.resolve(),args.state)
    elif args.command=='control':
        control(args.folder.resolve())
    elif args.command=='control-worker':
        if args.recording is None:
            parser.error('control-worker needs --recording')
        control_worker(args.folder.resolve(),args.recording=='on')
    else:
        verify(args.folder.resolve())


if __name__=='__main__':
    main()
