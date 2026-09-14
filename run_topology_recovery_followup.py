"""Bounded engineering follow-up: saved-state numerics or one fresh circle run.

No new observations, truth-assisted initialization, automatic retries or defaults.
Use --phase resolution / central with distinct, nonexistent --output directories.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

import numpy as np
import run_top017 as m
from sdf_inverse import work_accounting
from sdf_inverse.topology_controller import GEOMETRY_ERRORS

p = m.p
ROOT = m.ROOT
HISTORY = ROOT / 'results/validation/topology/TOP-017-20260914-staged-continuation'
CENTRAL = 'central-ellipse-star'
FREQUENCIES = p.TRAIN + p.EVALUATION
TOLERANCES = np.array([1e-5, 1e-7, 1e-7, 1e-7, 1e-5, 1e-5])
FULL_PLAN = ((1, 1000), (2, 1250), (3, 1750), (4, 4000))
write, read = m.write, m.read


def complex_record(value):
    return dict(real=np.asarray(value).real, imag=np.asarray(value).imag)


def archived_states():
    """Replay only an archived rejected step; the exact hash is mandatory."""
    far = HISTORY / 'runs/F-far-two-stars/stage_2'
    checkpoint = read(far / 'accepted_state.json')
    base = p.driver.deserialize_state(checkpoint['state'])
    attempt = json.loads((far / 'candidate_attempts.jsonl').read_text().splitlines()[-1])
    acceptance = read(far / 'acceptance.json')[-1]
    if not (m.state_hash(base) == checkpoint['state_sha256'] ==
            attempt['base_state_sha256'] == acceptance['base_state_sha256']):
        raise m.ImplementationError('archived rejected candidate base mismatch')
    candidate, _ = base.incremented(np.asarray(attempt['step'])).polar_angle_gauge_fixed()
    if m.state_hash(candidate) != acceptance['candidate_state_sha256']:
        raise m.ImplementationError('reconstructed candidate hash differs from archive')
    endpoint = read(HISTORY / 'runs/S-far-two-stars/stage_3/accepted_state.json')
    state = p.driver.deserialize_state(endpoint['state'])
    if m.state_hash(state) != endpoint['state_sha256']:
        raise m.ImplementationError('S endpoint checkpoint hash mismatch')
    return {'F_retained': base, 'F_rejected': candidate, 'S_endpoint': state}


def freeze(output, phase):
    output.mkdir(parents=True, exist_ok=False)
    roots = (p.DATA, m.SOURCE, HISTORY)
    names = subprocess.check_output(['git', 'ls-files', '--',
        *[str(x.relative_to(ROOT)) for x in roots]], cwd=ROOT, text=True).splitlines()
    manifest = dict(phase=phase, command=sys.argv,
        git_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=m.source_hashes(),
        historical_sha256={name:p.digest(ROOT/name) for name in names},
        numerical_workers=1, blas_threads=1, new_observations=False,
        supplied_target_count=False, optimizer_receives_truth=False,
        optimizer_receives_evaluation=False)
    write(output/'manifest.json',manifest)
    return manifest


def verify(manifest):
    m.verify_sources(manifest['source_sha256'])
    for name, sha in manifest['historical_sha256'].items():
        if p.digest(ROOT/name) != sha:
            raise m.ImplementationError(f'historical input changed: {name}')
    for name,sha in {**manifest.get('copied_input_sha256',{}),
                     **manifest.get('prior_attempt_sha256',{})}.items():
        if p.digest(Path(name)) != sha:
            raise m.ImplementationError(f'copied input changed: {name}')


def seal(output, manifest, result):
    try:
        verify(manifest)
        result['sources_and_history_unchanged'] = True
    except Exception:
        result.update(status='IMPLEMENTATION_ERROR', sources_and_history_unchanged=False,
                      integrity_error=traceback.format_exc())
    write(output/'result.json',result)
    write(output/'artifact_manifest.json', {str(x.relative_to(output)):p.digest(x)
        for x in sorted(output.rglob('*')) if x.is_file() and x.name!='artifact_manifest.json'})
    return result


def resolution(output):
    manifest = freeze(output, 'resolution')
    ledger = m.Ledger(cap=72, seconds=300)
    result = dict(status='IN_PROGRESS', states={}, frequencies_hz=FREQUENCIES,
                  prediction_tolerances=TOLERANCES, no_optimization=True)
    solve = p.driver.baseline.iteration01_solve_config()
    write(output/'contract.json',dict(nodes=[128,256,512],solve_cap=72,wall_seconds=300,
          solve_config=asdict(solve),frequencies_hz=FREQUENCIES,tolerances=TOLERANCES))
    try:
        states = archived_states()
        predictions = {}
        with ledger.instrument():
            for name,state in states.items():
                row = dict(state=p.driver.serialize_state(state),state_sha256=m.state_hash(state),
                           feasible={},predictions={},comparisons={})
                result['states'][name] = row
                predictions[name] = {}
                for nodes in (128,256,512):
                    row['feasible'][str(nodes)] = p.feasible(state,(nodes,),solve,.008)
                    if not row['feasible'][str(nodes)]:
                        raise m.NumericalFailure(f'{name} infeasible at {nodes} nodes')
                    value = p.prediction(state,FREQUENCIES,nodes,solve,ledger,name)
                    predictions[name][nodes] = value
                    row['predictions'][str(nodes)] = complex_record(value)
                    write(output/'progress.json',result)
                for low,high in ((128,256),(256,512)):
                    discrepancy = p.relative(predictions[name][low],predictions[name][high])
                    row['comparisons'][f'{low}/{high}'] = dict(discrepancy=discrepancy,
                        qualified=bool(np.all(np.isfinite(discrepancy)) and
                                       np.all(discrepancy<=TOLERANCES)))
                print(name,{k:v['qualified'] for k,v in row['comparisons'].items()},flush=True)
        # Training-only loss agreement of the archived rejected F step.
        observed,_ = m.observations(HISTORY,'far-two-stars')
        losses = {name:{str(n):.5*float(np.mean(p.relative(values[:,:2],observed[:,:2])**2))
            for n,values in predictions[name].items()} for name in ('F_retained','F_rejected')}
        result['F_step_losses'] = losses
        result['F_step_acceptance_256_512'] = m.old.acceptance(
            losses['F_retained']['256'],losses['F_rejected']['256'],
            losses['F_retained']['512'],losses['F_rejected']['512'])
        result['all_states_qualify_256_512'] = all(
            r['comparisons']['256/512']['qualified'] for r in result['states'].values())
        result['status'] = 'RESOLUTION_CHECK_COMPLETE'
    except Exception as exc:
        result.update(status='HARD_STOP',reason=getattr(exc,'code',type(exc).__name__),
                      detail=str(exc),traceback=traceback.format_exc())
    result['work'] = ledger.snapshot()
    return seal(output,manifest,result)


class TopologyLedger(m.Ledger):
    """Count TD system attempts as well as the existing forward solve wrapper.

