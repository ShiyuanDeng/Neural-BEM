"""Registered MA-007 selected operator differences and archived-source replay.

These are charged offline calculations on saved hook states. No value returned
here can choose a parent fit's endpoint or change a controller.
"""
import argparse
from dataclasses import asdict
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from time import perf_counter
import traceback
import numpy as np
from scipy.linalg import lu_solve
from bem_inverse.geometry_selection import make_update
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.continuation.lm_backend import normalize
from bem_inverse.geometry import values
from bem_inverse.io import write,digest,curve_from
from bem_inverse.modal_muller import ModalMuller,ModalSettings,token
from experiments.benchmark import campaign as c
from experiments.benchmark.ma007 import CASE,EXECUTION,Chunks,Capture,permutation,COORD,THREADS,OUTPUT,ARCHIVED,sources,hashes
from experiments.benchmark.ma007_retention import read

OPERATORS=('A','B_s','B_r','R')


def arrays(path):
    with np.load(c.ROOT/path,allow_pickle=False) as item:
        return {key:item[key] for key in item.files}


def relative(a,b,floor=1e-30):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),floor))


def wave_number(value):
    return complex(value['real'],value['imag']) if isinstance(value,dict) else complex(value)


def paired(R,X):
    return np.einsum('ij,ji->i',R,X)


