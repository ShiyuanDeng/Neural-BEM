"""SC-039: raw boundary data along saved inverse trajectories, for any later atlas.

At every distinct accepted state ("shot") of the declared trajectories, and at
every catalog frequency, store what any first-order shape atlas needs:

- the boundary nodes (parameter t, points, normals, arclength weights,
  curvature, speed) of the stored curve, on N and 2N nodes;
- the forward traces of every source and the reciprocal traces of every
  receiver (Dirichlet and Neumann parts, as the Müller solve returns them);
- the full source x receiver prediction.

No atlas is computed here. `shape_jacobian` is the contraction

    J[s, r, c] = (ki^2 - k^2) * sum_x w(x) u_s(x) v_r(x) h(x, c),

so any coordinate choice (normal harmonics, Cartesian coefficients, radial
modes, ...) is a later matrix product with its normal velocities h. The true
shapes are stored separately as evaluation-only reference shots. Run from the
repository root under EMNerf with one BLAS thread per worker:

PYTHONPATH=solvers:. python -m experiments.shape_continuation.trajectory_atlas pilot --output <dir>
PYTHONPATH=solvers:. python -m experiments.shape_continuation.trajectory_atlas collect --output <dir>
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

import numpy as np

from gpr_bem_kress import kress_incident_trace_on_boundary
from gpr_bem_kress.execution import execution

from . import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from .forward import PointSourceAcquisition, _solve, same_acquisition, shape_jacobian, solve
from .geometry import FourierCurve, normal_basis
from .lm_backend import normalize, relative_columns

RESULTS = sc.ROOT / 'results/validation/shape_continuation'
OUTPUT = RESULTS / 'SC-039-trajectory-atlas-data'
PLAN = sc.ROOT / 'docs/iterations/shape_frequency_continuation/iteration_20/03_plan.md'
GRIDS, DENSE_GRIDS = (512, 1024), (768, 1536)
STORED_BAND = 192  # shot keys pad every curve to this band


# ---------------------------------------------------------------- trajectories

@dataclass
class Step:
    curve: FourierCurve
    stage: str
    iteration: object          # int, or a string for recorded endpoints/checkpoints
    update_modes: object       # M; None for SPD (its update space is its radial chart)
    curve_band: int            # stored band K (SPD: radial K)
    wavenumbers: tuple         # frequencies the run was fitting at this state
    nodes: int                 # production grid the run used
    source: str
    loss: object = None
    stage_record: dict = None   # the run's stage (weights etc.); None for SPD
    residual_floor: float = None


@dataclass
class Trajectory:
    id: str
    algorithm: str
    case: str
    steps: list = field(default_factory=list)
    status: str = None
    reason: str = None
    branch_of: str = None
    sources: dict = field(default_factory=dict)

    def extend(self, steps):
        for step in steps:
            if self.steps and same_shape(self.steps[-1].curve, step.curve):
                continue  # a stage start repeats the previous accepted state
            self.steps.append(step)


def padded(curve, band=STORED_BAND):
    if curve.band > band:
        raise ValueError('curve exceeds the shot key band')
    return np.pad(curve.coefficients, (band - curve.band, band - curve.band))


def shot_key(curve):
    return hashlib.sha256(padded(curve).tobytes()).hexdigest()[:20]


def same_shape(a, b):
    return np.array_equal(padded(a), padded(b))


def relative(path):
    return str(Path(path).relative_to(sc.ROOT))


def history_steps(path, stage, floor):
    rows = sc.read(path)['history']
    return [Step(ast.curve_from(r['coefficients']), stage['label'], r['iteration'], stage['update_modes'],
                 ast.curve_from(r['coefficients']).band, tuple(stage['wavenumbers']), stage['nodes'],
                 relative(path), r['loss'], stage, floor) for r in rows]


def lm_run(trajectory, folder, stages, result_name, final_key):
    """Histories of an LM-backend run, then its recorded endpoint if it differs."""
    floor = sc.read(folder / 'configuration.json')['backend']['residual_floor']
    for stage in stages:
        path = folder / f"{stage['label']}_history.json"
        if path.exists():
            trajectory.sources[relative(path)] = sc.digest(path)
            trajectory.extend(history_steps(path, stage, floor))
    result = sc.read(folder / result_name)
    trajectory.sources[relative(folder / result_name)] = sc.digest(folder / result_name)
    trajectory.status, trajectory.reason = result.get('status'), result.get('reason')
    final = ast.curve_from(result[final_key])
    if not same_shape(trajectory.steps[-1].curve, final):
        last = trajectory.steps[-1]
        trajectory.steps.append(Step(final, last.stage, 'recorded_endpoint', last.update_modes, final.band,
                                     last.wavenumbers, last.nodes, relative(folder / result_name),
                                     None, last.stage_record, floor))
    return trajectory


def with_release(stages):
    """SC-035/037 append a same-data K=192 release stage after stage 4."""
    labels = [s['label'] for s in stages]
    if 'stage_5_release_repeat' in labels:
        return stages
    return stages + [dict(stages[-1], label='stage_5_release_repeat', curve_modes=192)]


def prefix(trajectory, through):
    """Steps of `trajectory` up to and including the last step of stage `through`."""
    last = max(i for i, s in enumerate(trajectory.steps) if s.stage == through)
    return trajectory.steps[:last + 1]


def spd_run(case):
    folder = RESULTS / 'SC-034-spd-legacy-controls/runs/L' / case
    configuration = sc.read(folder / 'configuration.json')
    lookup = dict(zip(ac.CATALOG_HZ, (o.wavenumber for o in ast.catalog_only(case))))
    driver = sc.spd_modules()[0].p.driver
    trajectory = Trajectory(f'H_spd_l/{case}', 'SPD-L (SC-034 arm L)', case)
    for path in sorted(folder.glob('stage_*/trajectory.jsonl')):
        n = int(path.parent.name.split('_')[1])
        active = tuple(lookup[f] for f in configuration['frequencies_hz'][:n])
        trajectory.sources[relative(path)] = sc.digest(path)
        steps = []
        for line in path.read_text().splitlines():
            row = json.loads(line)
            component = driver.deserialize_state(row['state']).components[0]
            steps.append(Step(sc.from_cartesian(component), path.parent.name, row['iteration'], None,
                              component.maximum_mode, active, configuration['nodes'][0], relative(path),
                              row.get('loss')))
        checkpoint = path.parent / 'accepted_state.json'
        if checkpoint.exists():  # a hard stop can leave this out of the trajectory log
            trajectory.sources[relative(checkpoint)] = sc.digest(checkpoint)
            component = driver.deserialize_state(sc.read(checkpoint)['state']).components[0]
            steps.append(Step(sc.from_cartesian(component), path.parent.name, 'accepted_checkpoint', None,
                              component.maximum_mode, active, configuration['nodes'][0], relative(checkpoint)))
        trajectory.extend(steps)
    result = sc.read(folder / 'result.json')
    trajectory.sources[relative(folder / 'result.json')] = sc.digest(folder / 'result.json')
    trajectory.status, trajectory.reason = result['status'], result['reason']
    assert same_shape(trajectory.steps[-1].curve, ast.curve_from(result['final_curve'])), trajectory.id
    return trajectory


def trajectories():
    """Every declared trajectory, each complete from the common start circle."""
    out, band = [], {}
    for case in ast.CASES:
        folder = RESULTS / 'SC-029-atlas-strategies/runs/baseline' / case / 'none'
        out.append(lm_run(Trajectory(f'A_hybrid/{case}', 'Original hybrid (SC-029 baseline)', case), folder,
                          sc.read(folder / 'configuration.json')['stages'], 'result.json', 'final_curve'))
    for arm, name in (('low', 'B_state_band'), ('high', 'C_state_band_high')):
        for case in ('circle_to_star', 'circle_to_c', 'kite', 'peanut'):
            folder = RESULTS / 'SC-035-state-band/runs' / case / arm
            t = lm_run(Trajectory(f'{name}/{case}', f'SC-035 {arm} state band', case), folder,
                       with_release(sc.read(folder / 'configuration.json')['stages']), 'continue.json', 'curve')
            out.append(t)
            if arm == 'low':
                band[case] = t
    for case in ('circle_to_star', 'circle_to_c', 'kite', 'peanut'):
        folder = RESULTS / 'SC-036-matched-finite-paths/inverse' / case / 'ray'
        out.append(lm_run(Trajectory(f'D_ray/{case}', 'SC-036 ray path', case), folder,
                          sc.read(folder / 'configuration.json')['stages'], 'result.json', 'final_curve'))
    for case in ('circle_to_star', 'circle_to_c', 'kite', 'peanut'):
        folder = RESULTS / 'SC-037-later-state-release/runs' / case
        t = Trajectory(f'E_wider_ladder/{case}', 'SC-037 wider state ladder', case, branch_of=band[case].id)
        t.extend(prefix(band[case], 'stage_1'))
        out.append(lm_run(t, folder, sc.read(folder / 'configuration.json')['stages'], 'result.json', 'curve'))
    root = RESULTS / 'SC-038-update-band-release'
    for case in ('circle_to_c', 'kite'):
        for arm, name in (('release_m', 'F_released_m'), ('fixed_m9', 'G_fixed_m9')):
            folder = root / 'runs' / case / arm
            t = Trajectory(f'{name}/{case}', f'SC-038 {arm}', case, branch_of=band[case].id)
            t.extend(prefix(band[case], 'stage_4'))
            stages = sc.read(folder / 'configuration.json')['stages']
            if case == 'kite' and arm == 'release_m':
                # The selected path replays M=15 and M=19 at 768/1536 nodes from the
                # M=11 endpoint; the stopped 512-node M=15 attempt is its own branch.
                lm_run(t, folder, stages[:1], 'result.json', 'curve')
                t.steps = [s for s in t.steps if s.iteration != 'recorded_endpoint']
                start = len(t.steps)
                dense = root / 'dense_kite/runs/release_m'
                lm_run(t, dense, sc.read(dense / 'configuration.json')['stages'], 'result.json', 'curve')
                final = root / 'final_m19/runs/release_m'
                lm_run(t, final, sc.read(final / 'configuration.json')['stages'], 'result.json', 'curve')
                assert start < len(t.steps)
                attempt = Trajectory('F_released_m_512_attempt/kite', 'SC-038 release_m, stopped 512-node M=15 attempt',
                                     case, branch_of=t.id)
                attempt.extend(prefix(t, 'release_1'))
                out += [t, lm_run(attempt, folder, stages[1:], 'result.json', 'curve')]
                continue
            out.append(lm_run(t, folder, stages, 'result.json', 'curve'))
    dense = root / 'dense_kite/runs/fixed_m9'
    t = Trajectory('G_fixed_m9_dense_replay/kite', 'SC-038 fixed_m9, 768/1536 replay', 'kite',
                   branch_of='G_fixed_m9/kite')
    fixed = next(x for x in out if x.id == 'G_fixed_m9/kite')
    t.extend(prefix(fixed, 'release_1'))
    out.append(lm_run(t, dense, sc.read(dense / 'configuration.json')['stages'], 'result.json', 'curve'))
    out += [spd_run(case) for case in ast.CASES]
    return out


def shots(declared):
    """Distinct geometries over all trajectories, with the grids they need."""
    table = {}
    for t in declared:
        for index, step in enumerate(t.steps):
            key = shot_key(step.curve)
            entry = table.setdefault(key, dict(key=key, curve=step.curve, cases=set(), grids=set(GRIDS), steps=[]))
            entry['cases'].add(t.case)
            if step.nodes == DENSE_GRIDS[0]:
                entry['grids'] |= set(DENSE_GRIDS)
            entry['steps'].append((t.id, index))
    return table


def truth_shots():
    return {case: ast.curve_from(sc.read(ast.source_folder(case) / 'truth.json')) for case in ast.CASES}


# ------------------------------------------------------------------ collection

def catalog():
    """The 19 catalog wavenumbers and the shared line-source acquisition."""
    catalogs = {case: ast.catalog_only(case) for case in ast.CASES}
    first = catalogs[ast.CASES[0]]
    for case, items in catalogs.items():
        assert [o.wavenumber for o in items] == [o.wavenumber for o in first], case
        assert all(same_acquisition(a.acquisition, b.acquisition) for a, b in zip(items, first)), case
    return first, catalogs


def reciprocal_traces(state):
    """Exactly `shape_jacobian`'s reciprocal solve for every receiver."""
    with execution(kernels='reference', device='cpu'):
        d, n = kress_incident_trace_on_boundary(state.curve, state.acquisition.receivers, state.wavenumber)
    return _solve(state.matrix, state.factors, np.concatenate((d, n), axis=1).T)