The TD builds/solves its own system, outside the paired-forward wrapper. Its
existing record_work callback reports completion immediately after the solve.
    Only instrumentation changes; numerical arguments and return values are intact.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, preserve_errors=GEOMETRY_ERRORS)

    @contextmanager
    def instrument(self):
        build = m.rt.build_multicomponent_kress_tmz_frequency_system
        record = work_accounting.record_work
        pending = []

        def counted_build(boundary, omega, **kwargs):
            self.reserve(1)
            key = f'{self.stage}:topological_derivative:{float(omega)/(2*np.pi):.0f}'
            self.attempted['topological_derivative'] += 1
            self.frequency_attempted[key] += 1
            pending.append(key)
            return build(boundary,omega,**kwargs)

        def counted_record(**counts):
            for _ in range(counts.get('td_frequency_solve_count',0)):
                if not pending:
                    raise m.ImplementationError('TD completion without a reserved system')
                key = pending.pop(0)
                self.completed['topological_derivative'] += 1
                self.frequency_completed[key] += 1
            return record(**counts)

        m.rt.build_multicomponent_kress_tmz_frequency_system = counted_build
        work_accounting.record_work = counted_record
        try:
            with super().instrument():
                yield
        finally:
            for key in pending:
                self.failed['topological_derivative'] += 1
                self.frequency_failed[key] += 1
            m.rt.build_multicomponent_kress_tmz_frequency_system = build
            work_accounting.record_work = record


