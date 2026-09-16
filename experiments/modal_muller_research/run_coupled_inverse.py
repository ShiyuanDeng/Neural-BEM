"""Interacting-component recovery, automatic local mode enrichment, and J actions."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
from time import perf_counter
import numpy as np
import scipy
from experiments.bie002_modal_diagnostic.fixtures import inputs
from .inverse import ShapeChart
from .coupled_inverse import SceneChart,SceneEvaluator,invert_scene,rank_scene_modes
from .run_inverse import save,relative,shape_metrics,boundary


FREQUENCIES=[.5e9,1.25e9]


def fixture():
    acq,_=inputs()
    chart=SceneChart((ShapeChart((2,3),.445+.49j,.032),ShapeChart((2,3),.555+.515j,.028)))
    truth=np.array([.3,-.2,.96,.35,-.2,.1,.15,-.4,.2,1.05,-.25,.25,.15,-.1])
    initial=np.array([-.2,.3,1.03,0,0,0,0,.2,-.3,.96,0,0,0,0])
    return acq,chart,truth,initial


def chart_record(chart):
    return [dict(modes=c.modes,anchor=[c.anchor.real,c.anchor.imag],scale=c.scale) for c in chart.charts]


def metrics(chart,x,truth_chart,truth,acq,observed,clean):
    components=[shape_metrics(c,x[sl],tc,truth[ts])
                for c,sl,tc,ts in zip(chart.charts,chart.slices,truth_chart.charts,truth_chart.slices)]
    y=SceneEvaluator(chart,acq,FREQUENCIES,backend='nodal',nodes=256).forward(x)
    held=dict(acq)
    angle=.073
    rotate=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
    for key in ['source_points','receiver_points']:
        held[key]=((np.array(acq[key])-.5)@rotate.T+.5).tolist()
    hy=SceneEvaluator(chart,held,[.875e9],backend='nodal',nodes=256).forward(x)
    ht=SceneEvaluator(truth_chart,held,[.875e9],backend='nodal',nodes=256).forward(truth)
    return dict(components=components,boundary_rms_mm=float(np.sqrt(np.mean([c['boundary_rms_mm']**2 for c in components]))),
                clean_data_error=relative(y,clean),observed_data_error=relative(y,observed),held_out_error=relative(hy,ht))


def qualify(output):
    acq,chart,x,_=fixture()
    ref=SceneEvaluator(chart,acq,FREQUENCIES,backend='nodal',nodes=256)
    y=ref.forward(x);j=ref.base.operator_jacobian(True)
    rows=[]
    v=np.random.default_rng(34).normal(size=chart.size);v/=np.linalg.norm(v)
    for backend,options in [('nodal',dict(nodes=64)),('native',dict(cutoff=16,bandwidth=24)),
                            ('native',dict(cutoff=24,bandwidth=40)),('native',dict(cutoff=32,bandwidth=56))]:
        e=SceneEvaluator(chart,acq,FREQUENCIES,backend=backend,**options)
        actual=e.forward(x);f=e.sensitivity(x,'traces');jac=f.dense()
        h=1e-4
        fd=(e.forward(x+h*v)-e.forward(x-h*v))/(2*h)
        rows.append(dict(backend=backend,options=options,data_error=relative(actual,y),jacobian_error=relative(jac,j),
                         worst_column_error=float(np.max(np.linalg.norm(jac-j,axis=(0,1))/np.linalg.norm(j,axis=(0,1)))),
                         finite_difference_error=relative(f.matvec(v),fd),work=e.work))
    # Quantify multiple scattering; otherwise a two-object fixture could be trivial.
    independent=sum(SceneEvaluator(SceneChart((c,)),acq,FREQUENCIES,backend='nodal',nodes=128).forward(x[sl])
                    for c,sl in zip(chart.charts,chart.slices))
    record=dict(derivatives=rows,interaction_error_if_independent=relative(independent,y))
    save(output/'qualification.json',record)
    print('qualification',json.dumps(record),flush=True)


def action_benchmark(output):
    acq,chart,x,_=fixture()
    additions=[(i,m) for i in range(2) for m in range(2,21) if m not in chart.charts[i].modes]
    chart,x=chart.expanded(x,additions)
    rows=[]
    rng=np.random.default_rng(49)
    for count in [24,96,192]:
        angles=np.arange(count)*2*np.pi/count
        acq=dict(acq,source_points=np.column_stack((.5+.3*np.cos(angles),.5+.3*np.sin(angles))).tolist(),
                 receiver_points=np.column_stack((.5+.3*np.cos(angles+.2),.5+.3*np.sin(angles+.2))).tolist())
        evaluator=SceneEvaluator(chart,acq,[1.25e9],paired=False)
        evaluator.forward(x)
        tick=perf_counter();actions=evaluator.sensitivity(x,'traces');setup=perf_counter()-tick
        v=rng.normal(size=chart.size);w=rng.normal(size=actions.output_shape)+1j*rng.normal(size=actions.output_shape)
        tick=perf_counter();dense=actions.dense();assembly=perf_counter()-tick
        jv=actions.matvec(v);adj=actions.rmatvec(w)
        exact_adjoint=np.real(np.einsum('fdp,fd->p',dense.conj(),w))
        timings={}
        operations={'trace_jvp':lambda:actions.matvec(v),'trace_vjp':lambda:actions.rmatvec(w),
                    'dense_jvp':lambda:dense@v,
                    # Conjugate the small vector, not a full matrix on each call.
                    'dense_vjp':lambda:np.real(dense.reshape(-1,chart.size).T@w.reshape(-1).conj())}
        for name,operation in operations.items():
            measured=[]
            for _ in range(7):
                tick=perf_counter();operation();measured.append(perf_counter()-tick)
            timings[name]=float(np.median(measured))
        rows.append(dict(acquisition_count=count,measurements=count**2,parameters=chart.size,
            trace_array_bytes=actions.stored_bytes,dense_array_bytes=dense.nbytes,
            trace_setup_seconds=setup,dense_construction_seconds=assembly,
            jvp_error=relative(jv,dense@v),vjp_error=relative(adj,exact_adjoint),timings=timings))
        save(output/'action_benchmark.json',rows)
        print('action benchmark',json.dumps(rows[-1]),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('results/experiments/modal_muller_20260916/coupled_inverse'))
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--cases',nargs='+',default=['clean','noise_1pct','missing_two_modes'])
    parser.add_argument('--skip-benchmark',action='store_true')
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=True)
    qualify(output)
    if not args.skip_benchmark:
        action_benchmark(output)
    summary=[];enrichment=[]
    for case_index,case in enumerate(args.cases):
        acq,chart,truth,initial=fixture();truth_chart=chart
        noise=0. if case=='clean' else .01
        if case=='missing_two_modes':
            truth_chart,truth=chart.expanded(truth,[(0,5),(1,7)])
            truth[truth_chart.slices[0].stop-2:truth_chart.slices[0].stop]=[.5,-.35]
            truth[truth_chart.slices[1].stop-2:truth_chart.slices[1].stop]=[.3,.15]
        clean=SceneEvaluator(truth_chart,acq,FREQUENCIES,backend='nodal',nodes=256).forward(truth)
        fine=SceneEvaluator(truth_chart,acq,FREQUENCIES,backend='nodal',nodes=384).forward(truth)
        oracle_error=relative(clean,fine)
        rng=np.random.default_rng(20260917+case_index)
        perturbation=rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
        perturbation*=noise*np.linalg.norm(clean,axis=1)[:,None]/np.linalg.norm(perturbation,axis=1)[:,None]
        observed=clean+perturbation
        save(output/(case+'_inputs.json'),dict(acquisition=acq,frequencies=FREQUENCIES,chart=chart_record(chart),
            truth_chart=chart_record(truth_chart),truth=truth.tolist(),initial=initial.tolist(),noise_fraction=noise,
            noise_seed=20260917+case_index,observed_real=observed.real.tolist(),observed_imag=observed.imag.tolist(),
            clean_real=clean.real.tolist(),clean_imag=clean.imag.tolist(),oracle_256_384_error=oracle_error))
        base=None
        for repeat in range(args.repeats):
            arms=['native_dense','nodal_dense'] if repeat%2==0 else ['nodal_dense','native_dense']
            if repeat==0:
                arms.append('native_linear_operator')
            for arm in arms:
                backend='nodal' if arm=='nodal_dense' else 'native'
                storage='linear_operator' if arm.endswith('linear_operator') else 'dense'
                result=invert_scene(chart,acq,FREQUENCIES,observed,initial,backend=backend,
                    jacobian_storage=storage,regularization=0 if noise==0 else .001)
                x=np.array(result['parameters'])
                result['metrics']=metrics(chart,x,truth_chart,truth,acq,observed,clean)
                save(output/f'{case}_{arm}_{repeat}.json',result)
                row=dict(case=case,arm=arm,repeat=repeat,seconds=result['seconds'],
                         success=all(s['success'] for s in result['stages']),
                         forward_evaluations=sum(s['work']['forward_evaluations'] for s in result['stages']),
                         **result['metrics'])
                summary.append(row);save(output/'summary.json',summary)
                print('inverse',json.dumps(row),flush=True)
                if arm=='native_dense' and repeat==0:
                    base=result
        if noise==0:
            continue
        x=np.array(base['parameters']);current=chart;rounds=[];tick=perf_counter()
        for round_index in range(3):
            selection=rank_scene_modes(current,x,acq,FREQUENCIES,observed,noise_fraction=noise,cutoff=32,bandwidth=56)
            print('selection',case,json.dumps(selection),flush=True)
            round_record=dict(selection=selection)
            rounds.append(round_record)
            if selection['selected'] is None:
                break
            current,x=current.expanded(x,[selection['selected']])
            result=invert_scene(current,acq,FREQUENCIES,observed,x,continuation=False,cutoff=32,bandwidth=56)
            round_record['result']=result;x=np.array(result['parameters'])
        extra=perf_counter()-tick
        after=metrics(current,x,truth_chart,truth,acq,observed,clean)
        record=dict(case=case,rounds=rounds,extra_seconds=extra,final_chart=chart_record(current),
                    final_parameters=x.tolist(),before=base['metrics'],after=after)
        save(output/(case+'_enrichment.json'),record)
        enrichment.append(record);save(output/'enrichment_summary.json',enrichment)
        print('enrichment',case,json.dumps(dict(extra_seconds=extra,before=base['metrics'],after=after)),flush=True)
    save(output/'manifest.json',dict(arguments=vars(args)|{'output':str(output)},
        python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
        thread_environment={k:os.environ.get(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('experiments/modal_muller_research').glob('*.py')},
        timing_scope='Whole inverses include trial forwards, geometry rebuilds and Jacobian actions; independent data generation and validation excluded.'))


if __name__=='__main__':
    main()
