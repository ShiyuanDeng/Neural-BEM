"""Activity 09 report from saved fits. Stage scoring only; no forward solves."""
from csi_runtime import ROOT, provenance
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from bem_inverse.io import curve_from
import csi_fit as F

OUT = ROOT/'results/bem/baseline_data/fresnel_own_forward/2026-11-18'
OLD = ROOT/'results/bem/baseline_data/csi_five_frequency/2026-11-18'
DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/09_fit_tables_from_our_forward'
SHAPES = ('circle', 'star', 'kite', 'hook')


def load(path):
    return json.loads(path.read_text())


def collect(root, shape):
    case = shape+'__c4'
    attempt = root/case/'cuda/attempt_01'
    metrics = load(attempt/'metrics.json')
    fit = load(attempt/'fit.json')
    manifest = load(attempt/'manifest.json')
    stages = [dict(stage=s['stage'], M=s['M'], contrast=s['contrast'],
                   score=F.score(case, curve_from(s['curve']), s['contrast'])) for s in fit['stages']]
    return dict(metrics=metrics, fit=fit, manifest=manifest, stages=stages)


def main():
    pairs = {s: dict(own=collect(OUT, s), csi=collect(OLD, s)) for s in SHAPES}
    checks = load(OUT/'checks_summary.json')
    # Compare saved settings, allowing only data-dependent weak-start values/timing to differ.
    same = {}
    for shape, pair in pairs.items():
        settings = []
        for data in pair.values():
            x = dict(data['manifest']['settings'])
            x.pop('start_contrast')
            weak = dict(x.pop('contrast_start'))
            for key in ('estimated_susceptibility', 'clipped', 'seconds'):
                weak.pop(key)
            x['weak_start_rule'] = weak
            settings.append(x)
        same[shape] = settings[0] == settings[1]
    record = dict(provenance=provenance(), settings_equal_to_activity07=same,
        cases={s: {label: dict(stages=d['stages'], metrics=d['metrics'],
                              run_provenance=d['manifest']['provenance'])
                   for label, d in pair.items()} for s, pair in pairs.items()})
    (OUT/'stage_scores_and_comparison.json').write_text(json.dumps(record, indent=2)+'\n')
    figures = DOC/'figures'
    figures.mkdir(exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(10, 9), constrained_layout=True)
    for ax, (shape, pair) in zip(axes.flat, pairs.items()):
        truth = F.truth_for(shape+'__c4')[0].values(4096)*50
        own = curve_from(pair['own']['fit']['final_curve']).values(4096)*50
        old = curve_from(pair['csi']['fit']['final_curve']).values(4096)*50
        ax.fill(truth.real, truth.imag, color='#e8edf1', zorder=0)
        for z, label, color, style, width in (
                (truth, 'Truth', '#202c38', '-', 2.0),
                (old, 'Activity 07: CSI data', '#dc7b22', '-', 1.3),
                (own, 'Activity 09: own-forward data', '#1564aa', '--', 1.3)):
            z = np.r_[z, z[0]]
            ax.plot(z.real, z.imag, label=label, color=color, ls=style, lw=width)
        a = 100*pair['own']['metrics']['score']['area_error']
        b = 100*pair['csi']['metrics']['score']['area_error']
        ax.set_title(f'{shape.capitalize()}   area error: {a:.4g}% vs {b:.2f}%', fontsize=11)
        ax.set(xlabel='x (mm)', ylabel='y (mm)', aspect='equal')
        ax.grid(alpha=.2)
        ax.margins(.1)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='outside lower center', ncol=3, frameon=False)
    fig.suptitle('Same five frequencies and fit settings; only the data source changes', fontsize=13)
    fig.savefig(figures/'outlines.png', dpi=180)
    plt.close(fig)
    lines = ['# Fit tables made by our own forward: results', '',
        '18 November 2026. Runner: `bem-own`. [Plan](plan.md); [accepted checks](prefit_checks.md).',
        'Four new tables, four checks and four GPU fits, each run once. No rerun or tuning.',
        'The coordinator accepted the checks before fitting and gave the go on 18 November.', '',
        '## Data and settings', '',
        'CPU reference `nodal_kress` made the data at 2048 nodes, with 1024/2048 doubling.',
        'All four shapes are the frozen TG-002 truth at contrast 4. Each table keeps the frozen',
        'Fresnel row order, pair mask and 8820 rows at 0.5, 1, 1.5, 2 and 2.5 GHz.', '',
        'The fit is the unchanged activity 07 wrapper: `modal_muller` + `slider`, GPU,',
        'centred 65 mm circle, real data only, no localization, warm-up or declared noise.',
        'Contrast is recovered from the weak start. Series limit 1e-9; budget 13,412 work units.', '',
        'Ladder quotas are 1000, 1000, 1000, 1000 and 4000, then the default all-frequency stages.',
        'Saved settings equal activity 07 after excluding the data-dependent weak-start value and time:',
        ', '.join(f'{s}: {"yes" if v else "NO"}' for s, v in same.items())+'.', '',
        'All fits ran detached, one at a time in this activity. Other sessions shared the machine,',
        'so times are indicative. No elapsed-time stop was applied. Each manifest records its',
        'commit, available memory and whether the solver was dirty.', '',
        '## Checks before fitting', '',
        '| Shape | Worst doubling error | Worst reader error | Worst modal truth mismatch |',
        '|---|---:|---:|---:|']
    for s, c in checks.items():
        lines.append(f"| {s} | {max(r['doubling_relative'] for r in c['per_frequency']):.3e} | {max(r['reader_relative'] for r in c['per_frequency']):.3e} | {c['checks']['modal_truth_worst']:.3e} |")
    lines += ['', 'All layout checks pass. Circle against the exact series: worst 6.101e-15 relative.',
        'The differences from the frozen CSI data repeat activity 07 within 3.229e-15.',
        'The [check report](prefit_checks.md) gives every frequency, the forward and the hashes.', '',
        '## Fits beside activity 07', '',
        'Area error is the symmetric difference area divided by truth area, in percent.',
        'Scores below come from the unchanged `csi_fit.score`; truth is used only after fitting.', '',
        '| Shape | Data | Outcome | Last stage | Work units | Fit seconds | Contrast | Area error (%) |',
        '|---|---|---|---|---:|---:|---:|---:|']
    for shape, pair in pairs.items():
        for label in ('csi', 'own'):
            m = pair[label]['metrics']
            lines.append(f"| {shape} | {'activity 07 CSI' if label == 'csi' else 'own forward'} | {m['outcome']} | {m['last_stage']} | {m['work_units']} | {m['fit_seconds']:.3f} | {m['contrast']:.10f} | {100*m['score']['area_error']:.8g} |")
    lines += ['', '## Area error at every saved stage', '',
        'Each stage curve is read from `fit.json` as `stages[i]["curve"]`, decoded with',
        '`bem_inverse.io.curve_from`, then scored with `csi_fit.score(case, curve, contrast)`.',
        'No solve is run for these scores. Both data sources are scored the same way.', '',
        '| Shape | Stage | Band | Own-forward area error (%) | Activity 07 area error (%) |',
        '|---|---|---:|---:|---:|']
    for shape, pair in pairs.items():
        old = {s['stage']: s for s in pair['csi']['stages']}
        for s in pair['own']['stages']:
            previous = old.pop(s['stage'], None)
            other = f"{100*previous['score']['area_error']:.8g}" if previous else 'not saved'
            lines.append(f"| {shape} | {s['stage']} | {s['M']} | {100*s['score']['area_error']:.8g} | {other} |")
        for s in old.values():
            lines.append(f"| {shape} | {s['stage']} | {s['M']} | not saved | {100*s['score']['area_error']:.8g} |")
    lines += ['', '## Final data mismatch', '',
        'Relative scattered-field mismatch, percent. These values are saved by the unchanged',
        'wrapper after each fit at its own forward resolution; no additional solve was run.', '',
        '| Shape | Data | 0.5 GHz | 1 GHz | 1.5 GHz | 2 GHz | 2.5 GHz |',
        '|---|---|---:|---:|---:|---:|---:|']
    for shape, pair in pairs.items():
        for label in ('csi', 'own'):
            r = pair[label]['metrics']['final_residual']
            lines.append('| '+shape+' | '+label+' | '+' | '.join(f"{100*r[f'{f:g}GHz']:.6g}" for f in (.5, 1, 1.5, 2, 2.5))+' |')
    lines += ['', '## Outlines', '', '![Four outlines over truth, beside activity 07](figures/outlines.png)', '',
        '## Run records', '',
        '| Shape | Start (UTC) | Commit | Solver dirty | Start memory (GiB) | Peak host / GPU (GiB) |',
        '|---|---|---|---|---:|---:|']
    for shape, pair in pairs.items():
        d = pair['own']; p = d['manifest']['provenance']; m = d['metrics']
        lines.append(f"| {shape} | {p['utc']} | `{p['commit'][:9]}` | {p['solver_used_dirty']} | {p['memory_available_gib']:.2f} | {m['peak_memory_gib']:.2f} / {m['gpu_peak_allocated_gib']:.2f} |")
    lines += ['', 'Evidence: [fits, checks and manifests](../../../../results/bem/baseline_data/fresnel_own_forward/2026-11-18/).',
        'The [stage scores and comparisons](../../../../results/bem/baseline_data/fresnel_own_forward/2026-11-18/stage_scores_and_comparison.json)',
        'retain all scores and run provenance. Tables, prediction arrays and fit-local bulk stay',
        'local and ignored, with SHA-256 receipts in the data and bulk manifests.', '',
        '## Conclusions and report', '',
        'Conclusion is added after inspecting the figure and these saved results.', '']
    (DOC/'results.md').write_text('\n'.join(lines))
    print(json.dumps({s: dict(area_error_percent=100*d['own']['metrics']['score']['area_error'],
                              seconds=d['own']['metrics']['fit_seconds'], settings_equal=same[s])
                      for s, d in pairs.items()}, indent=2))


if __name__ == '__main__':
    main()
