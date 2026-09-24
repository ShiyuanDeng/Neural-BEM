"""Rebuild SC-030 tables, verification and plots from saved artifacts; no solves.

Run with EMNerf Python. Deliberately outside frozen numerical sources: reporting
does not alter the measured experiment. Requires all 36 attempted workers.
"""
import csv
import hashlib
import json
from pathlib import Path
from statistics import median

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CASES = ('wrong_circle', 'circle_to_star', 'circle_to_c', 'kite', 'peanut', 'hook')
LABELS = ('Circle', 'Star', 'C', 'Kite', 'Peanut', 'Hook')
ARMS = ('spd008', 'hybrid_reference', 'hybrid_cache')
NAMES = ('SPD-008', 'Hybrid, cache off', 'Hybrid, cache on')


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(value):
    return 'unavailable' if value is None else f'{value:.6f}'


def coeff(record):
    return np.asarray(record['real'])+1j*np.asarray(record['imag'])


def points(record, count=8192, scale=50.):
    c = coeff(record)
    k = len(c)//2
    spectrum = np.zeros(count, complex)
    spectrum[np.arange(-k, k+1) % count] = c
    return scale*np.fft.ifft(spectrum)*count


def audit_starts():
    rows, count = [], 4096
    theta = 2*np.pi*np.arange(count)/count
    for case in CASES:
        folder = HERE/'runs/repeat_0'/case
        frame = json.loads((folder/'spd008/stage_1/trajectory.jsonl').read_text().splitlines()[0])
        assert frame['iteration'] == 0 and len(frame['state']) == 1
        raw = frame['state'][0]
        k, v = raw['maximum_mode'], np.asarray(raw['parameters'])
        cut = 2*(k+1)
        cosine = v[:cut].reshape(-1, 2)
        sine = np.vstack((np.zeros(2), v[cut:].reshape(-1, 2)))
        native = np.cos(theta[:, None]*np.arange(k+1))@cosine + np.sin(theta[:, None]*np.arange(k+1))@sine
        for arm in ARMS[1:]:
            initial = read(folder/arm/'stage_1_history.json')['history'][0]
            assert initial['iteration'] == 0
            curve = points(initial['coefficients'], count, scale=.05) + (.5+.5j)
            delta = float(np.max(np.abs(curve-(native[:, 0]+1j*native[:, 1]))))
            loss_delta = abs(initial['loss']-frame['loss'])
            rows.append(dict(case=case, arm=arm, maximum_actual_start_difference_m=delta,
                initial_loss_difference=loss_delta, passed=delta <= 1e-14 and loss_delta <= 1e-14))
    result = dict(evaluation_only=True, physical_solves=0, nodes=count,
        uses_actual_saved_iteration_zero_states=True, rows=rows, passed=all(r['passed'] for r in rows))
    write(HERE/'actual_start_audit.json', result)
    return result


