"""MA-007 fixed-state active-objective qualification and nine local branches.

Every branch has the registered two-iteration/200-unit opportunity. Production
cutoff is frozen; witnesses cannot supply a move beyond it. Full-real monitors
are separately charged offline evaluations and never enter branch decisions.
"""
import argparse
from dataclasses import replace
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from time import perf_counter
import traceback

import numpy as np
from bem_inverse.geometry_selection import make_update
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.lm_backend import (FitStage,BackendConfig,Ledger,Objective,fit_stage,
                                                NORMAL_RETURN,STAGE_QUOTA,normalize)
from bem_inverse.geometry import resize
from bem_inverse.io import write,digest,curve_from,curve_record
from bem_inverse.modal_muller import ModalMuller,ModalSettings,token
from bem_inverse.modal_accuracy import IndependentModalMuller,displacement_comparison
from bem_inverse.runner import audit
from .ma007 import CASE,OUTPUT,COORD,EXECUTION,THREADS,Chunks,sources,hashes
from .ma007_retention import read
from .ma007_recording import Recorder
from . import campaign as c

LEVELS=dict(F=(.5,.75,1.,1.25,1.5,1.75,2.,2.25,2.5),
            M=(3,5,7,9,11,15,19,25,31,37,49,61,79,95,127),
            K=(8,12,16,20,24,32,40,52,64,96,128,192,256,384),
            U=(64,96,128,160,192,256,320))


def branch_manifest(role):
    if role['status']!='reached':
        return [dict(name=name,status=role['status']) for name in
                ('HOLD','F1','F2','M1','M2','K1','K2','U1','U2')]
    actual=dict(F=max(role['frequencies_hz'])/1e9,M=role['M'],K=role['K'],U=role['K_u'])
    entries=[dict(name='HOLD',axis=None,value=None,status='pending')]
    for axis in ('F','M','K','U'):
        higher=[x for x in LEVELS[axis] if x>actual[axis]]
        for index in range(2):
            entries.append(dict(name=axis+str(index+1),axis=axis,
                value=higher[index] if index<len(higher) else None,
                status='pending' if index<len(higher) else 'RANGE_LIMITED'))
    return entries


def observations_for(problem,role,entry):
    catalog=getattr(problem,role['catalog'])
    if entry['axis']=='F':
        selected=set(role['frequencies_hz'])|{o.frequency_hz for o in catalog if o.frequency_hz<=entry['value']*1e9}
    else: selected=set(role['frequencies_hz'])
    return tuple(o for o in catalog if o.frequency_hz in selected)


def setup(problem,role,entry,label,iterations=2,quota=200):
    observations=observations_for(problem,role,entry)
    M=entry['value'] if entry['axis']=='M' else role['M']
    K=entry['value'] if entry['axis']=='K' else role['K']
    U=entry['value'] if entry['axis']=='U' else role['K_u']
    curve=resize(curve_from(role['curve']),K)
    stage=FitStage(label,observations,tuple(np.ones(len(observations))/len(observations)),
        tuple(1e-5 if o.frequency_hz<=.5e9 else 1e-7 for o in observations),
        M,K,token(U),token(U+32),iterations,quota,resolution_kind='modal')
    config=replace(BackendConfig(**role['config']),initial_damping=role['lambda_carried'])
    return curve,stage,config


