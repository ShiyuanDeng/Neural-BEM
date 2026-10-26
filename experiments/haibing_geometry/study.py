"""HB-002: saved-trajectory safe steps and physical-metric information spectra."""
from pathlib import Path
import os, subprocess, time, traceback
import numpy as np
from bem_inverse import a1_geometry as a1
from bem_inverse.io import read, write, curve_from, digest
from bem_inverse.continuation.geometry import resize, values, grid_size
from bem_inverse.geometry_selection import make_update
from bem_inverse.physics import Execution
from bem_inverse.b5_residual import normalize
from experiments.frequency_interpolation.study import SPECS
from experiments.benchmark.campaign import problem
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/validation/cleaned_interfaces'
OUT=BASE/'HB-002-geometry'

def qcoeff(curve):
    k=curve.band; w=np.zeros((2*k+1,)*2,complex)
    for m in range(1,k+1):
        for l in range(m):
            w[k+m-1-l,k+l]+=curve.coefficients[k+m]
            w[k-1-l,k-m+l]-=curve.coefficients[k-m]
    return a1.real_product(w,w,2)

def geometry():
    result=[]
    for case in ('circle__c4','peanut__c4','hook__c13.3'):
        folder=BASE/'NR-001/M1/runs'/case
        states=read(folder/'accepted.json')['states']
        pairs=[i for i in range(len(states)-1) if states[i]['stage']==states[i+1]['stage']]
        chosen=set(np.asarray(pairs)[np.linspace(0,len(pairs)-1,8,dtype=int)].tolist())
        rows=[]
        for i in pairs:
            anchor,target=states[i:i+2]; z=curve_from(anchor['curve']); new=resize(curve_from(target['curve']),z.band)
            q=qcoeff(z); b=a1.half(q); simple=float(2*q[b,b].real-np.sum(abs(q)))
            step=float(np.sum(abs(z.modes)*abs(new.coefficients-z.coefficients)))
            row=dict(case=case,index=i,stage=anchor['stage'],iteration=anchor['iteration'],K=z.band,
                     actual_step_W_bound=step,simple_q_lower=simple,
                     simple_safe=bool(simple>step**2),selected_sharp=i in chosen)
            if i in chosen:
                saved=read(folder/(anchor['stage']+'.json')); cutoff=saved.get('Ku') or saved['nodes']//8
                start=time.perf_counter()
                try:
                    _,receipt=a1.log_modulus(q,cutoff+64,tolerance=1e-12,max_degree=1000)
                    lower=receipt['certificate']['lower']
                    row.update(sharp=receipt,sharp_safe=bool(lower>step**2),
                               maximum_step_fraction=float(np.sqrt(lower)/step) if step else None)
                except Exception as exc:
                    row.update(sharp_failure=str(exc),sharp_safe=False)
                row['sharp_seconds']=time.perf_counter()-start
                print(case,i,row['sharp_safe'],row.get('maximum_step_fraction'),flush=True)
            rows.append(row);write(OUT/(case+'.json'),dict(source_sha256=digest(folder/'accepted.json'),rows=rows))
        result.append(dict(case=case,steps=len(rows),simple_safe=sum(r['simple_safe'] for r in rows),
                           sharp_tested=len(chosen),sharp_safe=sum(r.get('sharp_safe',False) for r in rows),
                           sharp_refused=sum('sharp_failure' in r for r in rows)))
    write(OUT/'geometry_summary.json',result)

def complex_array(raw):
    return np.asarray([complex(x['real'],x['imag']) for x in np.asarray(raw,dtype=object).ravel()]).reshape(np.shape(raw))

def spectrum(J,G):
    d,V=np.linalg.eigh(G); keep=d>d[-1]*1e-12
    W=V[:,keep]/np.sqrt(d[keep]); s=np.linalg.svd(J@W,compute_uv=False)
    return s,int(sum(keep))

def information():
    rows=[]
    for name,(case,path,method) in SPECS.items():
        saved=read(BASE/path); z=curve_from(saved['curve']); p=problem(case)
        outputs=BASE/'FI-001'/name/'exact_outputs.json'
        J=complex_array(read(outputs)['jacobians'])
        update,_=make_update(method,p.length_unit_m,Execution(device='cpu',frequency_threads=1))
        space=update.prepare(z,saved['M'],z.band)
        n=grid_size(z.band); dz=z.values(n,1); speed=abs(dz); normal=-1j*dz/speed
        normal_basis=(values(space.derivatives,n)*normal.conj()[:,None]).real*p.length_unit_m
        G=normal_basis.T@(normal_basis*(speed/speed.sum())[:,None])
        obs=np.column_stack([o.scattered for o in p.real]);freq=np.array([o.frequency_hz for o in p.real])
        for M in sorted(set((3,min(11,saved['M']),saved['M']))):
            indices=np.flatnonzero(space.orders<=M);g=G[np.ix_(indices,indices)]
            for label,which in [('low',np.flatnonzero(freq<=.75e9)),('all',np.arange(len(freq)))]:
                j=normalize(J[which][:,:,indices].transpose(1,0,2),obs[:,which],np.ones(len(which))/len(which))
                s,rank=spectrum(j,g)
                scales=np.geomspace(.1,10,len(indices)); s2,_=spectrum(j*scales,g*scales[:,None]*scales[None,:])
                err=float(np.linalg.norm(s-s2)/np.linalg.norm(s))
                rows.append(dict(state=name,M=M,frequencies=label,n_frequencies=len(which),parameters=len(indices),
                    metric_rank=rank,relative_threshold=.001,count_above_threshold=int(sum(s>.001*s[0])),
                    singular_values=s,smallest_over_largest=float(s[-1]/s[0]),unit_change_relative_error=err,
                    input_sha256=digest(outputs),geometry_source=path,shape_metric='mean-square physical normal displacement'))
                print(name,M,label,rows[-1]['count_above_threshold'],err,flush=True)
        write(OUT/'information.json',rows)
    assert max(r['unit_change_relative_error'] for r in rows)<1e-8

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    write(OUT/'manifest.json',dict(revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        affinity=sorted(os.sched_getaffinity(0)),load=os.getloadavg(),source_sha256=digest(Path(__file__)),
        blas={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}))
    for name,fn in [('geometry',geometry),('information',information)]:
        try: fn()
        except Exception:
            (OUT/(name+'_failure.txt')).write_text(traceback.format_exc()); raise
