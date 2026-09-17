"""Paper-faithful fixed projection, equations E-9--E-15 of the 2023 paper.

The initial screen recomputed a basis for every model. That is an exploratory
moving-basis control, not the published regularized inversion algorithm.
"""
from pathlib import Path
import json
import numpy as np
from scipy.linalg import eigh,solve_triangular
from .screen import matrices,positive_qr,extrema


class FixedROM:
    def __init__(self,mass,stiff,prop,s,rank):
        values,vectors=eigh(mass)
        idx=np.arange(len(values)-1,len(values)-rank-1,-1)
        eig=values[idx];v=vectors[:,idx]
        if eig[-1]<=0:raise ValueError('Requested rank includes nonpositive data eigenvalues')
        w=v/np.sqrt(eig)[None,:]
        pi=w.T@prop@w
        # Appendix E specifies Lambda^-1/2 Z^T e0, followed by transforming
        # the mass matrix and a second Cholesky factorization.
        q,_=positive_qr(w[:s,:].T);blocks=[q]
        for _ in range(rank//s-1):
            candidate=pi@blocks[-1];full=np.concatenate(blocks,axis=1)
            for _ in range(2):candidate-=full@(full.T@candidate)
            block,r=positive_qr(candidate)
            if np.min(np.abs(np.diag(r)))<1e-13:raise ValueError('Krylov breakdown')
            blocks.append(block)
        q=np.concatenate(blocks,axis=1)
        self.projection=v@q
        self.reference=self.evaluate(mass,stiff)
        self.meta=dict(rank=rank,minimum_data_eigenvalue=float(values[0]),smallest_retained=float(eig[-1]),
                       condition=float(eig[0]/eig[-1]),orthogonality=float(np.linalg.norm(q.T@q-np.eye(rank))))

    def evaluate(self,mass,stiff):
        m=self.projection.T@mass@self.projection
        s=self.projection.T@stiff@self.projection
        lower=np.linalg.cholesky((m+m.T)/2)
        left=solve_triangular(lower,s,lower=True)
        return solve_triangular(lower,left.T,lower=True).T

    def objective(self,mass,stiff):
        difference=self.evaluate(mass,stiff)-self.reference
        return float(np.linalg.norm(np.triu(difference))**2)


def basin_fraction(values,truth_index):
    ends=[]
    for start in range(len(values)):
        here=start
        for _ in range(len(values)):
            choices=np.arange(max(0,here-1),min(len(values),here+2))
            nxt=choices[np.nanargmin(values[choices])]
            if nxt==here:break
            here=nxt
        ends.append(int(here))
    return float(np.mean(np.abs(np.array(ends)-truth_index)<=1)),ends


def run():
    out=Path('results/experiments/operator_rom_20260916');saved=np.load(out/'data.npz')
    depths=saved['depths'];d=saved['observed'];dd=saved['observed_second'];truth=int(np.argmin(abs(depths-.52)))
    models=[matrices(a,b,16) for a,b in zip(saved['data'],saved['second'])]
    m,s,p=matrices(d,dd,16)
    raw=np.sum((saved['data']-d)**2,axis=(1,2,3))
    records=[]
    for rank in (12,16,20,24,28):
        rom=FixedROM(m,s,p,2,rank)
        vals=np.array([rom.objective(mm,ss) for mm,ss,_ in models])
        fraction,ends=basin_fraction(vals,truth)
        row=dict(rank=rank,meta=rom.meta,objective=vals.tolist(),minima=depths[extrema(vals)].tolist(),basin_fraction=fraction,basin_ends=ends)
        records.append(row)
        print({k:row[k] for k in ('rank','minima','basin_fraction')},flush=True)
    result=dict(raw_minima=depths[extrema(raw)].tolist(),raw_basin_fraction=basin_fraction(raw,truth)[0],results=records)
    (out/'fixed_projection.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':run()
