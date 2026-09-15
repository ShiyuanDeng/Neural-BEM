"""Counted production forward wrappers and frozen saved geometry inputs."""
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import resource
import time
import numpy as np
from scipy.linalg import lu_factor, lu_solve
from scipy.special import hankel1
from ordered_boundary import OrderedBoundary2D, fourier_curve
from gpr_bem_kress import Material
from gpr_bem_kress.multicomponent import (
    MultiComponentAssemblyConfig, MultiComponentKressSolveConfig,
    build_multicomponent_kress_tmz_frequency_system,
    multicomponent_incident_trace_on_boundary,
    build_multicomponent_exterior_receiver_operator,
    _validate_exterior_points,
)
from gpr_bem_kress.shape_derivative import KressDirection
from sdf_inverse.explicit_fourier import CartesianFourierCurveState
from sdf_inverse.radial_topology import MultiRadialFourierState, component_radius_floor
from sdf_inverse.geometry import OrderedSDFGeometryConfig

LIMITS = dict(assemblies=800, derivatives=300, factorizations=600, solves=1000)
SOLVE_CONFIG = MultiComponentKressSolveConfig(
    assembly=MultiComponentAssemblyConfig(minimum_absolute_clearance=.010))
TOP018 = Path('results/validation/topology/TOP-018-20260915-resolution-qualified-pair')
TOP023 = Path('results/validation/topology/TOP-023-20260915-181302-terminal-model')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def json_default(value):
    if isinstance(value,np.ndarray):
        return value.tolist()
    if isinstance(value,np.generic):
        return value.item()
    if isinstance(value,Path):
        return str(value)
    raise TypeError(type(value))


def write_json(path,value):
    Path(path).write_text(json.dumps(value,indent=2,default=json_default,allow_nan=False)+'\n')


def complex_record(value):
    a=np.asarray(value)
    return dict(real=a.real.tolist(),imag=a.imag.tolist())


class Stop(RuntimeError):
    pass


class Ledger:
    def __init__(self,path,hashes):
        self.path=Path(path); self.hashes=hashes; self.counts=dict.fromkeys(LIMITS,0)
        self.context={}; self.started=time.perf_counter(); self.paused_seconds=0.

    def seconds(self):
        return time.perf_counter()-self.started-self.paused_seconds

    def guard(self):
        changed=[p for p,h in self.hashes.items() if digest(p)!=h]
        if changed:raise Stop('SOURCE_DRIFT: '+', '.join(changed))

    def check(self,costs=None):
        if self.seconds()>=1800:raise Stop('BUDGET_STOP: numerical time')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>=8*1024**3:
            raise Stop('BUDGET_STOP: RSS')
        for k,v in (costs or {}).items():
            if self.counts[k]+v>LIMITS[k]:raise Stop('BUDGET_STOP: '+k)

    def emit(self,operation,status,seconds=None,**details):
        record=dict(timestamp=datetime.now(timezone.utc).isoformat(),**self.context,
                    operation=operation,status=status,seconds=seconds,
                    numerical_seconds=self.seconds(),counts=self.counts.copy(),
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,**details)
        with self.path.open('a') as stream:stream.write(json.dumps(record,default=json_default)+'\n')

    def call(self,name,fn,costs=None,**details):
        costs=costs or {};self.check(costs)
        for k,v in costs.items():self.counts[k]+=v
        self.emit(name,'attempted',reserved=costs,**details)
        tick=time.perf_counter()
        try:value=fn()
        except BaseException as exc:
            self.emit(name,'failed',time.perf_counter()-tick,reason=repr(exc),**details)
            raise
        seconds=time.perf_counter()-tick
        self.emit(name,'completed',seconds,**details);self.check()
        return value,seconds


def deserialize(records):
    components=[]
    for r in records:
        if r['chart']!='cartesian':raise ValueError('Frozen fixtures are Cartesian.')
        v=np.array(r['parameters']); cut=2*(r['maximum_mode']+1)
        components.append(CartesianFourierCurveState(v[:cut].reshape(-1,2),
            np.vstack((np.zeros(2),v[cut:].reshape(-1,2))),r['component_id']))
    return MultiRadialFourierState(tuple(components))


def frozen_inputs():
    acquisition_path=TOP018/'inputs/far-two-stars/observations.json'
    original=json.loads(acquisition_path.read_text())
    sources,receivers=np.array(original['source_points']),np.array(original['receiver_points'])
    assert sources.shape==receivers.shape==(24,2)
    assert original['source_strengths_real']==[1e-6]*3 and original['source_strengths_imag']==[0.]*3
    acquisition={k:original[k] for k in ('source_points','receiver_points','eps0','mu0','exterior','interior')}
    acquisition.update(source_strength=1e-6,frequencies_hz=[500_000_000,1_250_000_000])
    common_path=TOP018/'inputs/far-two-stars/state.json'
    common_training=TOP018/'inputs/far-two-stars/training_observations.json'
    terminal_path=TOP023/'inputs.json'
    terminal=json.loads(terminal_path.read_text())
    records=[dict(id='common',state=json.loads(common_path.read_text()),
                  training=json.loads(common_training.read_text()),source=str(common_path)),
             dict(id='terminal',state=terminal['state'],training=terminal['training'],source=str(terminal_path))]
    paths=[acquisition_path,common_path,common_training,terminal_path]
    return acquisition,records,{str(p):digest(p) for p in paths}


