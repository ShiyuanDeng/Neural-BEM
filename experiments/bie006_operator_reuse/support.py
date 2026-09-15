"""Counted wrappers around unchanged production single-interface factories."""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import os
import resource
import time
import numpy as np
from scipy.linalg import lu_factor,lu_solve
from scipy.special import hankel1
from ordered_boundary import BoundaryValidationConfig,validate_periodic_parameterization
from gpr_bem_kress import Material,KressSolveConfig
from gpr_bem_kress.system import build_kress_tmz_frequency_system
from gpr_bem_kress.forward import (kress_incident_trace_on_boundary,
    build_exterior_receiver_operator,KressTMzForwardResult,_validate_exterior_points)
from gpr_bem_kress.shape_derivative import KressDirection,_directional_operators
from .fixtures import producer

LIMITS=dict(exact_assemblies=60,analytic_assemblies=24,factorizations=100,
            solves=150,updated_solves=30)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encode(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,Path):return str(value)
    raise TypeError(type(value).__name__)


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,default=encode,allow_nan=False)+'\n')


def relative(value,reference,floor=1e-300):
    return float(np.linalg.norm(value-reference)/max(np.linalg.norm(reference),floor))


def numerical_workers():
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            tokens=(p/'cmdline').read_bytes().split(b'\0')
            if not tokens or b'python' not in tokens[0]:continue
            command=b' '.join(tokens).decode(errors='replace')
            if any(s in command for s in ('experiments.','experiments/','run_top','run_fourier','run_bie','run_explicit','pytest')):
                found.append(dict(pid=int(p.name),command=command))
        except (OSError,ProcessLookupError):pass
    return found


class Stop(RuntimeError):
    pass


class Ledger:
    def __init__(self,output,hashes):
        self.output=Path(output);self.hashes=hashes;self.context={}
        self.counts=dict.fromkeys(LIMITS,0);self.started=time.perf_counter()

    def guard(self):
        changed=[p for p,h in self.hashes.items() if digest(p)!=h]
        if changed:raise Stop('SOURCE_DRIFT: '+','.join(changed))

    def check(self,costs=None):
        if time.perf_counter()-self.started>=900:raise Stop('BUDGET_STOP: 900 seconds')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>=4*1024**3:
            raise Stop('BUDGET_STOP: 4 GiB')
        for key,value in (costs or {}).items():
            if self.counts[key]+value>LIMITS[key]:raise Stop('BUDGET_STOP: '+key)

    def emit(self,operation,status,seconds=None,**extra):
        row=dict(timestamp=datetime.now(timezone.utc).isoformat(),**self.context,
                 operation=operation,status=status,seconds=seconds,
                 counts=self.counts.copy(),elapsed_seconds=time.perf_counter()-self.started,
                 peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,**extra)
        with (self.output/'work_ledger.jsonl').open('a') as stream:
            stream.write(json.dumps(row,default=encode,allow_nan=False)+'\n')

    def call(self,name,fn,costs=None,**extra):
        costs=costs or {};self.check(costs)
        for k,v in costs.items():self.counts[k]+=v
        self.emit(name,'attempted',reserved=costs,**extra);tick=time.perf_counter()
        try:value=fn()
        except BaseException as exc:
            self.emit(name,'failed',time.perf_counter()-tick,reason=repr(exc),**extra);raise
        seconds=time.perf_counter()-tick
        self.emit(name,'completed',seconds,**extra);self.check()
        return value,seconds


def geometry(c,s,n,acq):
    parameterization=producer(c,s)
    report=validate_periodic_parameterization(parameterization,
        BoundaryValidationConfig(num_samples_per_component=1024,fourier_bandwidth=3),raise_on_error=True)
    points=parameterization.evaluate(np.arange(1024)*2*np.pi/1024).points
    if np.any(points<.2) or np.any(points>.8):raise ValueError('Fixed geometry bounds refused')
    curve=parameterization.discretize(n,require_even=True)
    clearance=max(.01,2*float(curve.arc_length_weights.max()))
    distances={}
    for name in ('source_points','receiver_points'):
        distances[name]=_validate_exterior_points(np.asarray(acq[name]),curve,name=name,
                                                  minimum_clearance=clearance)
    return curve,dict(report=report.to_dict(),required_clearance_m=clearance,distances_m=distances)