def selected_derivatives(atlas,folder,role_name):
    role=next(x for x in read(atlas/'roles.json')['roles'] if x['role']==role_name)
    target=folder/role_name;target.mkdir(parents=True,exist_ok=False)
    if role['status']!='reached':
        result=dict(role=role_name,status=role['status']);write(target/'result.json',result);return result
    cells=read(atlas/role_name/'result.json')['cells']
    candidates=[]
    for cell in cells:
        if cell['catalog']!='real' or cell['selected_K_u'] is None: continue
        record=next(x for x in cell['attempted'] if x['cutoff']==cell['selected_K_u'])
        candidates.append((record['max_column_errors']['J_complete'][0],cell['frequency_hz'],cell))
    if not candidates:
        result=dict(role=role_name,status='unqualified',reason='no response-qualified real cell')
        write(target/'result.json',result);return result
    cell=max(candidates,key=lambda x:x[:2])[2];cutoff=cell['selected_K_u']
    geometry=arrays(str((atlas/role_name/'chunks/geometry_response_directions.npz').relative_to(c.ROOT)))
    entry=next(x for x in cell['artifacts'] if x['cutoff']==cutoff and x['workspace']==512)
    base_saved=arrays(entry['artifact']);errors=base_saved['J_complete_errors_plus32']
    chosen=[0]
    chosen.extend(int(x) for x in np.argsort(-errors,kind='stable') if int(x)!=0)
    chosen=chosen[:3]
    P=(len(geometry['export_permutation'])-1)//2
    problem=c.problem(CASE);curve=curve_from(role['curve'])
    observation=next(x for x in problem.real if x.frequency_hz==cell['frequency_hz'])
    capture=Capture();physics=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=512,
        cached_geometries=1),observer=capture)
    update=make_update('certified_spectral',problem.length_unit_m,EXECUTION);space=update.prepare(curve,P,curve.band)
    chunks=Chunks(target/'chunks');started=perf_counter();work=0;rows=[]
    for u in (cutoff,cutoff+32):
        try:
            work+=1;prediction=physics.evaluate(curve,observation,problem.contrast,token(u))
            base={k:np.array(capture.field[k],copy=True) for k in (*OPERATORS,'X_s')}
            work+=1;J=physics.derivative(prediction,update,space)[:,geometry['export_permutation']]
            for direction in chosen:
                V=geometry['cartesian_velocity_coefficients'][:,direction]
                exact_zero=bool(np.count_nonzero(V)==0)
                estimates=[];attempts=[];qualified=False
                if exact_zero:
                    row=dict(direction_export=direction,K_u=u,status='certified_zero_saved_tangent',
                        operator_FD_convergence=True,discrete_data_consistency=True,
                        Hadamard_consistency=True,refinement_step_fidelity=True)
                    rows.append(row);continue
                for h in (1e-7,5e-8,2.5e-8,1.25e-8):
                    try:
                        measured=[];operators=[];trial_values=[];amplitudes=[]
                        for sign in (1,-1):
                            perturbed=FourierCurve(curve.coefficients+sign*h*V)
                            perturbed.validate()
                            nodes=curve.nodes(len(geometry['parameters']))
                            physical=values(sign*h*V,len(nodes.parameters))*problem.length_unit_m
                            amplitudes.append(dict(rms_m=float(np.sqrt(nodes.arc_length_weights@
                                (abs(physical)**2)/nodes.perimeter)),max_m=float(np.max(abs(physical)))))
                            work+=1;p=physics.evaluate(perturbed,observation,problem.contrast,token(u))
                            measured.append(np.array(p.prediction,copy=True))
                            operators.append({key:np.array(capture.field[key],copy=True) for key in OPERATORS})
                            step=np.zeros(2*P+1);step[int(geometry['export_permutation'][direction])]=sign*h
                            candidate=update.trial(space,step)[0]
                            work+=1;trial_values.append(np.array(physics.evaluate(candidate,observation,
                                problem.contrast,token(u)).prediction,copy=True))
                        D={key:(operators[0][key]-operators[1][key])/(2*h) for key in OPERATORS}
                        fd=(measured[0]-measured[1])/(2*h)
                        trial_fd=(trial_values[0]-trial_values[1])/(2*h)
                        identity=paired(D['R'],base['X_s'])+paired(base['R'],lu_solve(prediction._handle.factors,
                            D['B_s']-D['A']@base['X_s']))
                        discrete=relative(identity,fd)
                        hadamard=relative(J[:,direction],fd)
                        trial_error=relative(trial_fd,J[:,direction])
                        rounded_zero=bool(np.linalg.norm(fd)==0)
                        refinement=None
                        if estimates:
                            previous=estimates[-1]
                            refinement={key:float(np.linalg.norm(1e-3*(previous[key]-D[key]))/
                                max(np.linalg.norm(1e-3*D[key]),1e-12*np.linalg.norm(base[key]),1e-30))
                                for key in OPERATORS}
                        artifact=chunks.save(f'U{u}_direction{direction}_h{h:g}',
                            dict(**{f'D_{key}':D[key] for key in OPERATORS},straight_data_fd=fd,
                                discrete_response_identity=identity,Hadamard_response=J[:,direction],
                                actual_trial_fd=trial_fd,straight_plus_data=measured[0],straight_minus_data=measured[1],
                                nonlinear_trial_plus_data=trial_values[0],nonlinear_trial_minus_data=trial_values[1]),
                            dict(role=role_name,frequency_hz=observation.frequency_hz,K_u=u,B_work=512,
                                direction_export=direction,direction_grouped=int(geometry['export_permutation'][direction]),
                                coordinate_increment_m=h,physical_amplitudes=amplitudes,
                                derivative_units='saved operator units per metre of optimizer coordinate',
                                h_ref_m=1e-3,source='centered differences of actual assembled operators',
                                zero_status='rounded data difference unresolved' if rounded_zero else 'nonzero'))
                        attempt=dict(h_m=h,artifact=artifact['path'],operator_relative=refinement,
                            discrete_data_relative=discrete,Hadamard_relative=hadamard,
                            actual_trial_relative=trial_error,rounded_zero=rounded_zero,physical_amplitudes=amplitudes)
                        attempts.append(attempt);estimates.append(D)
                        if refinement is not None and max(refinement.values())<=1e-3 and discrete<=1e-3 and not rounded_zero:
                            qualified=True;break
                    except Exception:
                        attempts.append(dict(h_m=h,status='failed',traceback=traceback.format_exc()));break
                last=attempts[-1]
                rows.append(dict(direction_export=direction,K_u=u,status='qualified' if qualified else 'unqualified',
                    attempts=attempts,operator_FD_convergence=bool(qualified),
                    discrete_data_consistency=bool(last.get('discrete_data_relative',np.inf)<=1e-3 and not last.get('rounded_zero',True)),
                    Hadamard_consistency=bool(last.get('Hadamard_relative',np.inf)<=1e-3 and not last.get('rounded_zero',True)),
                    refinement_step_fidelity=bool(last.get('actual_trial_relative',np.inf)<=1e-3 and qualified),
                    accepted_pair_h_m=[attempts[-2]['h_m'],last['h_m']] if qualified else None))
        except Exception:
            rows.append(dict(K_u=u,status='failed',traceback=traceback.format_exc()))
    value=dict(role=role_name,status='DERIVATIVE_CELLS_TERMINAL',frequency_hz=cell['frequency_hz'],
        selected_K_u=cutoff,directions_export=chosen,P=P,rows=rows,work_units=work,
        compute_seconds=perf_counter()-started-chunks.seconds,io_seconds=chunks.seconds,
        artifact_bytes=sum(x['bytes'] for x in chunks.rows),physics=physics.receipt(),
        flags_definition='four separate gates; discrete identity alone is not a physical certificate')
    write(target/'result.json',value);return value


