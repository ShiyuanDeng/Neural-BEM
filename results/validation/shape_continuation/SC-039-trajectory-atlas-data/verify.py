"""SC-039 completeness and integrity audit; no field solves.

1. Every declared shot and truth reference has its array file, whose SHA-256
   and collector version match its record.
2. Every saved LM-run loss along every trajectory is rebuilt from the stored
   predictions on the run's own grid, with that stage's weights and floor.
3. SPD-L's saved losses come from SPD's own solver; their agreement with the
   stored predictions is reported for information, not gated.
4. Resolution indicators: the 512/1024 paired-prediction agreement per shot.

Run from the repository root: PYTHONPATH=solvers:. python <this file>
"""
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation import trajectory_atlas as ta
from experiments.shape_continuation.lm_backend import normalize

HERE = Path(__file__).resolve().parent
COLLECTOR = sc.digest(Path(ta.__file__))


def audit_file(args):
    folder, name = args
    record = sc.read(HERE / folder / f'{name}.json')
    npz = HERE / folder / f'{name}.npz'
    return name, dict(exists=npz.exists(), hash_ok=npz.exists() and sc.digest(npz) == record['npz_sha256'],
                      collector_ok=record.get('collector_sha256') == COLLECTOR, bytes=record.get('npz_bytes'),
                      forward_residual=max(record['forward_residual'].values()),
                      reciprocal_residual=max(record['reciprocal_residual'].values()),
                      paired_grid_discrepancy=record['paired_grid_discrepancy'],
                      seconds=sum(record['seconds'].values()))


def spd_loss(predicted, observed):
    """SPD's normalization: 0.5 * mean_f ||prediction_f - observed_f||^2 / ||observed_f||^2."""
    return 0.5 * float(np.mean(np.linalg.norm(predicted - observed, axis=0) ** 2 / np.linalg.norm(observed, axis=0) ** 2))


def main():
    manifest = sc.read(HERE / 'manifest.json')
    jobs = [('shots', key) for key in manifest['shots']] + [('truth', case) for case in manifest['truth_reference']['cases']]
    with ProcessPoolExecutor(max_workers=8) as pool:
        files = dict(pool.map(audit_file, jobs))
    listed = ta.trajectories()
    assert [t.id for t in listed] == [t['id'] for t in manifest['trajectories']], 'trajectory list changed'
    catalogs = {case: ast.catalog_only(case) for case in ast.CASES}
    lm, spd, cache = [], [], {}
    for t in listed:
        for index, step in enumerate(t.steps):
            if step.loss is None:
                continue
            key = ta.shot_key(step.curve)
            if key not in cache:
                with np.load(HERE / 'shots' / f'{key}.npz') as data:
                    cache.clear()
                    cache[key] = {k: data[k] for k in data.files if k.startswith('prediction_') or k == 'wavenumbers'}
            shot = cache[key]
            columns = [list(shot['wavenumbers']).index(k) for k in step.wavenumbers]
            observed = np.column_stack([catalogs[t.case][i].scattered for i in columns])
            predicted = np.column_stack([np.diag(shot[f'prediction_{step.nodes}'][i]) for i in columns])
            if step.stage_record is not None:
                residual = normalize(predicted - observed, observed, tuple(step.stage_record['weights']), step.residual_floor)
                rebuilt = 0.5 * float(residual @ residual)
                lm.append(dict(trajectory=t.id, step=index, shot=key, saved=step.loss, rebuilt=rebuilt,
                               relative=abs(rebuilt - step.loss) / max(abs(step.loss), 1e-300)))
            else:
                rebuilt = spd_loss(predicted, observed)
                spd.append(dict(trajectory=t.id, step=index, shot=key, saved=step.loss, rebuilt=rebuilt,
                                relative=abs(rebuilt - step.loss) / max(abs(step.loss), 1e-300)))
    shots = {k: v for k, v in files.items() if k in manifest['shots']}
    discrepancy = np.array([v['paired_grid_discrepancy'] for v in shots.values()])
    worst_lm = max(lm, key=lambda r: r['relative'])
    summary = dict(
        shots=len(shots), truth=len(files) - len(shots),
        all_files_present=all(v['exists'] for v in files.values()),
        all_hashes_match=all(v['hash_ok'] for v in files.values()),
        all_from_one_collector=all(v['collector_ok'] for v in files.values()), collector_sha256=COLLECTOR,
        total_bytes=int(sum(v['bytes'] for v in files.values())),
        worst_forward_residual=max(v['forward_residual'] for v in files.values()),
        worst_reciprocal_residual=max(v['reciprocal_residual'] for v in files.values()),
        lm_losses_checked=len(lm), lm_losses_exact=sum(r['relative'] == 0 for r in lm),
        worst_lm_loss_relative=worst_lm['relative'], worst_lm_loss_row=worst_lm,
        spd_losses_compared=len(spd), spd_loss_relative_median=float(np.median([r['relative'] for r in spd])),
        spd_loss_relative_max=float(max(r['relative'] for r in spd)),
        resolution=dict(
            note='512 vs 1024 paired-prediction relative difference per shot and frequency (19 columns)',
            shots_all_frequencies_below_1e7=int(np.sum(np.all(discrepancy <= 1e-7, axis=1))),
            shots_any_frequency_above_1e7=int(np.sum(np.any(discrepancy > 1e-7, axis=1))),
            shots_any_frequency_above_1e5=int(np.sum(np.any(discrepancy > 1e-5, axis=1))),
            worst=float(discrepancy.max()),
            worst_shot=list(shots)[int(np.argmax(discrepancy.max(axis=1)))],
            per_shot={k: float(max(v['paired_grid_discrepancy'])) for k, v in shots.items()}),
        mean_seconds_per_shot=float(np.mean([v['seconds'] for v in shots.values()])))
    summary['passed'] = bool(summary['all_files_present'] and summary['all_hashes_match']
                             and summary['all_from_one_collector'] and summary['worst_lm_loss_relative'] <= 1e-12)
    sc.write(HERE / 'verification.json', dict(summary, lm_rows=lm, spd_rows=spd))
    print({k: v for k, v in summary.items() if k not in ('resolution', 'worst_lm_loss_row')})
    print({k: v for k, v in summary['resolution'].items() if k != 'per_shot'})


if __name__ == '__main__':
    main()
