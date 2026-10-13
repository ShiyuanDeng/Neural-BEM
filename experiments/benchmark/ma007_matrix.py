"""Prepare and dispatch MA-007's 18 nominal research fits after an explicit go.

Preparation runs no inverse, atlas, probe or derivative computation. The baseline
is the saved C0 run/atlas. Each fit starts independently at the sealed TG-002
circle; returned truth-based scores never enter the numerical controller.
"""
import argparse
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback
import numpy as np
from bem_inverse.four_control_policy import FourControlPolicy
from bem_inverse.io import write,digest,curve_from
from bem_inverse.modal_accuracy import IndependentModalMuller
from bem_inverse.runner import fit
from . import campaign as c
from .ma007 import CASE,OUTPUT,PLAN,COORD,EXECUTION,THREADS,sources,hashes
from .ma007_recording import Recorder
from .ma007_report import validate_recording
from .ma007_retention import read,retain

GENEROUS=(2.5,95,192,192)
CAPS={
    'G':GENEROUS,'F0':(1.,95,192,192),'M0':(2.5,19,192,192),
    'K0':(2.5,95,32,192),'U0':(2.5,95,192,64),
    'F1':(1.5,95,192,192),'M1':(2.5,37,192,192),
    'K1':(2.5,95,64,192),'U1':(2.5,95,192,128)}
IDS=tuple(CAPS)+('G_E0',)+tuple('O'+str(i) for i in range(1,9))
DEFAULT_FOLDER=OUTPUT/'research18-001'
BASELINE=dict(run='results/validation/modal_atlas/MA-007/phaseA-control-001/C0_recorded',
    atlas='results/validation/modal_atlas/MA-007/phaseA-atlas-003',response_cells=114)


def policy_for(identifier,caps,target=GENEROUS,*,historical=False):
    return FourControlPolicy(caps=tuple(caps),generous_target=tuple(target),
        order=identifier if identifier.startswith('O') else 'S0',
        historical_exit=historical or identifier=='G_E0')


def select_cstar(results,generous=GENEROUS):
    """The preregistered §6D selector, applied only after returned cap fits."""
    recovered=[(name,r) for name,r in results.items() if name in CAPS and r['recovered']]
    if not recovered:return tuple(generous),dict(rule='no recovered cap configuration: final G',selected='G')
    minimum=min(r['fit_and_localization_units'] for _,r in recovered)
    near=[(name,r) for name,r in recovered if r['fit_and_localization_units']<=1.01*minimum]
    name,result=min(near,key=lambda pair:(*pair[1]['assigned_caps'],pair[0]))
    return tuple(result['assigned_caps']),dict(rule='minimum work, within1%; F,M,K,Ku,lexical ties',
        selected=name,minimum_work_units=minimum,eligible=[name for name,_ in near])


def archive_source(folder):
    with tarfile.open(folder/'sources.tar.gz','w:gz') as archive:
        for path in sources():
            if path.is_file():archive.add(path,arcname=str(path.relative_to(c.ROOT)),recursive=False)


def prepare(folder):
    c.verify(require_inputs=True)
    if folder.exists():raise FileExistsError('Prepared queue already exists: '+str(folder))
    folder.mkdir(parents=True)
    problem=c.problem(CASE);physics=IndependentModalMuller(EXECUTION,trace_cap=192,workspace=512)
    specs=[]
    for identifier in IDS:
        caps=CAPS.get(identifier,GENEROUS)
        preview=policy_for(identifier,caps).plan(problem,physics)
        specs.append(dict(id=identifier,status='AWAITING_GO',caps=list(caps),
            target_rule='§6D C* from returned cap fits' if identifier.startswith('O') else 'current generous vector',
            preview_target=list(GENEROUS),preview=preview))
    from experiments.cleaned_interface.benchmark import environment
    archive_source(folder)
    write(folder/'manifest.json',dict(experiment='MA-007',case=CASE,baseline=BASELINE,
        phase_A='CLOSED_BY_USER; retain baseline atlas, no further Phase A tests',
        latest_user_instruction='Prepare all 18 research cases; start only after go',
        plan_sha256=digest(PLAN),input_manifest_sha256=digest(c.INPUTS/'manifest.json'),
        start_path=str(c.start_path().relative_to(c.ROOT)),start_sha256=digest(c.start_path()),
        source_hashes=hashes(),source_archive_sha256=digest(folder/'sources.tar.gz'),
        execution=asdict(EXECUTION),environment=environment(),workspace=512,
        queue=specs,nominal_fit_count=18,case_order=list(IDS),baseline_rerun=False,
        budgets=dict(fit_units=13412,fit_seconds=120,audit_aggregate_seconds=30,
            terminal_audit_reserve_seconds=10,full_fit_attempts=64,offline_seconds=72*3600),
        O8=dict(slot_end='saved winning branch endpoint',lambda_entry='reset default each decision slot',
            complete_contest_required=True,monitor='full real catalog at 320/352; charged online'),
        research_choices='unchanged from frozen plan; no default promotion',
        local_storage=read(OUTPUT/'storage_route.json')))
    write(folder/'state.json',dict(status='READY_AWAITING_GO',go_authorized=False,
        completed=[],pending=list(IDS),research_fits_started=0,workspace=512,
        baseline_atlas=BASELINE['atlas'],phase_A_closed=True,full_study_complete=False))
    return verify(folder)


