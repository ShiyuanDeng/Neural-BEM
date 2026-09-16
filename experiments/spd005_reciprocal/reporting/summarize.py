"""Rebuild SPD-005 comparisons without dispatching numerical solves."""
import argparse
from collections import Counter
from pathlib import Path
from statistics import median
import numpy as np
from scipy.spatial import cKDTree
from experiments.spd005_reciprocal import run as r


def reconcile(work):
    assert work['total_attempted'] == sum(work['attempted'].values())
    counts = {}
    for prefix, key in (('', 'systems'), ('derivative_assemblies_', 'operator_directions'),
                        ('reciprocal_batches_', 'reciprocal_batches')):
        attempted = sum(work.get(prefix+'attempted', {}).values())
        completed = sum(work.get(prefix+'completed', {}).values())
        failed = sum(work.get(prefix+'failed', {}).values())
        assert attempted == completed+failed
        counts[key] = attempted
    assert work['budget_work_units'] == sum(counts.values())
    assert work['within_solve_cap']
    for part in work.get('parts', []):
        reconcile(part)
    return counts


def summarize(bundle):
    r.verify(bundle)
    times = r.read(bundle/'timings.json')
    complete = r.read(bundle/'execution_status.json')['status'] == 'COMPLETE' and len(times) == 18
    rows, states = [], {}
    for timing in times:
        arm, scene = timing['arm'], timing['scene']
        folder = bundle/arm/'runs'/scene
        result = r.read(folder/'result.json')
        assert result['sources_and_inputs_unchanged']
        metric = r.read(folder/'F/metrics.json')
        stages = [r.read(path) for path in sorted((folder/'F').glob('stage_*/terminal.json'))]
        performance = r.read(folder/'performance.json')
        topology = r.read(folder/'topology/terminal.json')
        counts = Counter()
        for work in (result['topology_work'], result['continuation']['work']):
            counts.update(reconcile(work))
        passive = Counter(topology['controller_work']['totals'])
        passive.update(performance['outer_work']['totals'])
        assert counts['reciprocal_batches'] == passive['reciprocal_frequency_solve_count']
        assert counts['operator_directions'] == passive['derivative_assembly_count']
        states[(arm, scene)] = r.previous.p.driver.deserialize_state(metric['final_state'])
        row = dict(arm=arm, scene=scene, seconds=timing['seconds'], recovered=result['fresh_recovery_pass'],
            skipped=timing['skipped'], topology_seconds=result['topology_work']['active_wall_seconds'],
            continuation_seconds=result['continuation']['work']['active_wall_seconds'],
            events=[e['kind'] for e in topology['events']], work=dict(counts), passive_work=dict(passive),
            stage_effort=[{key:s[key] for key in ('accepted_steps','stage_outcome','optimizer_stop',
                'effective_training_exposure','unresolved_columns','one_sided_columns','exposure')} for s in stages],
            final=metric['final'], kernel_counts=performance['kernel_counts'], kernel_seconds=performance['kernel_seconds'])
        rows.append(row)
    comparisons = []
    for rep in range(2):
        for scene in r.SCENES:
            control = states.get((f'operator_{rep}', scene))
            if control is None:
                continue
            for arm in ('reciprocal', 'combined'):
                test = states.get((f'{arm}_{rep}', scene))
                if test is None:
                    continue
                assert control.component_ids == test.component_ids
                coeff = float(np.max(np.abs(control.parameter_vector()-test.parameter_vector())))
                delta = max(max(cKDTree(a).query(b)[0].max(),cKDTree(b).query(a)[0].max())
                    for a,b in zip(r.previous.p.boundary_points(control), r.previous.p.boundary_points(test)))
                controls = [next(x for x in rows if x['arm'] == f'{name}_{rep}' and x['scene'] == scene)
                            for name in ('operator', arm)]
                comparisons.append(dict(scene=scene, repetition=rep, arm=arm,
                    coefficient_difference_m=coeff, boundary_difference_m=float(delta),
                    events_match=controls[0]['events'] == controls[1]['events'],
                    both_recovered=all(x['recovered'] for x in controls)))
    aggregates = []
    for scene in r.SCENES:
        selected = [x for x in rows if x['scene'] == scene]
        values = {arm:median(x['seconds'] for x in selected if x['arm'].startswith(arm+'_'))
                  for arm in r.ARMS if any(x['arm'].startswith(arm+'_') for x in selected)}
        if len(values) != 3:
            continue
        aggregates.append(dict(scene=scene, median_seconds=values,
            reciprocal_speedup=values['operator']/values['reciprocal'],
            combined_speedup=values['operator']/values['combined'],
            readiness_incremental_speedup=values['reciprocal']/values['combined']))
    report = dict(status='PASS' if complete and all(x['recovered'] for x in rows) else 'INCOMPLETE_OR_FAILURE',
        rows=rows, comparisons=comparisons, aggregate=aggregates,
        scope='two repeated full workers per arm on three noiseless scenes; qualified truth data reused',
        host_isolation='Host-wide isolation unverified; sequential own workers, one BLAS thread.',
        profiles_note='Kernel times overlap (base assembly, RHS, reciprocal traces); do not sum nested spans.')
    r.write(bundle/'summary.json', report)
    r.write(bundle/'verification.json', dict(status=report['status'], counts_reconciled=True,
        sources_inputs_unchanged=True, expected_workers=18, completed_workers=len(rows),
        final_quality_pass=all(x['recovered'] for x in rows),
        comparisons=comparisons))
    lines = ['# SPD-005 — reciprocal Kress in the full inverse', '',
             f"Status: **{report['status']}**. See [summary.json](summary.json) for raw quality, timing and work counts.", '',
             '| Scene | Operator | Reciprocal | Reciprocal + readiness | Reciprocal gain | Combined gain | Readiness increment |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for row in aggregates:
        v = row['median_seconds']
        lines.append(f"| {row['scene']} | {v['operator']:.3f} s | {v['reciprocal']:.3f} s | {v['combined']:.3f} s | "
                     f"{row['reciprocal_speedup']:.2f}x | {row['combined_speedup']:.2f}x | {row['readiness_incremental_speedup']:.2f}x |")
    lines.extend(['', 'Two workers per arm/scene are planned; table medians use completed workers only.',
        'Includes fresh topology search,',
        'candidate fits, continuation and endpoint scoring; excludes archived truth-data generation.',
        'All arms use identical original starts, observations and controller/feasibility settings.',
        'Only the combined arm applies the predeclared training-only readiness gate.', '',
        'The reciprocal runtime retains operator derivatives below 128 nodes. Thus these',
        '64-node topology fits are unchanged; the reciprocal gain occurs in continuation.',
        'All original constraints and the FD-compatible stencil policy remain in force.', '',
        'A separate [remaining-cost profile](remaining_cost_profile/summary.json) diagnoses one',
        'continuation stage after all timed workers. Profiler times are excluded from this table.',
        'See the [iteration 05 closeout](../../../../docs/iterations/speedup/iteration_05/01_results.md)',
        'for the guarded qualification, endpoint comparison and next priority.', '',
        'Own workers ran sequentially with one BLAS thread. Host-wide process isolation was',
        'not established. These are three noiseless scenes, not an all-scene or noise qualification.', '',
        'The [manifest](manifest.json), measured_sources, qualification snapshots and per-arm',
        'input manifests preserve the actual source/configuration provenance. The [verification](verification.json)',
        'reconciles physical systems, operator directions and reciprocal RHS batches separately.',
        'Kernel profiling spans may overlap; use phase wall times for additive comparisons.', '',
        'Rebuild with `PYTHONPATH=solvers:. python -m experiments.spd005_reciprocal.reporting.summarize BUNDLE`.'])
    (bundle/'README.md').write_text('\n'.join(lines)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('bundle', type=Path)
    args = parser.parse_args()
    print(summarize(args.bundle.resolve())['status'])