def geometry(nodes):
    return dict(parameters=nodes.parameters, points=nodes.points, normals=nodes.normals,
                weights=nodes.arc_length_weights, curvatures=nodes.curvatures, speeds=nodes.speeds)


def compute(curve, grids, observations, contrast):
    """Every catalog frequency on every grid: traces, reciprocal traces and full predictions."""
    arrays, record = {}, dict(grids=sorted(grids), forward_residual={}, reciprocal_residual={}, seconds={})
    for n in sorted(grids):
        started = time.perf_counter()
        traces, reciprocal, prediction, forward_res, reciprocal_res = [], [], [], [], []
        for observation in observations:
            acquisition = observation.acquisition
            full = PointSourceAcquisition(acquisition.sources, acquisition.receivers, acquisition.strength, paired=False)
            state = solve(curve, observation.wavenumber, contrast, full, n)
            inverse, residual = reciprocal_traces(state)
            traces.append(state.traces)
            reciprocal.append(inverse)
            prediction.append(state.prediction)
            forward_res.append(state.system_residual)
            reciprocal_res.append(residual)
        for name, value in geometry(state.curve).items():
            arrays[f'{name}_{n}'] = value
        arrays[f'traces_{n}'] = np.stack(traces)            # (F, 2N, sources)
        arrays[f'reciprocal_{n}'] = np.stack(reciprocal)    # (F, 2N, receivers)
        arrays[f'prediction_{n}'] = np.stack(prediction)    # (F, sources, receivers)
        record['forward_residual'][n] = float(max(forward_res))
        record['reciprocal_residual'][n] = float(max(reciprocal_res))
        record['seconds'][n] = time.perf_counter() - started
    arrays['wavenumbers'] = np.array([o.wavenumber for o in observations])
    arrays['interior_wavenumbers'] = arrays['wavenumbers'] * np.sqrt(contrast)
    arrays['frequencies_hz'] = np.array(ac.CATALOG_HZ)
    arrays['coefficients'] = curve.coefficients
    arrays['length_unit_m'] = np.array(sc.LENGTH)
    arrays['center_m'] = np.array(sc.CENTER)
    arrays['contrast'] = np.array(contrast)
    low, high = sorted(grids)[:2]
    record['paired_grid_discrepancy'] = [float(relative_columns(np.diag(a)[:, None], np.diag(b)[:, None])[0])
        for a, b in zip(arrays[f'prediction_{low}'], arrays[f'prediction_{high}'])]
    record['full_grid_discrepancy'] = [float(np.linalg.norm(a - b) / np.linalg.norm(b))
        for a, b in zip(arrays[f'prediction_{low}'], arrays[f'prediction_{high}'])]
    record['forward_solves'] = record['reciprocal_solves'] = len(observations) * len(grids)
    return arrays, record


