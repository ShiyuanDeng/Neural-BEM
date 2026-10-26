"""HB-003 physical Schur, local ROM and residual-bound experiments."""
from pathlib import Path
from time import perf_counter
import os
import subprocess
import traceback
import numpy as np
from scipy.linalg import lu_factor, lu_solve, svd, svdvals
from bem_inverse.io import read, write, digest
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.forward_solvers import modal_muller as mm
from bem_inverse.physics import Execution
from bem_inverse.b5_residual import normalize
from experiments.linear_solves.is001 import inputs, observations
from experiments.benchmark.campaign import problem

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'results/validation/cleaned_interfaces'
OUT=BASE/'HB-003-response'

def machine():
    return dict(affinity=sorted(os.sched_getaffinity(0)),load=os.getloadavg(),
        revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        blas={k:os.getenv(k) for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']},
        gpu=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader'],capture_output=True,text=True).stdout.strip())

def solve(A,B):return lu_solve(lu_factor(A),B)
def paired(R,X):return np.einsum('ri,ir->r',R,X)
def relative(x,y):return float(np.linalg.norm(x-y)/max(np.linalg.norm(y),1e-300))
def timed(fun):
    tt=[]
    for _ in range(3):
        start=perf_counter();value=fun();tt.append(perf_counter()-start)
    return value,float(np.median(tt))

def schur():
    rows=[]
    for state,N in [('release',64),('final',128)]:
      for frequency in ['real','damped']:
        path=BASE/f'IS-001/{state}_Ku{N}_{frequency}.npz'
        data=np.load(path);A=data['current_A'];B=data['B'][:,:24];R=data['R']
        X,tfull=timed(lambda:solve(A,B));F=paired(R,X);n=2*N+1
        for keep in [N//4,N//2]:
          local=np.flatnonzero(abs(np.arange(-N,N+1))<=keep)
          L=np.r_[local,local+n];H=np.setdiff1d(np.arange(2*n),L)
          LL=A[np.ix_(L,L)];LH=A[np.ix_(L,H)];HL=A[np.ix_(H,L)];HH=A[np.ix_(H,H)]
          def eliminate(kind,q=0):
            if kind=='exact':Zrhs=solve(HH,np.hstack([HL,B[H]]))
            else:
              d=1/np.diag(HH);rhs=np.hstack([HL,B[H]]);term=d[:,None]*rhs;Zrhs=term.copy()
              for _ in range(q):term=term-d[:,None]*(HH@term);Zrhs+=term
            ZA=Zrhs[:,:len(L)];ZB=Zrhs[:,len(L):]
            S=LL-LH@ZA;be=B[L]-LH@ZB
            xl=solve(S,be)
            # Observation elimination includes both effective receiver and direct term.
            return paired(R[:,L]-R[:,H]@ZA,xl)+paired(R[:,H],ZB)
          exact,te=timed(lambda:eliminate('exact'))
          drop,td=timed(lambda:paired(R[:,L],solve(LL,B[L])))
          E=np.eye(len(H))-HH/np.diag(HH)[:,None]
          start=perf_counter();norm=float(svdvals(E)[0]);radius=float(max(abs(np.linalg.eigvals(E))));diagnostic_time=perf_counter()-start
          row=dict(state=state,N=N,frequency=frequency,keep=keep,n=len(A),low_size=len(L),high_size=len(H),source=str(path.relative_to(ROOT)),sha256=digest(path),full_seconds=tfull,exact_seconds=te,exact_error=relative(exact,F),drop_seconds=td,drop_error=relative(drop,F),high_inverse_defect_norm=norm,high_inverse_defect_radius=radius,defect_diagnostic_seconds=diagnostic_time,approx=[])
          for q in [0,2,4]:
            approx,t=timed(lambda:eliminate('approx',q));row['approx'].append(dict(q=q,seconds=t,error=relative(approx,F)))
          assert row['exact_error']<1e-9,row
          rows.append(row);write(OUT/'schur.json',dict(machine=machine(),rows=rows))
    return rows

def orth(columns):
    columns=columns/np.maximum(np.linalg.norm(columns,axis=0),1e-300)
    U,s,_=svd(columns,full_matrices=False)
    rank=int(np.sum(s>s[0]*1e-13))
    return U[:,:rank],s

def rom():
    curves=inputs();c0=curves['large_anchor'].coefficients;dc=curves['large'].coefficients-c0
    summary=[]
    for frequency,obs in observations().items():
      folder=OUT/f'rom_{frequency}';folder.mkdir(exist_ok=True)
      captured={}
      def observer(kind,data):
        if kind=='field':captured.update(data)
      context=mm.ModalMuller(Execution(device='cpu',frequency_threads=1),settings=mm.ModalSettings(cached_geometries=1),observer=observer)
      def assemble(alpha):
        captured.clear();start=perf_counter()
        pred=mm.forward_solve(FourierCurve(c0+alpha*dc),obs,13.3,mm.token(64),context=context)
        elapsed=perf_counter()-start
        A=captured['A'].copy();B=captured['B_s'].copy();R=captured['R'].copy();X=captured['X_s'].copy()
        np.savez_compressed(folder/f'alpha_{alpha:g}.npz',A=A,B=B,R=R,X=X)
        return dict(A=A,B=B,R=R,X=X,F=pred.prediction,assembly_seconds=elapsed)
      anchor=assemble(0.)
      start=perf_counter();dual=solve(anchor['A'].conj().T,anchor['R'].conj().T);V,s=orth(np.hstack([anchor['X'],dual]));base_setup=perf_counter()-start
      plus=assemble(.001);minus=assemble(-.001)
      start=perf_counter()
      dX=(plus['X']-minus['X'])/.002
      dY=(solve(plus['A'].conj().T,plus['R'].conj().T)-solve(minus['A'].conj().T,minus['R'].conj().T))/.002
      Ve,se=orth(np.hstack([anchor['X'],dual,dX,dY]));enrichment_setup=perf_counter()-start
      rows=[]
      for alpha in [0.,1.,.5,.25,.125,.0625]:
        target=anchor if alpha==0 else assemble(alpha)
        A,B,R,F=tuple(target[k] for k in ['A','B','R','F'])
        _,full_time=timed(lambda:paired(R,solve(A,B)))
        start=perf_counter();inverse_norm=1/float(svdvals(A)[-1]);bound_setup=perf_counter()-start
        for name,basis in [('base',V),('enriched',Ve)]:
          def project():
            Ar=basis.conj().T@A@basis;Br=basis.conj().T@B;Rr=R@basis
            factors=lu_factor(Ar);xr=lu_solve(factors,Br)
            return paired(Rr,xr),basis@xr,Ar,factors
          (Fr,Xr,Ar,factors),online=timed(project)
          start=perf_counter()
          Yr=basis@lu_solve(factors,basis.conj().T@R.conj().T,trans=2)
          rp=B-A@Xr;rd=R.conj().T-A.conj().T@Yr
          corr=paired(Yr.conj().T,rp);Fcorr=Fr+corr
          identity=paired(rd.conj().T,solve(A,rp))
          bounds=inverse_norm*np.linalg.norm(rd,axis=0)*np.linalg.norm(rp,axis=0)
          actual=abs(F-Fcorr)
          scale=np.linalg.norm(obs.scattered);epsilon=np.linalg.norm(bounds)/scale
          rhat=normalize((Fcorr-obs.scattered)[:,None],obs.scattered[:,None],[1.])
          rtrue=normalize((F-obs.scattered)[:,None],obs.scattered[:,None],[1.])
          objective_bound=epsilon*np.linalg.norm(rhat)+.5*epsilon**2
          objective_error=abs(.5*(rtrue@rtrue-rhat@rhat))
          bound_online=perf_counter()-start
          row=dict(alpha=alpha,model=name,rank=basis.shape[1],n=len(A),error=relative(Fr,F),full_solve_seconds=full_time,online_seconds=online,assembly_seconds=target['assembly_seconds'],inverse_norm_estimate=inverse_norm,inverse_norm_seconds=bound_setup,bound_online_seconds=bound_online,dual_identity_absolute_error=float(np.linalg.norm(F-Fcorr-identity)),corrected_error=relative(Fcorr,F),bound_relative=float(np.linalg.norm(bounds)/np.linalg.norm(F)),bound_over_actual=float(np.linalg.norm(bounds)/max(np.linalg.norm(actual),1e-300)),all_channels_covered_without_allowance=bool(np.all(actual<=bounds)),coverage_with_roundoff_allowance=bool(np.all(actual<=bounds+1e-12*np.linalg.norm(F))),bound_norm_covers_error=bool(np.linalg.norm(actual)<=np.linalg.norm(bounds)),objective_bound=float(objective_bound),objective_actual_error=float(objective_error),projected_condition=float(np.linalg.cond(Ar)))
          assert row['coverage_with_roundoff_allowance'],row
          rows.append(row)
          write(folder/'rows.json',dict(machine=machine(),rows=rows))
      item=dict(frequency=frequency,base_rank=V.shape[1],enriched_rank=Ve.shape[1],base_setup_seconds=base_setup,enrichment_setup_seconds=enrichment_setup,enrichment_physics_seconds=plus['assembly_seconds']+minus['assembly_seconds'],anchor_physics_seconds=anchor['assembly_seconds'],rows=rows)
      for name in ['base','enriched']:
        selected=[r for r in rows if r['model']==name and r['alpha']>0]
        item[name+'_adjacent_slopes']=[float(np.log2(a['error']/b['error'])) for a,b in zip(selected,selected[1:])]
      summary.append(item);write(OUT/'rom.json',dict(machine=machine(),summary=summary))
    return summary

def unpack(value):
    if isinstance(value,dict) and set(value)=={'real','imag'}:return value['real']+1j*value['imag']
    if isinstance(value,list):return [unpack(v) for v in value]
    return value

def lm():
    path=BASE/'FI-001/hook_release/exact_outputs.json';data=read(path)
    fields=np.asarray(unpack(data['fields']));jac=np.asarray(unpack(data['jacobians']))
    p=problem('hook__c13.3');obs=np.column_stack([o.scattered for o in p.real]);w=np.ones(19)/19
    r=normalize(fields.T-obs,obs,w);J=normalize(jac.transpose(1,0,2),obs,w)
    G=J.T@J;g=J.T@r;metric=np.maximum(np.diag(G),1e-12);rows=[]
    for lam in [1e-6,1e-3,1.]:
      H=G+lam*np.diag(metric);start=perf_counter();exact=np.linalg.solve(H,-g);full_time=perf_counter()-start
      # Standard CG on the symmetrically scaled SPD equation, exactly five iterations.
      invroot=1/np.sqrt(metric);Hs=invroot[:,None]*H*invroot[None,:];rhs=-invroot*g
      x=np.zeros_like(rhs);rr=rhs.copy();direction=rr.copy()
      for iteration in range(1,6):
        v=Hs@direction;old=rr@rr;step=old/(direction@v);x+=step*direction;rr-=step*v;direction=rr+(rr@rr/old)*direction
        dhat=invroot*x;start=perf_counter();defect=H@dhat+g;bound=np.linalg.norm(invroot*defect)/lam;bound_time=perf_counter()-start
        actual=np.linalg.norm(np.sqrt(metric)*(dhat-exact))
        row=dict(lam=lam,iteration=iteration,bound=float(bound),actual=float(actual),bound_over_actual=float(bound/actual),bound_seconds=bound_time,full_solve_seconds=full_time,covered=bool(actual<=bound*(1+1e-10)))
        assert row['covered'],row
        rows.append(row)
    write(OUT/'lm.json',dict(source=str(path.relative_to(ROOT)),sha256=digest(path),J_shape=J.shape,metric='Marquardt diagonal max(diag(JTJ),1e-12)',machine=machine(),rows=rows))

def main():
    write(OUT/'manifest.json',dict(machine=machine(),source_sha256=digest(Path(__file__)),plan_sha256=digest(ROOT/'docs/iterations/haibing_2026-10-26/response/03_plan.md')))
    try:
        schur();print('Schur complete',flush=True)
        lm();print('LM complete',flush=True)
        rom();print('ROM complete',flush=True)
    except Exception:
        (OUT/'failure.txt').write_text(traceback.format_exc());raise

if __name__=='__main__':main()
