"""Independent smooth-circle data and source-consistent support exclusions."""
from pathlib import Path
import json
import numpy as np
from ordered_boundary import circle
from experiments.modal_muller_research.run_native import nodal
from .core import CrossDual,CrossSectorDual,green,volume_operator
from .independent import groups


def fractional_truth(points,h):
    offsets=(np.arange(12)+.5)/12-.5
    fraction=np.zeros(len(points))
    for dx in offsets:
        for dz in offsets:
            fraction+=np.linalg.norm(points+h*np.array([dx,dz])-[.01,-.16],axis=1)<.036
    return fraction/len(offsets)**2


def run():
    out=Path('results/experiments/support_certificates_20260916')
    src=np.array([[-.2,0.],[.2,0.]])
    rx=np.c_[np.linspace(-.22,.22,20),np.full(20,.006)]
    eps0=8.8541878128e-12;mu0=1.25663706212e-6
    acq=dict(source_points=src,receiver_points=rx,source_strength=1.,exterior=dict(epsr=6.,mur=1.,sigma=0.),
             interior=dict(epsr=3.,mur=1.,sigma=0.),eps0=eps0,mu0=mu0)
    result=dict(grids=[],bounds=[])
    for frequency in (.75e9,1.25e9):
        k=2*np.pi*frequency*np.sqrt(eps0*mu0*6.)
        y=nodal([circle((.01,-.16),.036)],frequency,acq,256)['y'];norm=np.linalg.norm(y)
        for n in (8,12,16):
            h=.16/n;x=-.08+(np.arange(n)+.5)*h;z=-.24+(np.arange(n)+.5)*h
            pts=np.array([(a,b) for b in z for a in x]);g=volume_operator(k,pts,h*h)
            e=green(k,pts,src);a=k*k*h*h*green(k,rx,pts)
            chi=-.5*fractional_truth(pts,h)
            p=np.linalg.solve(np.eye(len(pts))-chi[:,None]*g,chi[:,None]*e)
            err=float(np.linalg.norm(a@p-y)/norm)
            result['grids'].append(dict(n=n,frequency=frequency,relative_error=err))
            print('grid',result['grids'][-1],flush=True)
            for name,mask in [('without_core',np.linalg.norm(pts-[.01,-.16],axis=1)>.031),('left',pts[:,0]<0)]:
                if n==16 and name=='without_core':continue
                ids=np.flatnonzero(mask);gg=g[np.ix_(ids,ids)];w=groups(pts[ids],count=2)
                for label,lower in [('known',None),('eps_ge_3',-.5),('eps_ge_2p7',-.55)]:
                    if n==16 and label=='known':continue
                    model=CrossDual(np.eye(len(ids))/-.5-gg,e[ids],a[:,ids]/norm,y/norm,w) if lower is None else CrossSectorDual(gg,e[ids],a[:,ids]/norm,y/norm,lower,0.,w)
                    bound=model.solve(max_steps=30,barriers=(1e-3,1e-4,1e-5,1e-6))
                    row=dict(n=n,frequency=frequency,name=name,material=label,**bound);result['bounds'].append(row)
                    print({key:row.get(key) for key in ('n','frequency','name','material','relative_residual_bound','seconds','success')},flush=True)
                    (out/'cross_qualification.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':run()
