"""Empty-start circular material search using a finite-insertion dictionary.

The search sees data and a plastic/PEC material library, not truth, target count,
or per-object search boxes. Dictionary screening neglects mutual scattering;
each shortlisted insertion is then jointly optimized with the coupled model.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import hankel1
from .mixed_circles import coefficients,predict,polar,wave
from .mixed_bem import predict as bem


def write(path,value):
    path.write_text(json.dumps(value,indent=2,default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x))+'\n')


def feasible(q):
    q=np.asarray(q).reshape(-1,3)
    if np.any(q[:,:2]<.3) or np.any(q[:,:2]>.7) or np.any(q[:,2]<.007) or np.any(q[:,2]>.05):return False
    return all(np.linalg.norm(a[:2]-b[:2])>a[2]+b[2]+.005 for i,a in enumerate(q) for b in q[:i])


def fit(q,kinds,sources,receivers,frequencies,observed,iterations=70):
    q=np.array(q,float).reshape(-1,3);n=q.size
    scales=np.linalg.norm(observed,axis=0)*np.sqrt(len(frequencies))
    def residual(q):
        prediction=predict(q,kinds,sources,receivers,frequencies)
        r=(prediction-observed)/scales
        return np.r_[r.real.ravel(),r.imag.ravel()]
    residual0=residual(q);loss=.5*residual0@residual0
    damping=1e-3;history=[];evaluations=1
    for iteration in range(iterations):
        _,jac=predict(q,kinds,sources,receivers,frequencies,jacobian=True)
        derivative=jac/scales[None,:,None]
        matrix=np.concatenate((derivative.real.reshape(-1,n),derivative.imag.reshape(-1,n)))*.02
        gradient=matrix.T@residual0;hessian=matrix.T@matrix
        history.append(dict(iteration=iteration,loss=loss,gradient=float(abs(gradient).max()),parameters=q.copy()))
        if abs(gradient).max()<1e-10 or loss<1e-18:break
        accepted=False
        for _ in range(7):
            step=-.02*np.linalg.solve(hessian+damping*np.diag(np.maximum(np.diag(hessian),1e-8)),gradient)
            clip=np.tile([.015,.015,.01],len(q))
            step/=max(1.,np.max(np.abs(step)/clip))
            for backtrack in range(12):
                trial=q+step.reshape(-1,3)*.5**backtrack
                if not feasible(trial):continue
                trial_residual=residual(trial);evaluations+=1
                trial_loss=.5*trial_residual@trial_residual
                if trial_loss<loss-1e-15:
                    q,residual0,loss=trial,trial_residual,trial_loss
                    damping=max(1e-9,damping*.3);accepted=True;break
            if accepted:break
            damping*=10
        if not accepted:break
    return dict(parameters=q,kinds=list(kinds),loss=float(loss),relative_error=float(np.sqrt(2*loss)),
                iterations=iteration+1,evaluations=evaluations,history=history)


def dictionary(sources,receivers,frequencies):
    axis=np.linspace(.32,.68,31)
    x,y=np.meshgrid(axis,axis)
    centers=np.c_[x.ravel(),y.ravel()]
    centers=centers[np.linalg.norm(centers-.5,axis=1)<.195]
    radii=[.012,.020,.028,.036]
    modes=np.arange(-10,11)
    descriptions=[];responses=[]
    for kind in ('plastic','metal'):
        for radius in radii:
            fields=[]
            for frequency in frequencies:
                ke=wave(frequency,6);ki=None if kind=='metal' else wave(frequency,3)
                scale,_,scaled_ratio,_=coefficients(modes,ke,radius,ki)
                rs,ts,*_=polar(sources[None,:,:]-centers[:,None,:])
                rr,tr,*_=polar(receivers[None,:,:]-centers[:,None,:])
                basis=.25j*hankel1(modes,ke*rs[:,:,None])*hankel1(modes,ke*rr[:,:,None])
                basis*=np.exp(1j*modes*(tr-ts)[:,:,None])
                fields.append(np.einsum('cpn,n->cp',basis,scaled_ratio/scale))
            responses.append(np.stack(fields,axis=-1))
            descriptions.extend(dict(center=center,radius=radius,kind=kind) for center in centers)
    return descriptions,np.concatenate(responses,axis=0)


def search(sources,receivers,frequencies,observed,target_relative,output):
    descriptions,atoms=dictionary(sources,receivers,frequencies)
    scales=np.linalg.norm(observed,axis=0)*np.sqrt(len(frequencies))
    current=np.empty((0,3));kinds=[];prediction=np.zeros_like(observed);events=[]
    loss=.5
    for event in range(4):
        approximate=(prediction[None]+atoms-observed[None])/scales
        scores=.5*np.sum(abs(approximate)**2,axis=(1,2))
        shortlist=[]
        for index in np.argsort(scores):
            candidate=descriptions[index]
            seed=np.r_[candidate['center'],candidate['radius']]
            if not feasible(np.vstack((current,seed))):continue
            if any(candidate['kind']==descriptions[j]['kind'] and
                   np.linalg.norm(candidate['center']-descriptions[j]['center'])<.018 for j in shortlist):continue
            shortlist.append(int(index))
            if len(shortlist)==8:break
        trials=[]
        for index in shortlist:
            candidate=descriptions[index];seed=np.r_[candidate['center'],candidate['radius']]
            result=fit(np.vstack((current,seed)),kinds+[candidate['kind']],sources,receivers,frequencies,observed)
            result['seed']=candidate;result['screen_loss']=float(scores[index]);trials.append(result)
            print('event',event,'candidate',candidate['kind'],candidate['center'].tolist(),
                  'fit loss',result['loss'],flush=True)
        if not trials:break
        best=min(trials,key=lambda x:x['loss'])
        if loss-best['loss']<=max(1e-8,.01*loss):break
        current=np.array(best['parameters']);kinds=best['kinds'];loss=best['loss']
        prediction=predict(current,kinds,sources,receivers,frequencies)
        events.append(dict(event=event,selected=best,trials=trials))
        record=dict(parameters=current,kinds=kinds,loss=loss,relative_error=np.sqrt(2*loss),
                    events=events,target_relative_error=target_relative,
                    supplied_target_count=False,supplied_material_assignment=False,
                    assumptions='Circular family; known sand/plastic properties; metal PEC; bounded common search region.')
        write(output/'search.json',record)
        if np.sqrt(2*loss)<=target_relative:break
    return record


def main(args):
    output=args.output;output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    scenes={
        'two':([[.43,.48,.030],[.58,.53,.022]],['plastic','metal']),
        'one-metal':([[.5,.51,.026]],['metal']),
        'three':([[.43,.48,.030],[.58,.53,.022],[.46,.62,.018]],['plastic','metal','plastic']),
        'swapped':([[.43,.48,.030],[.58,.53,.022]],['metal','plastic']),
    }
    positions,truth_kinds=scenes[args.scene];truth=np.array(positions)
    angle=np.arange(24)*2*np.pi/24
    sources=.5+.3*np.column_stack((np.cos(angle),np.sin(angle)))
    receivers=.5+.3*np.column_stack((np.cos(angle+.12),np.sin(angle+.12)))
    if args.project_acquisition:
        import run_radial_fourier_topology_inverse as baseline
        sources,receivers=baseline._ring_scan()
    frequencies=np.array([.5,.75,1.,1.25])*1e9;holdout=np.array([1.5,2.5])*1e9
    clean=bem(truth,sources,receivers,frequencies,nodes=128,kinds=truth_kinds)
    rng=np.random.default_rng(args.seed)
    noise=rng.normal(size=clean.shape)+1j*rng.normal(size=clean.shape)
    noise*=args.noise*np.linalg.norm(clean,axis=0)/np.linalg.norm(noise,axis=0)
    observed=clean+noise
    np.savez(output/'observations.npz',observed=observed,sources=sources,receivers=receivers,
             frequencies=frequencies,noise_level=args.noise,truth=truth)
    result=search(sources,receivers,frequencies,observed,max(1e-6,1.2*args.noise),output)
    estimated=np.array(result['parameters'])
    expected=bem(truth,sources,receivers,holdout,nodes=128,kinds=truth_kinds)
    predicted=predict(estimated,result['kinds'],sources,receivers,holdout,order=20)
    result.update(seconds=time.monotonic()-started,truth=truth,truth_kinds=truth_kinds,
        noise=args.noise,seed=args.seed,scene=args.scene,project_acquisition=args.project_acquisition,
        holdout_relative_errors=np.linalg.norm(predicted-expected,axis=0)/np.linalg.norm(expected,axis=0))
    write(output/'result.json',result)
    fig,ax=plt.subplots(figsize=(6,5));theta=np.linspace(0,2*np.pi,401)
    for q,kind in zip(truth,truth_kinds):
        color='#2b78b8' if kind=='plastic' else '#555555'
        ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),color=color,lw=3,label=f'True {kind}')
    for q,kind in zip(estimated,result['kinds']):
        color='#e48738' if kind=='plastic' else '#b04aad'
        ax.plot(q[0]+q[2]*np.cos(theta),q[1]+q[2]*np.sin(theta),'--',color=color,lw=2,label=f'Found {kind}')
    ax.set(xlim=(.32,.68),ylim=(.35,.65),aspect='equal',xlabel='x (m)',ylabel='y (m)',
           title=f'Empty-start material search: {len(estimated)} circles found\n{100*args.noise:g}% noise; BEM-generated data')
    ax.legend();ax.grid(alpha=.2);fig.tight_layout();fig.savefig(output/'reconstruction.png',dpi=180)
    print('FINAL',result['kinds'],result['relative_error'],result['holdout_relative_errors'],flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--noise',type=float,default=.01)
    parser.add_argument('--seed',type=int,default=16092026)
    parser.add_argument('--scene',choices=['two','one-metal','three','swapped'],default='two')
    parser.add_argument('--project-acquisition',action='store_true')
    main(parser.parse_args())