def regenerate(run,atlas,folder):
    """Caller puts the archived numerical source first on PYTHONPATH."""
    folder.mkdir(parents=True,exist_ok=False);problem=c.problem(CASE)
    index=read(run/'recording/index.json');chunks=Chunks(folder/'chunks')
    rng=np.random.default_rng(42007)
    fields=[e for e in index['events'] if e['kind']=='field']
    linearizations=[e for e in index['events'] if e['kind']=='linearization']
    samples=[*rng.choice(len(fields),min(20,len(fields)),replace=False)]
    sampled_j=[*rng.choice(len(linearizations),min(5,len(linearizations)),replace=False)]
    rows=[];work=0;started=perf_counter()
    operations=read(run/'plan.json')['operations'];stages={e['label']:e for e in operations if e['operation']=='fit'}
    services={};update=make_update('certified_spectral',problem.length_unit_m,EXECUTION)
    def service(workspace):
        if workspace not in services:
            services[workspace]=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=workspace,cached_geometries=1))
        return services[workspace]
    def observation(event):
        return next(o for o in (*problem.real,*problem.damped) if complex(o.wavenumber)==wave_number(event['wavenumber']))
    for i in samples:
        event=fields[int(i)];original=arrays(event['artifact'])
        try:
            work+=1;new=service(event['B_work']).evaluate(FourierCurve(original['coefficients']),
                observation(event),problem.contrast,token(event['K_u'])).prediction
            error=relative(new,original['prediction'],1e-14*np.linalg.norm(original['observed']))
            receipt=chunks.save(f'field_event{event["index"]}',dict(original=original['prediction'],regenerated=new),
                dict(original_event=event['index'],relative_error=error))
            rows.append(dict(kind='field',event=event['index'],passed=error<=1e-10,relative_error=error,artifact=receipt['path']))
        except Exception:
            rows.append(dict(kind='field',event=event['index'],passed=False,traceback=traceback.format_exc()))
    for i in sampled_j:
        event=linearizations[int(i)];original=arrays(event['artifact']);op=stages[event['stage']]
        prior=[e for e in fields if e['state_sha256']==event['state_sha256'] and e['index']<event['index']]
        # The immediately preceding reciprocal for each frequency identifies
        # production cutoff/workspace even after a monotone resolution repair.
        reciprocal=[e for e in index['events'] if e['kind']=='reciprocal' and
            e['state_sha256']==event['state_sha256'] and e['index']<event['index']]
        try:
            columns=[];observed=[]
            for frequency in op['stage']['frequencies_hz']:
                catalog=problem.damped if any(op['stage']['damping']) else problem.real
                o=next(o for o in catalog if o.frequency_hz==frequency)
                recent=next(e for e in reversed(reciprocal) if wave_number(e['wavenumber'])==complex(o.wavenumber))
                f=next(e for e in reversed(prior) if wave_number(e['wavenumber'])==complex(o.wavenumber) and e['K_u']==recent['K_u'])
                curve=FourierCurve(arrays(f['artifact'])['coefficients']);space=update.prepare(curve,event['M'],curve.band)
                work+=1;p=service(f['B_work']).evaluate(curve,o,problem.contrast,token(f['K_u']))
                work+=1;columns.append(service(f['B_work']).derivative(p,update,space));observed.append(o.scattered)
            matrix=normalize(np.stack(columns,axis=1),np.column_stack(observed),op['stage']['weights'],
                op['optimizer']['residual_floor'])
            error=relative(matrix,original['J_normalized'],1e-14)
            receipt=chunks.save(f'linearization_event{event["index"]}',dict(original=original['J_normalized'],regenerated=matrix),
                dict(original_event=event['index'],relative_error=error))
            rows.append(dict(kind='linearization',event=event['index'],passed=error<=1e-10,relative_error=error,artifact=receipt['path']))
        except Exception:
            rows.append(dict(kind='linearization',event=event['index'],passed=False,traceback=traceback.format_exc()))
    # This response cell has its own archived atlas source; the parent invokes
    # it separately with that source so its P map is also reproduced exactly.
    result=dict(status='REGENERATION_PASSED' if all(r['passed'] for r in rows) else 'REGENERATION_DEFECT',
        seed=42007,rows=rows,work_units=work,compute_seconds=perf_counter()-started-chunks.seconds,
        io_seconds=chunks.seconds,artifact_bytes=sum(x['bytes'] for x in chunks.rows),
        numerical_source_file=__import__('bem_inverse.modal_muller',fromlist=['']).__file__,geometry_settings=update.settings())
    write(folder/'result.json',result);return result


