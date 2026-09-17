"""Look for actual physical fits behind vanishing relaxed support bounds."""
from pathlib import Path
import json
import numpy as np
from scipy.optimize import least_squares


def fit(g,e,a,y,lo,hi,initial):
    n=len(g);eye=np.eye(n);cache={}
    def evaluate(x):
        if 'x' not in cache or not np.array_equal(cache['x'],x):
            mat=eye-x[:,None]*g
            p=np.linalg.solve(mat,x[:,None]*e);total=e+g@p
            response=np.linalg.solve(mat.T,a.T).T
            jac=(response[:,:,None]*total[None,:,:]).transpose(0,2,1).reshape(-1,n)
            cache.update(x=x.copy(),res=(a@p-y).ravel(),jac=jac)
        return cache
    def fun(x):
        c=evaluate(x)['res'];return np.r_[c.real,c.imag]
    def jac(x):
        c=evaluate(x)['jac'];return np.r_[c.real,c.imag]
    opt=least_squares(fun,np.full(n,initial),jac=jac,bounds=(lo,hi),max_nfev=500,ftol=1e-11,xtol=1e-11,gtol=1e-10)
    return dict(relative_error=float(np.linalg.norm(fun(opt.x))/np.linalg.norm(y)),contrast=opt.x.tolist(),nfev=opt.nfev,success=bool(opt.success))


def run():
    out=Path('results/experiments/support_certificates_20260916');data=np.load(out/'screen_data.npz')
    pts=data['points'];g=data['g'];e=data['e'];a=data['a'];y=data['y'];scale=np.linalg.norm(y)
    records=[]
    for name,mask in [('deep',pts[:,1]<-.169),('without_core',np.linalg.norm(pts-[.01,-.16],axis=1)>.031)]:
        ids=np.flatnonzero(mask)
        for label,lo,hi in [('low',-.75,0.),('both',-.75,1.5)]:
            result=fit(g[np.ix_(ids,ids)],e[ids],a[:,ids]/scale,y/scale,lo,hi,-.2)
            row=dict(name=name,material=label,**result);records.append(row)
            print({k:row[k] for k in ('name','material','relative_error','nfev','success')},flush=True)
            (out/'alternatives.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':run()