def monitor(problem,curve,chunks,label,*,workspace=512):
    """The registered two-cutoff common merit, using the shared normalization."""
    physics=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=workspace,cached_geometries=1))
    started=perf_counter(); predictions=[]; units=0
    try:
        for cutoff in (320,352):
            columns=[]
            for observation in problem.real:
                units+=1
                columns.append(physics.evaluate(curve,observation,problem.contrast,token(cutoff)).prediction)
            predictions.append(np.column_stack(columns))
        observed=np.column_stack([o.scattered for o in problem.real])
        weights=np.ones(19)/19
        residuals=[normalize(p-observed,observed,weights) for p in predictions]
        fields=np.linalg.norm(predictions[0]-predictions[1],axis=0)/np.maximum(np.linalg.norm(predictions[1],axis=0),1e-30)
        limits=np.array([1e-5 if o.frequency_hz<=.5e9 else 1e-7 for o in problem.real])
        losses=[.5*float(r@r) for r in residuals]
        path=chunks.save(label,dict(coefficients=curve.coefficients,production_prediction=predictions[0],
            witness_prediction=predictions[1],observed=observed,weights=weights,
            production_residual=residuals[0],witness_residual=residuals[1],field_errors=fields,
            relative_residuals=np.linalg.norm(predictions[1]-observed,axis=0)/np.linalg.norm(observed,axis=0)),
            dict(kind='common_real_monitor',cutoffs=[320,352],B_work=workspace,normalization='lm_backend.normalize',
                control_data_access='offline; never supplied to a fixed branch'))
        return dict(status='qualified' if np.all(fields<=limits) else 'MONITOR_UNRESOLVED',
            losses=losses,maximum_residual=float(max(np.linalg.norm(predictions[1]-observed,axis=0)/
                                                 np.linalg.norm(observed,axis=0))),
            work_units=units,compute_seconds=perf_counter()-started,path=path['path'],physics=physics.receipt())
    except Exception:
        return dict(status='MONITOR_UNRESOLVED',work_units=units,compute_seconds=perf_counter()-started,
                    traceback=traceback.format_exc(),physics=physics.receipt())


def prepare(atlas,folder):
    folder.mkdir(parents=True,exist_ok=False); c.verify(require_inputs=True)
    roles=read(atlas/'roles.json')['roles']
    write(folder/'roles.json',dict(roles=roles))
    with tarfile.open(folder/'sources.tar.gz','w:gz') as archive:
        for path in sources():
            if path.is_file(): archive.add(path,arcname=str(path.relative_to(c.ROOT)),recursive=False)
    manifest=dict(experiment='MA-007',case=CASE,parent_atlas=str(atlas.relative_to(c.ROOT)),
        source_hashes=hashes(),source_archive_sha256=digest(folder/'sources.tar.gz'),
        expected={r['role']:branch_manifest(r) for r in roles},
        limits=dict(iterations=2,branch_work_units=200,monitor_work_units=38),
        order='roles 1..5; HOLD,F1,F2,M1,M2,K1,K2,U1,U2',
        truth_boundary='score only after a returned numerical branch',
        workspace=512,qualification='all performed model checks charged in branch ledger')
    write(folder/'manifest.json',manifest)
    return manifest


def verify(folder):
    saved=read(folder/'manifest.json')
    if saved['source_hashes']!=hashes() or digest(folder/'sources.tar.gz')!=saved['source_archive_sha256']:
        raise ValueError('Probe source epoch changed')
    c.verify(require_inputs=True)
    return saved