def final_cell(atlas,folder):
    folder.mkdir(parents=True,exist_ok=False);role=next(x for x in read(atlas/'roles.json')['roles'] if x['role']=='5_final')
    if role['status']!='reached':
        write(folder/'result.json',dict(status=role['status']));return
    cell=next(x for x in read(atlas/'5_final/result.json')['cells'] if x['catalog']=='real' and x['frequency_hz']==2.5e9)
    entry=next(x for x in cell['artifacts'] if x['cutoff']==cell['selected_K_u'] and x['workspace']==512)
    old=arrays(entry['artifact']);problem=c.problem(CASE);curve=curve_from(role['curve'])
    service=ModalMuller(EXECUTION,ModalSettings(coefficient_workspace=512,cached_geometries=1))
    geom=arrays(str((atlas/'5_final/chunks/geometry_response_directions.npz').relative_to(c.ROOT)))
    P=(len(geom['export_permutation'])-1)//2;update=make_update('certified_spectral',problem.length_unit_m,EXECUTION)
    space=update.prepare(curve,P,curve.band);started=perf_counter();chunks=Chunks(folder/'chunks')
    try:
        p=service.evaluate(curve,problem.real[-1],problem.contrast,token(cell['selected_K_u']))
        J=service.derivative(p,update,space)[:,geom['export_permutation']]
        field_error=relative(p.prediction,old['prediction'],1e-14*np.linalg.norm(problem.real[-1].scattered))
        J_error=relative(J,old['J_complete'],1e-14*np.linalg.norm(problem.real[-1].scattered))
        receipt=chunks.save('final_2.5_real',dict(original_prediction=old['prediction'],regenerated_prediction=p.prediction,
            original_J=old['J_complete'],regenerated_J=J),dict(P=P,K_u=cell['selected_K_u'],B_work=512))
        result=dict(status='REGENERATION_PASSED' if max(field_error,J_error)<=1e-10 else 'REGENERATION_DEFECT',
            field_relative=field_error,J_relative=J_error,artifact=receipt['path'],work_units=2)
    except Exception:
        result=dict(status='REGENERATION_DEFECT',traceback=traceback.format_exc())
    result.update(compute_seconds=perf_counter()-started-chunks.seconds,io_seconds=chunks.seconds,
        artifact_bytes=sum(x['bytes'] for x in chunks.rows),
        numerical_source_file=__import__('bem_inverse.modal_muller',fromlist=['']).__file__)
    write(folder/'result.json',result);return result


