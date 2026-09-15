"""Bounded BIE-004 fixed-topology qualification; no inverse or shared writes."""
from __future__ import annotations
import os
import time
PROGRAM_STARTED=time.perf_counter()
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[key]='1'
import argparse
from dataclasses import asdict
from pathlib import Path
import gc
import json
import platform
import resource
import signal
import subprocess
import sys
import traceback
import numpy as np
import scipy
from ordered_boundary import OrderedBoundary2D, PeriodicCurve2D, circle, fourier_curve
from gpr_bem_kress import solve_kress_tmz_total_field_batch
from gpr_bem_kress.shape_derivative import KressDirection, linearize_kress_forward
from sdf_inverse.optimization import normalized_complex_residual
from .operators import directional_operators
from .support import (LIMITS,SOLVE_CONFIG,Ledger,Stop,write_json,digest,complex_record,
    frozen_inputs,deserialize,geometry_config,state_boundary,retract,state_directions,
    forward,tangent,relative,external_numerical_processes)

PLAN=Path('docs/iterations/boundary_bie/iteration_02/03_plan.md')
FREQUENCIES=(500_000_000,1_250_000_000)


def pair(y):
    return np.diag(y.T)


def residual_direction(y,observed):
    obs=np.asarray(observed).reshape(-1,1)
    # Invoke the production fixed residual transform. It is linear in the
    # prediction increment while observations and weights remain fixed.
    return normalized_complex_residual(obs+pair(y)[:,None],obs)[0]


def shifted_boundary(boundary,directions,step):
    result=[]
    for curve,direction in zip(boundary.components,directions):
        names=('points','first_derivatives','second_derivatives','third_derivatives')
        jets=[getattr(curve,name)+step*(0 if getattr(direction,name) is None else getattr(direction,name))
              for name in names]
        result.append(PeriodicCurve2D(curve.component_id,curve.parameters,*jets,period=curve.period))
    return OrderedBoundary2D(tuple(result))


def operator_error_rows(base,analytic,plus,minus,step,ell):
    size=base.system.geometry.num_nodes
    scaling=np.r_[np.ones(size),np.full(size,ell)]
    aa=analytic.dA*scaling[:,None]/scaling[None,:]
    fa=(plus.A-minus.A)/(2*step)*scaling[:,None]/scaling[None,:]
    ba=base.A*scaling[:,None]/scaling[None,:]
    rows=[]
    boundary=base.system.geometry
    def report(label,a,fd,parent,**metadata):
        error=float(np.linalg.norm(a-fd));norm=float(np.linalg.norm(fd))
        source=float(np.linalg.norm(parent))
        zero=float(np.linalg.norm(a))<=1e-10*source/ell
        allowance=100*np.finfo(float).eps/step*source
        passed=error<=1e-4*norm+allowance
        rows.append(dict(operator=label,**metadata,step=step,absolute_error=error,
            relative_error=None if zero else error/max(norm,1e-12*source/ell,1e-300),
            analytic_norm=float(np.linalg.norm(a)),fd_norm=norm,zero_control=zero,
            absolute_roundoff_allowance=allowance,passed=bool(passed)))
    for tr in range(2):
        for tc in range(2):
            for i,rs0 in enumerate(boundary.component_slices):
                for j,cs0 in enumerate(boundary.component_slices):
                    rs=slice(rs0.start+tr*size,rs0.stop+tr*size)
                    cs=slice(cs0.start+tc*size,cs0.stop+tc*size)
                    report('A',aa[rs,cs],fa[rs,cs],ba[rs,cs],trace_row=tr,trace_column=tc,
                           target_component=i,source_component=j,interaction='self' if i==j else 'cross')
    report('B',analytic.dB*scaling[:,None],(plus.B-minus.B)/(2*step)*scaling[:,None],base.B*scaling[:,None])
    report('C',analytic.dC/scaling[None,:],(plus.C-minus.C)/(2*step)/scaling[None,:],base.C/scaling[None,:])
    return rows


