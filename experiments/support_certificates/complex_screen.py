from pathlib import Path
import json
import numpy as np
from .complex_material import ComplexMaterialDual
from .layered import Layered
from .layered_screen import grid
from .independent import groups


def run():
    out=Path('results/experiments/support_certificates_20260916');saved=np.load(out/'layered_data.npz')
    frequency=float(saved['frequency']);eps0=8.8541878128e-12;mu0=1.25663706212e-6
    eps=6+1j*.02/(eps0*2*np.pi*frequency);ka=2*np.pi*frequency*np.sqrt(eps0*mu0);kg=ka*np.sqrt(eps)
    layer=Layered(ka,kg);src=saved['sources'];rx=saved['receivers'];y=saved['y'];norm=np.linalg.norm(y)
    records=[]
    for n in (8,12,16):
        pts,h=grid(n);g,e,a=layer.matrices(pts,h*h,src,rx)
        for name,mask in [('left',pts[:,0]<0),('full',np.ones(len(pts),bool))]:
            if name=='full' and n!=8:continue
            ids=np.flatnonzero(mask);w=groups(pts[ids],2)
            for cross in (False,True):
                model=ComplexMaterialDual(g[np.ix_(ids,ids)],e[ids],a[:,ids]/norm,y/norm,eps,(2.7,6.),(0.,.04/(eps0*2*np.pi*frequency)),w,cross=cross)
                row=dict(n=n,name=name,cross=cross,**model.solve(max_steps=35,barriers=(1e-3,1e-4,1e-5,1e-6)))
                records.append(row);print({k:row.get(k) for k in ('n','name','cross','relative_residual_bound','seconds','success','reason')},flush=True)
                (out/'complex_material.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':run()