def archived_roles():
    plan=read(ARCHIVED/'plan.json')
    ops={x['label']:x for x in plan['operations'] if x['operation']=='fit'}
    result=read(ARCHIVED/'result.json');problem=c.problem(CASE)
    entries=[]
    for name,label,path,key in (('initial','warmup_025_damped',ARCHIVED/'warmup_025_damped.json','curve'),
        ('last_damped','stage_4_damped',ARCHIVED/'stage_4_damped.json','curve'),
        ('failed_endpoint',result['stages'][-1]['stage'],ARCHIVED/'result.json','final_curve')):
        op=ops[label];stage=read(ARCHIVED/(label+'.json'))
        curve=curve_from(read(path)[key]) if name!='initial' else __import__('bem_inverse.geometry',fromlist=['resize']).resize(problem.initial,4)
        controller=stage['history'][0 if name=='initial' else -1]
        from bem_inverse.io import curve_record
        entries.append(dict(role=name,status='reached',curve=curve_record(curve),M=op['stage']['update_modes'],
            K=curve.band,K_u=stage['nodes']//8,frequencies_hz=op['stage']['frequencies_hz'],
            catalog='damped' if any(op['stage']['damping']) else 'real',lambda_carried=controller['next_damping'],
            controller=controller,config=op['optimizer'],source_epoch='DP-001/F_screen old trajectory',
            state_path=str(path.relative_to(c.ROOT)),state_sha256=digest(path),archived_plan_sha256=digest(ARCHIVED/'plan.json')))
    return entries


def qualify_archived(folder,role_name):
    from experiments.benchmark.ma007_probes import active_qualification
    folder.mkdir(parents=True,exist_ok=False)
    role=next(r for r in archived_roles() if r['role']==role_name)
    write(folder/'manifest.json',dict(role=role,source_hashes=hashes(),purpose='prescribed archived hook state; new implementation qualification'))
    return active_qualification(c.problem(CASE),role,folder)


def pilot_usage():
    """All failed and successful recording-pilot attempts share the same limits."""
    groups=[p for p in OUTPUT.glob('phaseA-*') if p.name!='phaseA-max-001']
    byte_count=sum(f.stat().st_size for p in groups for f in p.rglob('*') if f.is_file())
    seconds=0.
    for p in groups:
        if (p/'response_atlas.json').exists():seconds+=read(p/'response_atlas.json')['compute_seconds']
        if (p/'batch_validation.json').exists():
            seconds+=sum(x['compute_seconds']+x['monitor_seconds'] for x in read(p/'batch_validation.json')['rows'])
        if (p/'result.json').exists():
            r=read(p/'result.json');seconds+=r.get('compute_seconds',0)
        if p.name.startswith('phaseA-diagnostics'):
            seconds+=sum(read(f).get('compute_seconds',0) for f in p.glob('*/result.json'))
            seconds+=sum(read(f).get('compute_seconds',0) for f in p.glob('operators/*/result.json'))
    return dict(artifact_bytes=byte_count,offline_seconds=seconds,limits=dict(artifact_bytes=20*2**30,offline_seconds=10800))


def extract_numerical_source(archive,target):
    with tarfile.open(archive,'r:gz') as handle:
        members=[m for m in handle.getmembers() if m.name.startswith('solvers/')]
        if any(Path(m.name).is_absolute() or '..' in Path(m.name).parts or m.issym() or m.islnk() for m in members):
            raise ValueError('Unsafe archived source member')
        handle.extractall(target,members=members)


