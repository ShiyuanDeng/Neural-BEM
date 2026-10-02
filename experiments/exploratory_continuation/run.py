"""CPU controls; frozen observations are never relabeled as training data."""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
import traceback

for name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[name] = '1'
os.environ['SC_FORWARD_BACKEND'] = 'cpu'
os.environ['SC_FREQUENCY_THREADS'] = '1'

import numpy as np

import run_topology_scene_benchmark as frozen
from sdf_inverse import MultiRadialFourierState
from sdf_inverse.radial_topology import evaluate_current_domain_topological_derivative
from sdf_inverse.topology_controller import circle_component, topology_objective
from sdf_inverse.work_accounting import collect_work

from .indicators import threshold_circles
from .paths import scif_path, recursive_modes

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'results/validation/topology/TOP-006-20260911-scenes-v1'
OUTPUT = ROOT / 'results/exploratory_continuation'
LENGTH, ORIGIN = .05, np.array([.5, .5])


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=lambda x: x.tolist() if hasattr(x, 'tolist') else asdict(x))+'\n')


def seed_state(seeds):
    return MultiRadialFourierState(tuple(circle_component(s.center, s.radius, f'topo.{i}', 'cartesian')
        for i, s in enumerate(seeds))) if seeds else None


def audit(state, scene, spec, data, holdout):
    solve = frozen.driver.baseline.iteration01_solve_config()
    geometry = frozen.driver.baseline._geometry_config(spec['refined_nodes'])
    with collect_work() as work:
        _, training = topology_objective(state, data, geometry, solve)
        # topology_objective's aggregate norm is inadequate for the per-column
        # holdout gate, so evaluate each saved holdout prediction explicitly.
        if state is None:
            prediction = np.zeros_like(holdout.observed_scattered_response)
        else:
            from sdf_inverse.radial_topology import evaluate_multiradial_objective
            prediction = evaluate_multiradial_objective(state, holdout, geometry, solve_config=solve).prediction
    held = frozen.relative_columns(prediction, holdout.observed_scattered_response)
    geometric = frozen.geometry_metrics(state, scene, spec)
    gates = frozen.success_gates(geometric, training, float(max(held)), {}, spec)
    return dict(geometry=geometric, training_relative=float(training), holdout_relative=held,
                gates=gates, passed=all(gates.values()), audit_work=work.snapshot())


def initializers(output):
    spec = frozen.read(ROOT / 'config/topology_scenes_v1.json')
    config = frozen.controller_config(spec, 'A')
    x = np.linspace(.3, .7, 81)
    xx, yy = np.meshgrid(x, x)
    points = np.stack((xx, yy), axis=-1)
    rows, fields = [], []
    for scene in spec['scenes']:
        started = perf_counter()
        data, holdout = frozen.shared_data(REFERENCE, scene, spec)
        with collect_work() as work:
            values = evaluate_current_domain_topological_derivative(None, data, points.reshape(-1, 2)).values.reshape(xx.shape)
        seeds, mask = threshold_circles(points, values, threshold=.6)
        initial = seed_state(seeds)
        row = dict(scene=scene['id'], initializer='topo', seeds=seeds,
            initializer_seconds=perf_counter()-started, initializer_work=work.snapshot(),
            observation_sha256=hashlib.sha256((REFERENCE/'scenes'/scene['id']/'observations.json').read_bytes()).hexdigest(),
            current=audit(frozen.initial_state(scene), scene, spec, data, holdout),
            topo=audit(initial, scene, spec, data, holdout),
            lsm=dict(status='UNSUPPORTED_PAIRED_ACQUISITION', reason='24 paired rows are not the full 24-by-24 multistatic matrix'))
        write(output/'initializers'/f"{scene['id']}.json", row)
        rows.append(row)
        fields.append(values)
        print(json.dumps(dict(scene=scene['id'], seeds=len(seeds), current_iou=row['current']['geometry']['union_iou'],
                              topo_iou=row['topo']['geometry']['union_iou'])), flush=True)
    np.savez_compressed(output/'initializers'/'fields.npz', points=points, values=np.array(fields))
    write(output/'initializers'/'summary.json', dict(rows=rows, threshold=.6, grid_size=81,
          new_oracle_solves=0, frozen_training_frequencies_hz=spec['training_frequencies_hz'],
          preserved_holdout_frequencies_hz=spec['holdout_frequencies_hz']))
    plot_initializers(output, spec, rows, points, fields)


