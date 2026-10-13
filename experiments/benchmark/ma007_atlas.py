"""MA-007 fixed five-role response/operator atlas on saved actual-hook states.

No atlas calculation may modify a parent fit or choose its endpoint. Each cell
keeps arrays or a numerical terminal record. This module uses the maintained
modal solver and complete certified-spectral update, not an alternate solver.
"""
import argparse
from dataclasses import asdict
import fcntl
import hashlib
from pathlib import Path
import subprocess
import os
import sys
import tarfile
import threading
import resource
from time import perf_counter
import traceback

import numpy as np
from scipy.linalg import lu_factor, lu_solve
from bem_inverse.geometry_selection import make_update
from bem_inverse.continuation.geometry import FourierCurve, grid_size
from bem_inverse.geometry import values
from bem_inverse.io import write, digest, curve_from
from bem_inverse.modal_muller import ModalMuller, ModalSettings, token
from bem_inverse.modal_operator import hadamard
from bem_inverse.normal_basis import orthonormal_normal_basis
from . import campaign as c
from .ma007 import (CASE, OUTPUT, COORD, EXECUTION, THREADS, Chunks, Capture, permutation,
                   subblock_indices, hashes, monitor_gpu, available_memory)
from .ma007_retention import read

LADDER=(64,96,128,160,192,256,320)


def checkpoint_roles(control):
    run=control/'C0_recorded'
    problem=c.problem(CASE)
    result=read(run/'result.json')
    accepted=read(run/'accepted.json')['states']
    operations=read(run/'plan.json')['operations']
    by_label={op['label']:op for op in operations if op['operation']=='fit'}
    recording=read(run/'recording/index.json')
    refusals=[e for e in recording['events'] if e['kind']=='resolution_refusal']
    last_damped=next((s for s in reversed(result['stages']) if s['stage'].endswith('damped') and
                     not s['stage'].endswith('undamped')),None)
    all_real=next((s for s in accepted if s['active_frequency_count']==19 and
                  not s['stage'].endswith('damped')),None)
    records=[]
    def add(role,label,curve,occurrence,reason=None):
        if curve is None:
            records.append(dict(role=role,status=reason or 'not_reached',occurrence=occurrence));return
        op=by_label[label]; stage=read(run/(label+'.json'))
        history=stage['history']
        entry=next((h for h in reversed(history) if curve_from(h['coefficients']).coefficients.tobytes()==
                    curve_from(curve).coefficients.tobytes()),history[0])
        settings=op['stage']
        records.append(dict(role=role,status='reached',label=label,curve=curve,occurrence=occurrence,
            M=settings['update_modes'],K=settings['curve_modes'],K_u=settings['nodes']//8,
            frequencies_hz=settings['frequencies_hz'],catalog='damped' if any(settings['damping']) else 'real',
            lambda_carried=entry['next_damping'],config=op['optimizer'],controller=entry,
            source_epoch=result['source_epoch']))
    from bem_inverse.io import curve_record
    first=next(op for op in operations if op['operation']=='fit')
    # The original physical circle is exactly padded to its recorded initial K.
    from bem_inverse.geometry import resize
    add('1_initial',first['label'],curve_record(resize(problem.initial,first['stage']['curve_modes'])),
        dict(stage=first['label'],iteration=0))
    add('2_last_damped',last_damped['stage'] if last_damped else first['label'],
        last_damped['curve'] if last_damped else None,dict(stage=last_damped['stage']) if last_damped else {})
    add('3_first_all_real',all_real['stage'] if all_real else first['label'],
        all_real['curve'] if all_real else None,dict(stage=all_real['stage'],iteration=all_real['iteration']) if all_real else {})
    if refusals:
        refusal=refusals[0]; state_hash=refusal['states']['base']
        match=next(s for s in reversed(accepted) if hashlib.sha256(curve_from(s['curve']).coefficients.tobytes()).hexdigest()==state_hash)
        add('4_first_resolution_refusal',refusal['stage'],match['curve'],dict(event=refusal['index']))
    else:
        add('4_first_resolution_refusal',first['label'],None,{},'not_triggered')
    last=result['stages'][-1]
    add('5_final',last['stage'],result['final_curve'],dict(returned_outcome=result['outcome']))
    return records