def topology_prefix(initial, data, control, solve, ledger, output, controller=None):
    """Training-only autonomous topology phase. No desired count or target shape."""
    controller = p.benchmark.run_topology_aware_fourier_inverse if controller is None else controller
    output.mkdir(parents=True,exist_ok=False)
    write(output/'initial_state.json',p.driver.serialize_state(initial))
    def progress(frame):
        row = dict(cycle=frame.cycle,label=frame.label,loss=frame.loss,
                   state=p.driver.serialize_state(frame.state),work=ledger.snapshot())
        write(output/'checkpoint.json',row)
        with (output/'trajectory.jsonl').open('a') as stream:
            stream.write(json.dumps(row,default=lambda x:x.tolist() if hasattr(x,'tolist') else float(x))+'\n')
        print('topology',frame.cycle,frame.label,frame.loss,'solves',ledger.total,flush=True)
    with ledger.category_scope('topology_forward'):
        result = controller(initial,data,p.driver.baseline._geometry_config(64),
            p.driver.baseline._geometry_config(128),solve_config=solve,
            config=control,progress_callback=progress)
    write(output/'terminal.json',dict(stop_reason=result.stop_reason,
        final_state=p.driver.serialize_state(result.final_state),events=result.events,
        controller_work=result.work,work=ledger.snapshot()))
    write(output/'events.json',result.events)
    write(output/'topology_passes.json',result.passes)
    if result.stop_reason not in ('topology_stationary','recovered'):
        raise m.NumericalFailure(f'topology did not reach a declared handoff: {result.stop_reason}')
    return result.final_state


def continuation_start(state, control, solve):
    """Qualify and zero-pad whatever topology was found, without a count oracle."""
    if state is None:
        raise m.NumericalFailure('empty automatic topology endpoint')
    padded = p.padded(state)
    delta = max(float(np.max(np.linalg.norm(a-b,axis=1)))
                for a,b in zip(p.boundary_points(state),p.boundary_points(padded)))
    if delta > 1e-10:
        raise m.ImplementationError('padding changed the automatic endpoint geometry')
    if not p.feasible(padded,m.NODES,solve,control.minimum_component_radius_m):
        raise m.NumericalFailure('automatic topology endpoint fails continuation geometry checks')
    optimizer = replace(p._optimizer_config(padded,control),loss_tolerance=1e-14)
    return padded,optimizer,delta