def verify(folder):
    manifest=read(folder/'manifest.json');c.verify(require_inputs=True)
    if manifest['source_hashes']!=hashes():raise ValueError('Prepared source changed: reseal before dispatch')
    if digest(folder/'sources.tar.gz')!=manifest['source_archive_sha256']:raise ValueError('Source archive changed')
    if digest(PLAN)!=manifest['plan_sha256'] or digest(c.INPUTS/'manifest.json')!=manifest['input_manifest_sha256']:
        raise ValueError('Frozen plan or inputs changed')
    if tuple(manifest['case_order'])!=IDS or len(manifest['queue'])!=18:raise ValueError('Nominal queue differs from plan')
    route=manifest['local_storage']
    if not route['verified_local_storage'] or not Path(route['array_storage_root']).is_dir():
        raise ValueError('Approved local raw-array route is unavailable')
    for path in (c.ROOT,Path(route['array_storage_root'])):
        if shutil.disk_usage(path).free<20*2**30:raise ValueError('Less than the declared 20 GiB free margin')
    return manifest


def resolved_request(folder,identifier,workspace):
    manifest=verify(folder);state=read(folder/'state.json')
    if not state['go_authorized']:raise ValueError('Queue awaits the user go instruction')
    if identifier in CAPS:caps=CAPS[identifier]
    elif identifier=='G_E0':caps=tuple(state.get('generous_target',GENEROUS))
    else:caps=tuple(state['C_star'])
    return dict(id=identifier,caps=caps,target=tuple(state.get('generous_target',GENEROUS)),workspace=workspace)


def worker(folder,identifier,workspace):
    if identifier is None:raise ValueError('Worker requires a registered configuration ID')
    request=resolved_request(folder,identifier,workspace)
    run=folder/f'workspace_{workspace}'/'runs'/identifier;run.mkdir(parents=True,exist_ok=False)
    recorder=Recorder(run/'recording',digest(folder/'manifest.json'))
    physics=IndependentModalMuller(EXECUTION,trace_cap=request['caps'][3],workspace=workspace,observer=recorder)
    policy=policy_for(identifier,request['caps'],request['target'])
    started=perf_counter()
    try:
        result=fit(c.problem(CASE),solver='modal_muller',physics=physics,execution=EXECUTION,
            policy=policy,geometry_update='certified_spectral',localization_adapter=c.keep_start,
            output=run,on_event=lambda e:print(identifier,e['operation']['label'],e['reason'],flush=True))
        returned=perf_counter()
        from experiments.cleaned_interface import benchmark as ci
        metrics=ci.score(c.row(CASE),curve_from(result['final_curve']))
        residual=result.get('relative_residual')
        recovered=bool(result['final_audit_passed'] and metrics['rms_mm']<=1. and
            metrics['hausdorff_upper_mm']<=2. and residual is not None and np.all(np.asarray(residual)<=.003))
        result.update(case=CASE,configuration_id=identifier,assigned_caps=request['caps'],
            generous_target=request['target'],workspace=workspace,metrics=metrics,recovered=recovered,
            source_epoch=digest(folder/'manifest.json'),audited_output_seconds=returned-started)
    except Exception:
        result=dict(case=CASE,configuration_id=identifier,assigned_caps=request['caps'],workspace=workspace,
            outcome='IMPLEMENTATION_FAILURE',traceback=traceback.format_exc(),recovered=False,
            source_epoch=digest(folder/'manifest.json'))
    try:result['recording']=recorder.finish()
    except Exception:
        result['recording_failure']=traceback.format_exc()
        write(run/'recording_failure.json',dict(traceback=result['recording_failure']))
    write(run/'result.json',result)
    if 'physics' in result and (run/'recording/index.json').exists():
        validation=validate_recording(run)
        if not validation['readback_passed'] or not validation['replay_passed'] or not all(validation['reconciliation'].values()):
            write(run/'recording_integrity_failure.json',validation)
    retain(run)
    print(identifier,result['outcome'],result['recovered'],flush=True)
    return result