def prepare(control, folder):
    c.verify(require_inputs=True)
    folder.mkdir(parents=True,exist_ok=False)
    roles=checkpoint_roles(control)
    write(folder/'roles.json',dict(roles=roles))
    expected=[]
    for role in roles:
        kinds=('real','damped') if role['role']!='1_initial' and role.get('catalog')=='damped' else ('real',)
        for kind in kinds:
            for o in getattr(c.problem(CASE),kind):
                expected.append(dict(role=role['role'],catalog=kind,frequency_hz=o.frequency_hz,
                    status='pending' if role['status']=='reached' else role['status']))
    from .ma007 import sources
    with tarfile.open(folder/'sources.tar.gz','w:gz') as archive:
        for path in sources():
            if path.is_file(): archive.add(path,arcname=str(path.relative_to(c.ROOT)),recursive=False)
    manifest=dict(experiment='MA-007',purpose='C0 complete response atlas; no policy selection',
        case=CASE,parent_control=str(control.relative_to(c.ROOT)),
        parent_manifest_sha256=digest(control/'manifest.json'),roles_sha256=digest(folder/'roles.json'),
        source_hashes=hashes(),source_archive_sha256=digest(folder/'sources.tar.gz'),
        input_manifest_sha256=digest(c.INPUTS/'manifest.json'),expected_cells=expected,
        response_P=127,workspace=512,witness_workspace=768,max_workspace=1024,
        snapshot_fallback='store every attempted cutoff separately; sub-block property failed',
        limits=dict(offline_compute_seconds=10800,new_artifact_bytes=20*2**30),
        required_pending=['active-objective step/workspace qualification', 'nine local probes per role',
                          'selected operator derivatives', 'regeneration', 'resource forecast/release'])
    write(folder/'manifest.json',manifest)
    return manifest


def verify(folder):
    manifest=read(folder/'manifest.json')
    if manifest['source_hashes']!=hashes() or digest(folder/'sources.tar.gz')!=manifest['source_archive_sha256']:
        raise ValueError('Atlas source epoch changed')
    if digest(folder/'roles.json')!=manifest['roles_sha256']:
        raise ValueError('Atlas checkpoint identities changed')
    c.verify(require_inputs=True)
    return manifest


def errors(low, high):
    fields=float(np.linalg.norm(low['prediction']-high['prediction'])/max(np.linalg.norm(high['prediction']),1e-30))
    columns={name:np.linalg.norm(low[name]-high[name],axis=0)/np.maximum(np.linalg.norm(high[name],axis=0),1e-30)
             for name in ('J_complete','J_intrinsic')}
    return fields,columns


