"""Actual maintained-policy supplemental experiment on the twelve TD starts."""
import os
for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['SC_FORWARD_BACKEND'] = 'cpu'
os.environ['SC_FREQUENCY_THREADS'] = '1'

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import traceback
import numpy as np

from experiments.cleaned_interface.io import write, read, digest
from experiments.cleaned_interface.physics import Execution
from experiments.cleaned_interface.problem import Problem, Observation
from experiments.cleaned_interface.runner import fit
from experiments.shape_continuation.forward import PointSourceAcquisition
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.multi_object import MultiCurve
from .indicators import CircleSeed
from .run import ROOT, OUTPUT, REFERENCE, LENGTH, frozen, seed_state, sc_curve, audit
from .maintained_adapter import (CoupledGeometry, CoupledNodalKress,
                                CoupledCumulativePolicy, preserve_td_start)

DESTINATION = OUTPUT/'maintained_policy'


def load_problem(scene, *, damped=False, destination=DESTINATION):
    path = OUTPUT/'frequency_data'/f'{scene}.npz'
    saved = np.load(path)
    if not read(path.with_suffix('.json'))['qualified']:
        raise ValueError('Archived real observations are unqualified.')
    acquisition = PointSourceAcquisition(saved['sources'], saved['receivers'], complex(saved['strength']))
    real = tuple(Observation(float(k), acquisition, values, float(f)) for k, values, f in
                 zip(saved['wavenumbers'], saved['observed'], saved['frequencies']))
    seeds = read(OUTPUT/'initializers'/f'{scene}.json')['seeds']
    initial = sc_curve(seed_state(tuple(CircleSeed(tuple(s['center']), s['radius']) for s in seeds)))
    if initial is None:
        raise ValueError('A fixed-topology policy requires a nonempty TD initialization.')
    catalog = real
    if damped:
        data_path = destination/'damped_data'/f'{scene}.npz'
        if not read(data_path.with_suffix('.json'))['qualified']:
            raise ValueError('Supplemental damped observations are unqualified.')
        values = np.load(data_path)['observed']
        catalog = tuple(Observation(o.wavenumber*(1+.25j), acquisition, y, o.frequency_hz)
                        for o, y in zip(real, values))
    return Problem(initial, real, catalog, float(saved['contrast']), damping_ratio=.25 if damped else 0.)


def input_signature(scene):
    """Hash fitting inputs, excluding scene labels/truth/heldout evaluation."""
    p = load_problem(scene)
    h = hashlib.sha256()
    for o in p.real:
        for a in (np.asarray([o.wavenumber]), o.acquisition.sources, o.acquisition.receivers,
                  np.asarray([o.acquisition.strength]), o.scattered):
            h.update(np.ascontiguousarray(a).tobytes())
    h.update(p.initial.coefficients.tobytes())
    h.update(np.asarray([p.contrast, p.length_unit_m]).tobytes())
    h.update(json.dumps(p.initial.ids).encode())
    return h.hexdigest()


def legacy_state(curve):
    from sdf_inverse import MultiRadialFourierState
    from sdf_inverse.explicit_fourier import CartesianFourierCurveState
    states = []
    for c, name in zip(curve.components, curve.ids):
        z, k = c.coefficients*LENGTH, c.band
        center = np.array([z[k].real+.5, z[k].imag+.5])
        cosine, sine = z[k+1:]+z[k-1::-1], 1j*(z[k+1:]-z[k-1::-1])
        states.append(CartesianFourierCurveState(np.vstack((center, np.column_stack((cosine.real, cosine.imag)))),
            np.vstack((np.zeros(2), np.column_stack((sine.real, sine.imag)))), name))
    return MultiRadialFourierState(tuple(states))


def score(scene_id, curve):
    from sdf_inverse.topology_controller import topology_objective
    from sdf_inverse.radial_topology import evaluate_multiradial_objective
    from sdf_inverse.work_accounting import collect_work
    spec = read(ROOT/'config/topology_scenes_v1.json')
    scene = next(s for s in spec['scenes'] if s['id'] == scene_id)
    data, held = frozen.shared_data(REFERENCE, scene, spec)
    # Original gates and observations, but adequate quadrature for K_geometry192.
    # This is independent post-fit evaluation and cannot affect schedule/selection.
    refined = dict(spec, refined_nodes=max(512, 2*(curve.band+1)))
    state = legacy_state(curve)
    geometry = replace(frozen.driver.baseline._geometry_config(refined['refined_nodes']),
                       validation_resolution=max(512, 2*curve.band+2))
    solve = frozen.driver.baseline.iteration01_solve_config()
    with collect_work() as work:
        _, training = topology_objective(state, data, geometry, solve)
        prediction = evaluate_multiradial_objective(state, held, geometry, solve_config=solve).prediction
    relative = frozen.relative_columns(prediction, held.observed_scattered_response)
    metrics = frozen.geometry_metrics(state, scene, spec)
    gates = frozen.success_gates(metrics, training, float(max(relative)), {}, spec)
    result = dict(geometry=metrics, training_relative=float(training), holdout_relative=relative,
                  gates=gates, passed=all(gates.values()), audit_work=work.snapshot())
    result['evaluation_nodes'] = refined['refined_nodes']
    result['evaluation_only'] = True
    return result