def plot_initializers(output, spec, rows, points, fields):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 4, figsize=(13, 10), constrained_layout=True)
    angle = np.linspace(0, 2*np.pi, 160)
    for ax, scene, row, values in zip(axes.flat, spec['scenes'], rows, fields):
        image = np.maximum(-values, 0)
        ax.imshow(image/max(image.max(), np.finfo(float).tiny), origin='lower', extent=(.3,.7,.3,.7), cmap='magma')
        for curve in frozen.truth_curves(scene):
            p = curve.discretize(512).points
            ax.plot(p[:,0], p[:,1], color='cyan', lw=1)
        for seed in row['seeds']:
            ax.plot(seed.center[0]+seed.radius*np.cos(angle),seed.center[1]+seed.radius*np.sin(angle), color='white', lw=1)
        ax.set_title(scene['id'], fontsize=9)
        ax.set_aspect('equal')
    fig.suptitle('Empty-domain topological initializer: truth cyan, seed circles white; 0.5 GHz training only')
    fig.savefig(output/'initializers'/'all_scenes.png', dpi=150)
    plt.close(fig)


def controller(output, scene_id, initializer, *, guarded=False, full=False):
    """Two-cycle matched pilot; original scene/acquisition/gates, reduced budget."""
    from sdf_inverse.topology_controller import run_topology_aware_fourier_inverse
    spec = frozen.read(ROOT/'config/topology_scenes_v1.json')
    scene = next(s for s in spec['scenes'] if s['id'] == scene_id)
    data, holdout = frozen.shared_data(REFERENCE, scene, spec)
    initial = frozen.initial_state(scene)
    if initializer == 'topo':
        from .indicators import CircleSeed
        rows = frozen.read(output/'initializers'/f'{scene_id}.json')['seeds']
        initial = seed_state(tuple(CircleSeed(tuple(row['center']),row['radius']) for row in rows))
    config = frozen.controller_config(spec, 'H' if guarded or full else 'A')
    if not full:
        config = replace(config, maximum_cycles=2, fixed_iterations=6,
                         candidate_refinement_iterations=2, maximum_candidates_per_type=12)
    production, refined = [frozen.driver.baseline._geometry_config(spec[name])
                           for name in ('production_nodes', 'refined_nodes')]
    directory = 'controller_full' if full else 'controller_guarded' if guarded else 'controller'
    path = output/directory/initializer/f'{scene_id}.json'
    checkpoint = output/directory/initializer/f'{scene_id}.checkpoint.json'
    started = perf_counter()
    record = dict(scene=scene_id, initializer=initializer, controller=asdict(config),
                  original_frozen_budget=full, controller_policy='H' if guarded or full else 'A',status='STARTED')
    write(path, record)
    def progress(frame):
        from sdf_inverse.work_accounting import current_work
        write(checkpoint,dict(scene=scene_id,initializer=initializer,cycle=frame.cycle,
              label=frame.label,loss=frame.loss,work=current_work(),seconds=perf_counter()-started,
              state=frozen.driver.serialize_state(frame.state)))
    try:
        result = run_topology_aware_fourier_inverse(initial, data, production, refined,
            solve_config=frozen.driver.baseline.iteration01_solve_config(), config=config,progress_callback=progress)
        record.update(status='COMPLETED', stop_reason=result.stop_reason, work=result.work,
            final_state=frozen.driver.serialize_state(result.final_state),
            events=result.events, trajectory_checks=frozen.trajectory_checks(result.frames,result.events,config),
            endpoint=audit(result.final_state,scene,spec,data,holdout))
    except Exception:
        record.update(status='EXCEPTION', traceback=traceback.format_exc())
    record['wall_seconds'] = perf_counter()-started
    write(path, record)
    print(json.dumps(dict(scene=scene_id, initializer=initializer, status=record['status'], seconds=record['wall_seconds'])),flush=True)


