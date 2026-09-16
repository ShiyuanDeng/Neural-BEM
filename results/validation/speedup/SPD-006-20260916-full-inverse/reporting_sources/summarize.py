"""Read-only numerical-evidence aggregation; no inverse dispatch."""
import argparse
from collections import Counter
from pathlib import Path
from statistics import median
import numpy as np
from scipy.spatial import cKDTree
from experiments.spd006_compiled import run as r


def reconcile(work):
    assert work['total_attempted'] == sum(work['attempted'].values())
    counts = {}
    for prefix, name in (('', 'physical_systems'), ('derivative_assemblies_', 'operator_directions'),
                         ('reciprocal_batches_', 'reciprocal_batches'), ('compiled_batches_', 'compiled_batches')):
        attempted = sum(work.get(prefix+'attempted', {}).values())
        assert attempted == sum(work.get(prefix+'completed', {}).values())+sum(work.get(prefix+'failed', {}).values())
        counts[name] = attempted
    assert work['budget_work_units'] == sum(counts.values())
    assert work['within_solve_cap']
    for event in ('attempted', 'completed', 'failed'):
        if 'compiled_per_frequency_'+event in work:
            assert sum(work['compiled_per_frequency_'+event].values()) == sum(work.get('compiled_batches_'+event, {}).values())
    for part in work.get('parts', []): reconcile(part)
    return counts


