"""Bounded follow-up checks only: saved states and isolated forwards, never fits."""
import os
for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np

from brg_paper import BASE, ROOT, GIB, LADDER, now, solver_state, write, digest, bulk_manifest
sys.path[:0] = [str(ROOT/'solvers'), str(ROOT)]
OUT = BASE/'followup_checks'


def load(path):
    return json.loads(path.read_text())


def curve(row):
    from bem_inverse.io import curve_from
    return curve_from(row)


def wave_radius(c):
    a = c.coefficients.copy();a[c.band] = 0
    return float(abs(a).sum())


def saved_records():
    from experiments.baselines.brg.brg_data import true_curve
    from experiments.comparison.scoring import region, region_scores
    OUT.mkdir(parents=True, exist_ok=True)
    states = load(BASE/'glider_10/cuda_fit/attempt_01/local/accepted.json')['states']
    truth = true_curve('glider');actual, _ = region([truth.values(16384)])
    stages = {}
    for row in states:
        stages[row['stage']] = row
    rows = []
    for label, row in stages.items():
        c = curve(row['curve']);found, _ = region([c.values(16384)])
        scores = region_scores(found, actual)
        rows.append(dict(stage=label,k=LADDER[row['active_frequency_count']-1],
            iteration=row['iteration'], maximum_active_residual=row['maximum_stage_residual'],
            area_error=scores['area_error'], wave_radius=wave_radius(c), accepted_work_units=row['units']))
    write(OUT/'glider_10_stage_endpoints.json', dict(sources='Saved accepted states only; no forward or fit.',
          true_wave_radius=wave_radius(truth), rows=rows))
    left=BASE/'glider_033/cpu_fit';right=BASE/'glider_033/cuda_fit/attempt_01'
    cpu = load(left/'local/accepted.json')['states'];gpu = load(right/'local/accepted.json')['states']
    gm = {(r['stage'],r['iteration']):r for r in gpu}
    comparisons = []
    for a in cpu:
        key=(a['stage'],a['iteration'])
        if key not in gm: continue
        b=gm[key];x=curve(a['curve']).values(1024);y=curve(b['curve']).values(1024)
        comparisons.append(dict(stage=key[0],iteration=key[1],
              relative_curve_difference=float(np.linalg.norm(x-y)/np.linalg.norm(x)),
              maximum_point_difference=float(abs(x-y).max()),cpu_work=a['units'],gpu_work=b['units'],
              cpu_residual=a['maximum_stage_residual'],gpu_residual=b['maximum_stage_residual']))
    first=next((r for r in comparisons if r['relative_curve_difference']>1e-10),None)
    traces={}
    for label in dict.fromkeys(r['stage'] for r in comparisons):
        files=[left/'local'/f'{label}.json',right/'local'/f'{label}.json']
        if not all(p.exists() for p in files): continue
        a,b=[load(p) for p in files]
        hista={r['iteration']:r for r in a['history']};histb={r['iteration']:r for r in b['history']}
        iterations=[]
        for i in sorted(set(hista)&set(histb)):
            x,y=hista[i],histb[i]
            ta=[r for r in a['trials'] if r['iteration']==i]
            tb=[r for r in b['trials'] if r['iteration']==i]
            sig=lambda trials:[{k:r.get(k) for k in ('status','damping','backtrack','reason')} for r in trials]
            iterations.append(dict(iteration=i,decisions_equal=sig(ta)==sig(tb),
                  cpu_trials=sig(ta),gpu_trials=sig(tb),
                  cpu_damping=x['damping'],gpu_damping=y['damping'],
                  cpu_next_damping=x['next_damping'],gpu_next_damping=y['next_damping'],
                  cpu_step=x['step_m'],gpu_step=y['step_m'],
                  cpu_loss=x['loss'],gpu_loss=y['loss'],cpu_gradient=x['gradient_inf'],gpu_gradient=y['gradient_inf'],
                  cpu_work=x['work']['work_units'],gpu_work=y['work']['work_units']))
        traces[label]=iterations
    configs={}
    for name,path in [('cpu',left),('gpu',right)]:
        c=load(path/'local/configuration.json');m=load(path/'manifest.json')
        configs[name]=dict(execution=c['execution'],update=c['update'],
                          fit_seconds=m['policy']['fit_seconds'],fit_units=m['policy']['fit_units'],
                          operations=m['policy']['operations'],solver_source=m['solver_start'],
                          sources=m['sources'])
    write(OUT/'accepted_trace_comparison.json',dict(first_above_1e10=first,
          threshold=1e-10,comparisons=comparisons,iteration_decisions=traces))
    write(OUT/'pass_configuration_comparison.json',configs)
    print('First accepted curve difference above 1e-10:',first,flush=True)
    print('Glider10 stages:',len(rows),flush=True)