def geometry_config(nodes):
    return OrderedSDFGeometryConfig(bounds=((.2,.2),(.8,.8)),num_nodes=nodes,
                                    validation_resolution=1024)


def state_boundary(state,nodes):
    if any(component_radius_floor(c)<.008 for c in state.components):
        raise ValueError('Production component radius floor refused state')
    return state.boundary(geometry_config(nodes))


def retract(state,direction,step):
    raw=state.incremented(step*direction)
    regauged,_=raw.polar_angle_gauge_fixed()
    delta=max(float(np.linalg.norm(a.cosine_coefficients-b.cosine_coefficients,axis=1).sum()
                    +np.linalg.norm(a.sine_coefficients-b.sine_coefficients,axis=1).sum())
              for a,b in zip(raw.components,regauged.components))
    if delta>1e-10:raise Stop(f'GAUGE_PATH_UNQUALIFIED: retraction changes coefficients by {delta:.3e} m')
    return regauged,delta


def state_directions(state,boundary,direction):
    result=[]
    for component,sl,curve in zip(state.components,state.parameter_slices,boundary.components):
        v=direction[sl];cut=2*(component.maximum_mode+1)
        p=fourier_curve(v[:cut].reshape(-1,2),np.vstack((np.zeros(2),v[cut:].reshape(-1,2))),
                        component_id=component.component_id,period=curve.period)
        evaluation=p.evaluate(curve.parameters)
        result.append(KressDirection(*[getattr(evaluation,n) for n in
            ('points','first_derivatives','second_derivatives','third_derivatives')]))
    return tuple(result)


@dataclass
class Base:
    system: object
    receiver: object
    A: np.ndarray
    B: np.ndarray
    C: np.ndarray
    U: np.ndarray
    Y: np.ndarray
    factors: tuple
    sources: np.ndarray
    receivers: np.ndarray
    strengths: np.ndarray
    incident: np.ndarray
    times: dict
    material_args: dict


def forward(boundary,frequency,acquisition,ledger):
    sources=np.array(acquisition['source_points']);receivers=np.array(acquisition['receiver_points'])
    strengths=np.full(len(sources),acquisition['source_strength'],complex)
    args={k:Material(**acquisition[k]) for k in ('exterior','interior')}
    args.update({k:acquisition[k] for k in ('eps0','mu0')})
    clearance=SOLVE_CONFIG.minimum_field_point_clearance_in_weights*float(np.max(boundary.arc_length_weights))
    for points,name in ((sources,'source_points'),(receivers,'receiver_points')):
        ledger.call('field_point_validation',lambda:_validate_exterior_points(points,boundary,
                    name=name,minimum_clearance=clearance))
    system,ta=ledger.call('system_assembly',lambda:build_multicomponent_kress_tmz_frequency_system(
        boundary,2*np.pi*frequency,**args,config=SOLVE_CONFIG.assembly),dict(assemblies=1),n=2*boundary.num_nodes)
    (bd,bn),tb=ledger.call('incident_rhs',lambda:multicomponent_incident_trace_on_boundary(
        boundary,sources,system.k_exterior,strengths))
    receiver,tc=ledger.call('receiver_operator',lambda:build_multicomponent_exterior_receiver_operator(
        boundary,receivers,system.k_exterior))
    A,B,C=system.system_matrix,np.concatenate((bd,bn),axis=1).T,receiver.state_rows
    factors,tf=ledger.call('lu_factor',lambda:lu_factor(A),dict(factorizations=1),n=len(A))
    U,ts=ledger.call('primal_rhs_solve',lambda:lu_solve(factors,B),dict(solves=1),rhs_count=len(sources))
    Y,te=ledger.call('receiver_evaluation',lambda:C@U)
    incident=strengths[:,None]*.25j*hankel1(0,system.k_exterior*np.linalg.norm(
        receivers[None,:,:]-sources[:,None,:],axis=-1))
    residual=float(np.linalg.norm(A@U-B)/np.linalg.norm(B))
    if residual>1e-10:raise Stop('PRIMAL_SOLVE_UNQUALIFIED')
    return Base(system,receiver,A,B,C,U,Y,factors,sources,receivers,strengths,incident,
                dict(assembly=ta,rhs=tb,receiver_operator=tc,factorization=tf,solve=ts,evaluation=te),args)


def tangent(base,operators,ledger):
    ledger.emit('base_lu','reused',0.,rhs_count=base.B.shape[1])
    dU,ts=ledger.call('tangent_rhs_solve',lambda:lu_solve(base.factors,
        operators.dB-operators.dA@base.U),dict(solves=1),rhs_count=base.B.shape[1])
    dY,te=ledger.call('tangent_receiver_evaluation',lambda:operators.dC@base.U+base.C@dU)
    return dY,dict(tangent_solve=ts,tangent_evaluation=te)


def relative(first,second,floor=1e-300):
    return float(np.linalg.norm(first-second)/max(np.linalg.norm(second),floor))


def external_numerical_processes():
    """Record sibling repository numerical workers without touching them."""
    found=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==os.getpid():continue
        try:
            tokens=(p/'cmdline').read_bytes().split(b'\0')
            if not tokens or b'python' not in tokens[0]:continue
            command=b' '.join(tokens).decode(errors='replace')
            if any(s in command for s in ('experiments.top','experiments/top','run_top','run_fourier','run_bie','bie004_multi_derivative')):
                found.append(dict(pid=int(p.name),command=command))
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    return found
