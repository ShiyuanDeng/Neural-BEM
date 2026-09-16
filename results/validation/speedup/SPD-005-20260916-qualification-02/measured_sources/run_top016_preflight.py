"""TOP-016 bounded input, representation and numerical preflight; no inverse.

Run with single-thread BLAS. New output only; it never overwrites a run.
The physical solve wrapper counts attempted/completed/failed frequency solves.
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

import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'solvers'))
import run_topology_scene_benchmark as benchmark
import run_fourier_topology_controller as driver
from ordered_boundary import OrderedBoundary2D
from sdf_inverse.radial_topology import (MultiRadialFourierState,
    component_radius_floor, evaluate_multiradial_objective,
    multiradial_geometry_admissible)
from sdf_inverse.topology_controller import (TopologyControllerConfig,
    _optimizer_config, component_parameterization, zero_padded_component)
from sdf_inverse.curve_updates import fit_cartesian_fourier_curve_state
from sdf_inverse.optimization import ComplexScatteredData, normalized_complex_residual
import sdf_bem_multicomponent.forward as physical

DATA = ROOT / 'results/validation/topology/TOP-008-20260912-feasible-fd'
PLATEAU = ROOT / 'results/validation/topology/TOP-010-20260912-stopping-vs-stationarity/stageB_restart_continuation.json'
SCENES = ('far-two-stars', 'central-ellipse-star', 'merge')
TRAIN = (0.5e9, 0.75e9, 1.e9, 1.25e9)
EVALUATION = (1.5e9, 2.5e9)
NODE_PAIRS = ((64, 128), (128, 256), (256, 512))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    driver.write_json(Path(path), value)


class Obstruction(RuntimeError):
    pass


class Budget(Obstruction):
    pass


class Ledger:
    def __init__(self, cap=5000, seconds=1200., clock=time.perf_counter):
        self.cap, self.seconds, self.clock = cap, seconds, clock
        self.started = clock()
        self.attempted, self.completed, self.failed = Counter(), Counter(), Counter()
        self.derivative_attempted, self.derivative_completed, self.derivative_failed = Counter(), Counter(), Counter()
        self.reciprocal_attempted, self.reciprocal_completed, self.reciprocal_failed = Counter(), Counter(), Counter()
        self.calls = Counter()
        self.category = 'unclassified'

    @property
    def total(self):
        return sum(self.attempted.values())

    @property
    def budget_total(self):
        return self.total + sum(self.derivative_attempted.values()) + sum(self.reciprocal_attempted.values())

    def analytic_event(self, event, kind, omega, error):
        if kind not in ('base', 'direction', 'reciprocal'):
            raise ValueError('Unknown analytic work kind: '+kind)
        if event == 'attempt':
            self.reserve(1)
        category = self.category
        prefix = {'base':'', 'direction':'derivative_', 'reciprocal':'reciprocal_'}[kind]
        counters = {key:getattr(self, prefix+name) for key,name in
                    (('attempt','attempted'), ('completed','completed'), ('failed','failed'))}
        counters[event][category] += 1
        if kind == 'base' and hasattr(self, 'frequency_attempted'):
            key = f'{self.stage}:{category}:{float(omega)/(2*np.pi):.0f}'
            getattr(self, 'frequency_'+('attempted' if event == 'attempt' else event))[key] += 1

    def reserve(self, maximum):
        # This single-worker precheck guarantees a known batch fits. Individual
        # calls still enforce the cap/time; unused reserved work is not charged.
        if self.budget_total + maximum > self.cap:
            raise Budget(f'batch of {maximum} cannot fit remaining {self.cap-self.budget_total} work units')
        if self.clock()-self.started >= self.seconds:
            raise Budget('phase01 wall-clock ceiling')

    def snapshot(self):
        return dict(attempted=dict(self.attempted), completed=dict(self.completed),
                    failed=dict(self.failed), total_attempted=self.total,
                    calls=dict(self.calls), active_wall_seconds=self.clock()-self.started,
                    solve_cap=self.cap, wall_ceiling_seconds=self.seconds,
                    within_solve_cap=self.budget_total <= self.cap,
                    derivative_assemblies_attempted=dict(self.derivative_attempted),
                    derivative_assemblies_completed=dict(self.derivative_completed),
                    derivative_assemblies_failed=dict(self.derivative_failed),
                    reciprocal_batches_attempted=dict(self.reciprocal_attempted),
                    reciprocal_batches_completed=dict(self.reciprocal_completed),
                    reciprocal_batches_failed=dict(self.reciprocal_failed),
                    budget_work_units=self.budget_total,
                    budget_unit='one full frequency system, operator direction/tangent, or reciprocal RHS batch')

    @contextmanager
    def category_scope(self, name):
        old = self.category
        self.category = name
        try:
            yield
        finally:
            self.category = old

    @contextmanager
    def instrument(self):
        original = physical.solve_multicomponent_kress_tmz_total_field_batch
        def counted(*args, **kwargs):
            self.reserve(1)
            name = self.category
            self.attempted[name] += 1
            try:
                value = original(*args, **kwargs)
            except BaseException:
                self.failed[name] += 1
                raise
            self.completed[name] += 1
            return value
        physical.solve_multicomponent_kress_tmz_total_field_batch = counted
        old_handler = signal.getsignal(signal.SIGALRM)
        def alarm(*_):
            raise Budget('phase01 wall-clock ceiling during numerical work')
        signal.signal(signal.SIGALRM, alarm)
        signal.setitimer(signal.ITIMER_REAL, max(.001, self.seconds-(self.clock()-self.started)))
        try:
            from sdf_inverse.work_accounting import observe_analytic_work
            with observe_analytic_work(self.analytic_event):
                yield
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
            physical.solve_multicomponent_kress_tmz_total_field_batch = original


def padded(state):
    if any(c.maximum_mode > 9 for c in state.components):
        raise Obstruction('prescribed input exceeds K=9; truncation forbidden')
    return MultiRadialFourierState(tuple(zero_padded_component(c, 9)
        if c.maximum_mode < 9 else c for c in state.components))


def training_data(frequencies, observed):
    if any(f not in TRAIN for f in frequencies):
        raise ValueError('evaluation-only frequency excluded from optimizer data')
    observed = np.asarray(observed, complex)
    norms = np.linalg.norm(observed, axis=0)
    floor = 1e-12 * max(1., float(np.max(norms)), float(np.linalg.norm(observed))/np.sqrt(len(norms)))
    if not np.all(np.isfinite(norms)) or np.any(norms <= floor):
        raise Obstruction('unusable observation norm')
    return ComplexScatteredData(driver.baseline._problem(np.asarray(frequencies)),
                                observed, np.ones(len(frequencies))/len(frequencies))


def boundary_points(state, count=4096):
    return [component_parameterization(c).discretize(count).points for c in state.components]


def feasible(state, nodes, solve, floor):
    return (all(component_radius_floor(c) >= floor for c in state.components)
            and all(multiradial_geometry_admissible(state, driver.baseline._geometry_config(n),
                                                   solve_config=solve) for n in nodes))


def representation_state(scene):
    # Evaluation-only fit; never returned as a main-trial initialization.
    curves = benchmark.truth_curves(scene)
    components = [fit_cartesian_fourier_curve_state(curve.discretize(16384).points,
        maximum_mode=9, center=item['center'], component_id=item['component_id'], samples=16384)
        for curve, item in zip(curves, scene['truth'])]
    return MultiRadialFourierState(tuple(components)).polar_angle_gauge_fixed()[0]


def load_inputs(output):
    spec = benchmark.read(DATA/'scene_spec.json')
    if spec != benchmark.read(ROOT/'config/topology_scenes_v1.json'):
        raise Obstruction('historical spec differs from frozen v1')
    manifest, states, trainings, evaluations, scene_map = {}, {}, {}, {}, {}
    for scene in spec['scenes']:
        if scene['id'] not in SCENES:
            continue
        name = scene['id']; scene_map[name] = scene
        path = PLATEAU if name == SCENES[0] else DATA/'runs/H'/name/'metrics.json'
        record = benchmark.read(path)
        if name != SCENES[0] and not record['completed']:
            raise Obstruction(f'{name}: prescribed endpoint not completed')
        original = driver.deserialize_state(record['final_state'])
        state = padded(original)
        if len(state.components) != len(scene['truth']):
            raise Obstruction(f'{name}: input count does not meet contract')
        delta = max(float(np.max(np.linalg.norm(a-b, axis=1)))
                    for a,b in zip(boundary_points(original), boundary_points(state)))
        if delta > 1e-10:
            raise Obstruction(f'{name}: zero-padding changed physical boundary')
        target = output/'inputs'/name; target.mkdir(parents=True)
        observation = DATA/'scenes'/name/'observations.json'
        shutil.copyfile(observation, target/'observations.json')
        shutil.copyfile(path, target/'source_record.json')
        shutil.copyfile(DATA/'scenes'/name/'scene.json', target/'scene.json')
        training, evaluation = benchmark.shared_data(DATA, scene, spec)
        if training.observed_scattered_response.shape != (24,1):
            raise Obstruction('expected original 24-pair observations')
        if name != SCENES[0]:
            run_manifest=benchmark.read(DATA/'runs/H'/name/'manifest.json')
            if run_manifest['observations_sha256'] != digest(observation):
                raise Obstruction('observations do not match producing run')
        trainings[name] = training_data((TRAIN[0],), training.observed_scattered_response)
        evaluations[name] = evaluation
        states[name] = state
        write(target/'state.json', driver.serialize_state(state))
        manifest[name] = dict(source_path=str(path.relative_to(ROOT)), field='final_state',
            source_sha256=digest(path), observations_path=str(observation.relative_to(ROOT)),
            observations_sha256=digest(observation), portable_observations_sha256=digest(target/'observations.json'),
            component_ids=[c.component_id for c in state.components],
            original_modes=[c.maximum_mode for c in original.components],
            initial_coefficients=driver.serialize_state(state), zero_padding_maximum_point_change_m=delta,
            gauge_directions=len(state.gauge_tangent_basis()),
            retained_input_not_rejected_restart=True if name == SCENES[0] else None,
            original_state=driver.serialize_state(original))
    if set(states) != set(SCENES):
        raise Obstruction('missing prescribed scene')
    return spec, scene_map, states, trainings, evaluations, manifest


def prediction(state, frequencies, nodes, solve, ledger, category):
    ledger.reserve(len(frequencies)); ledger.calls[category] += 1
    with ledger.category_scope(category):
        return physical.predict_multicomponent_kress_paired_boundary_response(
            state.boundary(driver.baseline._geometry_config(nodes)),
            driver.baseline._problem(np.asarray(frequencies)), solve_config=solve).scattered_response


def relative(a,b):
    return np.linalg.norm(a-b, axis=0)/np.linalg.norm(b, axis=0)


def run_preflight(output, ledger, record):
    spec, scenes, states, trainings, evaluations, inputs = load_inputs(output)
    record['inputs'] = inputs
    solve = driver.baseline.iteration01_solve_config()
    control = TopologyControllerConfig(**spec['controller'], refined_feasibility_guard=True,
                                      feasible_fd_jacobian=True)
    record['solve_config'] = asdict(solve)
    record['controller_reference'] = asdict(control)
    record['optimizer_reference'] = {name:asdict(_optimizer_config(s,control)) for name,s in states.items()}
    write(output/'preflight.json', record)
    representation = {}
    for name in SCENES[:2]:
        truth_fit = representation_state(scenes[name])
        metrics = benchmark.geometry_metrics(truth_fit, scenes[name], spec)
        validity = {str(n):feasible(truth_fit,(n,),solve,control.minimum_component_radius_m)
                    for n in (64,128,256,512)}
        representation[name] = dict(metrics=metrics, feasible_by_nodes=validity,
            state=driver.serialize_state(truth_fit), evaluation_only=True,
            passed=metrics['maximum_matched_hausdorff_m'] <= 1e-4 and all(validity.values()))
        record['representation'] = representation
        write(output/'preflight.json',record)
        print('representation',name,metrics['maximum_matched_hausdorff_m']*1e3,'mm',validity,flush=True)
        if not representation[name]['passed']:
            raise Obstruction(f'representation/feasible-set gate failed for {name}')
    # Check all candidate node pairs before generating any new truth data.
    qualification, cache = [], {}
    for low,high in NODE_PAIRS:
        row = dict(nodes=[low,high],scenes={},passed=True)
        for name in SCENES:
            state=states[name]
            if not feasible(state,(low,high),solve,control.minimum_component_radius_m):
                row['scenes'][name]=dict(feasible=False);row['passed']=False
                continue
            for nodes in (low,high):
                if (name,nodes) not in cache:
                    cache[name,nodes]=prediction(state,TRAIN,nodes,solve,ledger,'start_resolution')
            errors=relative(cache[name,low],cache[name,high])
            row['scenes'][name]=dict(feasible=True,relative_discrepancy=errors,
                passed=bool(np.max(errors[1:])<=1e-7 and np.max(errors)<=spec['oracle_relative_tolerance']))
            row['passed'] &= row['scenes'][name]['passed']
        qualification.append(row);record['resolution_ladder']=qualification
        write(output/'preflight.json',record)
        print('resolution',low,high,row['passed'],flush=True)
        if row['passed']:
            record['selected_nodes']=[low,high]
            break
    else:
        raise Obstruction('no declared production/refined node pair qualifies saved states')
    low,high=record['selected_nodes']
    for name in SCENES:
        original=driver.deserialize_state(inputs[name]['original_state'])
        before=prediction(original,(TRAIN[0],),low,solve,ledger,'padding_prediction')
        after=cache[name,low][:,:1]
        discrepancy=float(relative(before,after)[0])
        inputs[name]['padding_prediction_relative_discrepancy']=discrepancy
        if discrepancy>1e-10:
            raise Obstruction(f'{name}: padding prediction differs')
    record['status']='INPUT_AND_RESOLUTION_PASS'
    write(output/'preflight.json',record)
    return spec,scenes,states,trainings,evaluations,solve,control,cache


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=False)
    threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}
    if any(v!='1' for v in threads.values()):
        raise ValueError('set OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=MKL_NUM_THREADS=1')
    sources=[Path(__file__),*sorted((ROOT/'solvers').rglob('*.py')),
             ROOT/'run_topology_scene_benchmark.py',ROOT/'run_fourier_topology_controller.py',
             ROOT/'config/topology_scenes_v1.json',ROOT/'config/topology_scenes_v2.json']
    manifest=dict(experiment='TOP-016',execution_revision=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sources},
        python=sys.version,platform=platform.platform(),cpu=platform.processor(),
        threads=threads,concurrency=1,load_average=os.getloadavg(),
        command=sys.argv,owner='Codex /root',reviewer='Codex /root/top016_review')
    write(output/'manifest.json',manifest)
    contract=dict(experiment='TOP-016',training_frequencies_hz=TRAIN,evaluation_frequencies_hz=EVALUATION,
        maximum_mode=9,node_pairs=NODE_PAIRS,phase01_frequency_solve_cap=5000,phase01_seconds=1200,
        principal_scenes=SCENES[:2],control_scene=SCENES[2],stage_caps=[1000,1250,1750,4000],
        main_arm_cap=8000,main_arm_seconds=1800,optional_local_stage_caps=[250,350,500,900],
        optional_local_arm_cap=2000,optional_local_arm_seconds=600,
        objective_target=1e-14,loss_change_stopping=False,absolute_margin=1e-14,relative_margin=1e-8,
        representation_error_m=1e-4,padding_error_m=1e-10,new_frequency_resolution_relative=1e-7,
        screen=dict(directions=8,amplitudes_m=[.0005,.001],signs=[-1,1],median_gain=1.5,
                    fraction_gain=0.5,minimum_usable=4,uncertainty_factor=5),
        optimizer_receives_truth=False,optimizer_receives_evaluation=False)
    write(output/'contract.json',contract)
    ledger=Ledger();record=dict(status='IN_PROGRESS')
    try:
        with ledger.instrument():
            run_preflight(output,ledger,record)
    except Obstruction as exc:
        record.update(status='OBSTRUCTION',reason=str(exc),exception_type=type(exc).__name__)
    except Exception as exc:
        record.update(status='IMPLEMENTATION_ERROR',reason=str(exc),exception_type=type(exc).__name__)
        raise
    finally:
        record['work']=ledger.snapshot()
        write(output/'preflight.json',record)
        write(output/'sensitivity.json',dict(status='NOT_RUN',reason=record.get('reason','preflight-only invocation')))
        write(output/'pilot_metrics.json',dict(status='NOT_RUN',reason=record.get('reason','preflight-only invocation'),
            runs=[dict(scene=s,arm=a,status='NOT_RUN') for s in SCENES for a in ('S','F')]))
        print(json.dumps(dict(status=record['status'],reason=record.get('reason'),work=record['work'])),flush=True)

if __name__=='__main__':
    main()
