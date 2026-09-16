"""Qualification and matched inverses with shape-dependent scattering matrices."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
from time import perf_counter
import numpy as np
from .deformable_scattering import DeformableEvaluator,LinearizedEvaluator,compile_shape_jet,operator_shape_jet
from .deformation_inverse import shape_fixture,NodalDeformableEvaluator,invert_relinearized
from .pose_inverse import invert_pose
from .run_scattering_library import FREQUENCIES,metrics,chart_record
from .run_inverse import save,relative


ROOT=Path('results/experiments/modal_muller_20260916/deformable_scattering')


def qualification(output):
    acq,chart,truth,initial=shape_fixture(4)
    references=[]
    for x in [initial,truth]:
        oracle=NodalDeformableEvaluator(chart,acq,FREQUENCIES,nodes=256)
        references.append((oracle.forward(x),oracle.jacobian(x)))
    rows=[]
    configs=[('native',dict(order=12,cutoff=m,bandwidth=2*m)) for m in [12,16,20,24,32]]
    configs.extend(('nodal_rebuild',dict(nodes=n)) for n in [24,32,48,64])
    configs.extend(('nodal',dict(order=12,nodes=n)) for n in [32,48,64])
    for backend,options in configs:
        measured=[];errors=[]
        for x,(y,j) in zip([initial,truth],references):
            tick=perf_counter()
            e=(NodalDeformableEvaluator(chart,acq,FREQUENCIES,**options) if backend=='nodal_rebuild' else
               DeformableEvaluator(chart,acq,FREQUENCIES,backend=backend,**options))
            v,d=e.forward(x),e.jacobian(x);measured.append(perf_counter()-tick)
            errors.append(dict(data_error=relative(v,y),jacobian_error=relative(d,j),
                worst_column=float(np.max(np.linalg.norm(d-j,axis=(0,1))/np.linalg.norm(j,axis=(0,1))))))
        qualified=all(r['data_error']<1e-9 and r['jacobian_error']<1e-8 and r['worst_column']<1e-7 for r in errors)
        row=dict(backend=backend,options=options,errors=errors,forward_and_jacobian_seconds=measured,qualified=qualified)
        rows.append(row);print('resolution',json.dumps(row),flush=True)
    native=next(r['options'] for r in rows if r['backend']=='native' and r['qualified'])
    compiled_nodes={r['options']['nodes'] for r in rows if r['backend']=='nodal' and r['qualified']}
    nodes=next(r['options']['nodes'] for r in rows if r['backend']=='nodal_rebuild' and r['qualified']
               and r['options']['nodes'] in compiled_nodes)
    save(output/'qualification.json',dict(rows=rows,selected_native=native,selected_nodes=nodes,
         criteria=dict(data_error=1e-9,jacobian_error=1e-8,worst_column=1e-7)))
    return native,nodes


def frozen_range(output,native):
    acq,chart,truth,initial=shape_fixture(4)
    exact=DeformableEvaluator(chart,acq,FREQUENCIES,**native)
    model=LinearizedEvaluator(exact,initial);rows=[]
    # Keep the full truth pose in every check; vary only actual deformation.
    for scale in [.125,.25,.5,1.,1.5]:
        x=truth.copy()
        for sl in chart.slices: x[sl][3:]*=scale
        actual=exact.forward(x);approx=model.forward(x)
        rows.append(dict(deformation_scale=scale,data_error=relative(approx,actual),
                         jacobian_error=relative(model.jacobian(x),exact.jacobian(x))))
    save(output/'frozen_range.json',rows)
    print('frozen range',json.dumps(rows),flush=True)


def mode_fingerprints(output):
    from .coefficient_operator import LaurentGeometry
    g=LaurentGeometry.circle(radius=.03)
    modes=[2,3,5]
    directions=[{1+k:.0005/g.scale,1-k:.0005/g.scale} for k in modes]
    t,j,_=compile_shape_jet(g,directions,64.,45.25,.04,order=12)
    difference=t.modes[None,:]-t.modes[:,None]
    rows=[]
    for harmonic,derivative in zip(modes,j):
        forbidden=np.abs(difference)!=harmonic
        rows.append(dict(radial_harmonic=harmonic,modes=t.modes.tolist(),
            forbidden_fraction=float(np.linalg.norm(derivative[forbidden])/np.linalg.norm(derivative)),
            absolute_derivative=np.abs(derivative).tolist()))
    save(output/'mode_fingerprints.json',rows)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--qualification-only',action='store_true')
    args=parser.parse_args();ROOT.mkdir(parents=True,exist_ok=True)
    native,nodes=qualification(ROOT)
    if args.qualification_only: return
    frozen_range(ROOT,native);mode_fingerprints(ROOT);summary=[]
    for case_index,case in enumerate(['pair_clean','four_clean','four_noise1pct']):
        acq,chart,truth,initial=shape_fixture(2 if case.startswith('pair') else 4)
        clean=NodalDeformableEvaluator(chart,acq,FREQUENCIES,nodes=256).forward(truth)
        fine=NodalDeformableEvaluator(chart,acq,FREQUENCIES,nodes=384).forward(truth)
        noise=.01 if case.endswith('noise1pct') else 0.
        rng=np.random.default_rng(20261117+case_index)
        perturbation=rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
        perturbation*=noise*np.linalg.norm(clean,axis=1)[:,None]/np.linalg.norm(perturbation,axis=1)[:,None]
        observed=clean+perturbation
        record=chart_record(chart)
        record['directions']=[[[[j,complex(v).real,complex(v).imag] for j,v in d.items()] for d in row] for row in chart.directions]
        save(ROOT/(case+'_inputs.json'),dict(acquisition=acq,chart=record,truth=truth.tolist(),initial=initial.tolist(),
             frequencies=FREQUENCIES,noise_fraction=noise,noise_seed=20261117+case_index,
             oracle_256_384_error=relative(clean,fine),clean_real=clean.real.tolist(),clean_imag=clean.imag.tolist(),
             observed_real=observed.real.tolist(),observed_imag=observed.imag.tolist()))
        arms=['nodal_rebuild64','nodal_rebuild_qualified','native_exact','nodal_exact','native_relinearized','nodal_relinearized']
        for repeat in range(args.repeats):
            for arm in arms if repeat%2==0 else list(reversed(arms)):
                tick=perf_counter()
                if arm.endswith('relinearized'):
                    backend=arm.split('_')[0]
                    options=native if backend=='native' else dict(order=12,nodes=nodes)
                    result=invert_relinearized(chart,acq,FREQUENCIES,observed,initial,backend=backend,**options)
                else:
                    if arm.startswith('nodal_rebuild'):
                        evaluator=NodalDeformableEvaluator(chart,acq,FREQUENCIES,nodes=64 if arm.endswith('64') else nodes)
                    else:
                        backend=arm.split('_')[0]
                        evaluator=DeformableEvaluator(chart,acq,FREQUENCIES,backend=backend,
                            **(native if backend=='native' else dict(order=12,nodes=nodes)))
                    result=invert_pose(chart,acq,FREQUENCIES,observed,initial,evaluator=evaluator)
                result['seconds']=perf_counter()-tick
                result.update(case=case,arm=arm,repeat=repeat)
                result['metrics']=metrics(chart,np.array(result['parameters']),truth,acq,observed,clean)
                # Compare all recovered coordinates with the exact nodal control.
                result['parameter_error']=float(np.linalg.norm(np.array(result['parameters'])-truth))
                save(ROOT/f'{case}_{arm}_{repeat}.json',result)
                row={k:result[k] for k in ['case','arm','repeat','seconds','success','residual_norm','work','parameter_error']}
                row.update(result['metrics']);row['forward_evaluations']=result['work']['forward_evaluations']
                if 'outer_trials' in result: row['outer_trials']=result['outer_trials']
                summary.append(row);save(ROOT/'summary.json',summary)
                print('inverse',json.dumps(row),flush=True)
        # A single unrefreshed model is a deliberately approximate control.
        tick=perf_counter();exact=DeformableEvaluator(chart,acq,FREQUENCIES,**native)
        model=LinearizedEvaluator(exact,initial)
        frozen=invert_pose(chart,acq,FREQUENCIES,observed,initial,evaluator=model)
        frozen['seconds_including_compilation']=perf_counter()-tick
        frozen['metrics']=metrics(chart,np.array(frozen['parameters']),truth,acq,observed,clean)
        save(ROOT/(case+'_frozen_control.json'),frozen)
    paths=list(Path('experiments/modal_muller_research').glob('*.py'))+list(Path('solvers/gpr_bem_kress').glob('*.py'))
    save(ROOT/'manifest.json',dict(python=platform.python_version(),arguments=vars(args),
         selected_native=native,selected_nodes=nodes,source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
         threads={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
         scope='Cold complete inverses including local compilations, derivatives, surrogate inner fits, '
               'and exact candidate checks. Observations, independent validation, and resolution qualification excluded.'))


if __name__=='__main__': main()
