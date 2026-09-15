"""Execute only the frozen BIE-006 contract. No inverse or shared mutations."""
import os
for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS',
             'VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[name]='1'
from pathlib import Path
import argparse
from datetime import datetime,timezone
import platform
import resource
import shutil
import signal
import subprocess
import sys
import time
import traceback
import numpy as np
import scipy
from gpr_bem_kress import solve_kress_tmz_total_field_batch
from .fixtures import frozen_inputs,FREQUENCIES,AMPLITUDES,TRAJECTORY,ACQUISITION
from .models import tangent,operator_prediction
from .support import (Ledger,Stop,LIMITS,digest,write_json,relative,numerical_workers,
                      forward,derivative,geometry)

PLAN=Path('docs/iterations/boundary_bie/iteration_03/03_plan.md')


def tangent_setup(base,d,ledger):
    ledger.emit('base_lu','reused',0.)
    return ledger.call('tangent_setup',lambda:tangent(base.A,base.B,base.C,base.U,base.factors,d),
                        dict(solves=1),rhs_count=base.B.shape[1])


def predictions(base,d,dy,h,ledger,order):
    result={}
    for arm in order:
        before=numerical_workers()
        if arm=='T':
            y,seconds=ledger.call('tangent_online',lambda:base.Y+h*dy)
            result['T']=dict(Y=y,seconds=seconds)
        else:
            op,seconds=ledger.call('operator_online',lambda:operator_prediction(base.A,base.B,base.C,d,h),
                dict(factorizations=1,solves=1,updated_solves=1),rhs_count=base.B.shape[1])
            if op['approximate_residual']>1e-10:raise Stop('SURROGATE_SOLVE_UNQUALIFIED')
            op['seconds']=seconds;result['O']=op
        result[arm]['workers_before']=before;result[arm]['workers_after']=numerical_workers()
    return result


