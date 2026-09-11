#!/usr/bin/env python3
"""Frozen scene benchmark for automatic topology, with paired policies and visuals.

Run from the repository root with PYTHONPATH=solvers. The default invocation
prepares observations, runs all 24 inversions and renders their saved results.
Controller failures are benchmark outcomes, not reasons to omit a scene.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from time import monotonic, perf_counter
import traceback

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ.setdefault('MPLCONFIGDIR', '/tmp/topology-scenes-matplotlib')

import numpy as np
from scipy.optimize import linear_sum_assignment

import run_fourier_topology_controller as driver
from ordered_boundary import OrderedBoundary2D, circle, ellipse, star
from sdf_bem_multicomponent import predict_multicomponent_kress_paired_boundary_response
from sdf_inverse import ComplexScatteredData, MultiRadialFourierState
from sdf_inverse.curve_updates import RadialFourierCurveState
from sdf_inverse.experiment_record import source_provenance
from sdf_inverse.radial_topology import _inside_polygon, _minimum_polygon_distance
from sdf_inverse.topology_controller import (
    TopologyControllerConfig, TopologyFrame, component_parameterization,
    run_topology_aware_fourier_inverse, state_in_chart, topology_objective,
)
from sdf_inverse.work_accounting import accounted_call, collect_work, current_work

ROOT = Path(__file__).resolve().parent
DEFAULT_SPEC = ROOT / 'config/topology_scenes_v1.json'
# An arm is a named controller policy over the frozen scenes. Scenes, data,
# acquisition, budgets and gates never vary with the arm.
ARM_POLICIES = {'A': dict(include_simplest_candidate=False),
                'F': dict(include_simplest_candidate=True),
                'G': dict(include_simplest_candidate=False, refined_feasibility_guard=True)}
ARM_LABELS = {'A': 'default A', 'F': 'selective F', 'G': 'guarded G'}
POLICY_KEYS = sorted({key for policy in ARM_POLICIES.values() for key in policy})
DEFAULT_ARMS = ('A', 'F')
# Archived bundle analyses iterate this name; it stays the pair they ran.
ARMS = DEFAULT_ARMS


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def truth_curves(scene):
    constructors = {'circle': circle, 'ellipse': ellipse, 'star': star}
    return tuple(constructors[item['kind']](**{k: v for k, v in item.items() if k != 'kind'})
                 for item in scene['truth'])


def initial_state(scene):
    components = tuple(RadialFourierCurveState(np.asarray(item['center']),
        np.asarray(item['cosine']), np.asarray(item['sine']), item['component_id'])
        for item in scene['initial'])
    return state_in_chart(MultiRadialFourierState(components), 'cartesian') if components else None


def controller_config(spec, arm):
    return TopologyControllerConfig(**spec['controller'], **ARM_POLICIES[arm])


def suite_arms(output):
    """The arms a prepared bundle actually declares, so summaries stay honest."""
    arms = read(output / 'manifest.json').get('arms', DEFAULT_ARMS)
    return tuple(arms)


def relative_columns(predicted, observed):
    return np.linalg.norm(predicted - observed, axis=0) / np.maximum(
        np.linalg.norm(observed, axis=0), np.finfo(float).tiny)


def scene_geometry_check(scene, spec):
    truth = [c.discretize(spec['geometry_samples']).points for c in truth_curves(scene)]
    initial = initial_state(scene)
    start = [] if initial is None else [component_parameterization(c).discretize(
        spec['geometry_samples']).points for c in initial.components]
    config = controller_config(spec, DEFAULT_ARMS[0])
    within = all(np.max(np.linalg.norm(p - config.inspection_center, axis=1)) <=
                 config.inspection_radius_m + 1e-12 for p in truth + start)
    separated = all(not np.any(_inside_polygon(a, b)) and not np.any(_inside_polygon(b, a))
                    for i, a in enumerate(truth) for b in truth[i+1:])
    far_disjoint = all(not np.any(_inside_polygon(a, b)) and not np.any(_inside_polygon(b, a))
                       for a in start for b in truth)
    gap = min((float(_minimum_polygon_distance(a, b).min()) for a in start for b in truth), default=None)
    valid = within and separated and (not scene['id'].startswith('far-') or far_disjoint)
    return dict(valid=valid, within_inspection_disk=within, truth_components_separated=separated,
                initial_truth_disjoint=far_disjoint, minimum_initial_truth_boundary_gap_m=gap)


def reuse_reference_data(output, reference, spec):
    """Copy checked observations and starting coefficients, without regenerating truth data."""
    if read(reference / 'scene_spec.json') != spec:
        raise ValueError('Reference data must use the identical frozen scene specification.')
    checks = []
    hashes = {}
    for scene in spec['scenes']:
        source = reference / 'scenes' / scene['id']
        target = output / 'scenes' / scene['id']
        target.mkdir(parents=True)
        if read(source / 'scene.json') != scene:
            raise ValueError('Reference scene definition changed.')
        check = read(source / 'oracle_check.json')
        if not check['passed'] or not read(source / 'geometry_check.json')['valid']:
            raise ValueError('Reference oracle or geometry is not qualified.')
        for name in ('scene.json', 'observations.json', 'initial_state.json',
                     'oracle_check.json', 'geometry_check.json'):
            shutil.copyfile(source / name, target / name)
        shared_data(output, scene, spec)  # validates the acquisition/material contract
        hashes[scene['id']] = digest(target / 'observations.json')
        checks.append(check)
    driver.write_json(output / 'oracle_checks.json', checks)
    driver.write_json(output / 'reference_data.json', dict(path=str(reference.resolve()),
        source_manifest_sha256=digest(reference / 'manifest.json'), observations_sha256=hashes,
        new_oracle_solves=0))


def prepare(output, spec_path, reference_data=None, arms=DEFAULT_ARMS, experiment_id='TOP-006'):
    output.mkdir(parents=True, exist_ok=False)
    spec = read(spec_path)
    driver.write_json(output / 'scene_spec.json', spec)
    provenance = source_provenance(ROOT)
    provenance['benchmark_spec_sha256'] = digest(output / 'scene_spec.json')
    driver.write_json(output / 'manifest.json', dict(experiment_id=experiment_id, spec_version=spec['version'],
        source=provenance, arms=list(arms), arm_policies={a: ARM_POLICIES[a] for a in arms},
        expected_runs=len(arms)*len(spec['scenes']), workers_limit=4,
        per_run_timeout_seconds=600, suite_wall_ceiling_seconds=2700,
        oracle_work_in_inversion_counts=False, controlled_wall_time_comparison=False))
    if reference_data is not None:
        reuse_reference_data(output, reference_data, spec)
        render_initials(output)
        return
    frequencies = np.asarray(spec['training_frequencies_hz'] + spec['holdout_frequencies_hz'])
    problem = driver.baseline._problem(frequencies)
    solve = driver.baseline.iteration01_solve_config()
    records = []
    for scene in spec['scenes']:
        path = output / 'scenes' / scene['id']
        path.mkdir(parents=True)
        check = scene_geometry_check(scene, spec)
        driver.write_json(path / 'geometry_check.json', check)
        if not check['valid']:
            raise ValueError(f"Invalid scene geometry: {scene['id']}")
        curves = truth_curves(scene)
        all_circles = all(item['kind'] == 'circle' for item in scene['truth'])
        started = perf_counter()
        if all_circles:
            observed = driver.baseline._oracle_response(
                np.array([item['center'] for item in scene['truth']]),
                np.array([item['radius'] for item in scene['truth']]), frequencies,
                component_ids=tuple(item['component_id'] for item in scene['truth']))
            oracle = 'independent cylindrical harmonics'
            changes = np.zeros(len(frequencies))
        else:
            predictions = [predict_multicomponent_kress_paired_boundary_response(
                OrderedBoundary2D(tuple(c.discretize(n) for c in curves)), problem,
                solve_config=solve).scattered_response
                for n in (spec['oracle_nodes'], spec['oracle_check_nodes'])]
            observed = predictions[0]
            changes = relative_columns(predictions[0], predictions[1])
            oracle = 'analytic boundaries, 256-node Kress; checked at 512 nodes (same solver)'
        record = dict(scene=scene['id'], oracle=oracle, resolution_relative_change=changes,
            passed=bool(np.max(changes) <= spec['oracle_relative_tolerance']),
            setup_seconds=perf_counter()-started)
        driver.write_json(path / 'oracle_check.json', record)
        observations = dict(frequencies_hz=frequencies, source_points=problem.source_points,
            receiver_points=problem.receiver_points, source_strengths_real=problem.source_strengths.real,
            source_strengths_imag=problem.source_strengths.imag,
            observed_real=observed.real, observed_imag=observed.imag,
            exterior=asdict(problem.exterior), interior=asdict(problem.interior),
            eps0=problem.eps0, mu0=problem.mu0, oracle=oracle)
        driver.write_json(path / 'observations.json', observations)
        driver.write_json(path / 'initial_state.json', driver.serialize_state(initial_state(scene)))
        driver.write_json(path / 'scene.json', scene)
        records.append(record)
        print(json.dumps(dict(scene=scene['id'], prepared=True, oracle_passed=record['passed'])), flush=True)
        if not record['passed']:
            raise ValueError(f"Oracle convergence gate failed: {scene['id']}")
    driver.write_json(output / 'oracle_checks.json', records)
    render_initials(output)


def shared_data(output, scene, spec):
    saved = read(output / 'scenes' / scene['id'] / 'observations.json')
    frequencies = np.array(saved['frequencies_hz'])
    observed = np.array(saved['observed_real']) + 1j*np.array(saved['observed_imag'])
    full_problem = driver.baseline._problem(frequencies)
    np.testing.assert_array_equal(full_problem.source_points, saved['source_points'])
    np.testing.assert_array_equal(full_problem.receiver_points, saved['receiver_points'])
    np.testing.assert_array_equal(frequencies, spec['training_frequencies_hz'] + spec['holdout_frequencies_hz'])
    np.testing.assert_array_equal(full_problem.source_strengths,
        np.array(saved['source_strengths_real']) + 1j*np.array(saved['source_strengths_imag']))
    if (asdict(full_problem.exterior) != saved['exterior'] or
            asdict(full_problem.interior) != saved['interior'] or
            full_problem.eps0 != saved['eps0'] or full_problem.mu0 != saved['mu0']):
        raise ValueError('Reference observations use different material constants.')
    n = len(spec['training_frequencies_hz'])
    return (ComplexScatteredData(driver.baseline._problem(frequencies[:n]), observed[:, :n]),
            ComplexScatteredData(driver.baseline._problem(frequencies[n:]), observed[:, n:]))


def union_mask(polygons, points):
    mask = np.zeros(len(points), dtype=bool)
    for polygon in polygons:
        bounded = np.all(points >= polygon.min(axis=0), axis=1) & np.all(points <= polygon.max(axis=0), axis=1)
        mask[bounded] |= _inside_polygon(points[bounded], polygon)
    return mask


def geometry_metrics(state, scene, spec):
    truth = [c.discretize(spec['geometry_samples']).points for c in truth_curves(scene)]
    final = [] if state is None else [component_parameterization(c).discretize(
        spec['geometry_samples']).points for c in state.components]
    distances = np.array([[max(_minimum_polygon_distance(a, b).max(),
                              _minimum_polygon_distance(b, a).max()) for b in truth] for a in final])
    pairs = []
    if final:
        rows, columns = linear_sum_assignment(distances)
        pairs = [dict(recovered_component=state.components[i].component_id,
            truth_component=scene['truth'][j]['component_id'], hausdorff_m=distances[i, j])
            for i, j in zip(rows, columns)]
    lo, hi = np.array(spec['iou_bounds'])
    x, y = np.meshgrid(np.linspace(lo[0], hi[0], spec['iou_grid_size']),
                       np.linspace(lo[1], hi[1], spec['iou_grid_size']))
    points = np.stack((x.ravel(), y.ravel()), axis=1)
    a, b = union_mask(truth, points), union_mask(final, points)
    return dict(component_count=len(final), truth_component_count=len(truth), matched_components=pairs,
        maximum_matched_hausdorff_m=max((p['hausdorff_m'] for p in pairs), default=None),
        union_iou=float(np.count_nonzero(a & b) / max(1, np.count_nonzero(a | b))),
        final_maximum_modes=[] if state is None else [c.maximum_mode for c in state.components])


def trajectory_checks(frames, events, config):
    monotone = all(b.loss <= a.loss + 1e-12*max(1., abs(a.loss)) for a, b in zip(frames, frames[1:]))
    margins = []
    for event in events:
        dp = event['production_before'] - event['production_after']
        dr = event['refined_before'] - event['refined_after']
        margin = config.acceptance_absolute_margin + config.acceptance_relative_margin*event['production_before']
        margins.append(min(dp, dr) > margin + config.cross_resolution_factor*abs(dp-dr))
    return dict(monotone_accepted_states=monotone, all_event_margins_pass=all(margins))


def success_gates(geometry, refined_relative, holdout_relative, checks, spec):
    gates = spec['gates']
    return dict(correct_count=geometry['component_count'] == geometry['truth_component_count'],
        boundary=geometry['maximum_matched_hausdorff_m'] is not None and
                 geometry['maximum_matched_hausdorff_m'] <= gates['maximum_matched_hausdorff_m'],
        overlap=geometry['union_iou'] >= gates['minimum_union_iou'],
        training=refined_relative <= gates['maximum_refined_training_relative_l2'],
        holdout=holdout_relative <= gates['maximum_holdout_relative_l2'], **checks)


def verify_source(output):
    source = read(output / 'manifest.json')['source']
    if digest(output / 'scene_spec.json') != source['benchmark_spec_sha256']:
        raise ValueError('Frozen benchmark scene specification changed.')
    changed = [name for name, checksum in source['source_sha256'].items() if digest(ROOT / name) != checksum]
    if changed:
        raise ValueError(f'Numerical source changed during benchmark: {changed}')


def run_one(output, scene_id, arm):
    verify_source(output)
    spec = read(output / 'scene_spec.json')
    scene = next(s for s in spec['scenes'] if s['id'] == scene_id)
    path = output / 'runs' / arm / scene_id
    path.mkdir(parents=True, exist_ok=False)
    data, holdout = shared_data(output, scene, spec)
    initial = driver.deserialize_state(read(output / 'scenes' / scene_id / 'initial_state.json'))
    config = controller_config(spec, arm)
    solve = driver.baseline.iteration01_solve_config()
    production, refined = [driver.baseline._geometry_config(spec[name])
                           for name in ('production_nodes', 'refined_nodes')]
    driver.write_json(path / 'manifest.json', dict(scene=scene_id, arm=arm, controller=asdict(config),
        source=read(output / 'manifest.json')['source'],
        observations_sha256=digest(output / 'scenes' / scene_id / 'observations.json'),
        initial_state=driver.serialize_state(initial), supplied_target_count=False,
        supplied_event_policy=False, supplied_truth_shape=False))
    frames = []
    def progress(frame):
        frames.append(frame)
        record = dict(cycle=frame.cycle, label=frame.label, loss=frame.loss,
                      state=driver.serialize_state(frame.state), work=current_work())
        driver.write_json(path / 'checkpoint.json', record)
        with (path / 'progress.jsonl').open('a') as stream:
            stream.write(json.dumps(record, default=lambda x: x.tolist() if hasattr(x, 'tolist') else float(x))+'\n')
        print(f'{scene_id} {arm}: cycle={frame.cycle} {frame.label} '
              f'M={0 if frame.state is None else len(frame.state.components)} J={frame.loss:.6g}', flush=True)
    started = perf_counter()
    try:
        result = run_topology_aware_fourier_inverse(initial, data, production, refined,
            solve_config=solve, config=config, progress_callback=progress)
        inversion_seconds = perf_counter()-started
        driver.write_json(path / 'trajectory.json', [dict(cycle=f.cycle, label=f.label, loss=f.loss,
            state=driver.serialize_state(f.state)) for f in result.frames])
        driver.write_json(path / 'topology_passes.json', result.passes)
        driver.write_json(path / 'events.json', result.events)
        with collect_work() as audit:
            loss, relative = accounted_call('final_production', topology_objective,
                result.final_state, data, production, solve)
            refined_loss, refined_relative = accounted_call('final_refined', topology_objective,
                result.final_state, data, refined, solve)
            if result.final_state is None:
                prediction = np.zeros_like(holdout.observed_scattered_response)
            else:
                from sdf_inverse.radial_topology import evaluate_multiradial_objective
                evaluation = accounted_call('holdout', evaluate_multiradial_objective,
                    result.final_state, holdout, refined, solve_config=solve)
                prediction = evaluation.prediction
        held = relative_columns(prediction, holdout.observed_scattered_response)
        geometry = geometry_metrics(result.final_state, scene, spec)
        checks = trajectory_checks(result.frames, result.events, config)
        gates = success_gates(geometry, refined_relative, float(max(held)), checks, spec)
        metrics = dict(scene=scene_id, group=scene['group'], arm=arm, completed=True,
            passed=all(gates.values()), gates=gates, geometry=geometry,
            stop_reason=result.stop_reason, final_loss=loss, final_relative_error=relative,
            refined_loss=refined_loss, refined_relative_error=refined_relative,
            holdout_relative_errors=held, maximum_holdout_relative_error=float(max(held)),
            final_state=driver.serialize_state(result.final_state),
            events=result.events, work=result.work, audit_work=audit.snapshot(),
            inversion_seconds=inversion_seconds, total_seconds=perf_counter()-started)
        driver.write_json(path / 'metrics.json', metrics)
        print(json.dumps(dict(scene=scene_id, arm=arm, completed=True, passed=metrics['passed'],
                             stop=result.stop_reason, gates=gates), default=bool), flush=True)
    except Exception:
        driver.write_json(path / 'failure.json', dict(scene=scene_id, arm=arm,
            reason='exception', traceback=traceback.format_exc(), elapsed_seconds=perf_counter()-started))
        raise


def run_job(output, scene_id, arm, deadline):
    path = output / 'runs' / arm / scene_id
    log_path = output / 'logs' / f'{arm}-{scene_id}.log'
    remaining = deadline-monotonic()
    if remaining <= 0:
        path.mkdir(parents=True, exist_ok=True)
        driver.write_json(path / 'failure.json', dict(scene=scene_id, arm=arm, reason='suite_wall_ceiling'))
        return dict(scene=scene_id, arm=arm, status='suite_wall_ceiling')
    command = [sys.executable, str(Path(__file__).resolve()), '--output', str(output), '--run-one', scene_id, arm]
    with log_path.open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=min(600., remaining), cwd=ROOT)
            status = 'complete' if result.returncode == 0 else 'error'
        except subprocess.TimeoutExpired:
            status = 'timeout'
            path.mkdir(parents=True, exist_ok=True)
            driver.write_json(path / 'failure.json', dict(scene=scene_id, arm=arm,
                reason='timeout', timeout_seconds=min(600., remaining),
                partial_work_is_lower_bound=True))
    if status == 'error' and not (path / 'failure.json').exists():
        path.mkdir(parents=True, exist_ok=True)
        driver.write_json(path / 'failure.json', dict(scene=scene_id, arm=arm, reason='process_exit',
                                                     returncode=result.returncode))
    record = dict(scene=scene_id, arm=arm, status=status)
    print(json.dumps(record), flush=True)
    return record


def plot_geometry(ax, scene, state, initial=None):
    plotted = []
    for i, curve in enumerate(truth_curves(scene)):
        p = curve.discretize(512).points
        plotted.append(p)
        ax.plot(*np.vstack((p, p[0])).T, '--', color='#263747', lw=1.7,
                label='Target' if i == 0 else None)
    for current, color, style, label in ((initial, '#a7adb5', ':', 'Initial'),
                                        (state, '#087f8c', '-', 'Reconstruction')):
        if current is not None:
            for i, component in enumerate(current.components):
                p = component_parameterization(component).discretize(512).points
                plotted.append(p)
                ax.plot(*np.vstack((p, p[0])).T, style, color=color, lw=1.7,
                        label=label if i == 0 else None)
    points = np.concatenate(plotted)
    lower = np.minimum((.28, .28), points.min(axis=0)-.015)
    upper = np.maximum((.72, .74), points.max(axis=0)+.015)
    ax.set(xlim=(lower[0], upper[0]), ylim=(lower[1], upper[1]), aspect='equal')
    ax.grid(alpha=.12)
    ax.tick_params(labelsize=7)


def render_initials(output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    spec = read(output / 'scene_spec.json')
    fig, axes = plt.subplots(3, 4, figsize=(14, 11), constrained_layout=True)
    for ax, scene in zip(axes.flat, spec['scenes']):
        plot_geometry(ax, scene, None, initial_state(scene))
        ax.set_title(scene['title'], fontsize=9)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('Frozen topology scenes v1 — dashed targets, dotted initial geometry')
    fig.savefig(output / 'initial_scenes.svg')
    fig.savefig(output / 'initial_scenes.png', dpi=140)
    plt.close(fig)


def summarize(output, render=True):
    spec = read(output / 'scene_spec.json')
    arms = suite_arms(output)
    rows, failures, pairs = [], [], []
    for scene in spec['scenes']:
        for arm in arms:
            path = output / 'runs' / arm / scene['id']
            if (path / 'metrics.json').exists():
                rows.append(read(path / 'metrics.json'))
            elif (path / 'failure.json').exists():
                failures.append(read(path / 'failure.json'))
        paths = [output / 'runs' / arm / scene['id'] / 'manifest.json' for arm in arms]
        if all(p.exists() for p in paths):
            manifests = [read(p) for p in paths]
            configs = [{k: v for k, v in m['controller'].items() if k not in POLICY_KEYS} for m in manifests]
            first = manifests[0]
            pairs.append(dict(scene=scene['id'],
                same_observations=all(m['observations_sha256']==first['observations_sha256'] for m in manifests),
                same_initial_state=all(m['initial_state']==first['initial_state'] for m in manifests),
                same_remaining_config=all(c==configs[0] for c in configs),
                same_source=all(m['source']==first['source'] for m in manifests)))
    totals = {arm:dict(completed=sum(r['arm']==arm for r in rows),
        passed=sum(r['arm']==arm and r['passed'] for r in rows),
        failed_or_missing=len(spec['scenes'])-sum(r['arm']==arm and r['passed'] for r in rows),
        bie_frequency_solve_count=sum(r['work']['totals']['bie_frequency_solve_count'] for r in rows if r['arm']==arm))
        for arm in arms}
    for arm in arms:
        partial_paths = [output / 'runs' / arm / f['scene'] / 'checkpoint.json'
                         for f in failures if f['arm']==arm]
        totals[arm]['error_or_timeout_count'] = len(partial_paths)
        totals[arm]['all_runs_bie_solve_lower_bound'] = totals[arm]['bie_frequency_solve_count'] + sum(
            read(p)['work']['totals']['bie_frequency_solve_count'] for p in partial_paths if p.exists())
    complete = len(rows)+len(failures)==len(arms)*len(spec['scenes'])
    result = dict(spec_version=spec['version'], arms=list(arms), complete=complete, metrics=rows, failures=failures,
        paired_input_checks=pairs, all_inputs_paired=len(pairs)==len(spec['scenes']) and
        all(all(v for k, v in pair.items() if k != 'scene') for pair in pairs), totals=totals)
    driver.write_json(output / 'suite_metrics.json', result)
    if render:
        render_results(output, spec, rows, arms)
    print(json.dumps(dict(complete=complete, totals=totals)), flush=True)
    return result


def saved_run_state(path, row):
    """Keep an aborted reconstruction visible, explicitly as the last saved state."""
    if row is not None:
        return driver.deserialize_state(row['final_state'])
    checkpoint = path / 'checkpoint.json'
    return driver.deserialize_state(read(checkpoint)['state']) if checkpoint.exists() else None


def saved_run_frames(path):
    if (path / 'trajectory.json').exists():
        records = read(path / 'trajectory.json')
    elif (path / 'progress.jsonl').exists():
        records = []
        lines = (path / 'progress.jsonl').read_text().splitlines()
        for index, line in enumerate(lines):
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                if index != len(lines)-1:
                    raise
                # A timeout may interrupt the last file write. Retain all complete records.
    else:
        records = []
    frames = [TopologyFrame(driver.deserialize_state(r['state']), r['loss'], r['label'], r['cycle'])
              for r in records]
    if frames and (path / 'failure.json').exists():
        last = frames[-1]
        frames[-1] = TopologyFrame(last.state, last.loss, 'FAILED — last saved accepted state', last.cycle)
    return tuple(frames)


def render_results(output, spec, rows, arms=DEFAULT_ARMS):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    lookup = {(r['scene'], r['arm']): r for r in rows}
    for group in ('original', 'new'):
        scenes = [s for s in spec['scenes'] if s['group']==group]
        fig, axes = plt.subplots(len(scenes), len(arms), squeeze=False,
                                 figsize=(5*len(arms), 3.2*len(scenes)), constrained_layout=True)
        for i, scene in enumerate(scenes):
            for j, arm in enumerate(arms):
                ax = axes[i, j]
                row = lookup.get((scene['id'], arm))
                path = output / 'runs' / arm / scene['id']
                state = saved_run_state(path, row)
                plot_geometry(ax, scene, state, initial_state(scene))
                detail = ('FAILED — last saved state' if (path / 'failure.json').exists() else 'INCOMPLETE') if row is None else (
                    f"{'PASS' if row['passed'] else 'FAIL'} | {row['geometry']['component_count']}/{len(scene['truth'])} objects"
                    f" | IoU {row['geometry']['union_iou']:.2f}")
                ax.set_title(f"{scene['id']} — {ARM_LABELS[arm]}\n{detail}", fontsize=10)
            xlim = (min(ax.get_xlim()[0] for ax in axes[i]), max(ax.get_xlim()[1] for ax in axes[i]))
            ylim = (min(ax.get_ylim()[0] for ax in axes[i]), max(ax.get_ylim()[1] for ax in axes[i]))
            for ax in axes[i]:
                ax.set(xlim=xlim, ylim=ylim)
        axes[0, 0].legend(fontsize=8)
        fig.suptitle('Dashed: target · dotted: initial · teal: final reconstruction', fontsize=13)
        fig.savefig(output / f'{group}_results.svg')
        fig.savefig(output / f'{group}_results.png', dpi=135)
        plt.close(fig)
    # The requested scene gets its own compact panel per arm, suitable for sharing.
    scene = next(s for s in spec['scenes'] if s['id']=='far-ellipse-star')
    fig, axes = plt.subplots(1, 1+len(arms), squeeze=False,
                             figsize=(4.3*(1+len(arms)), 4.5), constrained_layout=True)
    axes = axes[0]
    plot_geometry(axes[0], scene, None, initial_state(scene))
    axes[0].set_title('Starting circle and targets')
    axes[0].legend(fontsize=8)
    for ax, arm in zip(axes[1:], arms):
        row = lookup.get((scene['id'], arm))
        path = output / 'runs' / arm / scene['id']
        state = saved_run_state(path, row)
        plot_geometry(ax, scene, state)
        ax.set_title(f"{ARM_LABELS[arm].capitalize()} — "
                     + (('FAILED: last saved state' if (path / 'failure.json').exists() else 'incomplete')
                        if row is None else ('PASS' if row['passed'] else 'FAIL')))
    fig.savefig(output / 'far_ellipse_star.svg')
    fig.savefig(output / 'far_ellipse_star.png', dpi=160)
    plt.close(fig)
    for arm in arms:
        path = output / 'runs' / arm / scene['id']
        frames = saved_run_frames(path)
        if frames and not (path / 'inversion.mp4').exists():
            prefix = 'FAILED — ' if (path / 'failure.json').exists() else ''
            driver.render_case(path, f'{prefix}distant circle to ellipse/star / {arm}', truth_curves(scene),
                               frames, read(path / 'events.json') if (path / 'events.json').exists() else ())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--spec', type=Path, default=DEFAULT_SPEC)
    parser.add_argument('--reference-data', type=Path,
                        help='Reuse a matching prior benchmark dataset and initial states without oracle solves.')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--run-one', nargs=2, metavar=('SCENE', 'ARM'))
    parser.add_argument('--summary-only', action='store_true')
    parser.add_argument('--arms', default=','.join(DEFAULT_ARMS),
                        help='Comma-separated controller policies to run, e.g. A,G. Scenes and budgets never vary.')
    parser.add_argument('--experiment-id', default='TOP-006')
    parser.add_argument('--skip-render', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    arms = tuple(name.strip() for name in args.arms.split(',') if name.strip())
    if not arms or any(name not in ARM_POLICIES for name in arms) or len(set(arms)) != len(arms):
        raise SystemExit(f'--arms must be distinct names from {sorted(ARM_POLICIES)}')
    if args.summary_only:
        return 0 if summarize(output, not args.skip_render)['complete'] else 1
    if args.run_one:
        run_one(output, *args.run_one)
        return 0
    prepare(output, args.spec, args.reference_data, arms, args.experiment_id)
    if args.prepare_only:
        return 0
    (output / 'logs').mkdir()
    deadline = monotonic()+2700
    spec = read(output / 'scene_spec.json')
    # Start the requested scene first; no outcomes affect the remaining queue.
    scenes = sorted(spec['scenes'], key=lambda s: s['id'] != 'far-ellipse-star')
    records = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        jobs = [pool.submit(run_job, output, scene['id'], arm, deadline) for scene in scenes for arm in arms]
        for job in as_completed(jobs):
            records.append(job.result())
            driver.write_json(output / 'execution_status.json', records)
    summary = summarize(output, not args.skip_render)
    return 0 if summary['complete'] and not summary['failures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
