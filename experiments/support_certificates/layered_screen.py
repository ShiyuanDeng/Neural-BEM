from pathlib import Path
import json
import numpy as np
from .core import CrossSectorDual,SectorDual
from .layered import Layered
from .cross_qualification import fractional_truth
from .independent import groups


def grid(n):
    h=.16/n;x=-.08+(np.arange(n)+.5)*h;z=-.24+(np.arange(n)+.5)*h
    return np.array([(a,b) for b in z for a in x]),h


def truth(layer,n,src,rx):
    pts,h=grid(n);chi=-.5*fractional_truth(pts,h);keep=chi!=0
    pts=pts[keep];chi=chi[keep]
    g,e,a=layer.matrices(pts,h*h,src,rx)
    p=np.linalg.solve(np.eye(len(pts))-chi[:,None]*g,chi[:,None]*e)
    return a@p


def run():
    out=Path('results/experiments/support_certificates_20260916')
    frequency=.75e9;eps0=8.8541878128e-12;mu0=1.25663706212e-6
    eps=6+1j*.02/(eps0*2*np.pi*frequency)
    ka=2*np.pi*frequency*np.sqrt(eps0*mu0);kg=ka*np.sqrt(eps)
    src=np.array([[-.2,.03],[.2,.03]]);rx=np.c_[np.linspace(-.22,.22,20),np.full(20,.035)]
    layer=Layered(ka,kg,order=96);refined=Layered(ka,kg,order=192)
    result=dict(frequency=frequency,soil_eps_real=6.,soil_sigma=.02,truth_sigma=.01,truth_eps_real=3.,source_height=.03,receiver_height=.035,grids=[],bounds=[])
    previous=None
    for n in (24,40,56):
        y=truth(layer,n,src,rx)
        row=dict(n=n,change_from_previous=None if previous is None else float(np.linalg.norm(y-previous)/np.linalg.norm(y)))
        result['grids'].append(row);previous=y
        print('truth',row,flush=True)
    yref=truth(refined,56,src,rx)
    result['sommerfeld_96_192']=float(np.linalg.norm(y-yref)/np.linalg.norm(yref))
    y=yref;scale=np.linalg.norm(y)
    np.savez(out/'layered_data.npz',y=y,sources=src,receivers=rx,frequency=frequency)
    for n in (8,12,16):
        pts,h=grid(n);g,e,a=layer.matrices(pts,h*h,src,rx)
        own=truth(layer,n,src,rx)
        result['grids'].append(dict(n=n,forward_error_to_56=float(np.linalg.norm(own-y)/scale)))
        for name,mask in [('without_core',np.linalg.norm(pts-[.01,-.16],axis=1)>.031),('left',pts[:,0]<0),('full',np.ones(len(pts),bool))]:
            if (n==16 and name!='left') or (n==12 and name=='full'):continue
            ids=np.flatnonzero(mask);w=groups(pts[ids],count=2);gg=g[np.ix_(ids,ids)]
            for cross in (False,True):
                cls=CrossSectorDual if cross else SectorDual
                model=cls(gg,e[ids],a[:,ids]/scale,y/scale,-.55,0.,w)
                bound=model.solve(max_steps=30,barriers=(1e-3,1e-4,1e-5,1e-6))
                row=dict(n=n,name=name,cross=cross,**bound);result['bounds'].append(row)
                print({k:row.get(k) for k in ('n','name','cross','relative_residual_bound','seconds','success')},flush=True)
                (out/'layered.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':run()
