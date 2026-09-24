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


def points(record, count=8192):
    c = coeff(record)
    k = len(c)//2
    spectrum = np.zeros(count, complex)
    spectrum[np.arange(-k, k+1) % count] = c
    return 50*np.fft.ifft(spectrum)*count


def build():
    manifest = read(HERE/'manifest.json')
    changed = [name for name, digest in manifest['source_sha256'].items() if sha(ROOT/name) != digest]
    changed_inputs = [name for name, digest in manifest['input_sha256'].items() if sha(ROOT/name) != digest]
    assert not changed and not changed_inputs, (changed, changed_inputs)
    baseline = read(ROOT/'results/validation/speedup/SPD-008-20260917-geometry/campaign/manifest.json')
    baseline_drift = [name for name, digest in baseline['source_sha256'].items() if sha(ROOT/name) != digest]
    inherited = read(HERE/'inherited_configuration_audit.json')
    assert all(sha(ROOT/name) == digest for name, digest in inherited['input_sha256'].items())
    results = {}
    rows, missing = [], []
    for case in CASES:
        for arm in ARMS:
            for repeat in range(2):
                folder = HERE/'runs'/f'repeat_{repeat}'/case/arm
                if not (folder/'result.json').exists():
                    missing.append(str(folder.relative_to(HERE)))
                    continue
                r = read(folder/'result.json')
                config = read(folder/'configuration.json')
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
                s = r.get('score', {})
                residuals = s.get('catalog_relative_residual', [None]*19)
                rows.append(dict(case=case, arm=arm, repeat=repeat, status=r['status'], reason=r['reason'],
                    rms_mm=s.get('symmetric_rms_mm'), hausdorff_upper_mm=s.get('hausdorff_upper_mm'),
                    tightest_radius_mm=s.get('tightest_radius_mm'),
                    training_numerically_qualified=s.get('training_numerically_qualified'),
                    residual_125=residuals[8], residual_250=residuals[18],
                    work_units=r['work_units'], inverse_seconds=r['inverse_seconds'],
                    evaluation_seconds=r['evaluation_seconds'], worker_seconds=r['worker_seconds'],
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
    cache_pairs, repeats, replay, numerical = [], [], [], []
    aggregates = []
    for case in CASES:
        for repeat in range(2):
            a, b = (results[case, arm, repeat] for arm in ARMS[1:])
            cache_pairs.append(dict(case=case, repeat=repeat,
                exact=a['trajectory_digest'] == b['trajectory_digest'],
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
                exact=pair[0]['trajectory_digest'] == pair[1]['trajectory_digest']))
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
        inherited_settings_match_committed_version=True, all_run_configurations_match_contract=True,
        original_spd008_source_count=len(baseline['source_sha256']), original_spd008_changed_sources=baseline_drift,
        cache_pairs=cache_pairs,
        repetition_agreement=repeats, sc029_replay=replay, numerical_checks=numerical,
        all_cache_pairs_exact=all(r['exact'] for r in cache_pairs),
        all_repetitions_exact=all(r['exact'] for r in repeats),
        all_hybrid_endpoints_replay=all(r['endpoint_exact'] and r['work_equal'] for r in replay),
        all_accepted_steps_qualified=all(r['all_within_tolerance'] for r in numerical))
    write(HERE/'verification.json', verification)
    write(HERE/'summary.json', dict(aggregates=aggregates, verification=verification,
        completed_schedules=sum(r['status'] == 'COMPLETED_SCHEDULE' for r in rows),
        total_inverse_work_units=sum(r['work_units'] for r in rows),
        total_inverse_seconds=sum(r['inverse_seconds'] for r in rows),
        total_evaluation_seconds=sum(r['evaluation_seconds'] for r in rows)))
    lines = ['| Case | Arm | Status / reason | RMS mm | Hausdorff upper mm | Work units | Inverse seconds, median [range] |',
             '|---|---|---|---:|---:|---:|---:|']
    for a in aggregates:
        status = a['statuses'][0] if a['statuses'][0] == 'COMPLETED_SCHEDULE' else str(a['reasons'][0])
        rms, haus = a['rms_mm'][0], a['hausdorff_upper_mm'][0]
        lines.append(f"| {LABELS[CASES.index(a['case'])]} | {NAMES[ARMS.index(a['arm'])]} | {status} | "
            f"{fmt(rms)} | {fmt(haus)} | {a['work_units'][0]} | {a['inverse_median_seconds']:.1f} "
            f"[{a['inverse_min_seconds']:.1f}, {a['inverse_max_seconds']:.1f}] |")
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


def plots(results, aggregates):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
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
    axes.flat[0].legend(fontsize=8)
    fig.suptitle('SC-030: common-start reconstructions (first repetition, final retained state)')
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
    axes[0].set_ylabel('Inverse time [seconds]'); axes[0].legend()
    axes[1].set_ylabel('Symmetric boundary RMS [mm]'); axes[1].set_yscale('log')
    for ax in axes:
        ax.set_xticks(x); ax.set_xticklabels(LABELS); ax.grid(axis='y', alpha=.2)
    fig.suptitle('SC-030: cost and geometric error\nTimings: median and range of two sequential runs; hatched bars denote hard stops')
    fig.savefig(HERE/'cost_quality.png', dpi=160)
    fig.savefig(HERE/'cost_quality.pdf')
    plt.close(fig)


if __name__ == '__main__':
    import sys
    first_pass() if '--first-pass' in sys.argv else build()