def collect(run,atlas,folder):
    """One worker at a time, immutable source archive, all declared pilot cells."""
    from experiments.cleaned_interface.benchmark import environment
    folder.mkdir(parents=True,exist_ok=False);COORD.mkdir(exist_ok=True)
    with (COORD/'compute.lock').open('a') as compute,(COORD/'source.lock').open('a') as source:
        fcntl.flock(compute,fcntl.LOCK_EX);fcntl.flock(source,fcntl.LOCK_SH)
        initial_usage=pilot_usage()
        with tarfile.open(folder/'sources.tar.gz','w:gz') as archive:
            for path in sources():archive.add(path,arcname=str(path.relative_to(c.ROOT)),recursive=False)
        jobs=[]
        for role in read(atlas/'roles.json')['roles']:
            jobs.append(dict(name='active_'+role['role'],command='active',role=role['role'],status=role['status']))
        for role in ('initial','last_damped','failed_endpoint'):
            jobs.append(dict(name='archived_'+role,command='qualify-archived',role=role,status='reached'))
        for role in ('4_first_resolution_refusal','5_final'):
            jobs.append(dict(name='operators_'+role,command='derivatives',role=role,status='reached'))
        jobs.extend([dict(name='recording_regeneration',command='regenerate',status='reached'),
                     dict(name='atlas_final_regeneration',command='final-cell',status='reached')])
        manifest=dict(experiment='MA-007',case=CASE,purpose='C0 pilot remaining active/derivative/regeneration calculations',
            source_hashes=hashes(),source_archive_sha256=digest(folder/'sources.tar.gz'),
            environment=environment(),execution=asdict(EXECUTION),expected=jobs,
            parent_run=str(run.relative_to(c.ROOT)),parent_atlas=str(atlas.relative_to(c.ROOT)),
            retention='local raw arrays, committed hashes/receipts',initial_pilot_usage=initial_usage)
        write(folder/'manifest.json',manifest);completed=[];status='COLLECTING'
        for job in jobs:
            usage=pilot_usage()
            if usage['artifact_bytes']+2**30>20*2**30 or usage['offline_seconds']>=10800:
                status='RESOURCE_BLOCKED';break
            if job['status']!='reached':
                target=folder/job['name'];target.mkdir();write(target/'result.json',dict(status=job['status']))
                completed.append(dict(job=job,result=dict(status=job['status'])));continue
            env=dict(os.environ,PYTHONPATH=f'{c.ROOT}/solvers:{c.ROOT}',**THREADS)
            target=folder/job['name'];temporary=None
            if job['command']=='active':
                args=[sys.executable,'-m','experiments.benchmark.ma007_probes','qualify','--atlas',str(atlas),
                    '--role',job['role'],'--folder',str(target)]
            else:
                if job['command'] in ('regenerate','final-cell'):
                    archive=(run.parent if job['command']=='regenerate' else atlas)/'sources.tar.gz'
                    temporary=tempfile.TemporaryDirectory(prefix='ma007-source-replay-')
                    extract_numerical_source(archive,Path(temporary.name))
                    env['PYTHONPATH']=f'{temporary.name}/solvers:{c.ROOT}'
                target=folder/'operators' if job['command']=='derivatives' else target
                args=[sys.executable,str(Path(__file__).resolve()),job['command'],'--atlas',str(atlas),
                    '--run',str(run),'--folder',str(target)]
                if 'role' in job:args.extend(['--role',job['role']])
            try:
                with (folder/(job['name']+'.log')).open('w') as log:
                    process=subprocess.run(args,cwd=c.ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            finally:
                if temporary is not None:temporary.cleanup()
            result_path=target/job['role']/'result.json' if job['command']=='derivatives' else target/'result.json'
            if process.returncode or not result_path.exists():
                completed.append(dict(job=job,result=dict(status='IMPLEMENTATION_FAILURE',returncode=process.returncode)))
                status='IMPLEMENTATION_FAILURE';break
            result=read(result_path);completed.append(dict(job=job,result=result))
            write(folder/'progress.json',dict(status=status,completed=completed,pilot_usage=pilot_usage()))
            print(job['name'],result['status'],flush=True)
        if hashes()!=manifest['source_hashes']:raise ValueError('Diagnostic source epoch changed')
        if status=='COLLECTING':status='DIAGNOSTIC_CELLS_TERMINAL'
        write(folder/'diagnostics.json',dict(status=status,completed=completed,expected=len(jobs),terminal=len(completed),
            pilot_usage=pilot_usage(),complete_atlas=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('derivatives','regenerate','final-cell','qualify-archived','collect'))
    parser.add_argument('--folder',required=True,type=Path)
    parser.add_argument('--atlas',required=True,type=Path)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--role')
    args=parser.parse_args()
    if args.command=='collect':collect(args.run.resolve(),args.atlas.resolve(),args.folder.resolve());return
    elif args.command=='qualify-archived':result=qualify_archived(args.folder.resolve(),args.role)
    elif args.command=='derivatives':result=selected_derivatives(args.atlas.resolve(),args.folder.resolve(),args.role)
    elif args.command=='regenerate':result=regenerate(args.run.resolve(),args.atlas.resolve(),args.folder.resolve())
    else:result=final_cell(args.atlas.resolve(),args.folder.resolve())
    print(result['status'],flush=True)


if __name__=='__main__':main()