def write_shot(folder, name, curve, grids, observations, contrast, extra):
    npz, meta = folder / f'{name}.npz', folder / f'{name}.json'
    if meta.exists() and npz.exists():  # resume only what this exact collector produced
        record = sc.read(meta)
        if record.get('npz_sha256') == sc.digest(npz) and record.get('collector_sha256') == extra['collector_sha256']:
            return record
    arrays, record = compute(curve, grids, observations, contrast)
    temporary = folder / f'.{name}.tmp.npz'
    np.savez(temporary, **arrays)
    os.replace(temporary, npz)
    record.update(extra, npz_sha256=sc.digest(npz), npz_bytes=npz.stat().st_size)
    sc.write(meta, record)
    return record


def _worker(job):
    kind, name, coefficients, grids, extra, output = job
    extra = dict(extra, collector_sha256=sc.digest(Path(__file__)))
    try:
        first, _ = catalog()
        folder = Path(output) / kind
        folder.mkdir(parents=True, exist_ok=True)
        curve = FourierCurve(np.asarray(coefficients))
        return name, write_shot(folder, name, curve, grids, first, ac.contrast(), extra)
    except Exception:
        return name, dict(status='EXCEPTION', traceback=traceback.format_exc())


# ------------------------------------------------------------------ later atlas API

