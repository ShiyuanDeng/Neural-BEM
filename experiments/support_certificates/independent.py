"""Use independent smooth-boundary observations; qualify volume grid errors."""
from pathlib import Path
import json
import numpy as np
from ordered_boundary import circle
from experiments.modal_muller_research.run_native import nodal
from .core import Dual,SectorDual,green,volume_operator,scatter


def groups(points,count=4):
    # Fixed physical groups, independent of material truth or bound outcome.
    ix=np.clip(((points[:,0]+.08)/.16*count).astype(int),0,count-1)
    iz=np.clip(((points[:,1]+.24)/.16*count).astype(int),0,count-1)
    labels=iz*count+ix
    return np.array([labels==label for label in np.unique(labels)],float)


def run():
    out=Path('results/experiments/support_certificates_20260916');out.mkdir(exist_ok=True,parents=True)
    src=np.c_[np.linspace(-.2,.2,4),np.zeros(4)]
    rx=np.c_[np.linspace(-.22,.22,20),np.full(20,.006)]
    frequency=.75e9;eps0=8.8541878128e-12;mu0=1.25663706212e-6
    k=2*np.pi*frequency*np.sqrt(eps0*mu0*6.)
    acq=dict(source_points=src,receiver_points=rx,source_strength=1.,exterior=dict(epsr=6.,mur=1.,sigma=0.),
             interior=dict(epsr=3.,mur=1.,sigma=0.),eps0=eps0,mu0=mu0)
    shape=circle((.01,-.16),.036)
    y=nodal([shape],frequency,acq,256)['y'];y128=nodal([shape],frequency,acq,128)['y']
    norm=np.linalg.norm(y)
    result=dict(boundary_128_256=float(np.linalg.norm(y-y128)/norm),frequency=frequency,grids=[],bounds=[])
    for n in (8,12,16,24):
        h=.16/n;x=-.08+(np.arange(n)+.5)*h;z=-.24+(np.arange(n)+.5)*h
        pts=np.array([(a,b) for b in z for a in x]);area=h*h
        g=volume_operator(k,pts,area);e=green(k,pts,src);a=k*k*area*green(k,rx,pts)
        truth=np.linalg.norm(pts-[.01,-.16],axis=1)<.036
        pred=a@scatter(g,e,truth,-.5)
        err=float(np.linalg.norm(pred-y)/norm)
        result['grids'].append(dict(n=n,cells=len(pts),truth_cells=int(truth.sum()),relative_error=err))
        print('grid',result['grids'][-1],flush=True)
        # Bound cost is kept fixed as the quadrature grid is refined.
        if n not in (8,16,24):continue
        for name,mask in [('deep',pts[:,1]<-.17),('left',pts[:,0]<0),('full',np.ones(len(pts),bool))]:
            if n==24 and name=='full':continue
            ids=np.flatnonzero(mask);w=groups(pts[ids])
            for kind in ('binary','interval'):
                gg=g[np.ix_(ids,ids)]
                model=Dual(np.eye(len(ids))/-.5-gg,e[ids],a[:,ids]/norm,y/norm,w) if kind=='binary' else SectorDual(gg,e[ids],a[:,ids]/norm,y/norm,-.75,0,w)
                bound=model.solve(max_steps=30,barriers=(1e-3,1e-4,1e-5,1e-6))
                record=dict(n=n,name=name,kind=kind,**bound);result['bounds'].append(record)
                print({key:record.get(key) for key in ('n','name','kind','relative_residual_bound','seconds','success')},flush=True)
                (out/'independent.json').write_text(json.dumps(result,indent=2))
    np.savez(out/'independent_data.npz',sources=src,receivers=rx,y=y,frequency=frequency)


if __name__=='__main__':run()
