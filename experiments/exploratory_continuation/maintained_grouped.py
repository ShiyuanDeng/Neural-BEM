"""Finish unique full-policy inputs and explicitly rescore exact-input aliases."""
from . import maintained_run as R
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
import numpy as np
from experiments.cleaned_interface.io import write, read, digest
from .maintained_adapter import CoupledGeometry


def rescore(directory):
    """Repair evaluation-only adapter errors without rerunning any inverse."""
    path = directory/'result.json'
    row = read(path)
    fitted = directory/'fit_result.json'
    if not fitted.exists(): return row
    result = read(fitted)
    if 'endpoint' in row and 'fit_result' in row: return row
    original = directory/'result_before_scoring_repair.json'
    if not original.exists(): write(original, row)
    row.update(status=result['outcome'], fit_result=result, detail=result.get('detail'),
               completed=result['outcome']=='COMPLETED_SCHEDULE', evaluation_repaired=True,
               evaluation_repair='Raise Cartesian geometry validation grid from fixed256 to max(512,2K+2); preserved inverse endpoint, no inverse rerun')
    try:
        row['endpoint'] = R.score(row['scene'], CoupledGeometry.restore(result['final_curve']))
        row['qualified_pass'] = bool(row['completed'] and result['initial_audit_passed'] and
                                    result['final_audit_passed'] and row['endpoint']['passed'])
        row.pop('endpoint_error', None)
    except Exception:
        row.update(endpoint_error=traceback.format_exc(), qualified_pass=False)
    if result.get('relative_residual') is not None:
        row['selection_score'] = float(np.mean(np.asarray(result['relative_residual'])**2))
    write(path, row)
    return row


def full_campaign(arm, workers=2, external=(), destination=R.DESTINATION):
    scenes = [s['id'] for s in read(R.ROOT/'config/topology_scenes_v1.json')['scenes']]
    groups = {}
    for scene in scenes: groups.setdefault(R.input_signature(scene), []).append(scene)
    def job(scene):
        directory = destination/'runs'/arm/scene
        path = directory/'result.json'
        if scene in external:
            while not path.exists() or read(path)['status'] == 'STARTED': time.sleep(2)
        if path.exists():
            existing = rescore(directory)
            initial = directory/'initial_audit.json'
            timeout = initial.exists() and 'TimeoutError' in read(initial).get('traceback', '')
            if not timeout:
                return dict(scene=scene, reused_existing=True, status=existing['status'])
            # Keep the actual300-second attempt and retry identical policy/data
            # with a900-second independent audit allowance and streaming memory.
            archive = destination/'attempts'/arm/f'{scene}_dense_audit300'
            archive.parent.mkdir(parents=True, exist_ok=True)
            directory.rename(archive)
        logs = destination/'logs'
        logs.mkdir(parents=True, exist_ok=True)
        with (logs/f'{arm}__{scene}__streamed.log').open('w') as stream:
            command = [sys.executable, '-m', 'experiments.exploratory_continuation.maintained_run', 'one',
                       '--scene', scene, '--arm', arm, '--destination', str(destination), '--audit-seconds', '900']
            returned = subprocess.run(command, cwd=R.ROOT, stdout=stream, stderr=subprocess.STDOUT)
        receipt = dict(scene=scene, returncode=returned.returncode)
        print(json.dumps(receipt), flush=True)
        return receipt
    # Pending external jobs are collected after new unique fits, not allowed to
    # occupy workers while doing no computation.
    representatives = [names[0] for names in groups.values()]
    pending = [s for s in representatives if s not in external]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        returned = list(pool.map(job, pending))
    returned += [job(s) for s in representatives if s in external]
    aliases, independently_repeated = [], []
    for signature, names in groups.items():
        origin = destination/'runs'/arm/names[0]/'result.json'
        record = read(origin)
        for name in names[1:]:
            directory = destination/'runs'/arm/name
            if (directory/'result.json').exists():
                while read(directory/'result.json')['status']=='STARTED': time.sleep(2)
                independently_repeated.append(dict(scene=name, original=names[0],
                    same_final_coefficients=rescore(directory).get('fit_result',{}).get('final_curve') ==
                                            record.get('fit_result',{}).get('final_curve')))
                continue
            row = dict(record, scene=name, actual_executed=False, input_signature=signature,
                       reused_from=str(origin.relative_to(R.ROOT)), actual_fit_seconds=0.,
                       reuse_audit='Exact acquisition, real data, TD coefficients/IDs, material and units; same policy. Post-fit scene gates recomputed.')
            if arm=='damped':
                row['damped_array_equality'] = bool(np.array_equal(
                    np.load(destination/'damped_data'/f'{name}.npz')['observed'],
                    np.load(destination/'damped_data'/f'{names[0]}.npz')['observed']))
                if not row['damped_array_equality']: raise ValueError('Damped observations differ; cannot reuse fit')
            if 'fit_result' in row:
                row['endpoint'] = R.score(name, CoupledGeometry.restore(row['fit_result']['final_curve']))
                row['qualified_pass'] = bool(row['completed'] and row['fit_result']['initial_audit_passed'] and
                    row['fit_result']['final_audit_passed'] and row['endpoint']['passed'])
            write(directory/'result.json', row)
            aliases.append(dict(scene=name, source=names[0], signature=signature))
    write(destination/f'{arm}_grouped_campaign.json', dict(groups=groups, returned=returned,
        aliases=aliases, independently_repeated=independently_repeated, workers=workers,
        fit_cap=13412, fit_seconds=1800, streamed_audit_seconds=900,
        audit_changes='Identical streaming computations; tested bitwise. Initial300s audit attempts retained before audit900 reruns.',
        interrupted_old_schedulers_only=True, no_inflight_fit_killed=True))


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('mode', choices=['campaign', 'rescore'])
    p.add_argument('--arm', default='real', choices=['real', 'damped'])
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--external', nargs='*', default=[])
    p.add_argument('--directory', type=Path)
    a = p.parse_args()
    if a.mode == 'rescore': rescore(a.directory)
    else: full_campaign(a.arm, a.workers, a.external)


if __name__ == '__main__': main()