def worker(folder, role_name, compute_allowance=10800., byte_allowance=20*2**30):
    manifest=verify(folder)
    role=next(r for r in read(folder/'roles.json')['roles'] if r['role']==role_name)
    target=folder/role_name; target.mkdir(exist_ok=False)
    started=perf_counter(); chunks=Chunks(target/'chunks')
    import torch
    torch.cuda.reset_peak_memory_stats()
    curve=curve_from(role['curve']); problem=c.problem(CASE); P=127; perm=permutation(P)
    update=make_update('certified_spectral',problem.length_unit_m,EXECUTION)
    space=update.prepare(curve,P,curve.band)
    count=grid_size(max(P,curve.band))
    nodes=curve.nodes(count); normal=nodes.normals@np.array([1,1j])
    intrinsic=orthonormal_normal_basis(nodes,P)/problem.length_unit_m
    cartesian=values(space.derivatives[:,perm],count)
    realized=(cartesian*normal.conj()[:,None]).real
    metric=update.metric(space,'mass')[np.ix_(perm,perm)]
    weights_samples=intrinsic*nodes.speeds[:,None]
    weight_spectrum=np.fft.fft(weights_samples,axis=0)/count
    identity=dict(role=role_name,parent_source_epoch=role['source_epoch'],atlas_source_epoch=digest(folder/'manifest.json'),
        P=P,M=role['M'],K=curve.band,normal_coordinate_order='constant, cos1,sin1,...',
        K_u_production=role['K_u'],B_work=512,length_unit_m=problem.length_unit_m,
        complete_units='data per metre of ordinary grouped optimizer coordinate (export permutation applied)',
        intrinsic_units='data per metre of L2(ds_package)-normalized normal coordinate',
        trace_order='Dirichlet, flux; modes -Ku..Ku; RHS sources then reciprocal receivers',
        channels='paired diagonal R @ X_s; source strength applied to B_s only',
        geometry_settings=update.settings())
    chunks.save('geometry_response_directions',dict(coefficients=curve.coefficients,
        cartesian_velocity_coefficients=space.derivatives[:,perm],cartesian_velocities=cartesian,
        realized_normal_velocities=realized,intrinsic_normal_velocities=intrinsic,
        intrinsic_cartesian_velocities=intrinsic*normal[:,None],metric_H=metric,
        export_permutation=perm,parameters=nodes.parameters,points=nodes.points,normals=nodes.normals,
        speed=nodes.speeds,arclength_weights=nodes.arc_length_weights,
        intrinsic_weight_fourier=weight_spectrum),identity)
    capture=Capture()
    physics=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=512,cached_geometries=1),observer=capture)
    workspace_physics=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=768,cached_geometries=1),observer=capture)
    max_workspace_physics=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=1024,cached_geometries=1),observer=capture)
    kinds=('real','damped') if role_name!='1_initial' and role['catalog']=='damped' else ('real',)
    cells=[]; status='COLLECTING'; work=dict(field_batches=0,reciprocal_batches=0,feedback_solves=0)
    for kind in kinds:
        for observation in getattr(problem,kind):
            used=sum(x['bytes'] for x in chunks.rows)
            compute_elapsed=perf_counter()-started-chunks.seconds
            if compute_elapsed>=compute_allowance or used+600*2**20>byte_allowance:
                status='RESOURCE_BLOCKED';break
            cell_name=f'{kind}_{observation.frequency_hz/1e9:g}'
            computed={}; attempted=[]; selected=None; failure=None
            def evaluate(cutoff,service=physics,workspace=512):
                cache_key=(cutoff,workspace)
                if cache_key in computed: return computed[cache_key]
                begin=perf_counter()
                work['field_batches']+=1
                prediction=service.evaluate(curve,observation,problem.contrast,token(cutoff))
                field=dict(capture.field)
                field.pop('state'); field.pop('observation')
                field.update(prediction=prediction.prediction,cutoff=cutoff,workspace=workspace,
                    diagnostics=prediction.diagnostics,status='field_computed_response_not_computed')
                computed[cache_key]=field
                work['reciprocal_batches']+=1
                jac=service.derivative(prediction,update,space)[:,perm]
                reciprocal=capture.reciprocal['X_r']
                weights=weight_spectrum[np.arange(-2*cutoff,2*cutoff+1)%count]
                j_intrinsic=hadamard(field['X_s'][:2*cutoff+1],reciprocal[:2*cutoff+1],weights,
                    cutoff,complex(observation.wavenumber)**2*(problem.contrast-1))
                field.update(J_complete=jac,J_intrinsic=j_intrinsic,X_r=reciprocal,
                    prediction=prediction.prediction,cutoff=cutoff,workspace=workspace,
                    compute_seconds=perf_counter()-begin,diagnostics=prediction.diagnostics)
                field['status']='response_computed'
                computed[cache_key]=field
                return field
            try:
                upper=[k for k in LADDER if k>=role['K_u']]
                for cutoff in upper:
                    low=evaluate(cutoff); witnesses=[evaluate(cutoff+delta) for delta in (32,64)]
                    comparisons=[errors(low,high) for high in witnesses]
                    field_limit=1e-5 if observation.frequency_hz<=.5e9 else 1e-7
                    passed=all(f<=field_limit and np.all(cols['J_complete']<=1e-3)
                               for f,cols in comparisons)
                    attempted.append(dict(cutoff=cutoff,passed=passed,
                        intrinsic_passed=all(np.all(x[1]['J_intrinsic']<=1e-3) for x in comparisons),
                        fields=[x[0] for x in comparisons],
                        max_column_errors={name:[float(np.max(x[1][name])) for x in comparisons]
                                           for name in ('J_complete','J_intrinsic')}))
                    if passed: selected=cutoff;break
                if selected is not None:
                    for cutoff in [k for k in LADDER if k<selected]:
                        low=evaluate(cutoff); witnesses=[evaluate(cutoff+delta) for delta in (32,64)]
                        comparisons=[errors(low,high) for high in witnesses]
                        passed=all(f<=field_limit and np.all(cols['J_complete']<=1e-3) for f,cols in comparisons)
                        attempted.append(dict(cutoff=cutoff,passed=passed,
                            intrinsic_passed=all(np.all(x[1]['J_intrinsic']<=1e-3) for x in comparisons),
                            fields=[x[0] for x in comparisons],
                            max_column_errors={name:[float(np.max(x[1][name])) for x in comparisons]
                                               for name in ('J_complete','J_intrinsic')}))
                        if passed: selected=cutoff;break
                # The workspace comparison holds geometry, response directions and
                # trace cutoff fixed; it does not promote a production cutoff.
                workspace_check=None
                chosen=selected or max(k for k,b in computed if b==512)
                lo=evaluate(chosen); hi=evaluate(chosen,workspace_physics,768)
                f,cols=errors(lo,hi)
                workspace_check=dict(cutoff=chosen,fields=f,
                    max_column_errors={name:float(np.max(e)) for name,e in cols.items()},
                    passed=f<=field_limit and np.all(cols['J_complete']<=1e-3),
                    intrinsic_passed=bool(np.all(cols['J_intrinsic']<=1e-3)))
                if not workspace_check['passed']:
                    highest=evaluate(chosen,max_workspace_physics,1024)
                    f2,c2=errors(hi,highest)
                    workspace_check['768_1024']=dict(fields=f2,
                        max_column_errors={name:float(np.max(e)) for name,e in c2.items()},
                        passed=f2<=field_limit and np.all(c2['J_complete']<=1e-3),
                        intrinsic_passed=bool(np.all(c2['J_intrinsic']<=1e-3)))
                    workspace_check['response_workspace_outcome']=('REQUIRES_COMMON_EPOCH_PROMOTION' if
                        workspace_check['768_1024']['passed'] else 'WORKSPACE_UNRESOLVED')
            except Exception:
                failure=traceback.format_exc(); workspace_check=None
            primary={k:v for (k,b),v in computed.items() if b==512}
            top_cutoff=max(primary,default=None); feedback=[]
            if top_cutoff is not None and 'X_r' in primary[top_cutoff]:
                top=primary[top_cutoff]
                top_x=np.column_stack((top['X_s'],top['X_r']))
                top_b=np.column_stack((top['B_s'],top['B_r']))
                for cutoff,value in sorted(primary.items()):
                    if cutoff==top_cutoff: continue
                    low_ids=subblock_indices(cutoff,top_cutoff)
                    high_ids=np.setdiff1d(np.arange(len(top['A'])),low_ids)
                    a_ll=top['A'][np.ix_(low_ids,low_ids)]; a_lh=top['A'][np.ix_(low_ids,high_ids)]
                    factors=lu_factor(a_ll); work['feedback_solves']+=2
                    reduced=lu_solve(factors,top_b[low_ids]); forcing=a_lh@top_x[high_ids]
                    correction=lu_solve(factors,forcing)
                    difference=reduced-top_x[low_ids]
                    denominator=np.maximum(np.linalg.norm(top_x[low_ids],axis=0),1e-30)
                    vector_arrays=dict(retained_difference= difference,
                        identity_residual=difference-correction,
                        relative_difference=np.linalg.norm(difference,axis=0)/denominator,
                        relative_identity_residual=np.linalg.norm(difference-correction,axis=0)/denominator)
                    if cutoff==selected: vector_arrays['feedback_vector']=forcing
                    receipt=chunks.save(f'{cell_name}_feedback_U{cutoff}',vector_arrays,
                        dict(identity,catalog=kind,frequency_hz=observation.frequency_hz,K_u=cutoff,
                            K_top=top_cutoff,definition='K_top sub-block reduced system, not independent small assembly'))
                    feedback.append(dict(cutoff=cutoff,artifact=receipt['path'],
                        max_relative_identity_residual=float(np.max(vector_arrays['relative_identity_residual']))))
            artifacts=[]
            for (cutoff,workspace),value in sorted(computed.items()):
                arrays={n:value[n] for n in ('prediction','J_complete','J_intrinsic','X_s','X_r') if n in value}
                arrays.update(observed=observation.scattered,residual=value['prediction']-observation.scattered)
                if workspace==512:
                    # Required sub-block failure fallback for designated C0.
                    arrays.update({n:value[n] for n in ('A','B_s','B_r','R')})
                for parent in attempted:
                    if parent['cutoff']==cutoff:
                        for delta in (32,64):
                            if (cutoff+delta,512) in computed:
                                high=computed[(cutoff+delta,512)]
                                if any(n not in value or n not in high for n in ('J_complete','J_intrinsic')):
                                    continue
                                f,cols=errors(value,high)
                                arrays[f'field_error_plus{delta}']=np.asarray(f)
                                for name,e in cols.items(): arrays[f'{name}_errors_plus{delta}']=e
                receipt=chunks.save(f'{cell_name}_U{cutoff}_B{workspace}',arrays,
                    dict(identity,catalog=kind,frequency_hz=observation.frequency_hz,
                        wavenumber=observation.wavenumber,K_u=cutoff,B_work=workspace,
                        settings=asdict(physics.settings) if workspace==512 else asdict(workspace_physics.settings)))
                artifacts.append(dict(cutoff=cutoff,workspace=workspace,artifact=receipt['path'],
                    bytes=receipt['bytes'],compute_seconds=value.get('compute_seconds'),
                    response_status=value['status'],
                    system_residual=value['system_residual']))
            cell=dict(catalog=kind,frequency_hz=observation.frequency_hz,
                status='failed' if failure else 'qualified' if selected is not None else 'unqualified',
                response_gate='field and every complete-trial P column; intrinsic errors are diagnostic',
                traceback=failure,selected_K_u=selected,K_top=top_cutoff,
                attempted=attempted,workspace_check=workspace_check,feedback=feedback,artifacts=artifacts)
            cells.append(cell)
            write(target/'progress.json',dict(role=role_name,status=status,cells=cells,
                compute_seconds=perf_counter()-started-chunks.seconds,io_seconds=chunks.seconds,
                artifact_bytes=sum(x['bytes'] for x in chunks.rows),work=work))
            print(role_name,cell_name,cell['status'],'U',selected,'workspace',workspace_check,flush=True)
            computed.clear()
        if status=='RESOURCE_BLOCKED': break
    expected=19*len(kinds)
    value=dict(role=role_name,status='CELLS_TERMINAL' if len(cells)==expected else status,
        expected_cells=expected,cells=cells,work=work,compute_seconds=perf_counter()-started-chunks.seconds,
        io_seconds=chunks.seconds,elapsed_seconds=perf_counter()-started,
        artifact_bytes=sum(x['bytes'] for x in chunks.rows),chunks=len(chunks.rows),
        snapshots='all attempted B512 cutoffs retained separately',
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
        peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),
        peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),
        pending=manifest['required_pending'],physics=physics.receipt(),workspace_physics=workspace_physics.receipt())
    write(target/'result.json',value)
    return value