def active_qualification(problem,role,folder,epoch=None):
    """Actual production directions at the prescribed checkpoint and workspace."""
    hold=dict(name='HOLD',axis=None,value=None,status='pending')
    curve,stage,config=setup(problem,role,hold,'active_qualification',iterations=2,quota=None)
    update=make_update('certified_spectral',problem.length_unit_m,EXECUTION)
    recorder=Recorder(folder/'recording',epoch or digest(folder/'manifest.json'))
    physics=IndependentModalMuller(EXECUTION,trace_cap=320,workspace=512,observer=recorder)
    ledger=Ledger(cap=10000,seconds=10800,endpoint_reserve=0,strict_dispatch=True)
    ledger.begin_stage('active_qualification',None)
    started=perf_counter()
    try:
        space=update.prepare(curve,stage.update_modes,stage.curve_modes)
        objective=Objective(stage,problem.contrast,config,ledger,physics=physics)
        evaluation=objective.production(curve,'initial_active_fields')
        if evaluation is None: raise ValueError('Initial active fields unresolved')
        matrix=objective.jacobian(evaluation,update,space); gradient=matrix.T@evaluation.residual
        while True:
            promoted=physics.qualify_linearization(evaluation,stage,config,problem.contrast,space,update,
                ledger,matrix,gradient,role['lambda_carried'])
            if promoted is None: break
            stage,objective,evaluation=promoted['stage'],promoted['objective'],promoted['evaluation']
            matrix,gradient=promoted['matrix'],promoted['gradient']
        lower=dict(stage=stage,objective=objective,evaluation=evaluation,matrix=matrix,
            gradient=gradient,cutoff=stage.nodes//8,workspace=512)
        confirmations=[]
        for delta in (32,64):
            higher=physics._frame(curve,stage,config,problem.contrast,space,update,ledger,stage.nodes//8+delta)
            comparison,raw=physics._compare(lower,higher,config,space,update,role['lambda_carried'])
            from bem_inverse.continuation.lm_backend import observe
            observe(physics,'qualification',kind_detail='active_objective_confirmation',
                row=comparison,arrays=raw,ledger=ledger)
            confirmations.append(dict(delta=delta,passed=comparison['passed']))
        # Actual projected-trial FD on the active objective, seed and coordinate
        # increment prescribed by the plan, using the production/refined arrays.
        direction=np.random.default_rng(42001).normal(size=matrix.shape[1]); direction/=np.linalg.norm(direction)
        finer=physics._frame(curve,stage,config,problem.contrast,space,update,ledger,stage.nodes//8+32)
        values_fd=[]
        for sign in (1,-1):
            candidate=update.trial(space,sign*1e-7*direction)[0]
            measured=finer['objective'].production(candidate,'complete_trial_fd')
            if measured is None: raise ValueError('Complete-trial FD fields unresolved')
            values_fd.append(measured.residual)
        fd=(values_fd[0]-values_fd[1])/2e-7
        reference=finer['matrix']@direction
        fd_error=float(np.linalg.norm(fd-reference)/max(np.linalg.norm(fd),1e-30))
        chunks=Chunks(folder/'checks')
        artifact=chunks.save('complete_trial_fd',dict(direction=direction,finite_difference=fd,
            refined_directional_response=reference,production_J=matrix,refined_J=finer['matrix']),
            dict(seed=42001,coordinate_increment_m=1e-7,M=stage.update_modes,K=stage.curve_modes,
                 production_K_u=stage.nodes//8,witness_K_u=stage.nodes//8+32,B_work=512))
        value=dict(status='qualified' if fd_error<=1e-3 else 'unqualified',full_trial_fd_relative=fd_error,
            selected_K_u=stage.nodes//8,artifact=artifact['path'],work=ledger.snapshot(),
            trace_confirmations=confirmations,local_numerical_saturation=all(x['passed'] for x in confirmations))
    except Exception:
        value=dict(status='unqualified',traceback=traceback.format_exc(),work=ledger.snapshot())
    value.update(compute_seconds=perf_counter()-started,recording=recorder.finish(),physics=physics.receipt(),
        geometry_settings=update.settings())
    write(folder/'result.json',value)
    return value


def worker(folder,role_name,branch_name):
    manifest=verify(folder); problem=c.problem(CASE)
    role=next(r for r in read(folder/'roles.json')['roles'] if r['role']==role_name)
    entry=next(e for e in manifest['expected'][role_name] if e['name']==branch_name)
    target=folder/role_name/branch_name; target.mkdir(parents=True,exist_ok=False)
    if entry['status']!='pending':
        write(target/'result.json',dict(role=role_name,branch=branch_name,status=entry['status']));return
    curve,stage,config=setup(problem,role,entry,role_name+'_'+branch_name)
    recorder=Recorder(target/'recording',digest(folder/'manifest.json'))
    physics=IndependentModalMuller(EXECUTION,trace_cap=stage.nodes//8,workspace=512,observer=recorder,
        reject_unresolved_candidates=role.get('controller_kind','historical')!='historical')
    update=make_update('certified_spectral',problem.length_unit_m,EXECUTION)
    ledger=Ledger(cap=200,seconds=10800,endpoint_reserve=0,strict_dispatch=True)
    ledger.begin_stage(stage.label,200)
    accepted=[]; started=perf_counter()
    try:
        result=fit_stage(curve,stage,problem.contrast,update,config,ledger,physics=physics,
            on_accept=lambda iteration,evaluation:accepted.append(dict(iteration=iteration,units=ledger.units,
                loss=evaluation.loss,curve=curve_record(evaluation.curve))))
        value=dict(role=role_name,branch=branch_name,status=result.outcome,stop=result.stop_reason,
            detail=result.detail,accepted_steps=result.accepted_steps,curve=curve_record(result.curve),
            history=result.history,trials=result.trials,acceptance_checks=result.acceptance_checks,
            work=ledger.snapshot(),compute_seconds=perf_counter()-started,
            requested=dict(F_hz=[o.frequency_hz for o in stage.observations],M=stage.update_modes,
                K=stage.curve_modes,K_u=stage.nodes//8,B_work=512),actual_frozen_cutoff=physics.actual_cutoff,
            accepted_states=accepted,physics=physics.receipt(),geometry_settings=update.settings())
    except Exception:
        value=dict(role=role_name,branch=branch_name,status='IMPLEMENTATION_FAILURE',traceback=traceback.format_exc(),
            curve=curve_record(curve),work=ledger.snapshot(),compute_seconds=perf_counter()-started)
    value['recording']=recorder.finish()
    chunks=Chunks(target/'monitor')
    value['common_monitor']=monitor(problem,curve_from(value['curve']),chunks,'endpoint')
    # Offline geometry scoring follows the numerical return and is not a selector.
    from experiments.cleaned_interface import benchmark as ci
    value['metrics']=ci.score(c.row(CASE),curve_from(value['curve']))
    write(target/'result.json',value)
    print(role_name,branch_name,value['status'],value.get('accepted_steps'),flush=True)
    return value


def collect(atlas,folder,only=None):
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
        fcntl.flock(compute,fcntl.LOCK_EX); fcntl.flock(source,fcntl.LOCK_SH)
        manifest=prepare(atlas,folder)
        for role in read(folder/'roles.json')['roles']:
            for entry in manifest['expected'][role['role']]:
                if only and (role['role'],entry['name']) not in only: continue
                env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
                log=folder/(role['role']+'_'+entry['name']+'.log')
                with log.open('w') as handle:
                    done=subprocess.run([sys.executable,'-m','experiments.benchmark.ma007_probes','worker',
                        '--folder',str(folder),'--role',role['role'],'--branch',entry['name']],
                        cwd=c.ROOT,env=env,stdout=handle,stderr=subprocess.STDOUT)
                if done.returncode:
                    write(folder/'failed_process.json',dict(role=role['role'],branch=entry['name'],returncode=done.returncode))
                    return
        verify(folder)
        write(folder/'state.json',dict(status='PARTIAL_REGISTERED_BRANCH_CHECK' if only else 'BRANCHES_TERMINAL',
            complete_atlas=False,remaining=['active-objective audits','selected derivatives','regeneration','branch labels/report']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('collect','initial-hold','worker','qualify'))
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--atlas',type=Path)
    parser.add_argument('--role')
    parser.add_argument('--branch')
    args=parser.parse_args()
    if args.command in ('collect','initial-hold'):
        if args.atlas is None: parser.error('collection needs --atlas')
        collect(args.atlas.resolve(),args.folder.resolve(),{('1_initial','HOLD')} if args.command=='initial-hold' else None)
    elif args.command=='worker': worker(args.folder.resolve(),args.role,args.branch)
    else:
        args.folder=args.folder.resolve()
        role=next(r for r in read(args.atlas/'roles.json')['roles'] if r['role']==args.role)
        args.folder.mkdir(parents=True,exist_ok=False)
        from experiments.cleaned_interface.benchmark import environment
        write(args.folder/'manifest.json',dict(experiment='MA-007',case=CASE,
            purpose='offline active-objective qualification',role=args.role,
            parent_atlas=str(args.atlas),source_hashes=hashes(),environment=environment(),
            execution=EXECUTION.__dict__,settings=dict(workspace=512,trace_cap=320,
                seed=42001,coordinate_increment_m=1e-7)))
        active_qualification(c.problem(CASE),role,args.folder)


if __name__=='__main__': main()
