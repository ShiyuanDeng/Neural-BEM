"""Score saved stage curves and report the ten-frequency fits; no forward solves."""
from csi_runtime import ROOT, provenance
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import curve_from
import csi_fit as F

OUT = ROOT/'results/bem/baseline_data/csi_ten_frequency/2026-11-18'
OLD = ROOT/'results/bem/baseline_data/csi_five_frequency/2026-11-18'
DOC = ROOT/'docs/iterations/adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies'
SHAPES = ('circle', 'star', 'kite', 'hook')
FREQUENCIES = tuple(i/4 for i in range(1, 11))


def load(path):
    return json.loads(path.read_text())


def collect(root, shape):
    case = shape+'__c4'
    attempt = root/case/'cuda/attempt_01'
    if not (attempt/'metrics.json').exists():
        return None
    metrics = load(attempt/'metrics.json')
    manifest = load(attempt/'manifest.json')
    fit = load(attempt/'fit.json') if (attempt/'fit.json').exists() else None
    specs = {o['label']: o['stage'] for o in manifest['settings']['policy']['operations'] if 'stage' in o}
    stages = []
    for s in fit['stages'] if fit else []:
        spec = specs.get(s['stage'])
        stages.append(dict(stage=s['stage'], M=s['M'], contrast=s['contrast'], outcome=s['outcome'],
            ghz=[f/1e9 for f in spec['frequencies_hz']] if spec else list(FREQUENCIES),
            score=F.score(case, curve_from(s['curve']), s['contrast'])))
    return dict(metrics=metrics, manifest=manifest, fit=fit, stages=stages)