class Experiment:
    def __init__(self,output,ledger,acquisition,records):
        self.output=output;self.ledger=ledger;self.acq=acquisition;self.records=records
        self.controls=[];self.operator_checks=[];self.direction_checks=[]
        self.jacobians=[];self.refinements=[];self.taylor=[];self.timings=[];self.gauge=[]
        self.checkpoint()

    def checkpoint(self):
        for name in ('controls','operator_checks','direction_checks','jacobians','refinements','taylor','timings','gauge'):
            write_json(self.output/(name+'.json'),getattr(self,name))

    def base(self,state,nodes,frequency):
        boundary,tg=self.ledger.call('geometry_validation',lambda:state_boundary(state,nodes))
        base=forward(boundary,frequency,self.acq,self.ledger)
        base.times['geometry']=tg
        return base

    def analytic(self,base,directions,label):
        operators,seconds=self.ledger.call('directional_operator',lambda:directional_operators(base,directions),
            dict(assemblies=1,derivatives=1),direction=label,n=len(base.A))
        dy,times=tangent(base,operators,self.ledger)
        self.controls.append(dict(**self.ledger.context,direction=label,**operators.diagnostics,
                                  wrapper_seconds=seconds,**times))
        return operators,dy

    def fd(self,state,direction,step,nodes,frequency,label):
        values=[]
        for sign in (1,-1):
            (trial,error),elapsed=self.ledger.call('gauge_retraction',lambda:retract(state,direction,sign*step))
            self.gauge.append(dict(**self.ledger.context,direction=label,step=sign*step,
                physical_displacement_bound_m=error,seconds=elapsed,passed=error<=1e-10))
            values.append(self.base(trial,nodes,frequency))
        return values[0],values[1],(values[0].Y-values[1].Y)/(2*step)

    def wiring(self):
        self.ledger.context=dict(stage='wiring',case='single_control',frequency_hz=1_250_000_000)
        c=circle((.5,.5),.035,component_id='single').discretize(48)
        b=forward(OrderedBoundary2D((c,)),1_250_000_000,self.acq,self.ledger)
        d=KressDirection(c.points-[.5,.5],c.first_derivatives,c.second_derivatives,c.third_derivatives)
        ours,dy=self.analytic(b,(d,),'radial_scale')
        reference,_=self.ledger.call('existing_single_forward',lambda:solve_kress_tmz_total_field_batch(
            c,b.sources,b.receivers,2*np.pi*1_250_000_000,b.strengths,**b.material_args),
            dict(assemblies=1,factorizations=1,solves=1),rhs_count=24)
        expected,_=self.ledger.call('existing_single_jvp',lambda:linearize_kress_forward(reference,d),
            dict(assemblies=1,derivatives=1,factorizations=1,solves=1),rhs_count=24)
        errors={name:relative(x,y) for name,x,y in (
            ('dA',ours.dA,expected.d_system_matrix),('dB',ours.dB,expected.d_right_hand_side),
            ('dC',ours.dC,expected.d_receiver_matrix),('dY',dy,expected.d_scattered_receiver.T))}
        self.controls.append(dict(test='existing_single_interface_equivalence',errors=errors,passed=max(errors.values())<1e-10))
        if max(errors.values())>1e-10:raise Stop('WIRING_FAILURE: single-interface control')
        a=circle((.42,.46),.030,component_id='left').discretize(24)
        bcurve=fourier_curve([[.60,.54],[.040,0],[.003,0]],[[0,0],[0,.025],[0,-.002]],
                             component_id='right',period=3.7).discretize(32)
        boundary=OrderedBoundary2D((a,bcurve))
        base=forward(boundary,1_250_000_000,self.acq,self.ledger)
        def translation(curve,amount):
            return KressDirection(np.tile(amount,(curve.num_nodes,1)),*[np.zeros_like(curve.points)]*3)
        none=tuple(KressDirection() for _ in boundary.components)
        directions=[('left_translation',(translation(a,[1,0]),none[1])),
                    ('right_translation',(none[0],translation(bcurve,[0,1]))),
                    ('collective_translation',(translation(a,[1,-.5]),translation(bcurve,[1,-.5])))]
        t=2*np.pi*(bcurve.parameters-bcurve.parameters[0])/bcurve.period
        jets=[(3*2*np.pi/bcurve.period)**order*np.column_stack((np.cos(3*t+order*np.pi/2),
                np.sin(3*t+order*np.pi/2))) for order in range(4)]
        directions.append(('right_shape3',(none[0],KressDirection(*jets))))
        ell=float(np.linalg.norm(np.ptp(boundary.points,axis=0)))
        for label,direction in directions:
            self.ledger.context=dict(stage='wiring',case='unequal_grids_periods',frequency_hz=1_250_000_000)
            operators,dy=self.analytic(base,direction,label)
            for h in (1e-5,5e-6):
                plus=forward(shifted_boundary(boundary,direction,h),1_250_000_000,self.acq,self.ledger)
                minus=forward(shifted_boundary(boundary,direction,-h),1_250_000_000,self.acq,self.ledger)
                rows=operator_error_rows(base,operators,plus,minus,h,ell)
                self.operator_checks.extend([dict(**self.ledger.context,direction=label,**r) for r in rows])
                error=relative(pair(dy),pair((plus.Y-minus.Y)/(2*h)),1e-12*np.linalg.norm(np.diag(base.incident))/ell)
                self.direction_checks.append(dict(**self.ledger.context,direction=label,step=h,
                    relative_error=error,passed=error<=1e-4))
                if not all(r['passed'] for r in rows) or error>1e-4:
                    self.checkpoint();raise Stop('WIRING_FAILURE: coupled FD check '+label)
            if label=='collective_translation':
                invariant=float(np.linalg.norm(operators.dA))
                self.controls.append(dict(test='collective_translation_A_invariant',norm=invariant,passed=invariant<1e-10))
                if invariant>1e-10:raise Stop('WIRING_FAILURE: collective translation')
            else:
                sl=boundary.component_slices[0];cs=boundary.component_slices[1]
                cross_norm=float(np.linalg.norm(operators.dA[sl,cs]))
                self.controls.append(dict(test='cross_interaction_nonzero',direction=label,norm=cross_norm,passed=cross_norm>1e-12))
                if cross_norm<=1e-12:raise Stop('WIRING_FAILURE: cross derivative missing')
            self.checkpoint()
        print('WIRING_PASS',flush=True)

    def full_jacobian(self,record,method,*,stage='full_jacobian',repetition=None):
        self.ledger.guard()
        frequency=1_250_000_000;nodes=256
        self.ledger.context=dict(stage=stage,case=record['id'],frequency_hz=frequency,method=method,repetition=repetition)
        state=deserialize(record['state']);basis=state.gauge_tangent_basis()
        assert basis.shape==(34,76)
        observations=self.observed(record,frequency)
        before=self.ledger.counts.copy();tick=time.perf_counter()
        base=self.base(state,nodes,frequency)
        columns=[]
        for index,direction in enumerate(basis):
            if method=='analytic':
                directions=state_directions(state,base.system.geometry,direction)
                operators,dy=self.analytic(base,directions,index)
                del operators
            else:
                plus,minus,dy=self.fd(state,direction,1e-5,nodes,frequency,index)
                del plus,minus
            columns.append(residual_direction(dy,observations))
        result=np.column_stack(columns)
        total=time.perf_counter()-tick
        counts={k:self.ledger.counts[k]-before[k] for k in before}
        timing=dict(**self.ledger.context,total_seconds=total,counts=counts,q=len(basis),
                    nodes=nodes,rhs_count=24,base_times=base.times,
                    peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                    external_numerical_processes=external_numerical_processes(),load=os.getloadavg(),
                    includes_parent_and_derivative_setup=True)
        self.timings.append(timing)
        if stage=='full_jacobian':
            write_json(self.output/f"{record['id']}_{method}_jacobian.json",dict(
                matrix=result,basis=basis,observed=complex_record(observations),q=34,nodes=nodes,
                frequency_hz=frequency,coordinate_system='production orthonormal gauge coefficient basis',
                timing=timing))
        self.checkpoint();gc.collect()
        print(json.dumps(timing),flush=True)
        return result,base

    def observed(self,record,frequency):
        training=record['training']
        index=training['frequencies_hz'].index(frequency)
        return (np.array(training['observed_real'])+1j*np.array(training['observed_imag']))[:,index]

    def saved_state(self,record):
        state=deserialize(record['state']);basis=state.gauge_tangent_basis()
        _,base_gauge_error=retract(state,np.zeros(state.parameter_count),0.)
        samples=np.concatenate([c.parameterization().discretize(2048).points for c in state.components])
        ell=float(np.linalg.norm(np.ptp(samples,axis=0)))
        self.gauge.append(dict(case=record['id'],base_fixed_point_bound_m=base_gauge_error,passed=True))
        ja,base256=self.full_jacobian(record,'analytic')
        jf,_=self.full_jacobian(record,'fd')
        norms=np.linalg.norm(jf,axis=0)
        column_errors=np.linalg.norm(ja-jf,axis=0)/np.maximum(norms,1e-12*np.linalg.norm(jf))
        error=relative(ja,jf);worst=float(column_errors.max())
        jac_pass=error<=1e-4 and worst<=1e-4
        self.jacobians.append(dict(case=record['id'],frequency_hz=1_250_000_000,nodes=256,q=34,
            relative_frobenius_error=error,worst_column_relative_error=worst,column_relative_errors=column_errors,
            passed=jac_pass,fd_step=1e-5))
        if not jac_pass:
            self.checkpoint();print('FULL_JACOBIAN_GATE_FAILED '+record['id'],flush=True)
        rng=np.random.default_rng(20260915)
        mixed=rng.normal(size=len(basis));mixed/=np.linalg.norm(mixed)
        selected=[('translation_first',basis[0]),('last_shape',basis[-1]),('mixed',mixed@basis)]
        for frequency in FREQUENCIES:
            self.ledger.context=dict(stage='refinement',case=record['id'],frequency_hz=frequency)
            coarse=base256 if frequency==1_250_000_000 else self.base(state,256,frequency)
            fine=self.base(state,512,frequency)
            source_scale=float(np.linalg.norm(np.diag(coarse.incident)))
            discrepancy=relative(pair(coarse.Y),pair(fine.Y),1e-12*source_scale)
            self.refinements.append(dict(case=record['id'],frequency_hz=frequency,quantity='forward',
                relative_error=discrepancy,passed=discrepancy<=2e-7))
            for label,direction in selected:
                ds=[]
                for nodes,base in ((256,coarse),(512,fine)):
                    self.ledger.context=dict(stage='direction_validation',case=record['id'],frequency_hz=frequency,nodes=nodes)
                    dirs=state_directions(state,base.system.geometry,direction)
                    operators,dy=self.analytic(base,dirs,label)
                    physical=np.concatenate([d.points for d in dirs])
                    physical_rms=float(np.sqrt(np.mean(np.sum(physical**2,axis=1))))
                    for h in (1e-5,5e-6):
                        plus,minus,fd=self.fd(state,direction,h,nodes,frequency,label)
                        rows=operator_error_rows(base,operators,plus,minus,h,ell)
                        self.operator_checks.extend([dict(**self.ledger.context,direction=label,**r) for r in rows])
                        e=relative(pair(dy),pair(fd),1e-12*source_scale/ell)
                        self.direction_checks.append(dict(**self.ledger.context,direction=label,step=h,
                            relative_error=e,absolute_error=float(np.linalg.norm(pair(dy-fd))),
                            rms_displacement_per_unit_coefficient=physical_rms,
                            maximum_displacement_per_unit_coefficient=float(np.max(np.linalg.norm(physical,axis=1))),
                            passed=e<=1e-4,finite_difference_is_validation=True))
                        del plus,minus
                    if nodes==256:
                        # Report the current optimizer's configured FD scale as a
                        # separate accuracy control, never as the analytic backend.
                        plus,minus,fd=self.fd(state,direction,1e-4,nodes,frequency,label)
                        self.direction_checks.append(dict(**self.ledger.context,direction=label,step=1e-4,
                            relative_error=relative(pair(fd),pair(dy),1e-12*source_scale/ell),
                            passed=None,role='current_optimizer_step_accuracy_only'))
                        del plus,minus
                    ds.append(dy)
                    del operators
                error=relative(pair(ds[0]),pair(ds[1]),1e-12*source_scale/ell)
                self.refinements.append(dict(case=record['id'],frequency_hz=frequency,quantity='sensitivity',
                    direction=label,relative_error=error,passed=error<=2e-5))
                if frequency==1_250_000_000 and label=='mixed':
                    previous=None;ratios=[]
                    for h in (1e-4,5e-5,2.5e-5,1.25e-5):
                        trial,gauge_error=retract(state,direction,h)
                        shifted=self.base(trial,256,frequency)
                        remainder=float(np.linalg.norm(pair(shifted.Y-coarse.Y-h*ds[0])))
                        ratio=None if previous is None else previous/remainder
                        if ratio is not None:ratios.append(ratio)
                        self.taylor.append(dict(case=record['id'],frequency_hz=frequency,direction=label,
                            coefficient_step_m=h,remainder=remainder,halving_ratio=ratio,
                            gauge_displacement_bound_m=gauge_error))
                        previous=remainder
                    self.controls.append(dict(test='saved_mixed_taylor',case=record['id'],ratios=ratios,
                        passed=any(all(3.5<=v<=4.5 for v in ratios[i:i+2]) for i in range(len(ratios)-1))))
                self.checkpoint()
            del fine,coarse
        self.checkpoint();gc.collect()
        print('SAVED_STATE_COMPLETE '+record['id'],flush=True)

    def accuracy_passes(self):
        return (len(self.jacobians)==2 and all(r['passed'] for r in self.jacobians)
            and all(r['passed'] for r in self.refinements)
            and all(r['passed'] for r in self.operator_checks)
            and all(r.get('passed') is not False for r in self.direction_checks)
            and all(r.get('passed') is not False for r in self.controls))

    def benchmark(self):
        if not self.accuracy_passes():
            return dict(status='SKIPPED',reason='Accuracy gate failed')
        external=external_numerical_processes()
        if external:
            return dict(status='DEFERRED',reason='Other numerical worker active; timing measurements must be separate',external=external)
        record=next(r for r in self.records if r['id']=='terminal')
        for rep in range(3):
            for method in (('analytic','fd') if rep%2==0 else ('fd','analytic')):
                if external_numerical_processes():
                    return dict(status='DEFERRED',reason='Other numerical worker started between timing arms')
                _,base=self.full_jacobian(record,method,stage='paired_timing',repetition=rep)
                del base
        return dict(status='COMPLETE')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--previous',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    snapshot=json.loads(Path('experiments/bie004_multi_derivative/workspace_before.json').read_text())
    acquisition,records,input_hashes=frozen_inputs()
    source_hashes=snapshot['source_sha256']
    own_hashes={str(p):digest(p) for p in Path(__file__).parent.glob('*.py')}
    ledger=Ledger(args.output/'work_ledger.jsonl',{**source_hashes,**own_hashes,**input_hashes})
    ledger.started=PROGRAM_STARTED
    prior=None
    if args.previous:
        prior=json.loads((args.previous/'manifest.json').read_text())
        ledger.counts.update(prior['counts']);ledger.started-=prior['numerical_seconds']
    manifest=dict(experiment='BIE-004',approval='User instructed concurrent BIE-004 and topology, then: you keep on your bie then',
        status='IN PROGRESS',workspace=snapshot,source_hashes=source_hashes,experiment_hashes=own_hashes,
        input_hashes=input_hashes,acquisition=acquisition,records=records,limits=LIMITS,
        numerical_seconds_cap=1800,solve_config=asdict(SOLVE_CONFIG),geometry_config=asdict(geometry_config(256)),
        numerical_workers=1,blas_environment={k:os.environ[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
        python=sys.version,numpy=np.__version__,scipy=scipy.__version__,platform=platform.uname()._asdict(),
        initial_load=os.getloadavg(),initial_external_processes=external_numerical_processes(),
        previous_attempt=None if args.previous is None else str(args.previous),seed=20260915,
        plan_sha256=digest(PLAN),production_changes=False,inverse_executed=False)
    write_json(args.output/'manifest.json',manifest)
    (args.output/'approved_plan.md').write_bytes(PLAN.read_bytes())
    measured=args.output/'measured_sources';measured.mkdir()
    for name in own_hashes:(measured/Path(name).name).write_bytes(Path(name).read_bytes())
    (args.output/'commands.md').write_text('# Actual command\n\n```bash\nOMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=solvers:. '+sys.executable+' -m experiments.bie004_multi_derivative.run '+' '.join(sys.argv[1:])+'\n```\n')
    experiment=Experiment(args.output,ledger,acquisition,records)
    error=None;benchmark=dict(status='NOT_STARTED')
    def alarm(signum,frame):raise Stop('BUDGET_STOP: 1800 numerical seconds')
    signal.signal(signal.SIGALRM,alarm)
    signal.setitimer(signal.ITIMER_REAL,max(.001,1800-ledger.seconds()))
    try:
        ledger.guard()
        tests,_=ledger.call('algebra_tests',lambda:subprocess.run([sys.executable,'-m','pytest','-q',
            'experiments/bie004_multi_derivative/test_algebra.py'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True))
        (args.output/'tests.log').write_text(tests.stdout)
        if tests.returncode:raise Stop('WIRING_FAILURE: algebra tests')
        experiment.wiring()
        for record in records:
            ledger.guard();experiment.saved_state(record)
        benchmark=experiment.benchmark()
        ledger.guard()
    except BaseException as exc:
        error=repr(exc)
        (args.output/'failure.log').write_text(traceback.format_exc())
        print(traceback.format_exc(),flush=True)
    finally:
        signal.setitimer(signal.ITIMER_REAL,0)
        experiment.checkpoint()
        manifest.update(status='COMPLETE' if error is None else 'STOPPED',failure=error,
            benchmark=benchmark,accuracy_passed=experiment.accuracy_passes(),counts=ledger.counts,
            numerical_seconds=ledger.seconds(),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            final_load=os.getloadavg(),source_hashes_after={p:digest(p) for p in source_hashes})
        write_json(args.output/'manifest.json',manifest)
        print(json.dumps({k:manifest[k] for k in ('status','failure','accuracy_passed','benchmark','counts','numerical_seconds')}),flush=True)
    return int(error is not None)


if __name__=='__main__':raise SystemExit(main())