def load(path):
    with np.load(path) as data:
        return {k: data[k] for k in data.files}


def jacobian(shot, frequency, nodes, velocities, paired=True):
    """`shape_jacobian` from stored traces, for normal velocities (nodes, directions)."""
    n = nodes
    u, v = shot[f'traces_{n}'][frequency, :n], shot[f'reciprocal_{n}'][frequency, :n]
    k, ki = shot['wavenumbers'][frequency], shot['interior_wavenumbers'][frequency]
    weighted = shot[f'weights_{n}'][:, None] * np.asarray(velocities, float)
    if paired:
        return (ki ** 2 - k ** 2) * ((u * v).T @ weighted)          # (pairs, directions)
    return (ki ** 2 - k ** 2) * np.einsum('xs,xr,xc->src', u, v, weighted)


def cartesian_velocities(shot, nodes, band):
    """Normal velocity per metre of Re and Im of each stored coefficient c_p, |p| <= band."""
    t = shot[f'parameters_{nodes}']
    normal = shot[f'normals_{nodes}'] @ np.array([1, 1j])
    orders = np.arange(-band, band + 1)
    wave = np.exp(1j * t[:, None] * orders) / float(shot['length_unit_m'])
    return np.column_stack(((np.conj(normal)[:, None] * wave).real, (np.conj(normal)[:, None] * 1j * wave).real)), orders