def forward(c,s,n,frequency,acq,ledger):
    tick=time.perf_counter();times={}
    (curve,geo),times['geometry']=ledger.call('geometry_validation',lambda:geometry(c,s,n,acq))
    sources=np.asarray(acq['source_points']);receivers=np.asarray(acq['receiver_points'])
    strengths=np.full(len(sources),acq['source_strength'],complex)
    args={name:Material(**acq[name]) for name in ('exterior','interior')}
    args.update({name:acq[name] for name in ('eps0','mu0')})
    system,times['assembly']=ledger.call('exact_system_assembly',
        lambda:build_kress_tmz_frequency_system(curve,2*np.pi*frequency,**args),dict(exact_assemblies=1))
    (bd,bn),times['rhs']=ledger.call('incident_rhs',lambda:kress_incident_trace_on_boundary(
        curve,sources,system.k_exterior,strengths))
    receiver,times['receiver_operator']=ledger.call('receiver_operator',lambda:build_exterior_receiver_operator(
        curve,receivers,system.k_exterior))
    a,b,cc=system.system_matrix,np.concatenate((bd,bn),axis=1).T,receiver.state_rows
    factors,times['factorization']=ledger.call('exact_lu',lambda:lu_factor(a),dict(factorizations=1))
    u,times['solve']=ledger.call('exact_rhs_solve',lambda:lu_solve(factors,b),dict(solves=1),rhs_count=len(sources))
    y,times['evaluation']=ledger.call('exact_receiver_evaluation',lambda:cc@u)
    def finish():
        direct=strengths[:,None]*.25j*hankel1(0,system.k_exterior*np.linalg.norm(
            receivers[None,:,:]-sources[:,None,:],axis=-1))
        residual=float(np.linalg.norm(a@u-b)/np.linalg.norm(b))
        if residual>1e-10:raise Stop('EXACT_SOLVE_UNQUALIFIED')
        base=KressTMzForwardResult(system=system,solve_config=KressSolveConfig(),
            exterior_material=args['exterior'],interior_material=args['interior'],eps0=args['eps0'],mu0=args['mu0'],
            receiver_operator=receiver,source_points=sources,receiver_points=receivers,source_strengths=strengths,
            right_hand_side=b,solution=u,dirichlet_incident=bd,neumann_incident=bn,
            dirichlet_total=u[:n].T,neumann_total=u[n:].T,incident_receiver=direct,
            single_receiver=(receiver.single_layer_rows@u[n:]).T,
            double_receiver=(receiver.double_layer_rows@u[:n]).T,scattered_receiver=y.T,total_receiver=y.T+direct,
            linear_system_relative_residual=residual,
            per_source_relative_residual=np.linalg.norm(a@u-b,axis=0)/np.linalg.norm(b,axis=0),
            incident_representation_leak=float(np.linalg.norm(cc@b)/np.linalg.norm(direct)),
            solve_seconds=times['factorization']+times['solve'],
            receiver_evaluation_seconds=times['receiver_operator']+times['evaluation'],
            total_seconds=0.,diagnostics={})
        return base
    base,times['checks_and_result']=ledger.call('forward_checks',finish)
    return SimpleNamespace(A=a,B=b,C=cc,U=u,Y=y,factors=factors,curve=curve,base=base,
                           times=times,seconds=sum(times.values()),wall_seconds=time.perf_counter()-tick,geometry=geo)


def derivative(base,direction,ledger):
    def assemble():
        ev=producer(np.asarray(direction['cosine']),np.asarray(direction['sine'])).evaluate(base.curve.parameters)
        return _directional_operators(base.base,KressDirection(*[getattr(ev,name) for name in
            ('points','first_derivatives','second_derivatives','third_derivatives')]))
    op,seconds=ledger.call('analytic_directional_operators',assemble,dict(analytic_assemblies=1),
                           primal_kernel_recomputations=1)
    return (op.d_system_matrix,op.d_right_hand_side,op.d_receiver_matrix),seconds,dict(op.diagnostics)