def sc_curve(state, band=24):
    from experiments.shape_continuation.geometry import FourierCurve
    from experiments.shape_continuation.multi_object import MultiCurve
    if state is None:
        return None
    curves = []
    for component in state.components:
        p = frozen.component_parameterization(component).discretize(2048).points
        z = (p[:,0]-.5 + 1j*(p[:,1]-.5))/LENGTH
        curves.append(FourierCurve.from_samples(z,band))
    return MultiCurve(tuple(curves), tuple(c.component_id for c in state.components))


def prepare_frequency_data(output):
    """Extra low-frequency synthetic training, keeping 1.5/2.5 GHz held out."""
    from experiments.shape_continuation.forward import PointSourceAcquisition, Work, solve
    from experiments.shape_continuation.geometry import FourierCurve
    from experiments.shape_continuation.multi_object import MultiCurve
    spec = frozen.read(ROOT/'config/topology_scenes_v1.json')
    frequencies = [.25e9, .375e9, .5e9, .75e9, 1e9]
    path = output/'frequency_data'
    path.mkdir(parents=True, exist_ok=True)
    for scene in spec['scenes']:
        started = perf_counter()
        saved = frozen.read(REFERENCE/'scenes'/scene['id']/'observations.json')
        acquisition = PointSourceAcquisition((np.array(saved['source_points'])-ORIGIN)/LENGTH,
            (np.array(saved['receiver_points'])-ORIGIN)/LENGTH, strength=complex(saved['source_strengths_real'][0],saved['source_strengths_imag'][0]))
        components = []
        for curve in frozen.truth_curves(scene):
            p = curve.discretize(2048).points
            components.append(FourierCurve.from_samples((p[:,0]-.5+1j*(p[:,1]-.5))/LENGTH,24))
        truth = MultiCurve(tuple(components),tuple(s['component_id'] for s in scene['truth']))
        contrast = saved['interior']['epsr']/saved['exterior']['epsr']
        ks = [float(frozen.driver.baseline._wavenumbers(f)[0].real*LENGTH) for f in frequencies]
        work = Work(max_forwards=20,max_seconds=600)
        coarse = np.array([solve(truth,k,contrast,acquisition,128,work=work).prediction for k in ks])
        fine = np.array([solve(truth,k,contrast,acquisition,256,work=work).prediction for k in ks])
        errors = np.linalg.norm(coarse-fine,axis=1)/np.linalg.norm(fine,axis=1)
        original = np.array(saved['observed_real'])[:,0]+1j*np.array(saved['observed_imag'])[:,0]
        original_error = float(np.linalg.norm(fine[2]-original)/np.linalg.norm(original))
        # Preserve the exact archived 0.5 GHz training samples after verifying
        # source scaling, material, units and component interactions.
        fine[2] = original
        np.savez_compressed(path/f"{scene['id']}.npz",frequencies=frequencies,wavenumbers=ks,
            sources=acquisition.sources,receivers=acquisition.receivers,strength=acquisition.strength,
            contrast=contrast,observed=fine)
        record = dict(scene=scene['id'], frequencies_hz=frequencies, extended_acquisition=True,
            preserved_holdout_frequencies_hz=spec['holdout_frequencies_hz'], oracle_nodes=[128,256],
            oracle_relative_changes=errors, archived_half_ghz_relative_error=original_error,
            qualified=bool(max(errors.max(),original_error)<1e-5), oracle_work=work.summary(), seconds=perf_counter()-started)
        write(path/f"{scene['id']}.json",record)
        print(json.dumps(dict(scene=scene['id'], qualified=record['qualified'], oracle_error=float(errors.max()))),flush=True)