def build():
    campaign = read(HERE/'campaign.json')
    expected_workers = {(case, arm, repeat) for case in CASES for arm in ARMS for repeat in range(2)}
    actual_workers = [(r['case'], r['arm'], r['repeat']) for r in campaign['workers']]
    process_seconds = {(r['case'], r['arm'], r['repeat']): r['elapsed_seconds'] for r in campaign['workers']}
    assert campaign['status'] == 'DISPATCH_COMPLETE'
    assert len(actual_workers) == 36 and set(actual_workers) == expected_workers
    assert all(r['exit_code'] == 0 for r in campaign['workers'])
    assert campaign['elapsed_seconds'] <= 12*3600
    manifest = read(HERE/'manifest.json')
    changed = [name for name, digest in manifest['source_sha256'].items() if sha(ROOT/name) != digest]
    changed_inputs = [name for name, digest in manifest['input_sha256'].items() if sha(ROOT/name) != digest]
    assert not changed and not changed_inputs, (changed, changed_inputs)
    assert all(sha(HERE/'sources'/name) == digest for name, digest in manifest['source_sha256'].items())
    assert sha(HERE/'approved_plan.md') == manifest['plan_sha256']
    assert sha(ROOT/'docs/iterations/shape_frequency_continuation/iteration_12/03_plan.md') == manifest['plan_sha256']
    baseline = read(ROOT/'results/validation/speedup/SPD-008-20260917-geometry/campaign/manifest.json')
    baseline_drift = [name for name, digest in baseline['source_sha256'].items() if sha(ROOT/name) != digest]
    assert not baseline_drift, baseline_drift
    inherited = read(HERE/'inherited_configuration_audit.json')
    assert all(sha(ROOT/name) == digest for name, digest in inherited['input_sha256'].items())
    start_audit = audit_starts()
    assert start_audit['passed']
    results = {}
    rows, work_rows, cache_rows, stage_rows, missing = [], [], [], [], []
    for case in CASES:
        for arm in ARMS:
            for repeat in range(2):
                folder = HERE/'runs'/f'repeat_{repeat}'/case/arm
                if not (folder/'result.json').exists():
                    missing.append(str(folder.relative_to(HERE)))
                    continue
                r = read(folder/'result.json')
                config = read(folder/'configuration.json')
                assert (r['case'], r['arm'], r['repeat']) == (case, arm, repeat)
                for endpoint in ('start', 'end'):
                    env = read(folder/f'environment_{endpoint}.json')
                    assert all(env['threads'][key] == '1' for key in
                               ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'))
                    assert all(env[key] == manifest['environment'][key] for key in
                               ('python', 'numpy', 'scipy', 'platform', 'cpu', 'affinity'))
                assert all(c['peak_bytes'] <= c['max_bytes'] for c in r['cache'])
                if arm == 'spd008':
                    assert config['nodes'] == [512, 1024]
                    assert (config['maximum_mode'], config['reduced_directions']) == (17, 33)
                    assert config['minimum_component_radius_m'] == .008
                    assert config['runtime']['profile'] == 'compiled' and config['kernels'] == 'real_bessel'
                    assert config['geometry_validation'] == 'certified'
                    assert config['optimizer']['max_iterations'] == 22
                else:
                    assert config['geometry_validation'] == ('cache' if arm == 'hybrid_cache' else 'reference')
                    assert config['update']['projection_tolerance'] == 1e-5
                    assert config['backend']['step_control'] == 'coefficient'
                    for n, stage in enumerate(config['stages']):
                        assert (stage['nodes'], stage['refined_nodes'], stage['curve_modes']) == (512, 1024, 192)
                        assert stage['update_modes'] == (3, 5, 7, 9)[n]
                        assert stage['iterations'] == 22
                        assert stage['quota'] == (1000, 1250, 1750, 4000)[n]
                results[case, arm, repeat] = r
                assert r['work_units'] <= 8012 and r['inverse_seconds'] <= 3600
                identity = dict(case=case, arm=arm, repeat=repeat)
                work = r['work']
                if arm == 'spd008':
                    systems = dict(work['attempted'])
                    reciprocal = sum(work['reciprocal_batches_attempted'].values())
                    other = sum(work['derivative_assemblies_attempted'].values()) + sum(work['compiled_batches_attempted'].values())
                else:
                    systems = {}
                    for name, count in work['solves'].items():
                        category = name.split(':', 1)[1]
                        systems[category] = systems.get(category, 0) + count
                    reciprocal = sum(work['reciprocal_batches'].values())
                    other = 0
                assert sum(systems.values()) + reciprocal + other == r['work_units']
                work_rows.append(dict(**identity, initial_objective=systems.get('initial_objective', 0),
                    derivative_systems=systems.get('derivative', 0), candidate_systems=systems.get('candidate', 0),
                    acceptance_systems=systems.get('acceptance_validation', 0),
                    reciprocal_batches=reciprocal, other_units=other, total_units=r['work_units']))
                for stage in r['stages']:
                    stage_rows.append(dict(**identity, stage=stage['stage'], outcome=stage['outcome'],
                        stop=stage['stop'], accepted_steps=stage['accepted'], work_units=stage['units'],
                        final_loss=stage['final_loss']))
                cache_rows.append(dict(**identity,
                    shared_requests=sum(c['counts'].get('self_intersection.requests', 0) for c in r['cache']),
                    shared_hits=sum(c['counts'].get('self_intersection.hits', 0) for c in r['cache']),
                    hybrid_requests=sum(c['counts'].get('hybrid_self_intersection.requests', 0) for c in r['cache']),
                    hybrid_hits=sum(c['counts'].get('hybrid_self_intersection.hits', 0) for c in r['cache']),
                    shared_seconds=sum(c['seconds'].get('self_intersection', 0.) for c in r['cache']),
                    hybrid_seconds=sum(c['seconds'].get('hybrid_self_intersection', 0.) for c in r['cache']),
                    peak_bytes=max((c['peak_bytes'] for c in r['cache']), default=0)))
                s = r.get('score', {})
                residuals = s.get('catalog_relative_residual', [None]*19)
                rows.append(dict(case=case, arm=arm, repeat=repeat, status=r['status'], reason=r['reason'],
                    rms_mm=s.get('symmetric_rms_mm'), hausdorff_upper_mm=s.get('hausdorff_upper_mm'),
                    tightest_radius_mm=s.get('tightest_radius_mm'),
                    training_numerically_qualified=s.get('training_numerically_qualified'),
                    residual_125=residuals[8], residual_250=residuals[18],
                    work_units=r['work_units'], inverse_seconds=r['inverse_seconds'],
                    setup_seconds=r['setup_and_inverse_seconds']-r['inverse_seconds'],
                    evaluation_seconds=r['evaluation_seconds'], worker_seconds=r['worker_seconds'],
                    process_wall_seconds=process_seconds[case, arm, repeat],
                    completed_stages=sum(s['outcome'] in ('NORMAL_OPTIMIZER_RETURN', 'STAGE_QUOTA_REACHED')
                                         for s in r['stages']),
                    accepted_steps=sum(s['accepted'] for s in r['stages']),
                    cache_hits=sum(sum(v for k, v in c['counts'].items() if k.endswith('.hits')) for c in r['cache']),
                    cache_peak_bytes=max((c['peak_bytes'] for c in r['cache']), default=0),
                    trajectory_digest=r['trajectory_digest']))
    if rows:
        with (HERE/'case_results.csv').open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    assert not missing, 'Incomplete worker artifacts: '+repr(missing)
    assert len(rows) == 36
    for name, records in [('work_categories.csv', work_rows), ('stage_results.csv', stage_rows),
                          ('cache_results.csv', cache_rows)]:
        with (HERE/name).open('w') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(records)
    cache_pairs, repeats, replay, numerical = [], [], [], []
    aggregates = []
    for case in CASES:
        for repeat in range(2):
            a, b = (results[case, arm, repeat] for arm in ARMS[1:])
            cache_pairs.append(dict(case=case, repeat=repeat,
                exact=a['trajectory_digest'] == b['trajectory_digest'],
                score_exact=a.get('score') == b.get('score'),
                speedup=a['inverse_seconds']/b['inverse_seconds']))
            legacy = read(HERE.parent/'SC-029-atlas-strategies/runs/baseline'/case/'none/result.json')
            for arm in ARMS[1:]:
                r = results[case, arm, repeat]
                replay.append(dict(case=case, repeat=repeat, arm=arm,
                    endpoint_exact=bool(np.array_equal(coeff(r['final_curve']), coeff(legacy['final_curve']))),
                    work_equal=r['work_units'] == legacy['work']['work_units']))
        for arm in ARMS:
            pair = [results[case, arm, n] for n in range(2)]
            repeats.append(dict(case=case, arm=arm,
                exact=pair[0]['trajectory_digest'] == pair[1]['trajectory_digest'],
                score_exact=pair[0].get('score') == pair[1].get('score')))
            times = [r['inverse_seconds'] for r in pair]
            aggregates.append(dict(case=case, arm=arm,
                statuses=[r['status'] for r in pair], reasons=[r['reason'] for r in pair],
                rms_mm=[r.get('score', {}).get('symmetric_rms_mm') for r in pair],
                hausdorff_upper_mm=[r.get('score', {}).get('hausdorff_upper_mm') for r in pair],
                work_units=[r['work_units'] for r in pair], inverse_median_seconds=median(times),
                inverse_min_seconds=min(times), inverse_max_seconds=max(times)))
            for repeat in range(2):
                folder = HERE/'runs'/f'repeat_{repeat}'/case/arm
                if arm == 'spd008':
                    checks = [r for path in folder.glob('stage_*/acceptance.json') for r in read(path)]
                else:
                    checks = [r for path in folder.glob('stage_*_history.json') for r in read(path)['acceptance_checks']]
                accepted = [r for r in checks if r['accepted']]
                numerical.append(dict(case=case, arm=arm, repeat=repeat, accepted_checks=len(accepted),
                    max_prediction_discrepancy=max((max(r['prediction_discrepancy']) for r in accepted), default=0.),
                    all_within_tolerance=all(np.all(np.array(r['prediction_discrepancy']) <=
                        np.array([1e-5]+[1e-7]*(len(r['prediction_discrepancy'])-1))) for r in accepted)))
    verification = dict(source_and_input_hashes_unchanged=True,
        source_archive_and_frozen_plan_match=True, single_thread_settings_recorded=True,
        hardware_software_and_affinity_consistent=True, cache_memory_bound_respected=True,
        all_36_workers_finished=True, campaign_and_run_caps_respected=True, work_categories_reconcile=True,
        inherited_settings_match_committed_version=True, all_run_configurations_match_contract=True,
        actual_start_max_difference_m=max(r['maximum_actual_start_difference_m'] for r in start_audit['rows']),
        initial_loss_max_difference=max(r['initial_loss_difference'] for r in start_audit['rows']),
        original_spd008_source_count=len(baseline['source_sha256']), original_spd008_changed_sources=baseline_drift,
        cache_pairs=cache_pairs,
        repetition_agreement=repeats, sc029_replay=replay, numerical_checks=numerical,
        all_cache_pairs_exact=all(r['exact'] for r in cache_pairs),
        all_repetitions_exact=all(r['exact'] for r in repeats),
        paired_endpoint_scores_exact=all(r['score_exact'] for r in cache_pairs + repeats),
        all_hybrid_endpoints_replay=all(r['endpoint_exact'] and r['work_equal'] for r in replay),
        all_accepted_steps_qualified=all(r['all_within_tolerance'] for r in numerical),
        evaluation_errors=[dict(case=r['case'], arm=r['arm'], repeat=r['repeat'], error=r['evaluation_error'])
                           for r in results.values() if 'evaluation_error' in r],
        all_endpoint_scoring_completed=all(r.get('score', {}).get('evaluation_field_solves') == 27
                                         and 'evaluation_error' not in r for r in results.values()))
    write(HERE/'verification.json', verification)
    reductions = []
    for case in CASES:
        a, b = [next(r for r in aggregates if r['case'] == case and r['arm'] == arm) for arm in ARMS[1:]]
        reductions.append(dict(case=case,
            time_reduction_percent=100*(1-b['inverse_median_seconds']/a['inverse_median_seconds']),
            speedup=a['inverse_median_seconds']/b['inverse_median_seconds']))
    off, on = [sum(r['inverse_seconds'] for r in rows if r['arm'] == arm) for arm in ARMS[1:]]
    write(HERE/'summary.json', dict(aggregates=aggregates, verification=verification,
        cache_reductions=reductions, hybrid_cache_off_total_seconds=off, hybrid_cache_on_total_seconds=on,
        hybrid_total_time_reduction_percent=100*(1-on/off), campaign_wall_seconds=campaign['elapsed_seconds'],
        completed_schedules=sum(r['status'] == 'COMPLETED_SCHEDULE' for r in rows),
        total_inverse_work_units=sum(r['work_units'] for r in rows),
        total_inverse_seconds=sum(r['inverse_seconds'] for r in rows),
        total_evaluation_field_solves=sum(r.get('score', {}).get('evaluation_field_solves', 0) for r in results.values()),
        total_evaluation_seconds=sum(r['evaluation_seconds'] for r in rows)))
    lines = ['| Case | Arm | Status / reason | RMS mm | Hausdorff upper mm | Work units | Inverse seconds, median [range] |',
             '|---|---|---|---:|---:|---:|---:|']
    for a in aggregates:
        status = a['statuses'][0] if a['statuses'][0] == 'COMPLETED_SCHEDULE' else str(a['reasons'][0])
        rms, haus = a['rms_mm'][0], a['hausdorff_upper_mm'][0]
        lines.append(f"| {LABELS[CASES.index(a['case'])]} | {NAMES[ARMS.index(a['arm'])]} | {status} | "
            f"{fmt(rms)} | {fmt(haus)} | {a['work_units'][0]} | {a['inverse_median_seconds']:.2f} "
            f"[{a['inverse_min_seconds']:.2f}, {a['inverse_max_seconds']:.2f}] |")
    (HERE/'comparison_table.md').write_text('\n'.join(lines)+'\n')
    plots(results, aggregates)
    print(json.dumps({k: v for k, v in verification.items() if isinstance(v, bool)}, indent=2))


def first_pass():
    """A clearly labeled checkpoint before the second timing repetition."""
    rows, cache_pairs = [], []
    lines = ['# SC-030 first pass (one run per arm; repetition pending)', '',
        'These are preliminary single-run timings, not the final repeated comparison.', '',
        '| Case | Arm | Schedule status / reason | RMS mm | Work units | Inverse seconds |',
        '|---|---|---|---:|---:|---:|']
    for case, label in zip(CASES, LABELS):
        group = {}
        for arm, name in zip(ARMS, NAMES):
            r = read(HERE/'runs/repeat_0'/case/arm/'result.json')
            group[arm] = r
            row = dict(case=case, arm=arm, status=r['status'], reason=r['reason'],
                rms_mm=r.get('score', {}).get('symmetric_rms_mm'), work_units=r['work_units'],
                inverse_seconds=r['inverse_seconds'])
            rows.append(row)
            status = r['reason'] or r['status']
            lines.append(f"| {label} | {name} | {status} | {fmt(row['rms_mm'])} | "
                         f"{row['work_units']} | {row['inverse_seconds']:.1f} |")
        a, b = (group[arm] for arm in ARMS[1:])
        cache_pairs.append(dict(case=case, exact=a['trajectory_digest'] == b['trajectory_digest'],
            time_reduction_percent=100*(1-b['inverse_seconds']/a['inverse_seconds'])))
    write(HERE/'first_pass.json', dict(repetitions=1, final=False, rows=rows, cache_pairs=cache_pairs))
    lines += ['', 'Completing the four-stage schedule is not a recovery certificate. Errors and',
              'stop reasons remain separate. Both methods use the common wrong circle, data,',
              '512/1024 nodes and budgets, with the native algorithm differences documented',
              'in [the implementation review](implementation_review.md).', '',
              'All cache pairs exact: **'+str(all(r['exact'] for r in cache_pairs))+'**.']
    (HERE/'first_pass.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(cache_pairs, indent=2))


def plots(results, aggregates, timing_repetitions=2):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    colors = {'spd008':'#b85c1a', 'hybrid_reference':'#919ca4', 'hybrid_cache':'#007e73'}
    fig, axes = plt.subplots(2, 3, figsize=(12, 8), constrained_layout=True)
    for ax, case, label in zip(axes.flat, CASES, LABELS):
        source = 'SC-022-atlas-survey' if case in CASES[:3] else 'SC-025-band-policies'
        z = points(read(HERE.parent/source/'inputs'/case/'truth.json'))
        ax.plot(z.real, z.imag, color='#252525', lw=2, label='Truth')
        for arm in ('spd008', 'hybrid_cache'):
            r = results[case, arm, 0]
            z = points(r['final_curve'])
            complete = r['status'] == 'COMPLETED_SCHEDULE'
            ax.plot(z.real, z.imag, color=colors[arm], lw=1.6, ls='-' if complete else '--',
                label=NAMES[ARMS.index(arm)]+(' (stopped)' if not complete else ''))
        ax.set_title(label)
        ax.set_aspect('equal'); ax.grid(alpha=.15)
        ax.set_xlabel('x − 0.5 m [mm]'); ax.set_ylabel('y − 0.5 m [mm]')
    fig.legend(handles=[
        Line2D([], [], color='#252525', lw=2, label='Truth'),
        Line2D([], [], color=colors['spd008'], label='SPD-008: completed schedule'),
        Line2D([], [], color=colors['spd008'], ls='--', label='SPD-008: hard stop'),
        Line2D([], [], color=colors['hybrid_cache'], label='Hybrid, cache on')],
        loc='outside lower center', ncol=4, fontsize=9)
    fig.suptitle('SC-030: fixed-topology reconstructions, 512/1024 nodes\n'
                 'First repetition; common wrong-circle start; final retained states')
    fig.savefig(HERE/'boundaries.png', dpi=160)
    fig.savefig(HERE/'boundaries.pdf')
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), constrained_layout=True)
    x = np.arange(len(CASES)); width = .24
    for j, arm in enumerate(ARMS):
        group = [next(a for a in aggregates if a['case'] == case and a['arm'] == arm) for case in CASES]
        times = np.array([a['inverse_median_seconds'] for a in group])
        ranges = np.array([[a['inverse_min_seconds'] for a in group], [a['inverse_max_seconds'] for a in group]])
        bars = axes[0].bar(x+(j-1)*width, times, width, color=colors[arm], label=NAMES[j],
                    yerr=np.array([times-ranges[0], ranges[1]-times]), capsize=3)
        error_bars = axes[1].bar(x+(j-1)*width,
            [a['rms_mm'][0] if a['rms_mm'][0] is not None else np.nan for a in group], width, color=colors[arm])
        for timing_bar, error_bar, row in zip(bars, error_bars, group):
            if any(status != 'COMPLETED_SCHEDULE' for status in row['statuses']):
                for bar in (timing_bar, error_bar):
                    bar.set_hatch('///'); bar.set_edgecolor('#333333')
    axes[0].set_ylabel('Inverse time [seconds]')
    axes[0].legend(handles=[Patch(facecolor=colors[arm], label=name) for arm, name in zip(ARMS, NAMES)]
                   + [Patch(facecolor='white', edgecolor='#333333', hatch='///', label='Hard stop')], fontsize=9)
    axes[1].set_ylabel('Symmetric boundary RMS [mm]'); axes[1].set_yscale('log')
    positive = [a['rms_mm'][0] for a in aggregates if a['rms_mm'][0] is not None and a['rms_mm'][0] > 0]
    if positive:
        axes[1].set_ylim(10**np.floor(np.log10(min(positive))), 10**np.ceil(np.log10(max(positive))))
    for ax in axes:
        ax.set_xticks(x); ax.set_xticklabels(LABELS); ax.grid(axis='y', alpha=.2)
    timing_label = ('median and range of two sequential runs' if timing_repetitions == 2
                    else 'first repetition only')
    fig.suptitle('SC-030: cost and geometric error\nTimings: '+timing_label+'; hatched bars denote hard stops')
    fig.savefig(HERE/'cost_quality.png', dpi=160)
    fig.savefig(HERE/'cost_quality.pdf')
    plt.close(fig)


if __name__ == '__main__':
    import sys
    first_pass() if '--first-pass' in sys.argv else build()