def normal_velocities(shot, nodes, band):
    """Arclength normal harmonics 0..band, as `BorgesUpdate.velocities`."""
    curve = FourierCurve(shot['coefficients'])
    return normal_basis(curve.nodes(nodes), band) / float(shot['length_unit_m'])


# ------------------------------------------------------------------ driver

def declared(output):
    listed = trajectories()
    table = shots(listed)
    for t in listed:
        for step in t.steps:
            assert shot_key(step.curve) in table
    manifest = dict(experiment='SC-039', plan=relative(PLAN), plan_sha256=sc.digest(PLAN),
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=sc.ROOT, text=True).strip(),
        collector_sha256=sc.digest(Path(__file__)), command=sys.argv, python=sys.executable,
        grids=list(GRIDS), dense_grids=list(DENSE_GRIDS), frequencies_hz=list(ac.CATALOG_HZ),
        contrast=ac.contrast(), length_unit_m=sc.LENGTH, center_m=[sc.CENTER.real, sc.CENTER.imag],
        trajectories=[dict(id=t.id, algorithm=t.algorithm, case=t.case, status=t.status, reason=t.reason,
                           branch_of=t.branch_of, sources=t.sources,
                           steps=[dict(shot=shot_key(s.curve), stage=s.stage, iteration=s.iteration,
                                       update_modes=s.update_modes, curve_band=s.curve_band,
                                       active_wavenumbers=list(s.wavenumbers), nodes=s.nodes,
                                       source=s.source, saved_loss=s.loss) for s in t.steps])
                      for t in listed],
        shots={k: dict(cases=sorted(v['cases']), grids=sorted(v['grids']), stored_band=v['curve'].band,
                       steps=v['steps']) for k, v in table.items()},
        truth_reference=dict(cases=list(ast.CASES), evaluation_only=True))
    output.mkdir(parents=True, exist_ok=True)
    sc.write(output / 'manifest.json', manifest)
    return listed, table


def jobs_for(table, output, keys=None):
    jobs = [('shots', key, table[key]['curve'].coefficients, sorted(table[key]['grids']),
             dict(key=key, cases=sorted(table[key]['cases']), steps=table[key]['steps']), str(output))
            for key in (keys or table)]
    if keys is None:
        jobs += [('truth', case, curve.coefficients, list(GRIDS), dict(case=case, evaluation_only=True), str(output))
                 for case, curve in truth_shots().items()]
    return jobs


def run(jobs, workers, log):
    rows = {}
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for done, (name, record) in enumerate(pool.map(_worker, jobs), 1):
            rows[name] = record
            status = record.get('status', 'OK')
            log.write(f"{time.strftime('%H:%M:%S')} {done}/{len(jobs)} {name} {status} "
                      f"{sum(record.get('seconds', {}).values()):.1f}s\n")
            log.flush()
    return rows