def physics_checks():
    from bem_inverse import FourierCurve,Execution
    from bem_inverse.forward_solvers.modal_muller import ModalMuller,ModalSettings,forward_solve
    from bem_inverse.geometry_selection import make_update
    from experiments.baselines.brg.brg_data import observation,true_curve
    OUT.mkdir(parents=True, exist_ok=True);(OUT/'local').mkdir(exist_ok=True)
    existing=load(OUT/'physics_comparison.json') if (OUT/'physics_comparison.json').exists() else {}
    assert not existing.get('stopped_on_finding'), 'Stop condition already met; no more checks.'
    started=time.monotonic();records=existing.get('rows',[])
    for shape in ('unit_disk','true_glider'):
        for k in (1.,2.5,15.):
            if any(r['shape']==shape and r['k']==k for r in records):
                continue
            M=int(np.floor(3*k));K=max(2*M+2,9 if shape=='true_glider' else 1)
            original=FourierCurve.circle() if shape=='unit_disk' else true_curve('glider')
            z=np.zeros(2*K+1,complex);z[K-original.band:K+original.band+1]=original.coefficients
            c=FourierCurve(z);obs,path,_=observation('glider_033',k)
            row=dict(shape=shape,k=k,eta=.33,trace_minimum=192,update_band=M,storage_band=K,
                     started=now(),solver_start=solver_state(),source_sha256=digest(path))
            cs=[];ps=[];updates=[];spaces=[]
            for device in ('cpu','cuda'):
                ctx=ModalMuller(Execution(device=device,frequency_threads=1),
                               ModalSettings(trace_minimum=192,series_loss=1e-6,table_mode=True))
                cs.append(ctx);p=forward_solve(c,obs,.33,ctx.resolution_profile(K)['production'],context=ctx);ps.append(p)
                u,_=make_update('slider',1.,ctx.execution);updates.append(u);spaces.append(u.prepare(c,M,K))
            relative=lambda a,b:float(np.linalg.norm(a-b)/np.linalg.norm(a))
            Jc=cs[0].derivative(ps[0],updates[0],spaces[0])
            Jg=cs[1].derivative(ps[1],updates[0],spaces[0])
            Jnative=cs[1].derivative(ps[1],updates[1],spaces[1])
            row.update(prediction_relative_difference=relative(ps[0].prediction,ps[1].prediction),
                       b7_fixed_basis_relative_difference=relative(Jc,Jg),
                       b7_native_basis_relative_difference=relative(Jc,Jnative),
                       b6_direction_relative_difference=relative(spaces[0].derivatives,spaces[1].derivatives),
                       b6_cpu_rank=spaces[0].rank,b6_gpu_rank=spaces[1].rank,
                       cpu_diagnostics=ps[0].diagnostics,gpu_diagnostics=ps[1].diagnostics,
                       solver_end=solver_state(),wall_seconds=time.monotonic()-started)
            np.savez_compressed(OUT/'local'/f'{shape}_k_{k:g}.npz',cpu_prediction=ps[0].prediction,
              gpu_prediction=ps[1].prediction,cpu_jacobian=Jc,gpu_fixed_basis_jacobian=Jg,
              gpu_native_basis_jacobian=Jnative,cpu_b6=spaces[0].derivatives,gpu_b6=spaces[1].derivatives)
            records.append(row)
            finding=max(row[key] for key in ('prediction_relative_difference','b7_fixed_basis_relative_difference',
                                             'b7_native_basis_relative_difference'))>1e-10
            write(OUT/'physics_comparison.json',dict(rows=records,stopped_on_finding=finding,
                  threshold=1e-10,wall_seconds=time.monotonic()-started,bulk_files=bulk_manifest(OUT)))
            print({key:row[key] for key in ('shape','k','prediction_relative_difference','b7_fixed_basis_relative_difference',
                                           'b7_native_basis_relative_difference','b6_direction_relative_difference')},flush=True)
            for ctx in cs:
                if hasattr(ctx,'close'): ctx.close()
            if finding:
                print('STOP: difference exceeds 1e-10; report to coordinator.',flush=True)
                return


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('records','physics'));args=parser.parse_args()
    saved_records() if args.action=='records' else physics_checks()
