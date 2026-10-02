"""Work-, geometry-, derivative- and physics-matched continuation comparison."""
from . import maintained_run as R  # Fix BLAS environment before numerical imports.
import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace, asdict
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
import traceback
import numpy as np

from experiments.cleaned_interface.io import write, read, digest, portable
from experiments.cleaned_interface.physics import Execution
from experiments.cleaned_interface.runner import fit, audit
from experiments.shape_continuation.geometry import grid_size
from .maintained_adapter import CoupledCumulativePolicy, CoupledGeometry, CoupledNodalKress, preserve_td_start
from .paths import recursive_modes, scif_path

DESTINATION = R.DESTINATION/'matched512'


@dataclass(frozen=True)
class MatchedPolicy(CoupledCumulativePolicy):
    kind: str = 'cumulative'
    seed: int = 0
    radius: float = 1.

    def operations(self, problem, physics):
        inherited = super().operations(problem, physics)
        if self.kind == 'cumulative':
            # Common storage and 22 iterations per visit are explicit matched
            # settings. Full-default cumulative runs retain native K and warmup44.
            return tuple(replace(op, stage=replace(op.stage, curve_modes=192, iterations=22))
                         if op.kind == 'fit' else op for op in inherited)
        path = self.frequency_path(problem)
        operations = [inherited[0], inherited[1]]
        for visit, index in enumerate(path['indices']):
            o = problem.real[index]
            band = recursive_modes(o.wavenumber, self.radius, factor=1.5 if self.kind == 'rla' else 1.)
            operations.append(self._fit(problem, physics, f'{self.kind}_visit_{visit:02d}_frequency_{index}',
                (o,), band, 192, None, iterations=22,
                purpose='Single-frequency visit on the declared RLA/SCIF path; same optimizer/update/physics'))
        operations.append(inherited[-1])
        return tuple(operations)

    def frequency_path(self, problem):
        return (scif_path([o.frequency_hz for o in problem.real], seed=self.seed, max_visits=32)
                if self.kind == 'scif' else dict(indices=list(range(len(problem.real))), completed=True))

    def plan(self, problem, physics):
        return dict(super().plan(problem, physics), matched_settings=dict(
            kind=self.kind, seed=self.seed, storage_band=192, iterations_per_visit=22,
            common_work_cap=self.fit_units, common_wall_cap=self.fit_seconds,
            cumulative_changes='K192 throughout and warmup22 instead of native warmupK4/44; all subsequent operations retained',
            rla_factor=1.5, rla_selection_history='predefined from earlier small-campaign best tested factor; not selected on this supplement',
            scif_factor=1., scif_probability=.603, scif_seeds=list(range(8)),
            scif_selection='minimum five-real-frequency training residual among completed, numerically qualified paths',
            radius_from_initial_data_only=self.radius,
            path=None if self.kind == 'cumulative' else self.frequency_path(problem)))


def source_hashes():
    paths = [R.ROOT/'experiments/cleaned_interface'/name for name in
             ('runner.py', 'geometry.py', 'policy.py', 'physics.py', 'problem.py')]
    paths += [R.ROOT/'experiments/shape_continuation'/name for name in
              ('lm_backend.py', 'forward.py', 'multi_object.py', 'geometry.py')]
    paths += [Path(__file__), Path(__file__).with_name('maintained_adapter.py'),
              Path(__file__).with_name('maintained_run.py'), Path(__file__).with_name('paths.py'),
              R.ROOT/'config/topology_scenes_v1.json']
    return {str(p.relative_to(R.ROOT)):digest(p) for p in paths}