def central(output, repair_of=None):
    manifest = freeze(output,'central')
    prior_work = None
    if repair_of is not None:
        prior = read(repair_of/'result.json')
        if (prior.get('reason')!='PHYSICAL_SOLVE_FAILED' or prior.get('continuation_work') is not None
                or not prior.get('detail','').startswith('MultiComponentTopologyError:')
                or prior.get('prior_attempt_work') is not None):
            raise m.ImplementationError('repair budget requires the single saved instrumentation failure')
        prior_work = prior['topology_work']
        manifest['prior_attempt_sha256'] = {str(x):p.digest(x) for x in repair_of.rglob('*') if x.is_file()}
        write(output/'manifest.json',manifest)
    prior_solves = 0 if prior_work is None else prior_work['total_attempted']
    prior_seconds = 0 if prior_work is None else prior_work['active_wall_seconds']
    prefix_ledger = TopologyLedger(cap=4000-prior_solves,seconds=600-prior_seconds)
    prefix_work = None
    continuation_ledger = None
    result = dict(status='IN_PROGRESS',fresh_circle_start=True,
                  archived_optimized_state_used=False,supplied_target_count=False)
    inputs = output/'inputs'
    inputs.mkdir()
    for name,source in {
        'scene_spec.json':p.DATA/'scene_spec.json',
        'initial_state.json':p.DATA/'scenes'/CENTRAL/'initial_state.json',
        'observations.json':HISTORY/'inputs'/CENTRAL/'observations.json',
        'training_observations.json':HISTORY/'inputs'/CENTRAL/'training_observations.json',
    }.items():
        shutil.copyfile(source,inputs/name)
    spec = read(inputs/'scene_spec.json')
    scene = next(s for s in spec['scenes'] if s['id']==CENTRAL)
    initial = p.driver.deserialize_state(read(inputs/'initial_state.json'))
    control = p.benchmark.controller_config(spec,'H')
    solve = p.driver.baseline.iteration01_solve_config()
    saved = read(inputs/'training_observations.json')
    observed = np.array(saved['observed_real'])+1j*np.array(saved['observed_imag'])
    original = read(inputs/'observations.json')
    evaluation = (np.array(original['observed_real'])+1j*np.array(original['observed_imag']))[:,1:]
    reference_training,reference_evaluation = p.benchmark.shared_data(p.DATA,scene,spec)
    np.testing.assert_array_equal(saved['frequencies_hz'],p.TRAIN)
    np.testing.assert_array_equal(observed[:,:1],reference_training.observed_scattered_response)
    np.testing.assert_array_equal(evaluation,reference_evaluation.observed_scattered_response)
    np.testing.assert_array_equal(initial.parameter_vector(),p.benchmark.initial_state(scene).parameter_vector())
    if len(initial.components)!=1 or initial.component_ids!=('initial.circle',):
        raise m.ImplementationError('fresh circle input differs from declared initialization')
    write(output/'contract.json',dict(topology_controller=asdict(control),
        topology_nodes=[64,128],topology_solve_cap=prefix_ledger.cap,
        topology_wall_seconds=prefix_ledger.seconds,prior_attempt_work=prior_work,
        continuation_nodes=m.NODES,stage_plan=FULL_PLAN,continuation_solve_cap=8012,
        continuation_wall_seconds=1800,solve_config=asdict(solve),
        initial_state_sha256=m.state_hash(initial),training_frequencies_hz=p.TRAIN,
        evaluation_frequencies_hz=p.EVALUATION,normalization=m.NORMALIZATION,
        handoff_uses_truth_or_target_count=False,
        input_sha256={x.name:p.digest(x) for x in inputs.iterdir()}))
    manifest['copied_input_sha256'] = {str(x):p.digest(x) for x in inputs.iterdir()}
    write(output/'manifest.json',manifest)
    try:
        prefix_ledger.started = prefix_ledger.clock()
        with prefix_ledger.instrument():
            state = topology_prefix(initial,p.training_data(p.TRAIN[:1],observed[:,:1]),
                                    control,solve,prefix_ledger,output/'topology')
        prefix_work = prefix_ledger.snapshot()
        passive_count = read(output/'topology/terminal.json')['controller_work']['totals']['bie_frequency_solve_count']
        if sum(prefix_work['completed'].values()) != passive_count:
            raise m.ImplementationError('topology physical ledger disagrees with passive controller counts')
        state,optimizer,delta = continuation_start(state,control,solve)
        write(output/'handoff.json',dict(state=p.driver.serialize_state(state),
            state_sha256=m.state_hash(state),zero_padding_maximum_point_change_m=delta,
            supplied_target_count=False,optimizer=asdict(optimizer)))
        continuation_ledger = m.Ledger(cap=8012,seconds=1800)
        (output/'continuation').mkdir()
        scorer = lambda s:m.old.score(s,scene,spec,observed,evaluation,m.NODES,solve,continuation_ledger)
        with continuation_ledger.instrument():
            initial_score = scorer(state)
            write(output/'initial_continuation_score.json',initial_score)
            if not initial_score['numerically_qualified']:
                raise m.NumericalFailure('automatic endpoint fails continuation numerical qualification')
            schedule = m.run_schedule(state,'F',observed,m.NODES,solve,optimizer,
                control.minimum_component_radius_m,continuation_ledger,output/'continuation',
                initial_score,scorer,stage_plan=FULL_PLAN)
        result.update(status=schedule['status'],schedule=schedule,
            fresh_recovery_pass=bool(schedule['schedule_complete'] and
                schedule['numerically_qualified'] and schedule['reconstruction_gates_pass']))
    except Exception as exc:
        result.update(status='HARD_STOP',fresh_recovery_pass=False,
            reason=getattr(exc,'code',type(exc).__name__),detail=str(exc),traceback=traceback.format_exc())
    result['topology_work'] = prefix_ledger.snapshot() if prefix_work is None else prefix_work
    result['continuation_work'] = None if continuation_ledger is None else continuation_ledger.snapshot()
    result['total_attempted_frequency_solves'] = prefix_ledger.total + (
        0 if continuation_ledger is None else continuation_ledger.total)
    result['active_wall_seconds'] = result['topology_work']['active_wall_seconds'] + (
        0 if continuation_ledger is None else result['continuation_work']['active_wall_seconds'])
    result['prior_attempt_work'] = prior_work
    result['total_attempted_including_prior_attempt'] = result['total_attempted_frequency_solves']+prior_solves
    result['active_wall_seconds_including_prior_attempt'] = result['active_wall_seconds']+prior_seconds
    return seal(output,manifest,result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('resolution','central'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--repair-of',type=Path,help='Charge the saved instrumentation failure against the same budget')
    args = parser.parse_args()
    for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        if os.environ.get(key)!='1':
            raise ValueError('single-thread BLAS required')
    if args.repair_of is not None and args.phase!='central':
        parser.error('--repair-of is only valid for the central integration repair')
    result = (resolution(args.output.resolve()) if args.phase=='resolution' else
              central(args.output.resolve(),None if args.repair_of is None else args.repair_of.resolve()))
    print(json.dumps({key:result[key] for key in ('status','fresh_recovery_pass',
        'all_states_qualify_256_512','sources_and_history_unchanged') if key in result}),flush=True)
    return 0 if result['status'] in ('RESOLUTION_CHECK_COMPLETE','COMPLETED_SCHEDULE') else 1


if __name__=='__main__':
    sys.exit(main())
