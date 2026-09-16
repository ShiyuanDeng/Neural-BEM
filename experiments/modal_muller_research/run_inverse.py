"""Shape-recovery exploration with independent data, noise, and full-work timing.

Example: OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONPATH=solvers:. python -m experiments.modal_muller_research.run_inverse
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import scipy
from scipy.spatial import cKDTree

from experiments.bie002_modal_diagnostic.fixtures import inputs
from .inverse import ShapeChart,ShapeEvaluator,invert


FREQUENCIES=[.5e9,1.25e9]
TRUTH=np.array([1.2,-.8,.9,.4,-.2,.2,.1,1.1,1.3])
INITIAL=np.array([-.5,.5,1.02,0.,0.,0.,0.,0.,0.])


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def relative(a,b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b),1e-300))


def boundary(chart,x,count=2048):
    theta=np.arange(count)*(2*np.pi/count)
    z=sum(v*np.exp(1j*j*theta) for j,v in chart.physical_coefficients(x).items())
    return np.column_stack((z.real,z.imag))


def shape_metrics(chart,x,truth_chart,truth):
    a,b=boundary(chart,x),boundary(truth_chart,truth)
    return dict(boundary_rms_mm=1000*float(np.sqrt(np.mean(np.sum((a-b)**2,axis=1)))),
                boundary_hausdorff_mm=1000*float(max(cKDTree(a).query(b)[0].max(),cKDTree(b).query(a)[0].max())),
                center_error_mm=10*float(np.linalg.norm(np.asarray(x)[:2]-np.asarray(truth)[:2])))


def run_arm(arm,chart,acq,observed,initial,noise,verbose):
    tick=perf_counter()
    regularization=0. if noise==0 else .001
    if arm=='nodal64':
        result=invert(chart,acq,FREQUENCIES,observed,initial,backend='nodal',nodes=64,
                      regularization=regularization,verbose=verbose)
    elif arm=='native_fine':
        result=invert(chart,acq,FREQUENCIES,observed,initial,cutoff=32,bandwidth=64,
                      regularization=regularization,verbose=verbose)
    elif arm=='native_hadamard':
        result=invert(chart,acq,FREQUENCIES,observed,initial,cutoff=24,bandwidth=40,
                      jacobian_kind='hadamard',regularization=regularization,verbose=verbose)
    elif arm=='nodal_hadamard':
        result=invert(chart,acq,FREQUENCIES,observed,initial,backend='nodal',nodes=64,
                      jacobian_kind='hadamard',regularization=regularization,verbose=verbose)
    elif arm=='native_coarse_to_fine':
        result=invert(chart,acq,FREQUENCIES,observed,initial,cutoff=16,bandwidth=24,
                      terms=20,angular_order=20,regularization=regularization,verbose=verbose)
        # A fresh, more resolved solve checks the data error of the coarse optimum.
        check=ShapeEvaluator(chart,acq,FREQUENCIES,cutoff=32,bandwidth=64)
        coarse=ShapeEvaluator(chart,acq,FREQUENCIES,cutoff=16,bandwidth=24,terms=20,angular_order=20)
        x=np.array(result['parameters'])
        fine_y,coarse_y=check.forward(x),coarse.forward(x)
        discrepancy=relative(coarse_y,fine_y)
        threshold=max(1e-9,.02*noise)
        result['resolution_check']=dict(data_discrepancy=discrepancy,threshold=threshold,
                                        work=check.work,coarse_check_work=coarse.work)
        if discrepancy>threshold:
            polish=invert(chart,acq,FREQUENCIES,observed,x,cutoff=32,bandwidth=64,
                          regularization=regularization,continuation=False,verbose=verbose)
            offset=perf_counter()-tick-polish['seconds']
            for row in polish['history']:
                row['stage']+=len(result['stages']);row['elapsed_seconds']+=offset
            result['parameters']=polish['parameters']
            result['stages'].extend(polish['stages'])
            result['history'].extend(polish['history'])
            result['resolution_check']['polished']=True
        else:
            result['resolution_check']['polished']=False
    else:
        raise ValueError(arm)
    result['seconds']=perf_counter()-tick
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=Path('results/experiments/modal_muller_20260916/inverse_suite'))
    parser.add_argument('--cases',nargs='+',default=['clean','noise_1pct','unmodeled_mode7'])
    parser.add_argument('--arms',nargs='+',default=['native_fine','nodal64','native_coarse_to_fine'])
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--verbose',action='store_true')
    args=parser.parse_args()
    output=args.output;output.mkdir(parents=True,exist_ok=True)
    acq,_=inputs()
    chart=ShapeChart()
    summary=[]
    suite_started=perf_counter()
    for case_index,case in enumerate(args.cases):
        if case=='clean':
            noise=0.;truth_chart=chart;truth=TRUTH
        elif case=='noise_1pct':
            noise=.01;truth_chart=chart;truth=TRUTH
        elif case=='unmodeled_mode7':
            noise=.01;truth_chart=ShapeChart(modes=(2,3,5,7));truth=np.r_[TRUTH,.16,-.10]
        else:
            raise ValueError(case)
        clean=ShapeEvaluator(truth_chart,acq,FREQUENCIES,backend='nodal',nodes=256).forward(truth)
        fine=ShapeEvaluator(truth_chart,acq,FREQUENCIES,backend='nodal',nodes=512).forward(truth)
        oracle_error=relative(clean,fine)
        rng=np.random.default_rng(20260916+case_index)
        perturbation=rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
        perturbation*=noise*np.linalg.norm(clean,axis=1)[:,None]/np.linalg.norm(perturbation,axis=1)[:,None]
        observed=clean+perturbation
        # Held-out source/receiver angles and a frequency not used by inversion.
        held_acq=dict(acq)
        angle=.073
        rotate=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]])
        for key in ['source_points','receiver_points']:
            held_acq[key]=((np.array(acq[key])-.5)@rotate.T+.5).tolist()
        held_truth=ShapeEvaluator(truth_chart,held_acq,[.875e9],backend='nodal',nodes=256).forward(truth)
        save(output/(case+'_inputs.json'),dict(acquisition=acq,frequencies=FREQUENCIES,
            truth=truth.tolist(),truth_modes=truth_chart.modes,fit_modes=chart.modes,
            initial=INITIAL.tolist(),noise_fraction=noise,noise_seed=20260916+case_index,
            observed_real=observed.real.tolist(),observed_imag=observed.imag.tolist(),
            clean_real=clean.real.tolist(),clean_imag=clean.imag.tolist(),oracle_256_512_error=oracle_error))
        for repeat in range(args.repeats):
            arms=args.arms if repeat%2==0 else list(reversed(args.arms))
            for arm in arms:
                result=run_arm(arm,chart,acq,observed,INITIAL,noise,args.verbose)
                x=np.array(result['parameters'])
                # Validation cost is recorded separately from recovery cost.
                tick=perf_counter()
                y=ShapeEvaluator(chart,acq,FREQUENCIES,backend='nodal',nodes=256).forward(x)
                held=ShapeEvaluator(chart,held_acq,[.875e9],backend='nodal',nodes=256).forward(x)
                metrics=dict(**shape_metrics(chart,x,truth_chart,truth),
                    clean_data_error=relative(y,clean),observed_data_error=relative(y,observed),
                    held_out_data_error=relative(held,held_truth),
                    validation_seconds=perf_counter()-tick,oracle_256_512_error=oracle_error)
                name=f'{case}_{arm}_{repeat}'
                result.update(case=case,arm=arm,repeat=repeat,metrics=metrics,
                              truth=truth.tolist(),truth_modes=truth_chart.modes,initial=INITIAL.tolist())
                save(output/(name+'.json'),result)
                row=dict(case=case,arm=arm,repeat=repeat,seconds=result['seconds'],
                    forward_evaluations=sum(s['work']['forward_evaluations'] for s in result['stages']),
                    jacobian_evaluations=sum(s['work']['jacobian_evaluations'] for s in result['stages']),
                    optimizer_success=all(s['success'] for s in result['stages']),
                    resolution_polished=result.get('resolution_check',{}).get('polished'),**metrics)
                summary.append(row);save(output/'summary.json',summary)
                print(json.dumps(row),flush=True)
    save(output/'manifest.json',dict(seconds=perf_counter()-suite_started,
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
        thread_environment={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path('experiments/modal_muller_research').glob('*.py')},
        arguments=vars(args)|{'output':str(output)},
        timing_scope='Every inverse forward/Jacobian, trial step, geometry rebuild, fixed-acquisition setup, '
                     'and coarse-to-fine check; independent data generation and final validation excluded.'))
    plot(output,args.cases,args.arms)


def plot(output,cases,arms):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/modal_muller_matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    chart=ShapeChart()
    colors={'native_fine':'#3264bd','nodal64':'#dc7832','native_coarse_to_fine':'#259265',
            'native_hadamard':'#8257b5','nodal_hadamard':'#b93d62'}
    labels={'native_fine':'Native fine','nodal64':'Nodal analytic','native_coarse_to_fine':'Native coarse-to-fine',
            'native_hadamard':'Native Hadamard','nodal_hadamard':'Nodal Hadamard'}
    fig,axes=plt.subplots(2,len(cases),figsize=(4.4*len(cases),7.6),squeeze=False,layout='constrained')
    for col,case in enumerate(cases):
        raw=json.loads((output/(case+'_inputs.json')).read_text())
        truth=boundary(ShapeChart(modes=tuple(raw['truth_modes'])),raw['truth'])
        initial=boundary(chart,INITIAL)
        axes[0,col].plot(initial[:,0],initial[:,1],':',color='.5',label='Initial')
        axes[0,col].plot(truth[:,0],truth[:,1],color='black',linewidth=2.6,label='Truth')
        for arm in arms:
            path=output/f'{case}_{arm}_0.json'
            if not path.exists(): continue
            r=json.loads(path.read_text())
            xy=boundary(chart,r['parameters'])
            axes[0,col].plot(xy[:,0],xy[:,1],color=colors[arm],linestyle='--',linewidth=1.3,label=labels[arm])
            rows=r['history']
            axes[1,col].semilogy([h['elapsed_seconds'] for h in rows],
                                 [max(h['residual_norm'],1e-15) for h in rows],'-o',
                                 color=colors[arm],label=labels[arm],markersize=3)
        axes[0,col].set(title=case.replace('_',' '),xlabel='x (m)',ylabel='y (m)',aspect='equal')
        axes[0,col].legend(fontsize=7)
        axes[1,col].set(xlabel='Elapsed inverse time (s)',ylabel='Objective residual norm')
        axes[1,col].legend(fontsize=7)
    fig.savefig(output/'recoveries.png',dpi=180)
    fig.savefig(output/'recoveries.pdf')


if __name__=='__main__':
    main()
