"""Replay saved H3 curves, profile production and compare all-RHS solves.

Run with PYTHONPATH=solvers:. and single-thread BLAS, on cores 12--17.
No fit, truth scoring, solver change, or replacement accuracy model occurs here.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import gc
import json
import os
from pathlib import Path
import resource
import subprocess
from time import perf_counter
import traceback

import numpy as np
from scipy.linalg import lu_factor, lu_solve, svd
import torch

from bem_inverse import a4_fields, b7_data_jacobian
from bem_inverse.forward_solvers import modal_muller as MM
from bem_inverse.geometry_update_methods.slider import SliderUpdate
from bem_inverse.io import read, write, curve_from, digest
from bem_inverse.physics import Execution
from experiments.benchmark.campaign import problem

ROOT = Path(__file__).resolve().parents[2]
SAVED = ROOT/'results/validation/cleaned_interfaces/PS-003/H3/runs/hook__c13.3'
OUT = ROOT/'results/validation/cleaned_interfaces/IS-001'


def machine():
    return dict(time=subprocess.check_output(['date','--iso-8601=seconds'],text=True).strip(),
        revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        affinity=sorted(os.sched_getaffinity(0)), load=os.getloadavg(),
        free=subprocess.check_output(['free','-b'],text=True),
        gpu=subprocess.check_output(['nvidia-smi','--query-gpu=name,utilization.gpu,memory.used,memory.total',
                                     '--format=csv,noheader'],text=True).strip(),
        blas={k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        rss_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,source_sha256=digest(Path(__file__)))


def inputs():
    accepted = read(SAVED/'accepted.json')['states']
    rows = lambda stage: [r for r in accepted if r['stage']==stage]
    release = rows('release_M11')
    final = read(SAVED/'fixed_M67.json')
    nearfinal = rows('fixed_M55')[-2]
    def pad(row, band):
        curve = curve_from(row['curve'])
        return curve_from(dict(real=np.pad(curve.coefficients.real,(band-curve.band,)*2),
                               imag=np.pad(curve.coefficients.imag,(band-curve.band,)*2)))
    return dict(release=curve_from(release[-1]['curve']),
        release_anchor=curve_from(release[-2]['curve']),
        final=curve_from(final['curve']), final_anchor=pad(nearfinal,136),
        large=curve_from(release[1]['curve']), large_anchor=curve_from(release[0]['curve']))


def observations():
    p=problem('hook__c13.3')
    return dict(real=p.real[-1],damped=p.damped[-1])


def save_manifest():
    write(OUT/'manifest.json',dict(experiment='IS-001',machine=machine(),
        source_sha256=digest(Path(__file__)),saved={n:digest(SAVED/n) for n in
          ('accepted.json','release_M11.json','fixed_M67.json')},
        contrast=13.3,frequency_hz=2.5e9,rhs=48,repeats=3,
        states=dict(release='release_M11 iteration15 K24 Ku64; anchor iteration14',
          final='fixed_M67 K136 Ku128 carried endpoint; anchor fixed_M55 iteration3 padded to K136',
          large='release_M11 iteration0 -> iteration1, one actual accepted step'),
        iterative='global GMRES and rank-aware full block Arnoldi; both cold and fixed-LU right preconditioned',
        rtol=1e-12,restart=60,max_actions=1800,prediction_relative_tolerance=1e-9,
        concurrency='CPU cores12-17 single-thread BLAS; exclusive study GPU slot; outside graphics load recorded'))


@contextmanager
def split_lu(timings, module, label):
    original=module.lu_solve
    def wrapped(*args,**kwargs):
        started=perf_counter(); result=original(*args,**kwargs)
        timings[label]=timings.get(label,0.)+perf_counter()-started
        return result
    module.lu_solve=wrapped
    try: yield
    finally: module.lu_solve=original


def profile(name,cutoff):
    curve=inputs()[name]; obs=observations()
    settings=MM.ModalSettings(cached_geometries=1)
    records=[]
    # Real production slider weights, prepared once and excluded from physics timing.
    space=SliderUpdate(.05,device='cuda').prepare(curve,11 if name=='release' else 67,curve.band)
    weights=b7_data_jacobian.normal_velocity_weights(curve.coefficients,space.derivatives)
    for freq,o in obs.items():
        context=MM.ModalMuller(Execution(device='cuda',frequency_threads=1),settings=settings)
        for repeat in range(4):
            torch.cuda.synchronize(); before=context.receipt()['seconds']; details={}
            started=perf_counter()
            with split_lu(details,a4_fields,'forward_trace_solve'):
                pred=MM.forward_solve(curve,o,13.3,MM.token(cutoff),context=context)
            forward=perf_counter()-started
            with split_lu(details,b7_data_jacobian,'reciprocal_trace_solve'):
                J=context._derivative(pred._handle,weights)
            torch.cuda.synchronize()
            after=context.receipt()['seconds']; delta={k:after.get(k,0.)-before.get(k,0.) for k in after}
            details.update(fields_other=delta['fields']-details['forward_trace_solve'],
                           hadamard_and_checks=delta['jacobian']-details['reciprocal_trace_solve'])
            records.append(dict(state=name,Ku=cutoff,frequency=freq,repeat=repeat,first_use=repeat==0,
                wall_forward=forward,stages=delta,split=details,diagnostics=pred.diagnostics,
                jacobian_shape=J.shape,system_size=len(pred._handle.traces),machine=machine()))
            write(OUT/f'profile_{name}.json',records)
        del context,pred,J;gc.collect();torch.cuda.empty_cache()
    return records


def assemble(name,cutoff):
    curves=inputs(); obs=observations(); records=[]
    for freq,o in obs.items():
        items={}
        for role,key in [('current',name),('anchor',name+'_anchor')]:
            captured={}
            def observer(kind,payload):
                if kind=='field': captured.update(payload)
            context=MM.ModalMuller(Execution(device='cuda',frequency_threads=1),
                settings=MM.ModalSettings(cached_geometries=1),observer=observer)
            curve=curves[key];started=perf_counter()
            pred=MM.forward_solve(curve,o,13.3,MM.token(cutoff),context=context)
            items[role+'_A']=captured['A']
            if role=='current':
                items.update(B=np.hstack((captured['B_s'],captured['B_r'])),R=captured['R'])
            records.append(dict(role=role,state=key,Ku=cutoff,frequency=freq,seconds=perf_counter()-started,
                stages=context.receipt()['seconds'],diagnostics=pred.diagnostics,machine=machine(),
                peak_gpu_bytes=torch.cuda.max_memory_allocated()))
            del context,pred,captured;gc.collect();torch.cuda.empty_cache()
        path=OUT/f'{name}_Ku{cutoff}_{freq}.npz'
        np.savez_compressed(path,**items)
        if path.stat().st_size>95_000_000:
            np.savez_compressed(path.with_name(path.stem+'_anchor.npz'),anchor_A=items.pop('anchor_A'))
            np.savez_compressed(path,**items)
        write(OUT/f'assembly_{name}_Ku{cutoff}.json',records)
    return records


def global_gmres(A,B,precondition=None,rtol=1e-12,restart=60,max_actions=1800):
    """Batched global GMRES with right preconditioning and true residual checks.

    Frobenius inner products build one polynomial shared by all RHS. This is
    global GMRES, not 48 separate solves or a full 48-vector block Arnoldi basis.
    """
    apply=lambda Y: Y if precondition is None else lu_solve(precondition,Y,check_finite=True)
    X=np.zeros_like(B); scale=np.linalg.norm(B); history=[]; actions=0
    while actions<max_actions:
        residual=B-A@X;beta=np.linalg.norm(residual)
        if beta<=rtol*scale:break
        V=[residual/beta];Z=[];H=np.zeros((restart+1,restart),complex)
        for j in range(min(restart,max_actions-actions)):
            z=apply(V[j]);Z.append(z);w=A@z;actions+=1
            # Two passes keep the shared basis orthogonal at the requested accuracy.
            for _ in range(2):
                for i,v in enumerate(V):
                    h=np.vdot(v,w);H[i,j]+=h;w-=h*v
            H[j+1,j]=np.linalg.norm(w)
            target=np.zeros(j+2,complex);target[0]=beta
            y=np.linalg.lstsq(H[:j+2,:j+1],target,rcond=None)[0]
            relative=np.linalg.norm(target-H[:j+2,:j+1]@y)/scale
            history.append(float(relative))
            if relative<=rtol or abs(H[j+1,j])<1e-30:
                break
            V.append(w/H[j+1,j])
        for z,c in zip(Z,y):X+=c*z
        if np.linalg.norm(B-A@X)<=rtol*scale:break
    return X,dict(iterations=actions,history=history,true_residual=float(np.linalg.norm(B-A@X)/scale),
        converged=bool(np.linalg.norm(B-A@X)<=rtol*scale))


def block_gmres(A,B,precondition=None,rtol=1e-12,max_blocks=60):
    """Rank-aware full block Arnoldi, sharing the Krylov space across all RHS.

    SVD removes linearly dependent source/receiver columns. Two orthogonalizing
    passes and a true residual check protect the deflated block recurrence.
    """
    apply=lambda Y:Y if precondition is None else lu_solve(precondition,Y)
    scale=np.linalg.norm(B);U,s,Vh=svd(B,full_matrices=False)
    rank=int(np.count_nonzero(s>np.finfo(float).eps*max(B.shape)*s[0]))
    Q=[U[:,:rank]];Z=[];widths=[rank];H=np.empty((rank,0),complex)
    target=Q[0].conj().T@B;history=[];X=np.zeros_like(B)
    for j in range(max_blocks):
        z=apply(Q[-1]);Z.append(z);w=A@z
        action_scale=np.linalg.norm(w)
        oldrows=sum(widths);oldcols=H.shape[1];newcols=z.shape[1]
        column=np.zeros((oldrows,newcols),complex)
        for _ in range(2):
            offset=0
            for q in Q:
                coeff=q.conj().T@w;column[offset:offset+q.shape[1]]+=coeff
                w-=q@coeff;offset+=q.shape[1]
        U,s,Vh=svd(w,full_matrices=False)
        threshold=np.finfo(float).eps*max(A.shape)*action_scale
        next_rank=min(len(A)-oldrows,int(np.count_nonzero(s>threshold)))
        bottom=s[:next_rank,None]*Vh[:next_rank]
        enlarged=np.zeros((oldrows+next_rank,oldcols+newcols),complex)
        enlarged[:oldrows,:oldcols]=H;enlarged[:oldrows,oldcols:]=column
        enlarged[oldrows:,oldcols:]=bottom;H=enlarged
        target=np.pad(target,((0,next_rank),(0,0)))
        y=np.linalg.lstsq(H,target,rcond=None)[0]
        X=np.hstack(Z)@y
        relative=float(np.linalg.norm(B-A@X)/scale);history.append(relative)
        if relative<=rtol or next_rank==0:break
        Q.append(U[:,:next_rank]);widths.append(next_rank)
    return X,dict(iterations=j+1,block_widths=widths,history=history,
        true_residual=relative,converged=bool(relative<=rtol),
        scalar_krylov_columns=int(H.shape[1]))


def accuracy(A,B,R,X,reference,weights):
    ns=B.shape[1]//2
    predict=lambda T:np.einsum('ri,ir->r',R,T[:,:ns])
    pred=predict(reference)
    cutoff=(len(A)//2-1)//2;count=2*cutoff+1
    # Every Fourier weight in Hadamard contraction, so this covers any slider
    # weight in the retained trace product band without replaying preparation.
    from scipy.signal import fftconvolve
    moment=lambda T:fftconvolve(T[:count,:ns],T[:count,ns:],axes=0)
    J=moment(reference)
    actual=lambda T:b7_data_jacobian.hadamard(T[:count,:ns],T[:count,ns:],weights,cutoff,1.)
    actual_ref=actual(reference)
    return dict(jacobian_relative=float(np.linalg.norm(actual(X)-actual_ref)/np.linalg.norm(actual_ref)),jacobian_moment_relative=float(np.linalg.norm(moment(X)-J)/np.linalg.norm(J)),trace_relative=float(np.linalg.norm(X-reference)/np.linalg.norm(reference)),
        forward_relative=float(np.linalg.norm(X[:,:ns]-reference[:,:ns])/np.linalg.norm(reference[:,:ns])),
        reciprocal_relative=float(np.linalg.norm(X[:,ns:]-reference[:,ns:])/np.linalg.norm(reference[:,ns:])),
        prediction_relative=float(np.linalg.norm(predict(X)-pred)/np.linalg.norm(pred)),
        residual=float(np.linalg.norm(A@X-B)/np.linalg.norm(B)))


def solves(path):
    path=path.resolve()
    data=np.load(path);A=data['current_A'];B=data['B'];R=data['R']
    anchor=data['anchor_A'] if 'anchor_A' in data else np.load(path.with_name(path.stem+'_anchor.npz'))['anchor_A']
    reference=lu_solve(lu_factor(A),B);records=[]
    scales=np.linalg.norm(B,axis=0);balanced=B/scales[None,:]
    output_stem=path.stem+'_balanced'
    name=path.stem.split('_Ku')[0];curve=inputs()[name]
    space=SliderUpdate(.05,device='cpu').prepare(curve,67 if name=='final' else 11,curve.band)
    weights=b7_data_jacobian.normal_velocity_weights(curve.coefficients,space.derivatives)
    # LU setup and both 24-column solves match the production separation.
    anchor_times=[]
    for repeat in range(3):
        started=perf_counter();P=lu_factor(anchor);anchor_times.append(perf_counter()-started)
        started=perf_counter();factor=lu_factor(A);factor_seconds=perf_counter()-started
        started=perf_counter();X=np.hstack((lu_solve(factor,B[:,:24]),lu_solve(factor,B[:,24:])))
        solve_seconds=perf_counter()-started
        records.append(dict(method='LU',repeat=repeat,seconds=factor_seconds+solve_seconds,
            factor_seconds=factor_seconds,solve_seconds=solve_seconds,accuracy=accuracy(A,B,R,X,reference,weights)))
        write(OUT/(output_stem+'_partial.json'),dict(records=records,machine=machine()))
    for method,prec,solver in [('cold_global_GMRES',None,global_gmres),('anchored_global_GMRES',P,global_gmres),
                              ('cold_block_GMRES',None,block_gmres),('anchored_block_GMRES',P,block_gmres)]:
        if len(A)>514 and method.startswith('cold_'):
            continue  # Larger sizes answer anchored crossover, not another cold baseline.
        for repeat in range(3):
            started=perf_counter();Y,info=solver(A,balanced,prec);X=Y*scales[None,:];elapsed=perf_counter()-started
            records.append(dict(method=method,repeat=repeat,seconds=elapsed,**info,
                                accuracy=accuracy(A,B,R,X,reference,weights)))
            write(OUT/(output_stem+'_partial.json'),dict(records=records,machine=machine()))
    # Error operator for stationary anchor corrections. Its norm need not be <1
    # for GMRES convergence; exact singular norm and spectral radius are saved.
    E=np.eye(len(A),dtype=complex)-A@lu_solve(P,np.eye(len(A)))
    norm=float(np.linalg.norm(E,2));radius=float(np.max(abs(np.linalg.eigvals(E))))
    for row in records:
        h=row.get('history',[])
        row['observed_residual_ratio']=float((h[-1]/h[0])**(1/(len(h)-1))) if len(h)>1 and h[0]>0 else None
    result=dict(input=str(path.relative_to(ROOT)),matrix_shape=A.shape,rhs=B.shape[1],machine=machine(),
        anchor_factor_seconds=anchor_times,right_residual_operator_norm_2=norm,right_residual_operator_spectral_radius=radius,
        rhs_column_norms=scales,rhs_scaling='per-column unit norm for Krylov; original physical units restored for accuracy',records=records)
    write(OUT/(output_stem+'_solves.json'),result)
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['profile','assemble','solve'])
    parser.add_argument('--state',default='release',choices=['release','final','large'])
    parser.add_argument('--Ku',type=int,default=64);parser.add_argument('--path',type=Path)
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if not (OUT/'manifest.json').exists():save_manifest()
    try:
        if args.step=='profile':profile(args.state,args.Ku)
        elif args.step=='assemble':assemble(args.state,args.Ku)
        else:solves(args.path)
    except Exception:
        write(OUT/f'failed_{args.step}_{args.state}_Ku{args.Ku}.json',dict(args=vars(args),
            traceback=traceback.format_exc(),machine=machine()));raise

if __name__=='__main__':main()