def summarize(bundle):
    r.verify(bundle)
    timings = r.read(bundle/'timings.json')
    rows, states, by_key = [], {}, {}
    for timing in timings:
        label, scene = timing['arm'], timing['scene']
        folder = bundle/label/'runs'/scene
        if not (folder/'F/metrics.json').exists():
            rows.append(dict(**timing, incomplete=True)); continue
        result = r.read(folder/'result.json')
        assert result['sources_and_inputs_unchanged']
        metrics = r.read(folder/'F/metrics.json')
        topology = r.read(folder/'topology/terminal.json')
        performance = r.read(folder/'performance.json')
        stages = [r.read(p) for p in sorted((folder/'F').glob('stage_*/terminal.json'))]
        counts = Counter()
        for work in (result['topology_work'], result['continuation']['work']): counts.update(reconcile(work))
        passive = Counter(topology['controller_work']['totals']); passive.update(performance['outer_work']['totals'])
        for name, key in (('compiled_batches','compiled_frequency_batch_count'),
                          ('reciprocal_batches','reciprocal_frequency_solve_count'),
                          ('operator_directions','derivative_assembly_count')):
            assert counts[name] == passive[key], (label, scene, name, counts[name], passive[key])
        # Passive forward counts record completed inverse calls. The budget also
        # records refused/failed calls and direct readiness/endpoint predictions,
        # which bypass the inverse objective's passive forward counter.
        works = (result['topology_work'], result['continuation']['work'])
        physical_completed = sum(sum(w['completed'].values()) for w in works)
        physical_failed = sum(sum(w['failed'].values()) for w in works)
        direct_validation = sum(w['completed'].get(k, 0) for w in works for k in ('readiness', 'endpoint'))
        assert counts['physical_systems'] == physical_completed + physical_failed
        assert physical_completed == passive['bie_frequency_solve_count'] + direct_validation, (label, scene)
        states[label, scene] = r.previous.p.driver.deserialize_state(metrics['final_state'])
        diagnostics = [r.read(p) for p in sorted((folder/'F').glob('stage_*/compiled_backend.json'))]
        fallback = Counter(); angular = []
        for diagnostic in diagnostics:
            fallback.update({k:v for k,v in diagnostic['counts'].items() if k.startswith('fallback:')})
            for event in diagnostic['events']: angular.extend(event.get('angular_checks', []))
        row = dict(arm=label, scene=scene, seconds=timing['seconds'], recovered=result['fresh_recovery_pass'],
            status=result['status'], skipped=timing['skipped'], final=metrics.get('final'),
            topology_seconds=result['topology_work']['active_wall_seconds'],
            continuation_seconds=result['continuation']['work']['active_wall_seconds'],
            events=[event['kind'] for event in topology['events']], work=dict(counts), passive_work=dict(passive),
            physical_completed=physical_completed, physical_failed_or_refused=physical_failed,
            direct_validation_completed=direct_validation,
            stage_effort=[{k:s[k] for k in ('accepted_steps','stage_outcome','optimizer_stop','effective_training_exposure',
                'unresolved_columns','one_sided_columns','exposure')} for s in stages],
            compiled_fallbacks=dict(fallback), compiled_angular_checks=angular,
            kernel_counts=performance['kernel_counts'], kernel_seconds=performance['kernel_seconds'])
        rows.append(row); by_key[label, scene] = row
    comparisons = []
    for rep in range(2):
        for scene in r.SCENES:
            keys = [(f'{arm}_{rep}', scene) for arm in r.ARMS]
            if not all(key in states for key in keys): continue
            control, test = [states[k] for k in keys]; baseline, candidate = [by_key[k] for k in keys]
            same_components = control.component_ids == test.component_ids
            coeff = boundary = None
            if same_components:
                coeff = float(np.max(abs(control.parameter_vector()-test.parameter_vector())))
                boundary = float(max(max(cKDTree(a).query(b)[0].max(),cKDTree(b).query(a)[0].max())
                    for a,b in zip(r.previous.p.boundary_points(control),r.previous.p.boundary_points(test))))
            comparisons.append(dict(scene=scene, repetition=rep, same_components=same_components,
                coefficient_difference_m=coeff, boundary_difference_m=boundary,
                events_match=baseline['events']==candidate['events'],
                recovery_preserved=not baseline['recovered'] or candidate['recovered'],
                both_recovered=baseline['recovered'] and candidate['recovered'],
                speedup=baseline['seconds']/candidate['seconds'],
                accepted_steps_reference=[s['accepted_steps'] for s in baseline['stage_effort']],
                accepted_steps_compiled=[s['accepted_steps'] for s in candidate['stage_effort']]))
    aggregates = []
    for scene in r.SCENES:
        values = {arm: [x['seconds'] for x in rows if not x.get('incomplete') and x['scene']==scene
                       and x['arm'].startswith(arm+'_')] for arm in r.ARMS}
        if not all(values.values()): continue
        medians = {arm:median(v) for arm,v in values.items()}
        aggregates.append(dict(scene=scene, median_seconds=medians,
            repeats={k:len(v) for k,v in values.items()}, speedup=medians['reciprocal']/medians['compiled']))
    complete = (r.read(bundle/'execution_status.json')['status']=='COMPLETE' and len(rows)==16
                and len(comparisons)==8 and not any(row.get('incomplete') for row in rows)
                and all(t['returncode']==0 for t in timings))
    preserved = all(c['events_match'] and c['recovery_preserved'] for c in comparisons)
    numerically_qualified = all(row.get('final', {}).get('numerically_qualified', False) for row in rows)
    status = 'COMPLETE_QUALITY_PRESERVED' if complete and preserved and numerically_qualified else 'INCOMPLETE_OR_REGRESSION'
    result = dict(status=status, rows=rows, comparisons=comparisons, aggregate=aggregates,
        campaign=r.read(bundle/'execution_status.json'),
        scope='Fresh full workers, two arms with identical readiness, two repeats on four scenes; original inputs and gates.',
        cost_scope='Includes startup/topology/candidate fits/continuation/readiness/endpoints; excludes archived truth generation and videos.',
        work_unit_note='physical_systems means budget attempts, including refusals/failures; physical_completed reports completed systems. Other categories are separately charged batches/directions, not equal-cost systems.',
        geometry_note='One-component fits use reciprocal Kress; coarse topology and all independent endpoint/refined checks use full Kress.',
        host_isolation='Sequential own workers, one BLAS thread; host-wide isolation unverified.')
    r.write(bundle/'summary.json',result)
    r.write(bundle/'verification.json',dict(status=status, counts_reconciled=True, sources_inputs_unchanged=True,
        expected_workers=16, completed_workers=len(rows), paired_comparisons=len(comparisons),
        original_recovery_preserved=preserved, final_numerical_checks_pass=numerically_qualified))
    lines = ['# SPD-006 — compiled Kress continuation in full inverse workers', '',
        f'Status: **{status}**. Raw evidence: [summary.json](summary.json).', '',
        '| Scene | Reciprocal + readiness | Compiled + readiness | Ratio |', '|---|---:|---:|---:|']
    for row in aggregates:
        v=row['median_seconds']; lines.append(f"| {row['scene']} | {v['reciprocal']:.3f} s | {v['compiled']:.3f} s | {row['speedup']:.3f}x |")
    lines += ['', 'Medians use completed workers; repeat counts are in summary.json. Failed recovery outcomes are retained.',
        'Ratios are measured full-worker wall times. They are not estimates for all twelve topology scenes.',
        'Both arms use the original data, Cartesian gauge, controller, feasibility rules and training-only readiness.',
        'Compiled frequency batches, local factorizations and reduced solves are distinct from full physical systems.',
        'Physical budget attempts include failures/refusals. Completed physical systems reconcile with passive inverse counts plus direct readiness/endpoint predictions.',
        'Source and input snapshots are in manifest.json and measured_sources. Qualification and regression evidence are included.', '']
    profile_path = bundle/'remaining_cost_profile/summary.json'
    if profile_path.exists():
        profile = r.read(profile_path)
        assert profile['matches_archived_first_update']
        stencil = next(x for x in profile['functions'] if x['function']=='allowed')
        share = 100*stencil['cumulative_seconds']/profile['seconds_with_profiler']
        lines += ['## Remaining cost', '',
            f"One compiled central-case update took {profile['seconds_with_profiler']:.2f} s under CPU profiling; legacy stencil feasibility used {share:.1f}%.",
            'It reproduced the archived first accepted state exactly. Nested profile times must not be added.',
            'This is one update, not a whole-inverse percentage. See [profile.txt](remaining_cost_profile/profile.txt) and [profile summary](remaining_cost_profile/summary.json).', '',
            'The compiled runtime selects the numerical backend; the benchmark wrapper separately enables readiness.',
            'A file-only monitor read logs every 55 seconds during sequential workers. Host-wide isolation is unverified.',
            'The summary/profiling sources are archived separately from the frozen numerical sources.', '']
    (bundle/'README.md').write_text('\n'.join(lines))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--bundle',type=Path,required=True)
    summarize(parser.parse_args().bundle.resolve())
