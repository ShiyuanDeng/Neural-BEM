"""Approved TOP-017 only: bounded audit and restarted principal stages 2--4.

Historical drivers and numerical defaults remain unchanged. The fit interface is
training-only; immutable endpoint scoring is supplied by the outer orchestrator.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import traceback
import numpy as np
from scipy.spatial import cKDTree
import run_top016_pilot as old
p = old.p
from sdf_inverse.runtime import runtime_metadata, jacobian_work_bound
rt = old.rt
ROOT = Path(__file__).resolve().parent
BASE = '9ad3c8b191c7f1130764c0476480290b0f6a6e4a'
SOURCE = ROOT/'results/validation/topology/TOP-016-20260914-fixed-topology'
SCENES = p.SCENES[:2]
NODES = (128, 256)
QUOTAS = (1250, 1750, 4000)
NORMALIZATION = '0.5 * mean_f(||prediction_f-observed_f||_2^2 / ||observed_f||_2^2)'
write = old.write
read = p.benchmark.read


def state_hash(state):
    value = p.driver.serialize_state(state) if isinstance(state, p.MultiRadialFourierState) else state
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x)).encode()).hexdigest()


def evaluation_snapshot(evaluation):
    """Serialize an already computed objective; never dispatch work for logging."""
    return dict(state=p.driver.serialize_state(evaluation.state),
                state_sha256=state_hash(evaluation.state), loss=evaluation.loss,
                prediction_real=np.asarray(evaluation.prediction).real,
                prediction_imag=np.asarray(evaluation.prediction).imag)


def source_hashes():
    paths = [*sorted((ROOT/'solvers').rglob('*.py')),
             *sorted((ROOT/'config').rglob('*.py')),
             *[x for x in sorted(ROOT.glob('*.py')) if x.name!='summarize_top017.py']]
    return {str(x.relative_to(ROOT)): p.digest(x) for x in paths}


def verify_sources(expected):
    if source_hashes() != expected:
        raise ImplementationError('source checkout changed after preflight freeze')


class Stop(RuntimeError):
    code = 'IMPLEMENTATION_ERROR'
class StageQuota(Stop): code = 'STAGE_QUOTA_REACHED'
class TrialSolveCap(Stop): code = 'TRIAL_SOLVE_CAP'
class TrialWallLimit(Stop): code = 'TRIAL_WALL_LIMIT'
class PhysicalFailure(Stop): code = 'PHYSICAL_SOLVE_FAILED'
class NumericalFailure(Stop): code = 'NUMERICAL_FAILURE'
class UnresolvedDerivative(Stop): code = 'UNRESOLVED_DERIVATIVE'
class ExposureObstruction(Stop): code = 'EXPOSURE_OBSTRUCTION'
class ImplementationError(Stop): code = 'IMPLEMENTATION_ERROR'


class Ledger(p.Ledger):
    def __init__(self, cap=7000, seconds=1800., clock=time.perf_counter, preserve_errors=()):
        super().__init__(cap, seconds, clock)
        self.preserve_errors = tuple(preserve_errors)
        self.stage = None
        self.stage_start = 0
        self.stage_derivative_start = 0
        self.stage_quota = None
        self.endpoint = False
        self.frequency_attempted = Counter()
        self.frequency_completed = Counter()
        self.frequency_failed = Counter()

    def reserve(self, maximum):
        overhead = 12 if self.stage is not None and not self.endpoint else 0
        stage_spent = (self.total-self.stage_start
                       + sum(self.derivative_attempted.values())-self.stage_derivative_start)
        if self.clock()-self.started >= self.seconds:
            raise TrialWallLimit('hard trial/audit wall limit')
        if self.budget_total >= self.cap and maximum+overhead > 0:
            raise TrialSolveCap('actual total solve cap reached')
        if (self.stage_quota is not None and
                stage_spent+maximum+overhead > self.stage_quota and
                self.stage_quota-stage_spent <= self.cap-self.budget_total and
                self.budget_total+overhead <= self.cap):
            raise StageQuota('next complete batch and endpoint reserve exceed planned stage quota')
        if self.budget_total + maximum + overhead > self.cap:
            raise TrialSolveCap('next complete batch and endpoint reserve exceed total solve cap')

    def begin_stage(self, number, quota):
        # Check global limits independently of the previous stage's spent quota.
        if self.clock()-self.started >= self.seconds:
            raise TrialWallLimit('hard wall limit at stage boundary')
        if self.budget_total >= self.cap:
            raise TrialSolveCap('hard solve cap at stage boundary')
        self.stage, self.stage_start, self.stage_quota = number, self.total, quota
        self.stage_derivative_start = sum(self.derivative_attempted.values())

    @contextmanager
    def endpoint_scope(self):
        previous = self.endpoint
        self.endpoint = True
        try: yield
        finally: self.endpoint = previous

    def snapshot(self):
        row = super().snapshot()
        row.update(stage=self.stage, stage_attempted=self.total-self.stage_start,
                   stage_work_units=self.total-self.stage_start+sum(self.derivative_attempted.values())-self.stage_derivative_start,
                   stage_quota=self.stage_quota, endpoint_reserve=12 if self.stage else 0,
                   per_frequency_attempted=dict(self.frequency_attempted),
                   per_frequency_completed=dict(self.frequency_completed),
                   per_frequency_failed=dict(self.frequency_failed))
        return row

    @contextmanager
    def instrument(self):
        original = p.physical.solve_multicomponent_kress_tmz_total_field_batch
        def counted(*args, **kwargs):
            self.reserve(1)
            category = self.category
            frequency = float(args[3] if len(args)>3 else kwargs['angular_frequency'])/(2*np.pi)
            key = f'{self.stage}:{category}:{frequency:.0f}'
            self.attempted[category] += 1
            self.frequency_attempted[key] += 1
            try:
                value = original(*args, **kwargs)
            except BaseException as exc:
                self.failed[category] += 1
                self.frequency_failed[key] += 1
                if isinstance(exc, (Stop, KeyboardInterrupt, SystemExit)): raise
                if isinstance(exc, self.preserve_errors):
                    self.calls['preserved_candidate_refusals'] += 1
                    raise
                raise PhysicalFailure(f'{type(exc).__name__}: {exc}') from exc
            self.completed[category] += 1
            self.frequency_completed[key] += 1
            return value
        def alarm(*_): raise TrialWallLimit('hard wall limit during numerical batch')
        previous = signal.getsignal(signal.SIGALRM)
        p.physical.solve_multicomponent_kress_tmz_total_field_batch = counted
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, max(.001, self.seconds-(self.clock()-self.started)))
        try:
            from sdf_inverse.work_accounting import observe_analytic_work
            with observe_analytic_work(self.analytic_event):
                yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
            p.physical.solve_multicomponent_kress_tmz_total_field_batch = original


def fit_stage(initial, data, nodes, solve, optimizer, floor, ledger, output):
    """Only training data and accepted state enter this optimizer adapter."""
    output.mkdir(parents=True, exist_ok=False)
    low, high = nodes
    production = p.driver.baseline._geometry_config(low)
    refined = p.driver.baseline._geometry_config(high)
    frequencies = (data.forward_problem.angular_frequencies/(2*np.pi)).tolist()
    m = len(frequencies)
    context = dict(active_frequencies_hz=frequencies, normalization=NORMALIZATION,
                   production_nodes=low, refined_nodes=high)
    write(output/'optimizer.json',dict(config=asdict(optimizer), inverse_runtime=runtime_metadata(), **context,
          loss_change_stopping=False, cartesian_gauge=True, feasible_fd_jacobian=True,
          minimum_component_radius_m=floor, extra_feasibility_nodes=high))
    write(output/'initial_state.json',p.driver.serialize_state(initial))
    current = initial
    current_loss = None
    last_gradient = None
    accepted_steps = 0
    exposure = Counter()
    one_sided = unresolved = 0
    pending_batch = False
    checks = []
    ref_cache = {}
    result = None
    stop_code = 'NORMAL_OPTIMIZER_RETURN'
    reason = None
    error_traceback = None
    def append(name, value):
        with (output/name).open('a') as stream:
            stream.write(json.dumps(value, default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x))+'\n')
    def checkpoint(iteration, evaluation):
        nonlocal current, current_loss, accepted_steps
        current, current_loss, accepted_steps = evaluation.state, evaluation.loss, iteration
        write(output/'accepted_state.json',dict(iteration=iteration, state=p.driver.serialize_state(current),
              state_sha256=state_hash(current), production_loss=current_loss, **context, work=ledger.snapshot()))
    def batch(maximum_objectives):
        nonlocal pending_batch
        # The complete derivative plus one production/refined step opportunity
        # and endpoint reserve must fit before dispatch. Unused work is uncharged.
        ledger.reserve(maximum_objectives*m+3*m)
        exposure['jacobian_batches_started'] += 1
        pending_batch = True
        ledger.category = 'derivative'
    def diagnostic(event, payload):
        nonlocal pending_batch, one_sided, unresolved
        if event == 'jacobian_complete':
            exposure['jacobian_batches_completed'] += 1
            pending_batch = False
            one_sided += payload['one_sided_columns']
            unresolved += payload['unresolved_columns']
            append('jacobians.jsonl',dict(state_sha256=state_hash(payload['state']), **context,
                   directions=payload['directions'], one_sided_columns=payload['one_sided_columns'],
                   unresolved_columns=payload['unresolved_columns'], work=ledger.snapshot()))
            if payload['unresolved_columns']:
                raise UnresolvedDerivative('complete Jacobian contains unresolved columns; no step allowed')
            ledger.category = 'candidate'
        elif event == 'candidate_attempt':
            exposure['candidate_attempts'] += 1
            append('candidate_attempts.jsonl',dict(base_state_sha256=state_hash(payload['state']),
                   step=payload['step'], **context))
        elif event == 'candidate_evaluated':
            candidate = payload['candidate']
            base = payload['base']
            append('production_candidates.jsonl',dict(base_state_sha256=state_hash(base.state),
                   candidate_state_sha256=None if candidate is None else state_hash(candidate.state),
                   production_gain=None if candidate is None else base.loss-candidate.loss, **context))
        elif event == 'feasibility_refusal':
            exposure[ledger.category+'_feasibility_refusals'] += 1
            append('feasibility.jsonl',dict(category=ledger.category, state_sha256=state_hash(payload['state']),
                   reason=payload['reason'], **context))
    def progress(frame):
        nonlocal last_gradient
        last_gradient = dict(state_sha256=state_hash(frame.state), iteration=frame.iteration, **context,
            coefficient_gradient=frame.gradient,
            coefficient_infinity_norm=float(np.linalg.norm(frame.gradient,ord=np.inf)),
            reduced_infinity_norm=float(np.linalg.norm(frame.state.gauge_tangent_basis()@frame.gradient,ord=np.inf)))
        row = dict(state=p.driver.serialize_state(frame.state), state_sha256=state_hash(frame.state),
                   iteration=frame.iteration, loss=frame.loss, gradient=last_gradient,
                   damping=frame.damping, work=ledger.snapshot())
        append('trajectory.jsonl',row)
        write(output/'last_measured_gradient.json',last_gradient)
        print('stage',ledger.stage,'iteration',frame.iteration,'loss',frame.loss,'solves',ledger.total,flush=True)
    def refined_eval(evaluation):
        key = state_hash(evaluation.state)
        if key not in ref_cache:
            with ledger.category_scope('acceptance_validation'):
                exposure['acceptance_validation_calls'] += 1
                ref_cache[key] = rt.evaluate_multiradial_objective(evaluation.state,data,refined,solve_config=solve)
        else: exposure['refined_cache_hits'] += 1
        return ref_cache[key]
    def validate(base, candidate):
        ledger.reserve(2*m)
        rb, rc = refined_eval(base), refined_eval(candidate)
        discrepancy = p.relative(candidate.prediction,rc.prediction)
        row = dict(old.acceptance(base.loss,candidate.loss,rb.loss,rc.loss), **context,
                   base_state_sha256=state_hash(base.state), candidate_state_sha256=state_hash(candidate.state),
                   prediction_discrepancy=discrepancy, refined_base_loss=rb.loss, refined_candidate_loss=rc.loss)
        checks.append(row)
        write(output/'acceptance.json',checks)
        if not np.all(np.isfinite(discrepancy)) or np.any(discrepancy>np.where(np.array(frequencies)>.5e9+1.,1e-7,1e-5)):
            row['accepted'] = False
            row['numerical_obstruction'] = True
            write(output/'acceptance.json',checks)
            write(output/'numerical_failure.json', dict(
                reason='candidate leaves frozen numerical-resolution regime',
                **context, accepted=False, accepted_state_sha256=state_hash(current),
                production_base=evaluation_snapshot(base),
                production_candidate=evaluation_snapshot(candidate),
                refined_base=evaluation_snapshot(rb),
                refined_candidate=evaluation_snapshot(rc), acceptance=row,
                prediction_tolerances=np.where(np.array(frequencies)>.5e9+1.,1e-7,1e-5),
                geometry_configs={str(low):asdict(production),str(high):asdict(refined)},
                solve_config=asdict(solve), work=ledger.snapshot()))
            raise NumericalFailure('candidate leaves frozen numerical-resolution regime')
        return row['accepted']
    original = rt.evaluate_multiradial_objective
    def counted(*args, **kwargs):
        ledger.reserve(m)  # no partial multifrequency objective from a quota
        exposure[ledger.category+'_objective_calls'] += 1
        ledger.calls[ledger.category+'_objective_calls'] += 1
        return original(*args, **kwargs)
    rt.evaluate_multiradial_objective = counted
    ledger.category = 'initial_objective'
    try:
        q = len(initial.gauge_tangent_basis())
        derivative_bound = jacobian_work_bound(initial, q)*m
        minimum = m + derivative_bound + 3*m + 12
        write(output/'reservation.json',dict(reduced_directions=q, frequencies=m,
              complete_jacobian_bound=derivative_bound, initial_objective=m,
              inverse_runtime=runtime_metadata(), budget_unit='full system or directional assembly/tangent',
              candidate_and_validation=3*m, endpoint=12, minimum_opportunity=minimum,
              quota=ledger.stage_quota))
        if ledger.stage_quota < minimum:
            raise ExposureObstruction('quota cannot fund an initial model/step opportunity')
        result = rt.run_multiradial_fd_inverse(initial,data,production,solve_config=solve,config=optimizer,
            cartesian_gauge=True,minimum_component_radius_m=floor,feasibility_geometry_configs=(refined,),
            feasible_fd_jacobian=True,loss_change_stopping=False,candidate_acceptance_callback=validate,
            jacobian_batch_callback=batch,accepted_state_callback=checkpoint,progress_callback=progress,
            diagnostic_callback=diagnostic,
            evaluation_event_callback=lambda event:exposure.update({ledger.category+'_'+event:1}))
        current = result.final_state
        reason = result.stop_reason
        if result.unresolved_jacobian_column_count or reason == 'infeasible_jacobian':
            raise UnresolvedDerivative('optimizer returned unresolved derivative')
    except Stop as exc:
        stop_code, reason = exc.code, str(exc)
        if not isinstance(exc, StageQuota): error_traceback = traceback.format_exc()
    except Exception as exc:
        stop_code, reason, error_traceback = 'IMPLEMENTATION_ERROR',str(exc),traceback.format_exc()
    finally:
        rt.evaluate_multiradial_objective = original
    terminal_gradient = last_gradient if last_gradient and last_gradient['state_sha256']==state_hash(current) else None
    exposed = exposure['jacobian_batches_completed']>0 and unresolved==0
    if stop_code == 'STAGE_QUOTA_REACHED' and not exposed:
        stop_code = 'EXPOSURE_OBSTRUCTION'
    terminal = dict(stage_outcome=stop_code, optimizer_stop=reason if result is not None else None,
        reason=reason, traceback=error_traceback, final_state=p.driver.serialize_state(current),
        state_sha256=state_hash(current), production_loss=current_loss, accepted_steps=accepted_steps,
        **context, gradient=terminal_gradient, last_measured_gradient=last_gradient,
        gradient_status='measured_at_endpoint' if terminal_gradient is not None else 'unavailable_at_endpoint',
        one_sided_columns=one_sided, unresolved_columns=unresolved,
        counts_complete_through_last_jacobian=not pending_batch,
        exposure=dict(exposure), per_frequency_exposure={str(int(f)):dict(
            requested_multifrequency_objective_and_model_events=dict(exposure),
            attempted_physical_calls={k.split(':')[1]:v for k,v in ledger.frequency_attempted.items()
                if k.startswith(f'{ledger.stage}:') and k.endswith(f':{f:.0f}')},
            completed_physical_calls={k.split(':')[1]:v for k,v in ledger.frequency_completed.items()
                if k.startswith(f'{ledger.stage}:') and k.endswith(f':{f:.0f}')}) for f in frequencies},
        effective_training_exposure=exposed,
        convergence='CONFIRMED_BY_CONFIGURED_TEST' if result is not None and result.converged else 'UNCONFIRMED',
        work=ledger.snapshot())
    write(output/'terminal.json',terminal)
    return current, terminal


def run_schedule(initial, arm, observed, nodes, solve, optimizer, floor, ledger, output,
                 initial_score, scorer, fit=fit_stage, feasibility=p.feasible, stage_plan=None):
    """Outer owner keeps scorer/evaluation data outside the fit function."""
    plan = tuple(zip((2,3,4),QUOTAS)) if stage_plan is None else tuple(stage_plan)
    if arm not in ('S','F') or not plan or any(
            number not in (1,2,3,4) or quota <= 0 for number,quota in plan):
        raise ValueError('invalid declared continuation schedule')
    if any(b[0] != a[0]+1 for a,b in zip(plan,plan[1:])):
        raise ValueError('continuation stages must be consecutive')
    state = initial
    record = dict(arm=arm,status='IN_PROGRESS',initial_state=p.driver.serialize_state(initial),
                  initial_state_sha256=state_hash(initial),initial=initial_score,stages=[])
    try:
        for number, quota in plan:
            ledger.begin_stage(number,quota)
            active = 1 if arm=='S' else number
            data = p.training_data(p.TRAIN[:active],observed[:,:active])
            start_state_hash = state_hash(state)
            start_score = record.get('final',initial_score)
            state, terminal = fit(state,data,nodes,solve,optimizer,floor,ledger,output/f'stage_{number}')
            row = dict(stage=number,active_frequencies_hz=p.TRAIN[:active],terminal=terminal,
                       start_state_sha256=start_state_hash, start_score=start_score)
            record['stages'].append(row)
            record.pop('final',None)
            record.pop('final_score_state_sha256',None)
            if terminal['stage_outcome'] not in ('NORMAL_OPTIMIZER_RETURN','STAGE_QUOTA_REACHED'):
                record.update(status='HARD_STOP',reason=terminal['stage_outcome']);break
            if not terminal['effective_training_exposure']:
                raise ExposureObstruction('stage lacks a complete usable optimization model')
            if not feasibility(state,nodes,solve,floor):
                raise NumericalFailure('retained endpoint geometry infeasible')
            score = scorer(state)
            row.update(score=score,score_state_sha256=state_hash(state))
            record.update(final=score,final_score_state_sha256=state_hash(state))
            row['work_after_endpoint'] = ledger.snapshot()
            row['aggregate_start_objective'] = .5*float(np.mean(np.asarray(start_score['training_errors'])[:active]**2))
            row['aggregate_endpoint_objective'] = .5*float(np.mean(np.asarray(score['training_errors'])[:active]**2))
            if not score['numerically_qualified']:
                raise NumericalFailure('retained endpoint numerical qualification failed')
            row['stage_complete'] = True
            write(output/'metrics.json',record)
        else: record['status']='COMPLETED_SCHEDULE'
    except Stop as exc:
        record.update(status='HARD_STOP',reason=exc.code,detail=str(exc),traceback=traceback.format_exc())
    except Exception as exc:
        record.update(status='HARD_STOP',reason='IMPLEMENTATION_ERROR',detail=str(exc),traceback=traceback.format_exc())
    finally:
        record.update(final_state=p.driver.serialize_state(state),final_state_sha256=state_hash(state),work=ledger.snapshot())
        record['complete_effective_exposure'] = len(record['stages'])==len(plan) and all(
            r['terminal']['effective_training_exposure'] for r in record['stages'])
        record['numerically_qualified'] = bool(record['stages']) and all(
            r.get('score',{}).get('numerically_qualified',False) for r in record['stages'])
        record['schedule_complete'] = record['status']=='COMPLETED_SCHEDULE'
        record['convergence'] = 'CONFIRMED_BY_CONFIGURED_TESTS' if record['schedule_complete'] and all(
            r['terminal']['convergence']=='CONFIRMED_BY_CONFIGURED_TEST' for r in record['stages']) else 'UNCONFIRMED'
        record['reconstruction_gates_pass'] = record.get('final',{}).get('original_gates_pass',False)
        write(output/'metrics.json',record)
    return record


def observations(bundle, scene):
    saved = read(bundle/'inputs'/scene/'training_observations.json')
    observed = np.array(saved['observed_real'])+1j*np.array(saved['observed_imag'])
    original = read(bundle/'inputs'/scene/'observations.json')
    evaluation = (np.array(original['observed_real'])+1j*np.array(original['observed_imag']))[:,1:]
    return observed, evaluation


def freeze_inputs(bundle):
    # Compare every retained artifact byte against the reviewed git tree.
    listing = subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'--',str(SOURCE.relative_to(ROOT))],cwd=ROOT,text=True).splitlines()
    history = {}
    for name in listing:
        before = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)
        digest = hashlib.sha256(before).hexdigest()
        if p.digest(ROOT/name)!=digest: raise ImplementationError(f'historical artifact changed: {name}')
        history[name]=digest
    base_manifest = read(SOURCE/'manifest.json')
    for name,digest in source_hashes().items():
        # Experiment-owned additions are not inherited TOP-016 source. The
        # follow-up driver is separately frozen by its own output manifest.
        if 'top017' in name or name in ('solvers/sdf_inverse/radial_topology.py',
                                       'run_topology_recovery_followup.py'): continue
        original = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)
        if hashlib.sha256(original).hexdigest()!=digest:
            raise ImplementationError(f'unplanned inherited source change: {name}')
    for name, digest in base_manifest['final_source_sha256'].items():
        original = subprocess.check_output(['git','show',f'{BASE}:{name}'],cwd=ROOT)
        if hashlib.sha256(original).hexdigest()!=digest:
            raise ImplementationError(f'TOP-016 source provenance mismatch: {name}')
        if name!='solvers/sdf_inverse/radial_topology.py' and p.digest(ROOT/name)!=digest:
            raise ImplementationError(f'unplanned change to inherited source: {name}')
    spec = read(p.DATA/'scene_spec.json')
    if spec != read(ROOT/'config/topology_scenes_v1.json'):
        raise ImplementationError('frozen scene specification mismatch')
    screen = read(SOURCE/'phase1/sensitivity.json')
    if screen['status']!='SCREEN_PASS' or screen['selected_nodes']!=list(NODES):
        raise ImplementationError('qualified TOP-016 screen/resolution mismatch')
    states, optimizers, records = {}, {}, {}
    for scene in p.SCENES:
        target = bundle/'inputs'/scene
        target.mkdir(parents=True,exist_ok=False)
        for src,dest in [(SOURCE/'phase1'/f'{scene}_training_observations.json','training_observations.json'),
                         (SOURCE/'phase0/inputs'/scene/'observations.json','observations.json')]:
            shutil.copyfile(src,target/dest)
        saved=read(target/'observations.json')
        generated=p.driver.baseline._problem(np.asarray(saved['frequencies_hz']))
        for attr in ('source_points','receiver_points'):
            np.testing.assert_array_equal(getattr(generated,attr),saved[attr])
        np.testing.assert_array_equal(generated.source_strengths,
            np.asarray(saved['source_strengths_real'])+1j*np.asarray(saved['source_strengths_imag']))
        if any(asdict(getattr(generated,a))!=saved[a] for a in ('exterior','interior')) or any(
                getattr(generated,a)!=saved[a] for a in ('eps0','mu0')):
            raise ImplementationError('copied acquisition/material constants differ from generated problem')
        added=read(target/'training_observations.json')
        if added['frequencies_hz']!=list(p.TRAIN): raise ImplementationError('training frequencies changed')
        for part in ('observed_real','observed_imag'):
            values=np.asarray(added[part]);original=np.asarray(saved[part])
            if values.shape!=(24,4) or original.shape!=(24,3):raise ImplementationError('24-pair data shape mismatch')
            np.testing.assert_array_equal(values[:,0],original[:,0])
        if scene not in SCENES: continue
        s,f = (read(SOURCE/'runs'/f'{arm}-{scene}'/'metrics.json') for arm in ('S','F'))
        if s['final_state']!=f['final_state']: raise ImplementationError('paired states differ')
        h = state_hash(s['final_state'])
        for arm,record in (('S',s),('F',f)):
            stage = SOURCE/'runs'/f'{arm}-{scene}'/'stage_1'
            if [r['stage'] for r in record['stages']] != [1]: raise ImplementationError('prefix stage mismatch')
            if record['final_state']!=read(stage/'accepted_state.json')['state'] or record['final_state']!=read(stage/'terminal.json')['final_state']:
                raise ImplementationError('accepted/terminal endpoint mismatch')
            if record['final']!=record['stages'][0]['score'] or not record['final']['numerically_qualified']:
                raise ImplementationError('saved endpoint score association mismatch')
        write(target/'state.json',s['final_state'])
        shutil.copyfile(SOURCE/'runs'/f'S-{scene}'/'stage_1/optimizer.json',target/'optimizer.json')
        states[scene] = p.driver.deserialize_state(s['final_state'])
        if state_hash(states[scene].polar_angle_gauge_fixed()[0])!=h:
            raise ImplementationError('restart would change saved coefficients')
        if any(c.maximum_mode!=9 for c in states[scene].components): raise ImplementationError('principal K mismatch')
        opt = read(target/'optimizer.json')
        if opt != read(SOURCE/'runs'/f'F-{scene}'/'stage_1/optimizer.json'):
            raise ImplementationError('paired optimizer settings differ')
        optimizers[scene] = opt
        records[scene] = dict(state_sha256=h,source=f'runs/S-{scene}/metrics.json::final_state',
            common_prefix_per_old_arm_solves=s['work']['total_attempted'],original_top016_start_score=s['initial'],
            reused_start_score=s['final'],component_ids=[c.component_id for c in states[scene].components])
    shutil.copyfile(p.DATA/'scene_spec.json',bundle/'scene_spec.json')
    write(bundle/'reuse.json',records)
    write(bundle/'historical_manifest.json',history)
    return spec,states,optimizers


def projection_audit(scene, spec, solve, floor, ledger, observed, evaluation, checkpoint=lambda rows:None):
    truth = p.benchmark.truth_curves(scene)[0]
    rows = {}
    for k in (9,17):
        fits = {}
        row = dict(evaluation_only=True,used_for_inverse=False,maximum_mode=k,dense_geometry={})
        for count in (16384,32768):
            target = truth.discretize(count).points
            c = p.fit_cartesian_fourier_curve_state(target,maximum_mode=k,center=scene['truth'][0]['center'],
                component_id=scene['truth'][0]['component_id'],samples=count)
            state = p.MultiRadialFourierState((c,)).polar_angle_gauge_fixed()[0]
            fits[count] = state
            points = p.boundary_points(state,count)[0]
            distance = max(cKDTree(target).query(points)[0].max(),cKDTree(points).query(target)[0].max())
            row['dense_geometry'][str(count)] = dict(bidirectional_sample_distance_m=float(distance),state_sha256=state_hash(state))
        state = fits[16384]  # fixed existing projection protocol, never best-of-two
        row.update(state=p.driver.serialize_state(state),state_sha256=state_hash(state),
            benchmark_geometry=p.benchmark.geometry_metrics(state,scene,spec),
            radius_floor_m=p.component_radius_floor(state.components[0]),
            gauge_reprojection_maximum_m=state.polar_angle_gauge_fixed()[1],
            feasible_by_nodes={str(n):p.feasible(state,(n,),solve,floor) for n in NODES},
            projection_stability_max_point_m=float(np.max(np.linalg.norm(p.boundary_points(fits[16384],32768)[0]-p.boundary_points(fits[32768],32768)[0],axis=1))))
        rows[str(k)] = row
        checkpoint(rows)
        if all(row['feasible_by_nodes'].values()):
            row['score'] = old.score(state,scene,spec,observed,evaluation,NODES,solve,ledger)
            row['numerically_qualified'] = row['score']['numerically_qualified']
            if not row['numerically_qualified']:
                predictions = {n:p.prediction(state,p.TRAIN+p.EVALUATION,n,solve,ledger,'merge_projection_512_check') for n in (256,512)}
                discrepancy=p.relative(predictions[256],predictions[512])
                errors=p.relative(predictions[512],np.column_stack((observed,evaluation)))
                row['optional_512'] = dict(discrepancy=discrepancy,errors=errors,
                    qualified=bool(np.all(discrepancy<=np.array([1e-5,1e-7,1e-7,1e-7,1e-5,1e-5]))))
                row['audit_numerically_resolved_at_512'] = row['optional_512']['qualified']
        else: row['numerically_qualified']=False
        rows[str(k)] = row
        checkpoint(rows)
    return rows


def phase_a(bundle):
    output = bundle/'phase_a'
    output.mkdir(parents=True,exist_ok=False)
    record = dict(status='IN_PROGRESS',principal_starts={},merge_projection={})
    ledger = Ledger(256,300.)
    try:
        spec,states,optimizers = freeze_inputs(bundle)
        solve = p.driver.baseline.iteration01_solve_config()
        control = p.TopologyControllerConfig(**spec['controller'],refined_feasibility_guard=True,feasible_fd_jacobian=True)
        contract = dict(experiment='TOP-017',reviewed_base=BASE,execution_revision=subprocess.check_output(
            ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),principal_scenes=SCENES,maximum_mode=9,
            nodes=NODES,stage_labels=[2,3,4],stage_quotas=QUOTAS,trial_cap=7000,trial_seconds=1800,
            phase_a_cap=256,phase_a_seconds=300,campaign_watchdog_seconds=7500,maximum_new_solves=28256,
            numerical_workers=2,blas_threads=1,training_frequencies_hz=p.TRAIN,evaluation_frequencies_hz=p.EVALUATION,
            normalization=NORMALIZATION,optimizer=optimizers,solve_config=asdict(solve),
            geometry_configs={str(n):asdict(p.driver.baseline._geometry_config(n)) for n in NODES},
            original_top016_contract_sha256=p.digest(SOURCE/'contract.json'),
            acceptance=dict(absolute_margin=1e-14,relative_margin=1e-8,cross_resolution_factor=5),
            objective_target=1e-14,loss_change_stopping=False,endpoint_reserve=12,
            reset_policy='reset internal optimizer at each boundary, identical for S and F',
            optimizer_receives_truth=False,optimizer_receives_evaluation=False)
        write(bundle/'contract.json',contract)
        write(bundle/'manifest.json',dict(source_sha256=source_hashes(),reviewed_base=BASE,
            execution_revision=contract['execution_revision'],owner='Codex /root',reviewer='Codex /root/top017_review',
            input_sha256={str(x.relative_to(bundle)):p.digest(x) for x in (bundle/'inputs').rglob('*.json')},
            scene_spec_sha256=p.digest(bundle/'scene_spec.json'),historical_manifest_sha256=p.digest(bundle/'historical_manifest.json')))
        # Count only numerical audit wall time, excluding provenance/artifact reads.
        ledger.started = ledger.clock()
        with ledger.instrument():
            for scene in SCENES:
                state = states[scene]
                if not p.feasible(state,NODES,solve,control.minimum_component_radius_m):
                    raise NumericalFailure(f'{scene}: invalid retained start')
                observed,evaluation = observations(bundle,scene)
                item = next(s for s in spec['scenes'] if s['id']==scene)
                score = old.score(state,item,spec,observed,evaluation,NODES,solve,ledger)
                record['principal_starts'][scene] = dict(state_sha256=state_hash(state),feasible=True,score=score)
                write(output/'audit.json',record)
                if not score['numerically_qualified']: raise NumericalFailure(f'{scene}: start numerics fail')
            scene = next(s for s in spec['scenes'] if s['id']=='merge')
            observed,evaluation = observations(bundle,'merge')
            def save_projection(rows):
                record['merge_projection'] = rows
                write(output/'audit.json',record)
            record['merge_projection'] = projection_audit(scene,spec,solve,control.minimum_component_radius_m,ledger,observed,evaluation,save_projection)
        verify_sources(read(bundle/'manifest.json')['source_sha256'])
        record['status']='PHASE_A_PASS'
    except Stop as exc:
        record.update(status='OBSTRUCTION',reason=exc.code,detail=str(exc),traceback=traceback.format_exc())
    except Exception as exc:
        record.update(status='IMPLEMENTATION_ERROR',reason=str(exc),traceback=traceback.format_exc())
    finally:
        record['work']=ledger.snapshot()
        write(output/'audit.json',record)
        print(json.dumps(dict(status=record['status'],work=record['work'])),flush=True)
    return record


def trial(bundle, scene, arm):
    audit = read(bundle/'phase_a/audit.json')
    if audit['status']!='PHASE_A_PASS': raise ImplementationError('Phase A has not released trials')
    manifest = read(bundle/'manifest.json')
    verify_sources(manifest['source_sha256'])
    for name,digest in manifest['input_sha256'].items():
        if p.digest(bundle/name)!=digest: raise ImplementationError(f'input changed: {name}')
    if p.digest(bundle/'scene_spec.json')!=manifest['scene_spec_sha256']: raise ImplementationError('spec changed')
    output = bundle/'runs'/f'{arm}-{scene}'
    output.mkdir(parents=True,exist_ok=False)
    state = p.driver.deserialize_state(read(bundle/'inputs'/scene/'state.json'))
    opt = read(bundle/'inputs'/scene/'optimizer.json')
    optimizer = rt.ParameterFDConfig(**opt['config'])
    solve = p.driver.baseline.iteration01_solve_config()
    spec = read(bundle/'scene_spec.json')
    item = next(s for s in spec['scenes'] if s['id']==scene)
    observed,evaluation = observations(bundle,scene)
    write(output/'manifest.json',dict(source_sha256=source_hashes(),initial_state_sha256=state_hash(state),
          input_manifest_sha256=p.digest(bundle/'manifest.json'),command=sys.argv,
          training_observations_sha256=p.digest(bundle/'inputs'/scene/'training_observations.json'),
          optimizer_receives_truth=False,optimizer_receives_evaluation=False))
    ledger = Ledger()
    scorer = lambda s:old.score(s,item,spec,observed,evaluation,NODES,solve,ledger)
    with ledger.instrument():
        record = run_schedule(state,arm,observed,NODES,solve,optimizer,opt['minimum_component_radius_m'],
             ledger,output,audit['principal_starts'][scene]['score'],scorer)
    record['scene'] = scene
    record['sources_unchanged'] = source_hashes()==manifest['source_sha256']
    if not record['sources_unchanged']:
        record.update(status='HARD_STOP',reason='IMPLEMENTATION_ERROR',numerically_qualified=False,
                      schedule_complete=False,convergence='UNCONFIRMED')
    write(output/'metrics.json',record)
    print(json.dumps(dict(scene=scene,arm=arm,status=record['status'],reason=record.get('reason'),work=record['work'])),flush=True)
    return record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--phase',choices=('audit','trial'),required=True)
    parser.add_argument('--scene',choices=SCENES)
    parser.add_argument('--arm',choices=('S','F'))
    args=parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='1': raise ValueError('single-thread BLAS required')
    bundle=args.bundle.resolve()
    if args.phase=='audit': phase_a(bundle)
    else:
        if args.scene is None or args.arm is None: parser.error('trial needs scene and arm')
        trial(bundle,args.scene,args.arm)

if __name__=='__main__':main()
