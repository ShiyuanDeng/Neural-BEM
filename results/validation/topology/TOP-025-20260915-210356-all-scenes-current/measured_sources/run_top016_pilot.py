"""TOP-016 paired fixed-topology pilot, released only by saved screen PASS.

One trial per invocation; orchestration may launch independent read-only workers.
Truth/evaluation inputs stay outside the fit_stage optimizer interface.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict,replace
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import run_top016_preflight as p
from sdf_inverse import radial_topology as rt


class NumericalObstruction(p.Obstruction):pass


def write(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    p.write(tmp,value);os.replace(tmp,path)


class TrialLedger(p.Ledger):
    def __init__(self,cap,seconds):
        super().__init__(cap,seconds);self.stage_start=0;self.stage_cap=0
        self.stage=0;self.endpoint=False;self.endpoint_reserve=12

    def reserve(self,maximum):
        overhead=0 if self.endpoint else self.endpoint_reserve
        super().reserve(maximum+overhead)
        remaining=self.stage_cap-(self.total-self.stage_start)
        if maximum+overhead>remaining:
            raise p.Budget(f'stage {self.stage} batch needs {maximum} solves plus {overhead} endpoint reserve; {remaining} remain')

    def begin_stage(self,number,cap):
        self.stage=number;self.stage_start=self.total;self.stage_cap=cap

    @contextmanager
    def endpoint_scope(self):
        previous=self.endpoint;self.endpoint=True
        try:yield
        finally:self.endpoint=previous

    def snapshot(self):
        value=super().snapshot();value.update(stage=self.stage,stage_cap=self.stage_cap,
            stage_attempted=self.total-self.stage_start,endpoint_reserve=self.endpoint_reserve)
        return value


def acceptance(base,candidate,refined_base,refined_candidate):
    dp=base-candidate;dr=refined_base-refined_candidate
    margin=max(1e-14+1e-8*base,1e-14+1e-8*refined_base)
    uncertainty=5*abs(dp-dr)
    return dict(production_gain=dp,refined_gain=dr,margin=margin,
        disagreement_allowance=uncertainty,accepted=bool(min(dp,dr)>margin+uncertainty))


def fit_stage(initial,data,nodes,solve,optimizer,floor,ledger,output):
    """Training-only interface: no scene, truth, or evaluation observations."""
    output.mkdir(parents=True,exist_ok=False)
    low,high=nodes;production=p.driver.baseline._geometry_config(low)
    refined=p.driver.baseline._geometry_config(high)
    current=initial;last_gradient=None;accepted_steps=0;checks=[];ref_cache={}
    write(output/'initial_state.json',p.driver.serialize_state(initial))
    write(output/'optimizer.json',dict(config=asdict(optimizer),loss_change_stopping=False,
        active_frequencies_hz=(data.forward_problem.angular_frequencies/(2*np.pi)),
        minimum_component_radius_m=floor,cartesian_gauge=True,feasible_fd_jacobian=True,
        extra_feasibility_nodes=high))
    def checkpoint(iteration,evaluation):
        nonlocal current,accepted_steps,last_gradient
        current=evaluation.state;accepted_steps=iteration;last_gradient=None
        write(output/'accepted_state.json',dict(iteration=iteration,state=p.driver.serialize_state(current),
            production_loss=evaluation.loss,gradient_status='pending_next_jacobian',work=ledger.snapshot()))
    def progress(frame):
        nonlocal last_gradient
        ledger.category='objective'
        last_gradient=dict(coefficient_infinity_norm=float(np.linalg.norm(frame.gradient,ord=np.inf)),
            reduced_infinity_norm=float(np.linalg.norm(frame.state.gauge_tangent_basis()@frame.gradient,ord=np.inf)),
            coefficient_gradient=frame.gradient)
        row=dict(iteration=frame.iteration,state=p.driver.serialize_state(frame.state),loss=frame.loss,
            relative_l2=frame.relative_l2_error,gradient=last_gradient,damping=frame.damping,work=ledger.snapshot())
        with (output/'trajectory.jsonl').open('a') as stream:
            stream.write(json.dumps(row,default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x))+'\n')
        write(output/'terminal_gradient.json',last_gradient)
        print('iteration',ledger.stage,frame.iteration,frame.loss,'solves',ledger.total,flush=True)
    def batch(maximum_objectives):
        ledger.reserve(maximum_objectives*len(data.frequency_weights));ledger.category='derivative'
    def evaluate_refined(evaluation):
        key=evaluation.state.parameter_vector().tobytes()
        if key not in ref_cache:
            ledger.reserve(len(data.frequency_weights))
            with ledger.category_scope('acceptance_validation'):
                ledger.calls['validation_calls']+=1
                ref_cache[key]=rt.evaluate_multiradial_objective(evaluation.state,data,refined,solve_config=solve)
        else:ledger.calls['refined_cache_hits']+=1
        return ref_cache[key]
    def validate(base,candidate):
        # Reserve maximum work for both refined endpoints as one validation batch.
        ledger.reserve(2*len(data.frequency_weights))
        rb=evaluate_refined(base);rc=evaluate_refined(candidate)
        frequencies=np.asarray((data.forward_problem.angular_frequencies/(2*np.pi)))
        discrepancy=p.relative(candidate.prediction,rc.prediction)
        limits=np.where(frequencies>.5e9+1.,1e-7,1e-5)
        row=acceptance(base.loss,candidate.loss,rb.loss,rc.loss)
        row.update(candidate=p.driver.serialize_state(candidate.state),prediction_discrepancy=discrepancy)
        if np.any(discrepancy>limits):
            row.update(accepted=False,numerical_obstruction=True);checks.append(row)
            write(output/'acceptance.json',checks)
            raise NumericalObstruction('candidate leaves frozen numerical-resolution regime')
        checks.append(row);write(output/'acceptance.json',checks)
        return row['accepted']
    original_evaluate=rt.evaluate_multiradial_objective
    def counted_evaluate(*args,**kwargs):
        ledger.calls[ledger.category+'_calls']+=1
        return original_evaluate(*args,**kwargs)
    rt.evaluate_multiradial_objective=counted_evaluate
    ledger.category='objective'
    result=None;reason=None;failure=None
    try:
        result=rt.run_multiradial_fd_inverse(initial,data,production,solve_config=solve,config=optimizer,
            cartesian_gauge=True,minimum_component_radius_m=floor,feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=True,loss_change_stopping=False,candidate_acceptance_callback=validate,
            jacobian_batch_callback=batch,accepted_state_callback=checkpoint,progress_callback=progress,
            evaluation_event_callback=lambda event:ledger.calls.update({event:1}))
        current=result.final_state;reason=result.stop_reason
    except Exception as exc:
        reason=str(exc);failure=type(exc).__name__
    finally:
        rt.evaluate_multiradial_objective=original_evaluate
        terminal=dict(stop_reason=reason,failure_type=failure,accepted_steps=accepted_steps,
            gradient=last_gradient,gradient_status='measured' if last_gradient is not None else 'unavailable_after_budget_or_failure',
            final_state=p.driver.serialize_state(current),work=ledger.snapshot(),
            optimizer_completed=result is not None,
            one_sided_columns=None if result is None else result.one_sided_jacobian_column_count,
            unresolved_columns=None if result is None else result.unresolved_jacobian_column_count,
            accepted_gains=[min(c['production_gain'],c['refined_gain']) for c in checks if c['accepted']],
            rejected_gains=[min(c['production_gain'],c['refined_gain']) for c in checks if not c['accepted']])
        write(output/'terminal.json',terminal)
    return current,terminal


def score(state,scene,spec,observed,evaluation_observed,nodes,solve,ledger):
    # Endpoint already fixed. This function is never visible inside fit_stage.
    metrics=p.benchmark.geometry_metrics(state,scene,spec)
    with ledger.endpoint_scope():
        ledger.reserve(12)
        train={n:p.prediction(state,p.TRAIN,n,solve,ledger,'endpoint_training') for n in nodes}
        evaluation={n:p.prediction(state,p.EVALUATION,n,solve,ledger,'endpoint_evaluation') for n in nodes}
    train_errors=p.relative(train[nodes[1]],observed)
    eval_errors=p.relative(evaluation[nodes[1]],evaluation_observed)
    checks=dict(training_discrepancy=p.relative(train[nodes[0]],train[nodes[1]]),
                evaluation_discrepancy=p.relative(evaluation[nodes[0]],evaluation[nodes[1]]))
    numerical=bool(np.max(checks['training_discrepancy'][1:])<=1e-7 and
                   np.max(checks['training_discrepancy'])<=1e-5 and np.max(checks['evaluation_discrepancy'])<=1e-5)
    gates=dict(count=metrics['component_count']==metrics['truth_component_count'],
        boundary=metrics['maximum_matched_hausdorff_m']<=.001,iou=metrics['union_iou']>=.9,
        original_training=float(train_errors[0])<=.003,evaluation=float(np.max(eval_errors))<=.05)
    return dict(geometry=metrics,training_errors=train_errors,evaluation_errors=eval_errors,
        maximum_evaluation_error=float(np.max(eval_errors)),gates=gates,
        original_gates_pass=all(gates.values()),numerical_checks=checks,numerically_qualified=numerical)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--scene',choices=p.SCENES,required=True);parser.add_argument('--arm',choices=('S','F'),required=True)
    parser.add_argument('--local',action='store_true');args=parser.parse_args()
    bundle=args.bundle.resolve();screen=p.benchmark.read(bundle/'phase1/sensitivity.json')
    if screen['status']!='SCREEN_PASS':raise ValueError('binding screen has not released pilot')
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='1':raise ValueError('single-thread numerical worker required')
    if args.local and args.scene!='far-two-stars':raise ValueError('only prescribed local scene allowed')
    label=('local-' if args.local else '')+args.arm+'-'+args.scene
    output=bundle/'runs'/label;output.mkdir(parents=True,exist_ok=False)
    spec=p.benchmark.read(p.DATA/'scene_spec.json');scene=next(s for s in spec['scenes'] if s['id']==args.scene)
    saved=p.benchmark.read(bundle/'phase1'/f'{args.scene}_training_observations.json')
    observed=np.array(saved['observed_real'])+1j*np.array(saved['observed_imag'])
    original=p.benchmark.read(bundle/'phase0/inputs'/args.scene/'observations.json')
    evaluation_observed=(np.array(original['observed_real'])+1j*np.array(original['observed_imag']))[:,1:]
    state=p.driver.deserialize_state(p.benchmark.read(bundle/'phase0/inputs'/args.scene/'state.json'))
    if args.local:
        # Conditional truth-assisted local control; no search or alternate seed.
        main_records=[p.benchmark.read(bundle/'runs'/f'{a}-{s}'/'metrics.json')
                      for s in p.SCENES for a in ('S','F')]
        if any(r.get('final',{}).get('original_gates_pass') for r in main_records if r['scene'] in p.SCENES[:2]):
            raise ValueError('local control not eligible: a main principal reconstruction qualified')
        state=p.representation_state(scene)
        components=tuple(replace(c,cosine_coefficients=np.vstack((c.cosine_coefficients[0]+[.002,-.001],c.cosine_coefficients[1:]))) for c in state.components)
        state=p.MultiRadialFourierState(components)
    solve=p.driver.baseline.iteration01_solve_config();nodes=screen['selected_nodes']
    control=p.TopologyControllerConfig(**spec['controller'],refined_feasibility_guard=True,feasible_fd_jacobian=True)
    if not p.feasible(state,nodes,solve,control.minimum_component_radius_m):raise ValueError('prescribed seed infeasible; no substitute')
    optimizer=replace(p._optimizer_config(state,control),loss_tolerance=1e-14)
    caps=[250,350,500,900] if args.local else [1000,1250,1750,4000]
    ledger=TrialLedger(2000 if args.local else 8000,600. if args.local else 1800.)
    record=dict(scene=args.scene,arm=args.arm,truth_assisted_local_control=args.local,stages=[],
                initial_state=p.driver.serialize_state(state),status='IN_PROGRESS',declared_stage_caps=caps,
                numerical_concurrency=2,blas_threads=1,command=sys.argv)
    sources=[Path(__file__),p.ROOT/'run_top016_preflight.py',p.ROOT/'solvers/sdf_inverse/radial_topology.py',
             p.ROOT/'solvers/sdf_inverse/optimization.py']
    write(output/'manifest.json',dict(source_sha256={str(x.relative_to(p.ROOT)):p.digest(x) for x in sources},
        phase1_manifest_sha256=p.digest(bundle/'phase1/manifest.json'),initial_state=record['initial_state'],
        training_observations_sha256=p.digest(bundle/'phase1'/f'{args.scene}_training_observations.json'),
        optimizer_receives_truth=False,optimizer_receives_evaluation=False,concurrency=2,blas_threads=1))
    try:
        with ledger.instrument():
            for i,cap in enumerate(caps):
                ledger.begin_stage(i+1,cap)
                if i==0:
                    record['initial']=score(state,scene,spec,observed,evaluation_observed,nodes,solve,ledger)
                    if not record['initial']['numerically_qualified']:
                        raise NumericalObstruction('initial state fails frozen numerical qualification')
                active=1 if args.arm=='S' else i+1
                data=p.training_data(p.TRAIN[:active],observed[:,:active])
                state,terminal=fit_stage(state,data,nodes,solve,optimizer,
                    control.minimum_component_radius_m,ledger,output/f'stage_{i+1}')
                row=dict(stage=i+1,active_frequencies_hz=p.TRAIN[:active],terminal=terminal)
                record['stages'].append(row)
                record.pop('final',None) # never attach an older endpoint score to a newer accepted state
                try:
                    row['score']=score(state,scene,spec,observed,evaluation_observed,nodes,solve,ledger)
                    record['final']=row['score']
                    row['aggregate_objective']=.5*float(np.mean(np.asarray(row['score']['training_errors'])[:active]**2))
                except p.Obstruction as exc:
                    row['score_obstruction']=str(exc)
                write(output/'metrics.json',record)
                if terminal['failure_type'] or terminal['stop_reason']=='infeasible_jacobian':
                    status='INCONCLUSIVE' if terminal['failure_type'] in (None,'Budget','NumericalObstruction') else 'IMPLEMENTATION_ERROR'
                    record.update(status=status,reason=terminal['stop_reason']);break
                if not row.get('score',{}).get('numerically_qualified',False):
                    record.update(status='INCONCLUSIVE',reason='endpoint numerical qualification failed');break
            else:record['status']='COMPLETE'
    except p.Obstruction as exc:
        record.update(status='INCONCLUSIVE',reason=str(exc))
    except Exception as exc:
        record.update(status='IMPLEMENTATION_ERROR',reason=str(exc));raise
    finally:
        record['final_state']=p.driver.serialize_state(state);record['work']=ledger.snapshot()
        record['qualified_complete_reconstruction']=record['status']=='COMPLETE' and record.get('final',{}).get('original_gates_pass',False)
        write(output/'metrics.json',record)
        print(json.dumps(dict(scene=args.scene,arm=args.arm,status=record['status'],reason=record.get('reason'),work=record['work'])),flush=True)

if __name__=='__main__':main()
