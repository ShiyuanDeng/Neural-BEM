from pathlib import Path
import json
import numpy as np
from scipy.linalg import eigh
from .screen import Wave,matrices,extrema,positive_qr
from .fixed_projection import FixedROM,basin_fraction


def run():
    out=Path('results/experiments/operator_rom_20260916');saved=np.load(out/'data.npz')
    depths=saved['depths'];d=saved['observed'];dd=saved['observed_second'];truth=int(np.argmin(abs(depths-.52)))
    wave=Wave();background,_=wave.data(contrast=1.)
    models=[matrices(a,b,16) for a,b in zip(saved['data'],saved['second'])]
    result=dict(noise=[],finer=[])
    for level in (.001,.01,.05):
        for seed in range(10):
            rng=np.random.default_rng(700+seed);freq=np.linspace(12,40,64)
            coeff=rng.normal(size=(64,2,2));coeff=(coeff+coeff.transpose(0,2,1))/2
            cosine=np.cos(wave.times[:,None]*freq[None,:])
            noise=np.einsum('tf,fij->tij',cosine,coeff)
            noise_dd=-np.einsum('tf,fij->tij',cosine*freq[None,:]**2,coeff)
            scale=level*np.linalg.norm(d-background)/np.linalg.norm(noise)
            nd=d+scale*noise;ndd=dd+scale*noise_dd
            m,s,p=matrices(nd,ndd,16);nm,_,_=matrices(scale*noise,scale*noise_dd,16)
            # Truth is used only to emulate a measured/calibrated noise bound;
            # rank is chosen from its perturbation norm, never recovery error.
            cutoff=10*np.linalg.norm(nm,2);eigen=eigh(m,eigvals_only=True)
            rank=max(2,(np.count_nonzero(eigen>cutoff)//2)*2)
            rom=FixedROM(m,s,p,2,rank)
            vals=np.array([rom.objective(mm,ss) for mm,ss,_ in models])
            raw=np.sum((saved['data']-nd)**2,axis=(1,2,3))
            row=dict(level=level,seed=seed,rank=rank,raw_best_depth=float(depths[np.argmin(raw)]),rom_best_depth=float(depths[np.argmin(vals)]),
                     raw_basin_fraction=basin_fraction(raw,truth)[0],rom_basin_fraction=basin_fraction(vals,truth)[0])
            result['noise'].append(row)
        print('noise',level,'mean rank',np.mean([r['rank'] for r in result['noise'] if r['level']==level]),flush=True)
    # A different, denser grid and four nonsymmetric source locations.
    finer=Wave(nx=30,nz=38,source_count=4)
    fd,fdd,u,a=finer.data(return_snapshots=True);m,s,p=matrices(fd,fdd,16)
    checks=dict(mass=float(np.linalg.norm(m-u.T@u)/np.linalg.norm(m)),stiffness=float(np.linalg.norm(s-u.T@a@u)/np.linalg.norm(s)))
    roms=[];result['finer_construction_failures']=[]
    for rank in (16,24,32,40):
        try:roms.append(FixedROM(m,s,p,4,rank))
        except ValueError as error:result['finer_construction_failures'].append(dict(rank=rank,reason=str(error)))
    if roms:
        q,_=positive_qr(u@roms[0].projection)
        checks['fixed_projection_operator']=float(np.linalg.norm(roms[0].reference-q.T@a@q)/np.linalg.norm(roms[0].reference))
    values=[[] for _ in roms];raw=[]
    for j,depth in enumerate(depths):
        d,dd=finer.data(depth=depth);mm,ss,_=matrices(d,dd,16)
        raw.append(float(np.linalg.norm(d-fd)**2))
        for rr,vv in zip(roms,values):vv.append(rr.objective(mm,ss))
        if j%10==0:print('finer',j,flush=True)
    raw=np.array(raw);result['finer_raw']=dict(minima=depths[extrema(raw)].tolist(),basin_fraction=basin_fraction(raw,truth)[0],objective=raw.tolist())
    result['finer_checks']=checks
    for rr,vv in zip(roms,values):
        v=np.array(vv);row=dict(rank=rr.meta['rank'],minima=depths[extrema(v)].tolist(),basin_fraction=basin_fraction(v,truth)[0],objective=vv)
        result['finer'].append(row);print('finer result',row['rank'],row['basin_fraction'],len(row['minima']),flush=True)
    (out/'qualification.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':run()