def run_one(scene, arm, *, destination=DESTINATION, seconds=1800., resolution=512, audit_seconds=300.):
    directory = destination/'runs'/arm/scene
    started = perf_counter()
    row = dict(scene=scene, arm=arm, status='STARTED', selection_uses_holdout=False,
        same_real_observations=True, extra_damped_information=arm=='damped',
        input_signature=input_signature(scene), work_cap=13412, fit_seconds_cap=seconds, audit_seconds_cap=audit_seconds,
        input_sha256={str(p.relative_to(ROOT)):digest(p) for p in
            (OUTPUT/'frequency_data'/f'{scene}.npz', OUTPUT/'initializers'/f'{scene}.json')})
    write(directory/'result.json', row)
    try:
        problem = load_problem(scene, damped=arm=='damped', destination=destination)
        policy = CoupledCumulativePolicy(gamma=problem.damping_ratio,
            prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9), fit_seconds=seconds, audit_seconds=audit_seconds)
        physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1, resolution=resolution))
        result = fit(problem, policy=policy, physics=physics, output=directory,
                     geometry_adapter=CoupledGeometry, localization_adapter=preserve_td_start,
                     on_event=lambda event: print(json.dumps(dict(scene=scene, arm=arm,
                         label=event['operation']['label'], reason=event['reason'])), flush=True))
        curve = CoupledGeometry.restore(result['final_curve'])
        row.update(status=result['outcome'], detail=result['detail'], fit_result=result,
                   completed=result['outcome']=='COMPLETED_SCHEDULE')
        write(directory/'result.json', row)
        try:
            row['endpoint'] = score(scene, curve)
            row['qualified_pass'] = bool(row['completed'] and result['initial_audit_passed'] and
                                        result['final_audit_passed'] and row['endpoint']['passed'])
        except Exception:
            row.update(endpoint_error=traceback.format_exc(), qualified_pass=False)
    except Exception:
        row.update(status='EXCEPTION', traceback=traceback.format_exc(), qualified_pass=False, completed=False)
    row['wall_seconds'] = perf_counter()-started
    write(directory/'result.json', row)
    print(json.dumps(dict(scene=scene, arm=arm, status=row['status'], seconds=row['wall_seconds'])), flush=True)
    return row


def prepare_one(scene_id, *, destination=DESTINATION):
    """Qualify additional synthetic complex data; never relabel real observations."""
    started = perf_counter()
    spec = read(ROOT/'config/topology_scenes_v1.json')
    scene = next(s for s in spec['scenes'] if s['id'] == scene_id)
    real = load_problem(scene_id)
    truth = []
    for c in frozen.truth_curves(scene):
        p = c.discretize(2048).points
        truth.append(FourierCurve.from_samples((p[:, 0]-.5+1j*(p[:, 1]-.5))/LENGTH, 24))
    truth = MultiCurve(tuple(truth), tuple(s['component_id'] for s in scene['truth']))
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1))
    obs = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in real.real)
    coarse, fine = [np.asarray([physics.evaluate(truth, o, real.contrast, n).prediction for o in obs])
                    for n in (256, 512)]
    difference = np.linalg.norm(fine-coarse, axis=1)/np.linalg.norm(fine, axis=1)
    tolerance = np.asarray([1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in obs])
    directory = destination/'damped_data'
    directory.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(directory/f'{scene_id}.npz', observed=fine,
                        frequencies=[o.frequency_hz for o in obs], wavenumbers=[o.wavenumber for o in obs])
    row = dict(scene=scene_id, qualified=bool(np.all(difference <= tolerance)),
        nodes=[256, 512], relative_change=difference, tolerances=tolerance,
        real_input_sha256=digest(OUTPUT/'frequency_data'/f'{scene_id}.npz'),
        additional_information=True, qualification_work=physics.receipt(), seconds=perf_counter()-started)
    write(directory/f'{scene_id}.json', row)
    print(json.dumps(dict(scene=scene_id, qualified=row['qualified'], max_change=float(difference.max()))), flush=True)


def campaign(arm, destination, workers, seconds, resolution, prepare=False, skip=()):
    scenes = [s['id'] for s in read(ROOT/'config/topology_scenes_v1.json')['scenes'] if s['id'] not in skip]
    # Execute every requested configuration; no hidden reuse or deduplication.
    def job(scene):
        directory = destination/'logs'
        directory.mkdir(parents=True, exist_ok=True)
        with (directory/f'{"prepare" if prepare else arm}__{scene}.log').open('w') as stream:
            command = [sys.executable, '-m', 'experiments.exploratory_continuation.maintained_run',
                       'prepare-one' if prepare else 'one', '--scene', scene, '--arm', arm,
                       '--destination', str(destination), '--seconds', str(seconds), '--resolution', str(resolution)]
            started = perf_counter()
            returned = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            row = dict(scene=scene, returncode=returned.returncode, seconds=perf_counter()-started)
            print(json.dumps(row), flush=True)
            return row
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(job, scenes))
    write(destination/f'{"prepare" if prepare else arm}_campaign.json',
          dict(rows=rows, workers=workers, policy_wall_seconds=seconds, separately_executed_scenes=skip,
               subprocess_timeout=None, all_failures_retained=True))


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode', choices=['one', 'campaign', 'prepare-one', 'prepare'])
    parser.add_argument('--scene')
    parser.add_argument('--arm', choices=['real', 'damped'], default='real')
    parser.add_argument('--destination', type=Path, default=DESTINATION)
    parser.add_argument('--seconds', type=float, default=1800.)
    parser.add_argument('--resolution', type=int, default=512)
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--audit-seconds', type=float, default=300.)
    parser.add_argument('--skip', nargs='*', default=[])
    a = parser.parse_args()
    if a.mode == 'one': run_one(a.scene, a.arm, destination=a.destination, seconds=a.seconds, resolution=a.resolution, audit_seconds=a.audit_seconds)
    elif a.mode == 'prepare-one': prepare_one(a.scene, destination=a.destination)
    else: campaign(a.arm, a.destination, a.workers, a.seconds, a.resolution, prepare=a.mode=='prepare', skip=a.skip)


if __name__ == '__main__':
    main()