def publish(run,identifier):
    owned=['experiments/benchmark/ma007.py','experiments/benchmark/ma007_atlas.py',
        'experiments/benchmark/ma007_probes.py','experiments/benchmark/ma007_diagnostics.py',
        'experiments/benchmark/ma007_recording.py','experiments/benchmark/ma007_retention.py',
        'experiments/benchmark/ma007_report.py','experiments/benchmark/ma007_matrix.py',
        'experiments/benchmark/test_ma007.py','solvers/bem_inverse/four_control_policy.py',
        'solvers/bem_inverse/four_control_adaptive.py','solvers/bem_inverse/modal_accuracy.py',
        'solvers/bem_inverse/modal_muller.py','solvers/bem_inverse/continuation/lm_backend.py',
        'solvers/bem_inverse/continuation/globalization.py','solvers/bem_inverse/runner.py',
        'docs/iterations/modal_atlas/iteration_07/04_execution.md',str(run.relative_to(c.ROOT))]
    subprocess.run(['git','add','--',*owned],cwd=c.ROOT,check=True)
    if subprocess.run(['git','diff','--cached','--quiet'],cwd=c.ROOT).returncode:
        subprocess.run(['git','commit','-q','-m',f'experiment(MA-007): retain {identifier} returned evidence'],cwd=c.ROOT,check=True)
    subprocess.run(['git','push'],cwd=c.ROOT,check=True)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=c.ROOT,text=True).strip()
    remote=subprocess.check_output(['git','rev-parse','@{upstream}'],cwd=c.ROOT,text=True).strip()
    if head!=remote:raise RuntimeError('Push verification failed')


def run_queue(folder,go):
    if not go:raise ValueError('Explicit --go is required; preparation never launches a case')
    verify(folder);state=read(folder/'state.json')
    state.update(go_authorized=True,status='RUNNING',generous_target=list(GENEROUS))
    write(folder/'state.json',state);COORD.mkdir(exist_ok=True)
    workspace=state['workspace']
    cursor=0
    while cursor<len(IDS):
        identifier=IDS[cursor];cursor+=1
        if identifier in state['completed']:continue
        if identifier=='G_E0':
            results={name:read(folder/f'workspace_{workspace}'/'runs'/name/'result.json') for name in CAPS}
            target,selection=select_cstar(results,state['generous_target'])
            state.update(C_star=list(target),C_star_selection=selection);write(folder/'state.json',state)
        with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
            fcntl.flock(compute,fcntl.LOCK_EX);fcntl.flock(source,fcntl.LOCK_SH)
            verify(folder)
            log=folder/(identifier+f'_workspace{workspace}.log')
            env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
            with log.open('w') as handle:
                process=subprocess.run([sys.executable,'-m','experiments.benchmark.ma007_matrix','worker',
                    '--folder',str(folder),'--id',identifier,'--workspace',str(workspace)],
                    cwd=c.ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT)
        run=folder/f'workspace_{workspace}'/'runs'/identifier
        path=run/'result.json'
        if process.returncode or not path.exists():
            run.mkdir(parents=True,exist_ok=True)
            write(run/'process_failure.json',dict(id=identifier,returncode=process.returncode))
            publish(folder,identifier)
            raise RuntimeError('Implementation/process failure retained: '+identifier)
        result=read(path)
        state['completed'].append(identifier);state['pending']=[x for x in IDS if x not in state['completed']]
        state['research_fits_started']=len(state['completed']);state['last_outcome']=result['outcome']
        write(folder/'state.json',state);publish(folder,identifier)
        if result['outcome']=='WORKSPACE_EPOCH_PROMOTION_REQUIRED' and workspace==512:
            state.setdefault('superseded_epochs',[]).append(dict(workspace=512,completed=list(state['completed'])))
            workspace=768
            state.update(workspace=workspace,completed=[],pending=list(IDS),status='RUNNING',workspace_promotions=1)
            state.pop('C_star',None);state.pop('C_star_selection',None)
            write(folder/'state.json',state);publish(folder,'common workspace epoch promotion');cursor=0
            continue
        if result['outcome'] in ('WORKSPACE_UNRESOLVED','WORKSPACE_EPOCH_PROMOTION_REQUIRED'):
            state.update(status=result['outcome'],requires_plan_epoch_handling=True)
            write(folder/'state.json',state);publish(folder,'workspace closeout');return
        if result['outcome']=='IMPLEMENTATION_FAILURE' or (run/'recording_integrity_failure.json').exists() or (run/'recording_failure.json').exists():
            raise RuntimeError('Implementation/integrity failure retained; repair before continuing')
    state.update(status='NOMINAL_18_FITS_RETURNED',full_study_complete=False,
        pending_evidence=['research five-role atlases/probes','conditional plan extensions/confirmations','three-question report'])
    write(folder/'state.json',state);publish(folder,'nominal 18-fit batch')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','verify','run','worker'))
    parser.add_argument('--folder',type=Path,default=DEFAULT_FOLDER)
    parser.add_argument('--go',action='store_true')
    parser.add_argument('--id',choices=IDS)
    parser.add_argument('--workspace',type=int,choices=(512,768),default=512)
    args=parser.parse_args();folder=args.folder.resolve()
    if args.command=='prepare':prepare(folder);print('READY_AWAITING_GO: 18 nominal research cases')
    elif args.command=='verify':verify(folder);print('Prepared queue and immutable inputs verified; no case launched')
    elif args.command=='run':run_queue(folder,args.go)
    else:worker(folder,args.id,args.workspace)


if __name__=='__main__':main()
