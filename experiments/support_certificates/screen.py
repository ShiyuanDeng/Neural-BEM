"""First finite-volume support test. Run with single-threaded BLAS."""
from pathlib import Path
import json
import numpy as np
from .core import Dual,green,volume_operator,scatter


def run():
    out=Path('results/experiments/support_certificates_20260916')
    out.mkdir(parents=True,exist_ok=True)
    x=np.linspace(-.07,.07,8); z=np.linspace(-.23,-.09,8)
    points=np.array([(a,b) for b in z for a in x]); area=(x[1]-x[0])**2
    sources=np.c_[np.linspace(-.2,.2,4),np.zeros(4)]
    receivers=np.c_[np.linspace(-.22,.22,20),np.full(20,.006)]
    frequency=.75e9;k=2*np.pi*frequency/299792458*np.sqrt(6.)
    chi=-.5
    g=volume_operator(k,points,area);e=green(k,points,sources)
    a=k*k*area*green(k,receivers,points)
    truth=np.linalg.norm(points-np.array([.01,-.16]),axis=1)<.036
    p=scatter(g,e,truth,chi);y=a@p
    norm=np.linalg.norm(y); an=a/norm;yn=y/norm
    masks=dict(full=np.ones(len(points),bool),left=points[:,0]<-.001,
               right=points[:,0]>.001,shallow=points[:,1]>-.151,
               deep=points[:,1]<-.169,without_core=np.linalg.norm(points-[.01,-.16],axis=1)>.031)
    records=[]
    for name,mask in masks.items():
        ids=np.flatnonzero(mask)
        d=np.eye(len(ids))/chi-g[np.ix_(ids,ids)]
        dual=Dual(d,e[ids],an[:,ids],yn)
        result=dual.solve()
        linear=np.linalg.norm(an[:,ids]@np.linalg.lstsq(an[:,ids],yn,rcond=1e-13)[0]-yn)
        record=dict(name=name,cells=len(ids),linear_residual=float(linear),**result)
        records.append(record)
        print({key:record.get(key) for key in ('name','cells','bound','relative_residual_bound','linear_residual','seconds','success')},flush=True)
        (out/'screen.json').write_text(json.dumps(dict(chi=chi,frequency=frequency,truth_cells=int(truth.sum()),results=records),indent=2))
    np.savez(out/'screen_data.npz',points=points,area=area,sources=sources,receivers=receivers,truth=truth,g=g,e=e,a=a,y=y)


if __name__=='__main__':run()
