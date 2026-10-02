"""Fixed higher-order audit for4–8GHz; preserves the completed M<=3 study.

Only the already declared maximum M=6 is considered. No scattering data enter
order selection. Passing a candidate only permits the separate joint receiver
position check; it does not itself qualify a geometry rerun.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
import hashlib
from pathlib import Path
import numpy as np
from scipy.constants import c
from solvers.io.fresnel2001 import load_fresnel2001
from .multipole_sources import multipole_basis,fit_multipoles
from .qualify_sources import ROOT,OUTPUT,relative,near_map,save


def main():
    x,y=np.meshgrid(np.linspace(-.08,.08,11),np.linspace(-.08,.08,11))
    target=np.column_stack((x.ravel(),y.ravel()))
    slots=np.arange(49);window=(slots>=12)&(slots<=36);blocked=(slots>=21)&(slots<=27)
    report=dict(scope='fixed ceiling M=6 on local window120..240deg; frequencies4–8GHz only',
        rcond=1e-8,orders=[3,4,5,6],maximum_validation_error=.1,maximum_blocked_error=.1,
        maximum_target_change=.05,selection='smallest eligible order within15percent plus.002 of best eligible interleaved error',cases={})
    for label,filename in [('single','dielTM_dec8f.exp'),('twin','twodielTM_8f.exp')]:
        data=load_fresnel2001(ROOT/'data/fresnel'/filename)
        sources=data.source_points;points=data.receiver_points[data.receiver_labels[0]-1]
        rows=[]
        for fi in range(3,8):
            k=2*np.pi*data.frequencies_hz[fi]/c;incident=data.incident[fi].mean(axis=0)
            candidates=[];near_fields={}
            for order in report['orders']:
                a=multipole_basis(points,sources[0],k,order)[0]
                t=near_map(multipole_basis(target,sources[0],k,order),k)
                fit=fit_multipoles(a[window],incident[window]);near=t@fit.coefficients
                near_fields[order]=near;validation=[];split=[]
                for fold in (1,3):
                    held=window&(slots%4==fold)
                    partial=fit_multipoles(a[window&~held],incident[window&~held])
                    validation.append(relative(a[held]@partial.coefficients,incident[held]));split.append(t@partial.coefficients)
                partial=fit_multipoles(a[window&~blocked],incident[window&~blocked])
                gain=np.linalg.norm(t@fit.inverse_map,2)*np.linalg.norm(incident[window])/np.linalg.norm(near)
                candidates.append(dict(order=order,rank=fit.rank,condition=fit.scaled_condition,
                    coefficients_real=fit.coefficients.real,coefficients_imag=fit.coefficients.imag,
                    train_error=fit.relative_residual,validation_error=float(np.mean(validation)),
                    blocked_error=relative(a[blocked]@partial.coefficients,incident[blocked]),
                    target_split_change=relative(split[0],split[1]),blocked_target_change=relative(t@partial.coefficients,near),
                    target_noise_bound_0p1percent=.001*gain,
                    coefficient_noise_bound_0p1percent=float(.001*np.linalg.norm(fit.inverse_map,2)*np.linalg.norm(incident[window])/np.linalg.norm(fit.coefficients))))
            for row in candidates:
                order=row['order'];neighbor=order+1 if order<6 else order-1
                row['neighbor_order']=neighbor
                row['neighbor_target_change']=relative(near_fields[neighbor],near_fields[order])
                row['nominal_eligible']=bool(row['validation_error']<.1 and row['blocked_error']<.1 and
                    max(row['target_split_change'],row['blocked_target_change'],row['neighbor_target_change'],row['target_noise_bound_0p1percent'])<.05)
            eligible=[r for r in candidates if r['nominal_eligible']]
            selected=None
            if eligible:
                best=min(r['validation_error'] for r in eligible)
                selected=next(r['order'] for r in eligible if r['validation_error']<=1.15*best+.002)
            full_rank=[r for r in eligible if r['rank']==2*r['order']+1]
            full_order=None
            if full_rank:
                best_full=min(r['validation_error'] for r in full_rank)
                full_order=next(r['order'] for r in full_rank if r['validation_error']<=1.15*best_full+.002)
            rows.append(dict(frequency_hz=data.frequencies_hz[fi],selected_order=selected,
                selected_full_rank_order=full_order,candidates=candidates))
            print(label,fi+1,'selected',selected,[(r['order'],r['validation_error'],r['blocked_target_change'],r['rank']) for r in candidates],flush=True)
        report['cases'][label]=dict(data_sha256=data.source_sha256,frequencies=rows)
    report['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path(__file__),ROOT/'experiments/fresnel/multipole_sources.py')}
    save(OUTPUT/'higher_order_audit.json',report)


if __name__=='__main__':main()
