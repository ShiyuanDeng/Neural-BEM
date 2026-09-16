"""Known two-circle family; infer six geometric parameters and material labels."""
from __future__ import annotations
import argparse
import itertools
import json
from pathlib import Path
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares

from .mixed_circles import predict


def write(path, data):
    path.write_text(json.dumps(data,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x))+'\n')


def fit(initial,kinds,sources,receivers,frequencies,observed,max_nfev=120):
    scales=np.linalg.norm(observed,axis=0)*np.sqrt(len(frequencies))
    cache={};history=[]
    def compute(q):
        key=q.tobytes()
        if key not in cache:
            prediction,jac=predict(q,kinds,sources,receivers,frequencies,jacobian=True)
            residual=(prediction-observed)/scales
            derivative=jac/scales[None,:,None]
            cache.clear()
            cache[key]=(np.r_[residual.real.ravel(),residual.imag.ravel()],
                        np.concatenate((derivative.real.reshape(-1,6),derivative.imag.reshape(-1,6))))
            history.append(dict(parameters=q.copy(),loss=.5*np.linalg.norm(residual)**2))
        return cache[key]
    # Separate search boxes guarantee disjoint circles throughout local fitting.
    # Count, circle family, sand/plastic properties and these boxes are known.
    lower=[.33,.38,.008,.56,.38,.008]
    upper=[.48,.63,.038,.71,.63,.038]
    result=least_squares(lambda q:compute(q)[0],np.asarray(initial).ravel(),
        jac=lambda q:compute(q)[1],bounds=(lower,upper),x_scale=[.05,.05,.02]*2,
        ftol=1e-12,xtol=1e-12,gtol=1e-10,max_nfev=max_nfev)
    return dict(kinds=kinds,parameters=result.x.reshape(2,3),loss=result.cost,
        optimality=result.optimality,nfev=result.nfev,njev=result.njev,
        success=result.success,status=result.status,message=result.message,history=history)


def main(args):
    output=args.output;output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    truth=np.array([[.43,.48,.030],[.58,.53,.022]])
    kinds=('plastic','metal')
    angle=np.arange(24)*2*np.pi/24
    sources=.5+.3*np.column_stack((np.cos(angle),np.sin(angle)))
    receivers=.5+.3*np.column_stack((np.cos(angle+.12),np.sin(angle+.12)))
    frequencies=np.array([.5,.75,1.,1.25])*1e9
    holdout=np.array([1.5,2.5])*1e9
    if args.observations_bem:
        from .mixed_bem import predict as bem
        observed=bem(truth,sources,receivers,frequencies,nodes=128)
        expected=bem(truth,sources,receivers,holdout,nodes=128)
        refinement=bem(truth,sources,receivers,np.r_[frequencies,holdout],nodes=256)
        coarse=np.c_[observed,expected]
        discrepancy=np.linalg.norm(coarse-refinement,axis=0)/np.linalg.norm(refinement,axis=0)
        if max(discrepancy)>1e-8:raise RuntimeError('BEM observation refinement failed')
        write(output/'oracle_check.json',dict(nodes=[128,256],relative_discrepancy=discrepancy))
    else:
        observed=predict(truth,kinds,sources,receivers,frequencies,order=20)
        expected=predict(truth,kinds,sources,receivers,holdout,order=20)
    rng=np.random.default_rng(16092026)
    starts=[np.array([[.41,.50,.025],[.60,.50,.028]])]
    for _ in range(args.starts-1):
        starts.append(np.array([[rng.uniform(.38,.47),rng.uniform(.43,.58),rng.uniform(.015,.035)],
                                [rng.uniform(.565,.65),rng.uniform(.43,.58),rng.uniform(.015,.035)]]))
    rows=[]
    for noise in args.noise:
        perturbation=rng.normal(size=observed.shape)+1j*rng.normal(size=observed.shape)
        perturbation*=noise*np.linalg.norm(observed,axis=0)/np.linalg.norm(perturbation,axis=0)
        data=observed+perturbation
        np.savez(output/f'observations_noise_{noise:g}.npz',sources=sources,receivers=receivers,
                 frequencies=frequencies,observed=data,truth=truth,holdout=holdout,expected=expected)
        for assignment in itertools.product(('plastic','metal'),repeat=2):
            trials=[]
            for index,initial in enumerate(starts):
                trial=fit(initial,assignment,sources,receivers,frequencies,data,args.max_nfev)
                trial['start_index']=index
                trial['initial']=initial
                trials.append(trial)
                print(f'noise={noise:g} labels={assignment} start={index} loss={trial["loss"]:.6g} evaluations={trial["nfev"]}',flush=True)
            best=min(trials,key=lambda x:x['loss'])
            predicted=predict(best['parameters'],assignment,sources,receivers,holdout,order=20)
            row=dict(noise=noise,kinds=assignment,best=best,trials=trials,
                center_errors_mm=1000*np.linalg.norm(best['parameters'][:,:2]-truth[:,:2],axis=1),
                radius_errors_mm=1000*np.abs(best['parameters'][:,2]-truth[:,2]),
                holdout_relative_errors=np.linalg.norm(predicted-expected,axis=0)/np.linalg.norm(expected,axis=0))
            rows.append(row)
            write(output/'results.json',dict(rows=rows,truth=truth,truth_kinds=kinds,
                assumptions='Known count=2, circular shapes, disjoint search boxes, sand epsr=6, plastic epsr=3; metal is PEC TMz.',
                data_solver='mixed Muller/PEC BEM, 128 nodes checked at 256' if args.observations_bem else 'cylindrical harmonics order 20',
                inverse_solver='coupled cylindrical harmonics order 12, analytic geometry Jacobian',
                training_hz=frequencies,holdout_hz=holdout,seconds=time.monotonic()-started))
    fig,axes=plt.subplots(1,len(args.noise),figsize=(5*len(args.noise),4.5),squeeze=False)
    theta=np.linspace(0,2*np.pi,401)
    for ax,noise in zip(axes[0],args.noise):
        best=min((r for r in rows if r['noise']==noise),key=lambda r:r['best']['loss'])
        for i,color in enumerate(('#2b78b8','#535353')):
            for q,style,label in ((truth[i],'-',f'Truth {kinds[i]}'),
                    (best['best']['parameters'][i],'--',f'Fit {best["kinds"][i]}')):
                ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),style,color=color,label=label,lw=2)
        ax.set(xlim=(.36,.66),ylim=(.40,.61),aspect='equal',xlabel='x (m)',ylabel='y (m)',
            title=f'{100*noise:g}% complex noise\nlabels: {", ".join(best["kinds"])}')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
    fig.suptitle('Plastic + ideal metal circles in sand — six geometry parameters and labels inferred')
    fig.tight_layout();fig.savefig(output/'reconstruction.png',dpi=180)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--starts',type=int,default=3)
    parser.add_argument('--noise',type=float,nargs='+',default=[0.,.01])
    parser.add_argument('--max-nfev',type=int,default=120)
    parser.add_argument('--observations-bem',action='store_true')
    main(parser.parse_args())
