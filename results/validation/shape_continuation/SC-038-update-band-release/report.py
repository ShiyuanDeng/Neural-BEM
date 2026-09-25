"""SC-038 report from saved curves and measurements; no field solves."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'SC-035-state-band'
CASES = ('circle_to_c', 'kite')
ARMS = ('fixed_m9', 'release_m')
COLORS = {'fixed_m9': '#ad633c', 'release_m': '#167b74'}
LABELS = {'fixed_m9': 'M = 9 repeated', 'release_m': 'M = 11 → 15 → 19'}


def main():
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), layout='constrained')
    residual_fig, residual_axes = plt.subplots(1, 2, figsize=(11, 3.8), layout='constrained')
    rows, stages = [], []
    lines = ['| Case | Common start RMS (mm) | Old release RMS | All data, M=9 | All data, M ladder | Ladder / M=9 | New units M=9 / ladder |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for col, case in enumerate(CASES):
        truth = ast.curve_from(sc.read(ast.source_folder(case) / 'truth.json'))
        target = truth.values(16384)
        source = BASE / 'runs' / case / 'low'
        start = ast.curve_from(sc.read(source / 'stage_4_history.json')['history'][-1]['coefficients'])
        start_error = 1e3 * symmetric_rms_distance(start, target, sc.LENGTH)
        original = sc.read(source / 'continue.json')
        original_data = {a: sc.read(HERE / 'runs' / case / a / 'result.json') for a in ARMS}
        dense = case == 'kite' and all((HERE / 'dense_kite/runs' / a / 'result.json').exists() for a in ARMS)
        folders = {a: HERE / 'dense_kite/runs' / a if dense else HERE / 'runs' / case / a for a in ARMS}
        data = {a: sc.read(folders[a] / 'result.json') for a in ARMS}
        dense_data = dict(data)
        extra = dense and (HERE / 'final_m19/runs/release_m/result.json').exists()
        if extra:
            folders['release_m'] = HERE / 'final_m19/runs/release_m'
            data['release_m'] = sc.read(folders['release_m'] / 'result.json')
        for curve, label, color, style in [(truth, 'Truth', '#222222', '-'),
                                           (start, f'Start: {start_error:.4f} mm', '#888888', '--')]:
            z = curve.values(4096) * 50
            axes[0, col].plot(z.real, z.imag, color=color, ls=style, label=label)
        for arm, result in data.items():
            error = result['score']['symmetric_rms_mm']
            suffix = ' [time limit]' if result['reason'] == 'TRIAL_WALL_LIMIT' else ' [stopped]'
            label = LABELS[arm] + (suffix if result['status'] != 'COMPLETED_SCHEDULE' else '')
            z = ast.curve_from(result['curve']).values(4096) * 50
            axes[0, col].plot(z.real, z.imag, color=COLORS[arm], label=f'{label}: {error:.4f} mm')
            residual_axes[col].semilogy(np.asarray(ac.CATALOG_HZ) / 1e9, result['score']['catalog_relative_residual'],
                                        'o-', color=COLORS[arm], ms=3, label=label)
            points = [(0, start_error)]
            sequence = [(folders[arm], r) for r in result['stages']]
            if extra and arm == 'release_m':
                sequence = [(HERE / 'dense_kite/runs/release_m', r) for r in dense_data[arm]['stages']
                            if r['stage'] == 'dense_2'] + sequence
            if dense:
                sequence.insert(0, (HERE / 'runs' / case / arm, original_data[arm]['stages'][0]))
            for i, (folder, record) in enumerate(sequence, 1):
                history = sc.read(folder / f"{record['stage']}_history.json")['history']
                if not history:
                    continue
                segment = sc.read(folder / 'result.json')
                # A time stop may occur after acceptance but before its gradient/history row.
                curve = ast.curve_from(segment['curve'] if record['stage'] == segment['stages'][-1]['stage']
                                       else history[-1]['coefficients'])
                rms = 1e3 * symmetric_rms_distance(curve, target, sc.LENGTH)
                points.append((i, rms))
                stages.append(dict(case=case, arm=arm, rms_mm=rms, **record))
            axes[1, col].plot(*zip(*points), 'o-', color=COLORS[arm], label=label)
        fixed, released = [data[a] for a in ARMS]
        ef, er = [d['score']['symmetric_rms_mm'] for d in (fixed, released)]
        suffix_units = {a: d['complete_path_units'] - original_data[a]['prefix_units'] for a, d in data.items()}
        row = dict(case=case, start_rms_mm=start_error, old_release_rms_mm=original['score']['symmetric_rms_mm'],
                   fixed_m9_rms_mm=ef, release_m_rms_mm=er, release_vs_fixed_ratio=er / ef,
                   fixed_vs_start_ratio=ef / start_error, release_vs_start_ratio=er / start_error,
                   suffix_units=suffix_units,
                   latest_segment_units={a: d['work']['work_units'] for a, d in data.items()},
                   complete_path_units={a: d['complete_path_units'] for a, d in data.items()},
                   statuses={a: d['status'] for a, d in data.items()},
                   nodes=[768, 1536] if dense else [512, 1024],
                   remaining_M19_completion_used=bool(extra),
                   original_run_rms_mm={a: d['score']['symmetric_rms_mm'] for a, d in original_data.items()},
                   original_run_statuses={a: d['status'] for a, d in original_data.items()},
                   first_release_units={a: original_data[a]['stages'][0]['work']['work_units'] for a in ARMS},
                   mean_catalog_relative_residual={a: float(np.mean(d['score']['catalog_relative_residual'])) for a, d in data.items()},
                   hausdorff_mm={a: d['score']['hausdorff_mm'] for a, d in data.items()})
        regularity = {}
        shapes = dict(truth=truth, start=start, **{a: ast.curve_from(d['curve']) for a, d in data.items()})
        for name, curve in shapes.items():
            regularity[name] = {}
            for count in (8192, 16384):
                nodes = curve.nodes(count)
                j = int(np.argmax(np.abs(nodes.curvatures)))
                regularity[name][str(count)] = dict(minimum_sampled_radius_mm=float(50 / abs(nodes.curvatures[j])),
                    location_mm=(nodes.points[j] * 50).tolist(), speed_ratio=float(max(nodes.speeds) / min(nodes.speeds)))
        row['regularity'] = regularity
        if case == 'kite':
            centre = np.array(regularity['release_m']['16384']['location_mm'])
            zoom_fig, zoom_axes = plt.subplots(1, 2, figsize=(10, 4.5), layout='constrained')
            for name, color, label in [('truth', '#222222', 'Truth'), ('fixed_m9', COLORS['fixed_m9'], 'M = 9'),
                                       ('release_m', COLORS['release_m'], 'Released M')]:
                z = shapes[name].values(16384) * 50
                for ax in zoom_axes:
                    ax.plot(z.real, z.imag, color=color, label=label, lw=1.5)
            for ax in zoom_axes:
                ax.plot(*centre, 'o', color='#bb3434', ms=5, label='Smallest radius on result')
                ax.set(aspect='equal', xlabel='x (mm)', ylabel='y (mm)')
            zoom_axes[0].set(title='Kite: lower RMS, remaining sharp feature')
            zoom_axes[0].legend(fontsize=8)
            zoom_axes[1].set(xlim=(centre[0]-1.2, centre[0]+1.2), ylim=(centre[1]-1.2, centre[1]+1.2),
                             title='Detail near the smallest-radius point')
            zoom_fig.suptitle('Minimum sampled radius: truth %.3f mm; released M %.3f mm' %
                (regularity['truth']['16384']['minimum_sampled_radius_mm'], regularity['release_m']['16384']['minimum_sampled_radius_mm']))
            zoom_fig.savefig(HERE / 'kite_regularity.png', dpi=180)
            plt.close(zoom_fig)
        rows.append(row)
        lines.append(f"| {case} | {start_error:.6f} | {row['old_release_rms_mm']:.6f} | {ef:.6f} | {er:.6f} | {er/ef:.4f} | {suffix_units['fixed_m9']} / {suffix_units['release_m']} |")
        title = case.replace('circle_to_', '').title() + (' · dense final two stages' if dense else '')
        axes[0, col].set(title=title, xlabel='x (mm)', ylabel='y (mm)', aspect='equal')
        axes[0, col].legend(fontsize=8)
        axes[1, col].set(xlabel='Release stage (0 = common start)', ylabel='Boundary RMS error (mm)', xticks=[0, 1, 2, 3], yscale='log')
        axes[1, col].grid(alpha=.2)
        axes[1, col].legend(fontsize=8)
        residual_axes[col].semilogy(np.asarray(ac.CATALOG_HZ) / 1e9, original['score']['catalog_relative_residual'],
                                   '--', color='#888888', label='Old four-frequency result')
        residual_axes[col].set(title=title, xlabel='Frequency (GHz)', ylabel='Relative field residual')
        residual_axes[col].grid(alpha=.2)
        residual_axes[col].legend(fontsize=8)
    fig.suptitle('SC-038 · All 19 frequencies at every release stage · K = 192')
    fig.savefig(HERE / 'comparison.png', dpi=180)
    plt.close(fig)
    residual_fig.suptitle('SC-038 · All 19 frequencies are fitting data in the new suffixes')
    residual_fig.savefig(HERE / 'residuals.png', dpi=180)
    plt.close(residual_fig)
    if (HERE / 'dense_kite/completion.json').exists():
        lines += ['', 'Kite uses the matched 768/1536-node final two stages; its listed suffix units',
                  'include the reused first release stage, excluding the earlier stopped attempt.',
                  'The original 512/1024-node kite M ladder stopped at M=15 (0.278808 mm).',
                  'All original attempts, reused-prefix work and dense-stage costs are retained.']
    (HERE / 'comparison.md').write_text('\n'.join(lines) + '\n')
    sc.write(HERE / 'comparison.json', dict(rows=rows, stages=stages, report_sha256=sc.digest(Path(__file__).resolve())))
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