def continuation(output, scene_id, arm, *, work_cap=160, nodes=64):
    """Same SC LM/update backend across arms; fixed topology from TD seeds."""
    from experiments.shape_continuation.forward import PointSourceAcquisition, Work, solve
    from experiments.shape_continuation.inverse import Observation
    from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage, NORMAL_RETURN, STAGE_QUOTA, Stop
    from experiments.shape_continuation.multi_object import MultiUpdate, MultiCurve
    from experiments.shape_continuation.updates import BorgesUpdate
    from types import SimpleNamespace
    from .indicators import CircleSeed
    spec = frozen.read(ROOT/'config/topology_scenes_v1.json')
    scene = next(s for s in spec['scenes'] if s['id']==scene_id)
    directory='continuation' if work_cap==160 else f'continuation_cap{work_cap}'
    if nodes!=64:
        directory+=f'_n{nodes}'
    path = output/directory/arm/f'{scene_id}.json'
    started = perf_counter()
    record = dict(scene=scene_id,arm=arm,status='STARTED',extended_acquisition=True,
                  topology='fixed-count data-only topological seeds',selection_uses_holdout=False,
                  work_cap=work_cap,discretization=dict(curve_modes=24,nodes=nodes,refined_nodes=2*nodes))
    write(path,record)
    ledger = Ledger(cap=work_cap,seconds=300 if work_cap>160 else 120,endpoint_reserve=0)
    try:
        if not frozen.read(output/'frequency_data'/f'{scene_id}.json')['qualified']:
            raise ValueError('Extra-frequency observations did not qualify.')
        saved = np.load(output/'frequency_data'/f'{scene_id}.npz')
        acquisition = PointSourceAcquisition(saved['sources'],saved['receivers'],complex(saved['strength']))
        observations = tuple(Observation(float(k),acquisition,y) for k,y in zip(saved['wavenumbers'],saved['observed']))
        rows = frozen.read(output/'initializers'/f'{scene_id}.json')['seeds']
        initial = sc_curve(seed_state(tuple(CircleSeed(tuple(row['center']),row['radius']) for row in rows)))
        if initial is None:
            record.update(status='EMPTY_INITIALIZER',reason='Fixed-count SC backend cannot create a component.')
        else:
            # Radius estimate comes only from the initial image, never truth.
            radius = max(row['radius'] for row in rows)/LENGTH
            path_info = (scif_path(saved['frequencies'].tolist(),seed=int(arm.split('_')[1]),max_visits=32)
                         if arm.startswith('scif_') else dict(indices=list(range(len(observations))),completed=True))
            path_info['frequencies']=[float(saved['frequencies'][i]) for i in path_info['indices']]
            path_info['frequency_unit']='Hz'
            stages = []
            for j,index in enumerate(path_info['indices']):
                obs = observations[index]
                modes = 5 if arm=='sc_fixed_band' else recursive_modes(obs.wavenumber,radius,
                    float(arm.split('_')[1]) if arm.startswith('rla_') else 1.)
                stages.append(FitStage(f'visit-{j}-index-{index}',(obs,),(1.,),(1e-5,),modes,24,nodes,2*nodes,2))
            update = MultiUpdate(BorgesUpdate(LENGTH,projection_tolerance=1e-3))
            # The established coupled adapter exposes fit_stage, not the
            # single-curve run_policy/regauge wrapper. Keep all K fixed and
            # initialize each component through the same Borges regauge.
            curve = MultiCurve(tuple(update.base.regauge(c,24)[0] for c in initial.components),initial.ids)
            result = SimpleNamespace(curve=curve,stages=[],status='COMPLETED_SCHEDULE',reason=None,detail=None)
            try:
                for stage in stages:
                    ledger.begin_stage(stage.label,stage.quota)
                    fitted = fit_stage(result.curve,stage,float(saved['contrast']),update,
                        BackendConfig(max_damping_trials=2,max_backtracks=3),ledger)
                    result.stages.append(fitted)
                    result.curve = fitted.curve
                    if fitted.outcome not in (NORMAL_RETURN,STAGE_QUOTA):
                        result.status,result.reason,result.detail='HARD_STOP',fitted.outcome,fitted.detail
                        break
            except Stop as exc:
                result.status,result.reason,result.detail='HARD_STOP',exc.code,str(exc)
            audit_work = Work(max_forwards=20,max_seconds=120)
            predicted = np.array([solve(result.curve,o.wavenumber,float(saved['contrast']),acquisition,2*nodes,work=audit_work).prediction
                                  for o in observations])
            relative = np.linalg.norm(predicted-saved['observed'],axis=1)/np.linalg.norm(saved['observed'],axis=1)
            # Convert to an evaluation-only polygon state, retaining the full
            # Cartesian Fourier geometry (no radial fit or truth alignment).
            from sdf_inverse.explicit_fourier import CartesianFourierCurveState
            evaluated = []
            for curve,name in zip(result.curve.components,result.curve.ids):
                z = curve.coefficients*LENGTH
                k = curve.band
                center = np.array([z[k].real+.5,z[k].imag+.5])
                cosine = np.stack(((z[k+1:]+z[k-1::-1]).real,(z[k+1:]+z[k-1::-1]).imag),axis=1)
                sine = np.stack(((1j*(z[k+1:]-z[k-1::-1])).real,(1j*(z[k+1:]-z[k-1::-1])).imag),axis=1)
                evaluated.append(CartesianFourierCurveState(np.vstack((center,cosine)),
                    np.vstack((np.zeros(2),sine)),name))
            state = MultiRadialFourierState(tuple(evaluated))
            data,holdout = frozen.shared_data(REFERENCE,scene,spec)
            record.update(status=result.status,reason=result.reason,detail=result.detail,path=path_info,
                stages=[dict(label=s.stage_label, update_modes=stages[i].update_modes,
                             stop_reason=s.stop_reason, outcome=s.outcome,accepted_steps=s.accepted_steps,
                             acceptance_checks=s.acceptance_checks) for i,s in enumerate(result.stages)],
                stage_count=len(result.stages),all_visits_attempted=len(result.stages)==len(stages),
                path_completed=path_info['completed'] and len(result.stages)==len(stages) and result.status=='COMPLETED_SCHEDULE',
                training_relative=relative,selection_score=float(np.mean(relative**2)),
                endpoint=audit(state,scene,spec,data,holdout),audit_forward_work=audit_work.summary(),
                final_coefficients=[dict(real=c.coefficients.real,imag=c.coefficients.imag) for c in result.curve.components])
    except Exception:
        record.update(status='EXCEPTION',traceback=traceback.format_exc())
    record.update(work=ledger.snapshot(),wall_seconds=perf_counter()-started)
    write(path,record)
    print(json.dumps(dict(scene=scene_id,arm=arm,status=record['status'],seconds=record['wall_seconds'])),flush=True)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('mode',choices=['initializers','controller','controller_guarded','controller_full','prepare-frequencies','continuation'])
    parser.add_argument('--output',type=Path,default=OUTPUT)
    parser.add_argument('--scene')
    parser.add_argument('--arm')
    parser.add_argument('--work-cap',type=int,default=160)
    parser.add_argument('--nodes',type=int,default=64)
    args = parser.parse_args()
    if args.mode=='initializers': initializers(args.output)
    elif args.mode=='prepare-frequencies': prepare_frequency_data(args.output)
    elif args.mode.startswith('controller'): controller(args.output,args.scene,args.arm,
        guarded=args.mode=='controller_guarded',full=args.mode=='controller_full')
    else: continuation(args.output,args.scene,args.arm,work_cap=args.work_cap,nodes=args.nodes)


if __name__=='__main__':
    main()
