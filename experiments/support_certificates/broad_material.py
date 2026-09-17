from pathlib import Path
import json
import numpy as np
from .layered import Layered
from .layered_screen import grid
from .primal_check import fit


def run():
    out=Path('results/experiments/support_certificates_20260916');data=np.load(out/'layered_data.npz')
    f=float(data['frequency']);eps0=8.8541878128e-12;mu0=1.25663706212e-6
    bg=6+1j*.02/(eps0*2*np.pi*f);immax=.04/(eps0*2*np.pi*f);ka=2*np.pi*f*np.sqrt(eps0*mu0)
    pts,h=grid(16);pts=pts[pts[:,0]<0];g,e,a=Layered(ka,ka*np.sqrt(bg)).matrices(pts,h*h,data['sources'],data['receivers'])
    norm=np.linalg.norm(data['y']);records=[]
    for upper in (12.,24.):
        for initial in ((3.,bg.imag/2),(6.,bg.imag),(9.,bg.imag/2)):
            fitresult,p=fit(g,e,a/norm,data['y']/norm,bg,immax,initial,max_nfev=600,epsmax=upper)
            row=dict(epsmax=upper,initial=initial,**fitresult);records.append(row)
            print({k:row[k] for k in ('epsmax','initial','relative_error','nfev','success')},flush=True)
            (out/'broad_material.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':run()