def pilot(output, workers):
    """A few diverse shots; the stored traces must reproduce the backend exactly."""
    listed, table = declared(output)
    by_id = {t.id: t for t in listed}
    picks = dict(start=by_id['A_hybrid/peanut'].steps[0], collapsed_peanut=by_id['A_hybrid/peanut'].steps[-1],
                 sharp_kite=by_id['B_state_band/kite'].steps[-1], released_c=by_id['F_released_m/circle_to_c'].steps[-1],
                 dense_kite=by_id['F_released_m/kite'].steps[-1], spd_c_stop=by_id['H_spd_l/circle_to_c'].steps[-1])
    keys = [shot_key(s.curve) for s in picks.values()]
    started = time.perf_counter()
    with open(output / 'pilot.log', 'a') as log:
        records = run(jobs_for(table, output, keys), workers, log)
    elapsed = time.perf_counter() - started
    first, catalogs = catalog()
    checks = []
    for label, step in picks.items():
        key = shot_key(step.curve)
        shot = load(output / 'shots' / f'{key}.npz')
        curve = FourierCurve(shot['coefficients'])
        row = dict(label=label, shot=key, record=records[key])
        for frequency in (0, 9, 18):
            observation = first[frequency]
            state = solve(curve, observation.wavenumber, ac.contrast(), observation.acquisition, 512)
            row[f'paired_prediction_bitwise_f{frequency}'] = bool(np.array_equal(
                np.diag(shot['prediction_512'][frequency]), state.prediction))
            for name, basis in (('normal_M19', normal_velocities(shot, 512, 19)),
                                ('cartesian_P24', cartesian_velocities(shot, 512, 24)[0])):
                reference = shape_jacobian(state, basis)
                error = np.linalg.norm(jacobian(shot, frequency, 512, basis) - reference) / np.linalg.norm(reference)
                row[f'jacobian_{name}_f{frequency}'] = float(error)
            full = PointSourceAcquisition(observation.acquisition.sources, observation.acquisition.receivers,
                                          observation.acquisition.strength, paired=False)
            state_full = solve(curve, observation.wavenumber, ac.contrast(), full, 512)
            basis = normal_velocities(shot, 512, 9)
            reference = shape_jacobian(state_full, basis)
            row[f'jacobian_full_normal_M9_f{frequency}'] = float(
                np.linalg.norm(jacobian(shot, frequency, 512, basis, paired=False) - reference) / np.linalg.norm(reference))
        if step.stage_record is not None and step.loss is not None:
            # The run's own objective at this state, rebuilt from stored predictions on its grid.
            trajectory = next(t for t in listed if any(s is step for s in t.steps))
            index = [list(shot['wavenumbers']).index(k) for k in step.wavenumbers]
            observed = np.column_stack([catalogs[trajectory.case][i].scattered for i in index])
            predicted = np.column_stack([np.diag(shot[f'prediction_{step.nodes}'][i]) for i in index])
            residual = normalize(predicted - observed, observed, tuple(step.stage_record['weights']),
                                 step.residual_floor)
            row['saved_loss'] = step.loss
            row['rebuilt_loss'] = 0.5 * float(residual @ residual)
            row['loss_relative_error'] = abs(row['rebuilt_loss'] - step.loss) / step.loss
        checks.append(row)
    jac = [v for r in checks for k, v in r.items() if k.startswith('jacobian_')]
    bitwise = [v for r in checks for k, v in r.items() if k.startswith('paired_prediction_bitwise')]
    losses = [r['loss_relative_error'] for r in checks if 'loss_relative_error' in r]
    summary = dict(checks=checks, seconds=elapsed, workers=workers,
                   worst_jacobian_relative=max(jac), all_paired_predictions_bitwise=all(bitwise),
                   worst_loss_relative=max(losses) if losses else None,
                   passed=bool(max(jac) <= 1e-12 and all(bitwise) and losses and max(losses) <= 1e-12),
                   mean_seconds_per_base_shot=float(np.mean([sum(v for n, v in r['record']['seconds'].items()
                                                                 if int(n) in GRIDS) for r in checks])),
                   mean_bytes_per_base_shot=float(np.mean([r['record']['npz_bytes'] for r in checks
                                                           if r['record']['grids'] == list(GRIDS)])))
    sc.write(output / 'pilot.json', summary)
    return summary


def collect(output, workers):
    listed, table = declared(output)
    jobs = jobs_for(table, output)
    sc.write(output / 'dispatch.json', dict(shots=len(table), truth=len(ast.CASES), workers=workers,
        forward_solves=sum(19 * len(j[3]) for j in jobs), reciprocal_solves=sum(19 * len(j[3]) for j in jobs),
        started=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    started = time.perf_counter()
    with open(output / 'collect.log', 'a') as log:
        rows = run(jobs, workers, log)
    failures = {k: v for k, v in rows.items() if v.get('status') == 'EXCEPTION'}
    sc.write(output / 'completion.json', dict(status='COMPLETE' if not failures else 'FAILURES',
        failures=failures, seconds=time.perf_counter() - started, collected=len(rows) - len(failures),
        finished=time.strftime('%Y-%m-%dT%H:%M:%S%z')))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mode', choices=('list', 'pilot', 'collect'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--workers', type=int, default=10)
    args = parser.parse_args()
    if args.mode == 'list':
        listed, table = declared(args.output)
        for t in listed:
            print(f'{t.id:36s} {len(t.steps):4d} steps  {t.status} {t.reason or ""}')
        print(len(table), 'distinct shots,', sum(len(v['grids']) > 2 for v in table.values()), 'with dense grids')
    elif args.mode == 'pilot':
        print(json.dumps({k: v for k, v in pilot(args.output, args.workers).items() if k != 'checks'}, indent=1))
    else:
        collect(args.output, args.workers)


if __name__ == '__main__':
    main()
