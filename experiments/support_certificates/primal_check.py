"""Physical upper witnesses and fresh checks of retained complex dual bounds."""
from pathlib import Path
import json
import hashlib
import subprocess
import numpy as np
from scipy.optimize import least_squares
from .complex_material import ComplexMaterialDual
from .layered import Layered
from .layered_screen import grid
from .independent import groups


def fit(g,e,a,y,background,immax,initial,max_nfev=350,epsmax=6.):
    n=len(g);eye=np.eye(n);cache={}
    def evaluate(x):
        if 'x' not in cache or not np.array_equal(x,cache['x']):
            eps=x[:n]+1j*x[n:];chi=eps/background-1
            mat=eye-chi[:,None]*g;p=np.linalg.solve(mat,chi[:,None]*e)
            total=e+g@p;response=np.linalg.solve(mat.T,a.T).T
            jc=(response[:,:,None]*total[None,:,:]).transpose(0,2,1).reshape(-1,n)/background
            jj=np.c_[jc,1j*jc];res=(a@p-y).ravel()
            cache.update(x=x.copy(),p=p,res=np.r_[res.real,res.imag],jac=np.r_[jj.real,jj.imag])
        return cache
    x=np.r_[np.full(n,initial[0]),np.full(n,initial[1])]
    opt=least_squares(lambda x:evaluate(x)['res'],x,jac=lambda x:evaluate(x)['jac'],bounds=(np.r_[np.full(n,2.7),np.zeros(n)],np.r_[np.full(n,epsmax),np.full(n,immax)]),
                      x_scale='jac',max_nfev=max_nfev,ftol=1e-10,xtol=1e-10,gtol=1e-9)
    return dict(relative_error=float(np.linalg.norm(opt.fun)/np.linalg.norm(y)),parameters=opt.x.tolist(),nfev=opt.nfev,success=bool(opt.success)),evaluate(opt.x)['p']


def run():
    out=Path('results/experiments/support_certificates_20260916');saved=np.load(out/'layered_data.npz')
    records=json.loads((out/'complex_material.json').read_text());f=float(saved['frequency']);eps0=8.8541878128e-12;mu0=1.25663706212e-6
    bg=6+1j*.02/(eps0*2*np.pi*f);immax=.04/(eps0*2*np.pi*f);ka=2*np.pi*f*np.sqrt(eps0*mu0);layer=Layered(ka,ka*np.sqrt(bg))
    y=saved['y'];scale=np.linalg.norm(y);result=dict(dual_checks=[],physical_witnesses=[])
    for row in records:
        if not row['success']:continue
        pts,h=grid(row['n']);g,e,a=layer.matrices(pts,h*h,saved['sources'],saved['receivers'])
        mask=pts[:,0]<0 if row['name']=='left' else np.ones(len(pts),bool);ids=np.flatnonzero(mask)
        gg=g[np.ix_(ids,ids)];ee=e[ids];aa=a[:,ids]/scale;yy=y/scale
        model=ComplexMaterialDual(gg,ee,aa,yy,bg,(2.7,6.),(0.,immax),groups(pts[ids],2),cross=row['cross'])
        ev=model.evaluate(np.array(row['multipliers']));eig=np.linalg.eigvalsh(ev['q'])
        check=dict(n=row['n'],name=row['name'],cross=row['cross'],fresh_raw_bound=float(ev['value']),stored_bound=row['bound'],minimum_eigenvalue=float(eig[0]),minimum_inequality_multiplier=float(np.min(np.array(row['multipliers'])[model.positive])))
        assert eig[0]>0 and check['minimum_inequality_multiplier']>0
        assert row['bound']<=ev['value']+1e-10
        result['dual_checks'].append(check)
        if row['cross'] and row['n'] in (8,16):
            for start in ((3.,bg.imag/2),(4.5,bg.imag)):
                witness,p=fit(gg,ee,aa,yy,bg,immax,start)
                realp=np.r_[p.reshape(-1,1).real,p.reshape(-1,1).imag]
                cons=np.einsum('jk,ijk->i',realp,model.qi@realp-2*model.bi)+model.constants
                assert max(cons[model.positive])<1e-9
                assert max(abs(cons[len(model.positive):]),default=0.)<1e-9
                assert row['bound']<=witness['relative_error']**2+1e-9
                record=dict(n=row['n'],name=row['name'],initial=start,**witness);result['physical_witnesses'].append(record)
                print({k:record[k] for k in ('n','name','relative_error','nfev','success')},flush=True)
        (out/'primal_checks.json').write_text(json.dumps(result,indent=2))
    roots=[Path('experiments/support_certificates'),Path('experiments/operator_rom'),Path('experiments/passive_shape')]
    files=[p for root in roots for p in root.glob('*.py')]
    manifest=dict(git_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                  note='Final source hashes. Retained complex dual multipliers freshly reconstructed and checked; earlier controls predate algebra-preserving performance edits.')
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))


if __name__=='__main__':run()