def collect(control, folder):
    COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
        fcntl.flock(compute,fcntl.LOCK_EX); fcntl.flock(source,fcntl.LOCK_SH)
        from .ma007_diagnostics import pilot_usage
        prior=pilot_usage()
        compute_limit=max(0.,10800-prior['offline_seconds'])
        byte_limit=max(0,20*2**30-prior['artifact_bytes'])
        manifest=prepare(control,folder); completed=[]; status='COLLECTING'
        manifest.update(pilot_usage_at_start=prior,remaining_pilot_compute_seconds=compute_limit,
            remaining_pilot_artifact_bytes=byte_limit)
        write(folder/'manifest.json',manifest)
        stop=threading.Event(); samples=[]; monitor=threading.Thread(target=monitor_gpu,args=(stop,samples),daemon=True)
        monitor.start()
        memory_before=available_memory()
        for role in read(folder/'roles.json')['roles']:
            if role['status']!='reached': continue
            elapsed=sum(x['compute_seconds'] for x in completed)
            used=sum(x['artifact_bytes'] for x in completed)
            if elapsed>=compute_limit or used>=byte_limit:
                status='RESOURCE_BLOCKED';break
            env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
            with (folder/(role['role']+'.log')).open('w') as log:
                done=subprocess.run([sys.executable,'-m','experiments.benchmark.ma007_atlas','worker',
                    '--folder',str(folder),'--role',role['role'],
                    '--compute-allowance',str(compute_limit-elapsed),'--byte-allowance',str(byte_limit-used)],
                    cwd=c.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            path=folder/role['role']/'result.json'
            if done.returncode or not path.exists():
                status='ATLAS_PROCESS_FAILED';write(folder/(role['role']+'_failure.json'),dict(returncode=done.returncode));break
            completed.append(read(path))
            if completed[-1]['status']!='CELLS_TERMINAL': status=completed[-1]['status'];break
        verify(folder)
        stop.set(); monitor.join(timeout=12)
        if status=='COLLECTING': status='RESPONSE_CELLS_TERMINAL'
        value=dict(status=status,full_atlas_complete=False,roles=completed,
            compute_seconds=sum(x['compute_seconds'] for x in completed),
            io_seconds=sum(x['io_seconds'] for x in completed),artifact_bytes=sum(x['artifact_bytes'] for x in completed),
            pending=manifest['required_pending'])
        measured=[s for s in samples if 'used_bytes' in s]
        value['resources']=dict(memory_before=memory_before,memory_after=available_memory(),
            peak_rss_bytes=max((x['peak_rss_bytes'] for x in completed),default=None),
            peak_gpu_reserved_bytes=max((x['peak_gpu_reserved_bytes'] for x in completed),default=None),
            peak_gpu_used_sample_bytes=max((x['used_bytes'] for x in measured),default=None),
            gpu_capacity_bytes=measured[0]['total_bytes'] if measured else None)
        write(folder/'resource_samples.json',dict(samples=samples))
        write(folder/'response_atlas.json',value)
        print(status,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('collect','worker','verify'))
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--control',type=Path)
    parser.add_argument('--role')
    parser.add_argument('--compute-allowance',type=float,default=10800.)
    parser.add_argument('--byte-allowance',type=int,default=20*2**30)
    args=parser.parse_args()
    if args.command=='collect':
        if args.control is None: parser.error('collect needs --control')
        collect(args.control.resolve(),args.folder.resolve())
    elif args.command=='worker': worker(args.folder.resolve(),args.role,args.compute_allowance,args.byte_allowance)
    else: verify(args.folder.resolve())


if __name__=='__main__': main()