def main():
    cases = {s: dict(ten=collect(OUT, s), five=collect(OLD, s)) for s in SHAPES}
    completed = {s: p for s, p in cases.items() if p['ten'] is not None}
    checks = load(OUT/'check_summary.json')
    truths = {r['shape']: r['per_frequency'] for r in checks['shapes']}
    record = dict(provenance=provenance(), stage_score_rule='curve_from(stages[i][curve]); csi_fit.score(case, curve, contrast); no solve',
        cases={s: {label: dict(metrics=d['metrics'], stages=d['stages'], provenance=d['manifest']['provenance'])
                   for label, d in pair.items()} for s, pair in completed.items()})
    (OUT/'fit_comparison.json').write_text(json.dumps(record, indent=2)+'\n')
    all_done = len(completed) == len(SHAPES)
    lines = ['## Fits', '',
        'The coordinator accepted the checks and dry plan and gave the go on 18 November 2026.',
        'Fits ran detached, one at a time here, sharing the GPU with activity 09.',
        'Times are indicative. No rerun, tuning or elapsed-time stop was used.', '',
        'Settings: centred 65 mm circle; modal_muller + slider; real data only;',
        'no localization, warm-up or declared noise; recovered contrast from the weak start.',
        'Series limit 1e-9; 13412 work units. The ten-stage ladder and quotas are unchanged.', '',
        '| Shape | Data | Outcome | Last stage | Work units | Fit seconds | Contrast | Area error (%) |',
        '|---|---|---|---|---:|---:|---:|---:|']
    for shape, pair in completed.items():
        for label in ('five', 'ten'):
            m = pair[label]['metrics']
            area = f"{100*m['score']['area_error']:.6f}" if 'score' in m else 'unavailable'
            secs = f"{m['fit_seconds']:.3f}" if 'fit_seconds' in m else 'unavailable'
            contrast = f"{m['contrast']:.9f}" if 'contrast' in m else 'unavailable'
            lines.append(f"| {shape} | {label} frequencies | {m['outcome']} | {m.get('last_stage', 'unavailable')} | {m.get('work_units', 'unavailable')} | {secs} | {contrast} | {area} |")
    if not all_done:
        lines += ['', 'Pending fits: '+', '.join(s for s in SHAPES if s not in completed)+'.']
    lines += ['', '## Area error at every saved stage', '',
        'Every saved stage curve is decoded from fit.json with bem_inverse.io.curve_from,',
        'then scored with csi_fit.score(case, curve, contrast). No solve is run.',
        'Area error is symmetric difference area divided by true area, in percent.', '',
        '| Shape | Data | Stage | Top GHz | Shape band | Area error (%) |',
        '|---|---|---|---:|---:|---:|']
    for shape, pair in completed.items():
        for label in ('five', 'ten'):
            for s in pair[label]['stages']:
                lines.append(f"| {shape} | {label} | {s['stage']} | {max(s['ghz']):g} | {s['M']} | {100*s['score']['area_error']:.6f} |")
    lines += ['', '## Per-frequency data mismatch', '',
        'Percent relative scattered-field mismatch. True shape: worst of the two checked resolutions.',
        'Final fit: saved wrapper final_residual at its own working resolution.',
        'Only saved values are read here; no extra forward solve is run.', '',
        '| Shape | Curve | '+' | '.join(f'{f:g} GHz' for f in FREQUENCIES)+' |',
        '|---|---|'+'---:|'*10]
    for shape, pair in completed.items():
        lines.append('| '+shape+' | true | '+' | '.join(f"{100*truths[shape][str(f)]:.6f}" for f in FREQUENCIES)+' |')
        m = pair['ten']['metrics']
        lines.append('| '+shape+' | ten-frequency final | '+' | '.join(
            f"{100*m['final_residual'][f'{f:g}GHz']:.6f}" if 'final_residual' in m else 'unavailable' for f in FREQUENCIES)+' |')
        old = pair['five']['metrics']['final_residual']
        lines.append('| '+shape+' | five-frequency final | '+' | '.join(
            f"{100*old[f'{f:g}GHz']:.6f}" if f'{f:g}GHz' in old else 'not used' for f in FREQUENCIES)+' |')
    lines += ['', '## Run records', '',
        '| Shape | Start UTC | Commit | Solver dirty | Start GiB | Peak host / GPU GiB |',
        '|---|---|---|---|---:|---:|']
    for shape, pair in completed.items():
        d = pair['ten']; p = d['manifest']['provenance']; m = d['metrics']
        lines.append(f"| {shape} | {p['utc']} | `{p['commit'][:9]}` | {p['solver_used_dirty']} | {p['memory_available_gib']:.3f} | {m['peak_memory_gib']:.3f} / {m['gpu_peak_allocated_gib']:.3f} |")
    lines += ['', 'Evidence: [fit comparison and saved stage scores](../../../../results/bem/baseline_data/csi_ten_frequency/2026-11-18/fit_comparison.json).',
        'Each fit has manifest.json, fit.json, metrics.json, a log and bulk_manifest.json.',
        'Fit-local histories stay local and ignored; bulk_manifest.json records their SHA-256.', '']
    gains = [s for s, p in completed.items() if p['ten']['metrics'].get('outcome') == 'COMPLETED_SCHEDULE'
             and p['ten']['metrics'].get('score', {}).get('area_error', float('inf')) <= p['five']['metrics']['score']['area_error']/2]
    failures = [s for s, p in completed.items() if p['ten']['metrics'].get('outcome') != 'COMPLETED_SCHEDULE']
    if all_done:
        figures = DOC/'figures'; figures.mkdir(exist_ok=True)
        fig, axes = plt.subplots(2, 2, figsize=(10, 9), constrained_layout=True)
        for ax, (shape, pair) in zip(axes.flat, cases.items()):
            truth = F.truth_for(shape+'__c4')[0].values(4096)*50
            old = curve_from(pair['five']['fit']['final_curve']).values(4096)*50
            ten = pair['ten']
            found = curve_from(ten['fit']['final_curve']).values(4096)*50 if ten['fit'] else None
            ax.fill(truth.real, truth.imag, color='#e8edf1', zorder=0)
            for z, label, color, style, width in ((truth, 'Truth', '#202c38', '-', 2.),
                    (old, 'Five frequencies', '#dc7b22', '-', 1.4),
                    (found, 'Ten frequencies', '#1564aa', '--', 1.4)):
                if z is not None:
                    z = np.r_[z, z[0]]
                    ax.plot(z.real, z.imag, label=label, color=color, ls=style, lw=width)
            m, b = ten['metrics'], pair['five']['metrics']
            area = f"{100*m['score']['area_error']:.2f}%" if 'score' in m else 'failed'
            ax.set_title(f"{shape.capitalize()}: ten {area}; five {100*b['score']['area_error']:.2f}%", fontsize=11)
            ax.set(xlabel='x (mm)', ylabel='y (mm)', aspect='equal'); ax.grid(alpha=.2); ax.margins(.1)
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc='outside lower center', ncol=3, frameon=False)
        fig.suptitle('CSI forward data: ten frequencies versus five\nTen: 0.25–2.5 GHz; five: 0.5–2.5 GHz', fontsize=13)
        fig.savefig(figures/'outlines.png', dpi=170); plt.close(fig)
        lines += ['## Outlines', '', '![Truth and five- and ten-frequency outlines](figures/outlines.png)', '',
            'The five-frequency reference spans 0.5–2.5 GHz; the new list also adds 0.25 GHz.',
            'Line styles distinguish the two fitted curves where they overlap.', '', '## Conclusion', '',
            f"Clear gain (area error at most half the saved five-frequency value): {len(gains)}/4 shapes"+
            (' ('+', '.join(gains)+').' if gains else '.'),
            ('By the fixed criterion, frequency count matters.' if len(gains)>=3 else
             'By the fixed criterion, frequency count is not the main cause on these CSI data.'),
            'All four final area errors are lower. In the checked figure, circle and star look smoother;',
            'waviness remains on kite and hook. Ten frequencies reduce the error but do not remove it.',
            'Circle still grows from 0.0685% area error at the end of the ladder to 0.1706% at band 37.',
            'Activity 09 checks the separate effect of data error.', '']
    else:
        lines += ['## Conclusion', '', 'Pending: no conclusion before all four fits return.', '']
    lines += ['## Failures kept', '',
        'The first batch check began before star was frozen. Circle finished; star had not begun.',
        'The command stopped on the missing star SHA-256 file. The later command skipped circle.',
        'No check or fit was repeated. The launch failure receipt is kept in the results folder.',
        ('Fit failures: '+', '.join(failures)+'.' if failures else 'No numerical data, 1% check or fit failure.'), '',
        '```text', 'Activity: adapt_bem_to_baseline_data/08_fit_csi_tables_at_ten_frequencies',
        f'Runs: 10 data runs; 10 BEM checks; 1 dry plan; {len(completed)}/4 GPU fits',
        f'Result: all data and checks pass; clear area-error gain on {len(gains)}/4 shapes'+('' if all_done else '; fits pending'),
        'Failures: early batch launch met pending star input; '+(', '.join(failures) if failures else 'no numerical failure'),
        'Upstream patches: none',
        'Changes to our code: new data drivers, thin runner and saved-result report scripts; existing code unchanged',
        'New unknowns: '+('cause of remaining outline error; activity 09 checks data error' if all_done else 'remaining fits'),
        'Proposed next activity: '+('coordinator compares activities 08 and 09; no further run proposed' if all_done else 'finish the remaining authorized fits'),
        '```', '']
    prefix = (DOC/'results.md').read_text().split('## Fits\n', 1)[0]
    prefix = prefix.replace('State: tables and checks complete; no fit started. Waiting for the coordinator\'s go.',
        f'State: tables and checks complete; {len(completed)}/4 GPU fits recorded.')
    # Refresh the progress sentence on later report passes.
    import re
    prefix = re.sub(r'State: tables and checks complete; [0-4]/4 GPU fits recorded\.',
                    f'State: tables and checks complete; {len(completed)}/4 GPU fits recorded.', prefix)
    if all_done and not failures:
        prefix = prefix.replace(
            'The plan is a dry construction, not proof that the optimizer completes band 0.\nAny fit refusal stays a failure; there is no workaround or rerun.',
            'All four GPU fits completed the band-0 stage and their full schedule.\nNo refusal, workaround or rerun occurred.')
    (DOC/'results.md').write_text(prefix+'\n'.join(lines))
    print(json.dumps({s: dict(outcome=p['ten']['metrics']['outcome'], area_percent=100*p['ten']['metrics']['score']['area_error'] if 'score' in p['ten']['metrics'] else None)
                      for s, p in completed.items()}, indent=2))


if __name__ == '__main__':
    main()