def run(output,ledger,inputs):
    c,s=np.asarray(inputs['cosine']),np.asarray(inputs['sine']);acq=inputs['acquisition']
    rows=[];refs=[];controls=[];timings=[];saved={};geometries=[]
    def checkpoint():
        for name,value in [('accuracy',rows),('refinements',refs),('controls',controls),
                           ('timings',timings),('geometry',geometries)]:
            write_json(output/(name+'.json'),value)
        np.savez_compressed(output/'predictions.npz',**saved)
    for frequency in FREQUENCIES:
        ledger.guard();bases={};directions={}
        for n in [128,256]:
            ledger.context=dict(stage='base',frequency_hz=frequency,nodes=n)
            bases[n]=forward(c,s,n,frequency,acq,ledger)
            saved[f'base_{frequency}_{n}']=bases[n].Y
        base,fine=bases[128],bases[256]
        base_discrepancy=relative(base.Y.diagonal(),fine.Y.diagonal())
        refs.append(dict(kind='base',frequency_hz=frequency,paired_relative=base_discrepancy,
                         full_relative=relative(base.Y,fine.Y),qualified=base_discrepancy<=2e-7))
        ledger.context=dict(stage='production_parity',frequency_hz=frequency,nodes=128)
        parity,_=ledger.call('public_forward_parity',lambda:solve_kress_tmz_total_field_batch(
            base.curve,base.base.source_points,base.base.receiver_points,2*np.pi*frequency,
            base.base.source_strengths,exterior=base.base.exterior_material,
            interior=base.base.interior_material,eps0=acq['eps0'],mu0=acq['mu0']),
            dict(exact_assemblies=1,factorizations=1,solves=1))
        pe=max(relative(base.U,parity.solution),relative(base.Y,parity.scattered_receiver.T))
        controls.append(dict(kind='production_parity',frequency_hz=frequency,relative=pe,passed=pe<=2e-11))
        if pe>2e-11:raise Stop('PRODUCTION_PARITY_FAILED')
        for direction in inputs['directions']:
            name=direction['id'];per_n={}
            for n in [128,256]:
                ledger.context=dict(stage='direction_setup',frequency_hz=frequency,nodes=n,direction=name)
                d,td,diag=derivative(bases[n],direction,ledger)
                dy,tt=tangent_setup(bases[n],d,ledger)
                per_n[n]=(d,dy,td,tt)
                controls.append(dict(kind='derivative_primal',frequency_hz=frequency,nodes=n,
                                     direction=name,diagnostics=diag,
                                     passed=all(v<=2e-11 for k,v in diag.items() if k.startswith('primal_'))))
                saved[f'dy_{frequency}_{name}_{n}']=dy
            d,dy,td,tt=per_n[128]
            derivative_discrepancy=relative(dy.diagonal(),per_n[256][1].diagonal())
            refs.append(dict(kind='derivative',frequency_hz=frequency,direction=name,
                paired_relative=derivative_discrepancy,full_relative=relative(dy,per_n[256][1]),
                qualified=derivative_discrepancy<=2e-5))
            directions[name]=per_n
            for index,h in enumerate(AMPLITUDES):
                ledger.context=dict(stage='accuracy',frequency_hz=frequency,nodes=128,direction=name,amplitude_m=h)
                cc=c+h*np.asarray(direction['cosine']);ss=s+h*np.asarray(direction['sine'])
                try:
                    # This validation is the common online geometry cost of each arm.
                    (_,geo),gt=ledger.call('candidate_geometry',lambda:geometry(cc,ss,128,acq))
                except ValueError as exc:
                    geometries.append(dict(frequency_hz=frequency,direction=name,amplitude_m=h,
                                           feasible=False,reason=str(exc)))
                    checkpoint();continue
                geometries.append(dict(frequency_hz=frequency,direction=name,amplitude_m=h,
                                       feasible=True,details=geo))
                pred=predictions(base,d,dy,h,ledger,['T','O'] if index%2==0 else ['O','T'])
                before=numerical_workers();exact=forward(cc,ss,128,frequency,acq,ledger)
                after=numerical_workers()
                ledger.context.update(nodes=256)
                reference=forward(cc,ss,256,frequency,acq,ledger)
                floor=1e-12*float(np.linalg.norm(np.diag(base.base.incident_receiver)))
                discrepancy=relative(exact.Y.diagonal(),reference.Y.diagonal(),floor)
                qualified=discrepancy<=2e-7 and base_discrepancy<=2e-7 and derivative_discrepancy<=2e-5
                key=f'{frequency}_{name}_{index}'
                for label,y in [('E',exact.Y),('R',reference.Y),('T',pred['T']['Y']),('O',pred['O']['Y'])]:
                    saved[key+'_'+label]=y
                row=dict(key=key,frequency_hz=frequency,direction=name,amplitude_m=h,
                         rms_displacement_m=h*direction['rms_over_max'],qualified=qualified,
                         refinement_relative=discrepancy,full_refinement_relative=relative(exact.Y,reference.Y),
                         base_seconds=base.seconds,derivative_seconds=td,tangent_setup_seconds=tt,
                         geometry_seconds=gt,exact_seconds=exact.seconds,reference_seconds=reference.seconds,
                         exact_stage_seconds=exact.times,exact_wall_seconds=exact.wall_seconds,
                         T_online_seconds=gt+pred['T']['seconds'],O_online_seconds=gt+pred['O']['seconds'],
                         O_stage_seconds=pred['O']['times'],O_approximate_residual=pred['O']['approximate_residual'],
                         O_exact_matrix_residual=float(np.linalg.norm(exact.A@pred['O']['U']-exact.B)/np.linalg.norm(exact.B)),
                         workers_before=before,workers_after=after,
                         arm_workers={arm:{k:v for k,v in pred[arm].items() if k.startswith('workers_')} for arm in ['T','O']},
                         incident_floor=floor,reference_norm=float(np.linalg.norm(reference.Y.diagonal())))
                for label in ['T','O']:
                    y=pred[label]['Y']
                    row[label+'_relative']=relative(y.diagonal(),reference.Y.diagonal(),floor)
                    row[label+'_absolute']=float(np.linalg.norm(y.diagonal()-reference.Y.diagonal()))
                    row[label+'_full_relative']=relative(y,reference.Y,floor)
                    row[label+'_same_grid_relative']=relative(y.diagonal(),exact.Y.diagonal(),floor)
                row['O_T_relative']=relative(pred['O']['Y'].diagonal(),pred['T']['Y'].diagonal(),floor)
                rows.append(row);checkpoint()
                print(f"{frequency/1e9:g}GHz {name} {h*1000:g}mm T={row['T_relative']:.3e} O={row['O_relative']:.3e} ref={discrepancy:.2e}",flush=True)
        ledger.guard();del bases,directions
    # Fixed timing finalist; not selected by measured prediction errors.
    direction=inputs['directions'][0];h=.001;frequency=FREQUENCIES[1]
    cc=c+h*np.asarray(direction['cosine']);ss=s+h*np.asarray(direction['sine'])
    for repeat in range(3):
        ledger.guard();ledger.context=dict(stage='timing',repeat=repeat,frequency_hz=frequency,nodes=128,
                                           direction=direction['id'],amplitude_m=h)
        before=numerical_workers();base=forward(c,s,128,frequency,acq,ledger)
        d,td,_=derivative(base,direction,ledger);dy,tt=tangent_setup(base,d,ledger)
        record=dict(repeat=repeat,base_seconds=base.seconds,derivative_seconds=td,tangent_setup_seconds=tt,
                    workers_before=before,load_before=list(os.getloadavg()),base_stage_seconds=base.times)
        for arm in (['E','T','O'],['T','O','E'],['O','E','T'])[repeat]:
            if arm=='E':
                exact=forward(cc,ss,128,frequency,acq,ledger)
                record['exact_seconds']=exact.seconds;record['exact_stage_seconds']=exact.times
            else:
                (_,geo),gt=ledger.call('timing_candidate_geometry',lambda:geometry(cc,ss,128,acq))
                value=predictions(base,d,dy,h,ledger,[arm])[arm]
                record[arm+'_online_seconds']=gt+value['seconds']
                record[arm+'_geometry_seconds']=gt
                record[arm+'_workers']=dict(before=value['workers_before'],after=value['workers_after'])
                if arm=='O':record['O_stage_seconds']=value['times']
        record['workers_after']=numerical_workers();record['load_after']=list(os.getloadavg())
        timings.append(record);checkpoint();ledger.guard()
        print('timing repeat',repeat,record['exact_seconds'],record['T_online_seconds'],record['O_online_seconds'],flush=True)
    return dict(accuracy_rows=len(rows),qualified_rows=sum(r['qualified'] for r in rows),
                feasibility_rows=len(geometries),all_controls_pass=all(r['passed'] for r in controls),
                all_base_refinements_pass=all(r['qualified'] for r in refs))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    output=args.output;output.mkdir(parents=True,exist_ok=False)
    inputs=frozen_inputs();write_json(output/'inputs.json',inputs)
    paths=set(Path('experiments/bie006_operator_reuse').glob('*.py'))
    for module in list(sys.modules.values()):
        file=getattr(module,'__file__',None)
        if file:
            p=Path(file).resolve()
            if p.is_relative_to(Path('solvers').resolve()) and p.suffix=='.py':paths.add(p.relative_to(Path.cwd()))
    hashes={str(p):digest(p) for p in sorted(paths)}
    hashes.update({str(p):digest(p) for p in [TRAJECTORY,ACQUISITION]})
    for p in sorted(paths):
        target=output/'measured_sources'/p;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    shutil.copy2(PLAN,output/'frozen_plan.md')
    manifest=dict(experiment='BIE-006',approval='User: then go, 2026-09-15',
                  started_utc=datetime.now(timezone.utc).isoformat(),status='IN PROGRESS',
                  command=' '.join(sys.argv),head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  source_input_hashes=hashes,limits=LIMITS,seconds_cap=900,rss_cap_gib=4,
                  platform=platform.platform(),cpu=Path('/proc/cpuinfo').read_text().split('model name')[1].split('\n')[0],
                  python=sys.version,numpy=np.__version__,scipy=scipy.__version__,
                  threads={name:os.environ[name] for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
                  load_before=list(os.getloadavg()),workers_before=numerical_workers())
    write_json(output/'manifest.json',manifest);ledger=Ledger(output,hashes)
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(Stop('BUDGET_STOP: 900 seconds alarm')))
    signal.alarm(900)
    code=0
    try:
        ledger.guard();manifest['outcome']=run(output,ledger,inputs);ledger.guard()
        manifest['status']='COMPLETE'
    except BaseException as exc:
        manifest['status']='FAILED_OR_STOPPED';manifest['reason']=repr(exc)
        (output/'traceback.txt').write_text(traceback.format_exc());code=1
        print(traceback.format_exc(),flush=True)
    finally:
        signal.alarm(0);manifest.update(counts=ledger.counts,elapsed_seconds=time.perf_counter()-ledger.started,
            peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            load_after=list(os.getloadavg()),workers_after=numerical_workers(),
            source_drift=[p for p,h in hashes.items() if digest(p)!=h])
        write_json(output/'manifest.json',manifest)
    return code


if __name__=='__main__':raise SystemExit(main())