def audit_cache(destination):
    """Reuse only the exact complete numerical-audit inputs, never fit endpoints."""
    directory = destination/'audit_cache'
    directory.mkdir(parents=True, exist_ok=True)
    sources = source_hashes()
    def cached(curve, stage, config, problem, physics, update, seconds):
        record = dict(curve=CoupledGeometry.record(curve), M=stage.update_modes, nodes=stage.nodes,
            refined_nodes=stage.refined_nodes, config=asdict(config), contrast=problem.contrast,
            data=[dict(k=o.wavenumber, y=o.scattered, sources=o.acquisition.sources,
                       receivers=o.acquisition.receivers, strength=o.acquisition.strength, f=o.frequency_hz) for o in problem.real],
            update=update.settings(), execution=asdict(physics.execution), sources=sources, seconds=seconds)
        key = hashlib.sha256(json.dumps(portable(record), sort_keys=True).encode()).hexdigest()
        path = directory/f'{key}.json'
        with (directory/f'{key}.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if path.exists():
                receipt = read(path)
                return dict(receipt['audit'], reused_exact_audit=True, reuse_key=key,
                            actual_new_audit_units=0, charged_reference_units=receipt['audit']['work']['work_units'])
            result = audit(curve, stage, config, problem, physics, update, seconds)
            write(path, dict(inputs=record, audit=result))
            return dict(result, reused_exact_audit=False, reuse_key=key,
                        actual_new_audit_units=result['work']['work_units'])
    return cached


def run_one(scene, arm, destination=DESTINATION, cap=512, seconds=7200.):
    directory = destination/'runs'/arm/scene
    started = perf_counter()
    problem = R.load_problem(scene)
    kind, seed = ('scif', int(arm.split('_')[1])) if arm.startswith('scif_') else (arm, 0)
    seeds = read(R.OUTPUT/'initializers'/f'{scene}.json')['seeds']
    radius = max(s['radius'] for s in seeds)/R.LENGTH
    policy = MatchedPolicy(kind=kind, seed=seed, radius=radius, gamma=0., fit_units=cap,
        fit_seconds=seconds, prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9), audit_seconds=900.)
    physics = CoupledNodalKress(Execution(device='cpu', frequency_threads=1, resolution=512))
    row = dict(scene=scene, arm=arm, status='STARTED', input_signature=R.input_signature(scene),
               source_sha256=source_hashes(), matched_settings=dict(work_cap=cap, seconds=seconds,
               K=192, nodes=[512, 1024], iterations_per_visit=22), actual_executed=True,
               heldout_selection=False)
    write(directory/'result.json', row)
    try:
        result = fit(problem, policy=policy, physics=physics, output=directory,
            geometry_adapter=CoupledGeometry, localization_adapter=preserve_td_start,
            audit_adapter=audit_cache(destination),
            on_event=lambda event: print(json.dumps(dict(scene=scene, arm=arm,
                label=event['operation']['label'], reason=event['reason'])), flush=True))
        curve = CoupledGeometry.restore(result['final_curve'])
        relative = result.get('relative_residual')
        completed = result['outcome'] == 'COMPLETED_SCHEDULE'
        if kind == 'scif': completed &= policy.frequency_path(problem)['completed']
        row.update(status=result['outcome'], fit_result=result, completed=bool(completed),
            selection_score=float(np.mean(np.asarray(relative)**2)) if relative is not None else None)
        write(directory/'result.json', row)
        try:
            row['endpoint'] = R.score(scene, curve)
            row['qualified_pass'] = bool(completed and result['initial_audit_passed'] and
                                        result['final_audit_passed'] and row['endpoint']['passed'])
        except Exception:
            row.update(endpoint_error=traceback.format_exc(), qualified_pass=False)
    except Exception:
        row.update(status='EXCEPTION', traceback=traceback.format_exc(), completed=False, qualified_pass=False)
    row['wall_seconds'] = perf_counter()-started
    write(directory/'result.json', row)
    print(json.dumps(dict(scene=scene, arm=arm, status=row['status'], seconds=row['wall_seconds'])), flush=True)
    return row


def campaign(destination=DESTINATION, workers=4, cap=512, seconds=7200., arms=None):
    scenes = [s['id'] for s in read(R.ROOT/'config/topology_scenes_v1.json')['scenes']]
    groups = {}
    for scene in scenes: groups.setdefault(R.input_signature(scene), []).append(scene)
    arms = arms or ['cumulative', 'rla'] + [f'scif_{seed}' for seed in range(8)]
    jobs = [(arm, names[0]) for arm in arms for names in groups.values()]
    def job(item):
        arm, scene = item
        path = destination/'runs'/arm/scene/'result.json'
        if path.exists() and read(path)['status'] != 'STARTED':
            old = read(path)
            if old['source_sha256'] != source_hashes():
                raise ValueError('Cannot reuse a result from different source hashes.')
            return dict(arm=arm, scene=scene, reused_existing=True)
        logs = destination/'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs/f'{arm}__{scene}.log').open('w') as stream:
            command = [sys.executable, '-m', 'experiments.exploratory_continuation.maintained_matched',
                       'one', '--scene', scene, '--arm', arm, '--destination', str(destination),
                       '--cap', str(cap), '--seconds', str(seconds)]
            returned = subprocess.run(command, cwd=R.ROOT, stdout=stream, stderr=subprocess.STDOUT)
        result = dict(arm=arm, scene=scene, returncode=returned.returncode)
        print(json.dumps(result), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=workers) as pool:
        returned = list(pool.map(job, jobs))
    # Exact-input aliases are scored independently against their own heldouts.
    reuse = []
    for arm in arms:
        for signature, names in groups.items():
            origin = destination/'runs'/arm/names[0]/'result.json'
            record = read(origin)
            for name in names[1:]:
                row = dict(record, scene=name, actual_executed=False,
                    reused_from=str(origin.relative_to(R.ROOT)), input_signature=signature,
                    reuse_audit='Byte-identical real measurements/acquisition/TD curves, IDs/material/units; identical policy and source hashes',
                    actual_fit_seconds=0.)
                if 'fit_result' in row:
                    row['endpoint'] = R.score(name, CoupledGeometry.restore(row['fit_result']['final_curve']))
                    row['qualified_pass'] = bool(row.get('completed') and row['fit_result']['initial_audit_passed'] and
                                                row['fit_result']['final_audit_passed'] and row['endpoint']['passed'])
                write(destination/'runs'/arm/name/'result.json', row)
                reuse.append(dict(arm=arm, scene=name, reused_from=names[0], input_signature=signature))
    write(destination/'campaign.json', dict(groups=groups, jobs=returned, aliases=reuse,
        workers=workers, cap=cap, seconds=seconds, arms=arms, source_sha256=source_hashes(),
        cost_semantics='Charge reference work for every nominal path; also report actual work after exact-input/audit reuse'))


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('mode', choices=['one', 'campaign'])
    p.add_argument('--scene')
    p.add_argument('--arm', default='scif_0')
    p.add_argument('--arms', nargs='*')
    p.add_argument('--cap', type=int, default=512)
    p.add_argument('--seconds', type=float, default=7200.)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--destination', type=Path, default=DESTINATION)
    a = p.parse_args()
    if a.mode == 'one': run_one(a.scene, a.arm, a.destination, a.cap, a.seconds)
    else: campaign(a.destination, a.workers, a.cap, a.seconds, a.arms)


if __name__ == '__main__': main()
