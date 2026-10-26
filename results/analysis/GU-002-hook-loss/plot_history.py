"""Plot saved GU-002 histories; performs no forward solves or inverse fits."""
import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, NullFormatter
import numpy as np

SOURCE = Path('/home/drdeng/Neural_SDF_BEM_AD_organised/results/validation/cleaned_interfaces/GU-002')
OUT = Path(__file__).resolve().parent
COLORS = {'spectral': '#c75928', 'slider': '#007f8b', 'slider_cpu': '#78848b'}
TITLES = {'spectral': 'Spectral · 92 accepted steps · 8.3 s · failed',
          'slider': 'GPU slider · 125 accepted steps · 30.3 s · recovered'}
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'axes.labelcolor': '#243543',
                     'text.color': '#243543', 'xtick.color': '#465460',
                     'ytick.color': '#465460', 'svg.fonttype': 'none'})


def load(arm):
    folder = SOURCE / arm / 'runs/hook__c13.3'
    fit = json.loads((folder / 'fit_result.json').read_text())
    stages, offset = [], 0
    for row in fit['stages']:
        stage = json.loads((folder / (row['stage'] + '.json')).read_text())
        stage['offset'] = offset
        stage['x'] = np.array([offset + h['iteration'] for h in stage['history']])
        stages.append(stage)
        offset += row['accepted_steps']
    assert offset == sum(s['accepted_steps'] for s in fit['stages'])
    return fit, stages


DATA = {arm: load(arm) for arm in ('spectral', 'slider_cpu', 'slider')}


def groups(stages):
    result = []
    for stage in stages:
        name = stage['stage']
        short = {'warmup_025_damped': 'Warm-up', 'stage_1_damped': 'D1',
                 'stage_2_damped': 'D2', 'stage_3_damped': 'D3',
                 'stage_4_damped': 'D4', 'stage_4_undamped': 'Real',
                 'release_M11': 'M11', 'release_M15': 'M15',
                 'release_M19': 'M19'}.get(name, 'M25–67')
        left, right = stage['offset'], int(stage['x'][-1])
        if result and result[-1][0] == short:
            result[-1][2] = right
        else:
            result.append([short, left, right])
    return result


def decorate(ax, stages, labels=False):
    for i, (label, left, right) in enumerate(groups(stages)):
        if i % 2 == 0:
            ax.axvspan(left, right, color='#eef3f6', zorder=0)
        if left:
            ax.axvline(left, color='#d4dde2', lw=.8, ls=':', zorder=0)
        if labels:
            ax.text((left+right)/2, 1.035, label, transform=ax.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=8, rotation=90 if right-left < 6 else 0)
    ax.grid(axis='y', which='major', color='#dce3e7', lw=.7, alpha=.8)
    ax.set_xlim(-1, int(stages[-1]['x'][-1])+2)
    ax.set_yscale('log')
    ax.yaxis.set_minor_formatter(NullFormatter())


fig, axes = plt.subplots(2, 2, figsize=(15, 9.4), gridspec_kw={'height_ratios': [1.3, 1]},
                         layout=None)
fig.subplots_adjust(left=.075, right=.98, top=.79, bottom=.12, wspace=.23, hspace=.18)
fig.suptitle('Hook c13.3 | Loss and gradient through the fit', x=.075, y=.97,
             ha='left', fontsize=21, fontweight='bold')
fig.text(.075, .925, 'GU-002 · saved runs only · x = cumulative accepted steps; retries do not increment x', fontsize=12)
fig.text(.075, .89, 'Segments break at stage changes. Loss catalogs and update directions can change there; jumps are not rejected steps.', fontsize=10)

for col, arm in enumerate(('spectral', 'slider')):
    fit, stages = DATA[arm]
    top, bottom = axes[:, col]
    top.set_title(TITLES[arm], loc='left', pad=49, fontsize=12)
    decorate(top, stages, labels=True)
    decorate(bottom, stages)
    for stage in stages:
        history, xs = stage['history'], stage['x']
        losses = [r['loss'] for r in history]
        gradients = [r['gradient_inf'] for r in history]
        top.plot(xs, losses, color=COLORS[arm], lw=2, marker='o', ms=2.5)
        bottom.plot(xs, gradients, color=COLORS[arm], lw=1.8, marker='o', ms=2.5)
        for trial in stage['trials']:
            if trial['status'] == 'nondecreasing' and trial.get('loss', 0) > 0:
                top.scatter(stage['offset'] + trial['iteration'], trial['loss'],
                            marker='x', color='#9d526b', s=26, linewidths=1, zorder=6)
    if arm == 'slider':
        for stage in DATA['slider_cpu'][1]:
            top.plot(stage['x'], [r['loss'] for r in stage['history']], color=COLORS['slider_cpu'],
                     ls='--', lw=.9, alpha=.8)
        top.text(.035, .045, 'CPU-preparation slider overlaps the GPU curve.', transform=top.transAxes,
                 fontsize=9, bbox=dict(facecolor='white', edgecolor='none', alpha=.9))
        top.set_ylim(1e-15, 2)
        top.yaxis.set_major_locator(LogLocator(base=10, numticks=7))
        top.annotate('M15 plateau', xy=(103, .024019), xytext=(68, 5e-7),
                     arrowprops=dict(arrowstyle='->', color='#465460', lw=1), fontsize=10)
    else:
        top.set_ylim(.002, 2)
        top.annotate('Physics failure after step 92', xy=(92, stages[-1]['history'][-1]['loss']),
                     xytext=(37, 1.05), fontsize=10,
                     arrowprops=dict(arrowstyle='->', color='#465460', lw=1))
        top.annotate('Small-gradient plateau in D3', xy=(42, .0059346), xytext=(32, .017),
                     fontsize=9, arrowprops=dict(arrowstyle='->', color='#465460', lw=1))
    top.tick_params(labelbottom=False)
    top.set_ylabel('Data loss · log scale')
    bottom.set_ylabel('Max |gradient component| · log scale')
    bottom.set_ylim(1e-6, 1e3)
    bottom.set_xlabel('Cumulative accepted iteration')

fig.text(.075, .055, 'D1–D4: damped stages. Real: undamped stage 4. M11 onward: full real catalog and increasing update band.', fontsize=10)
fig.text(.075, .028, 'Top panels use different loss ranges. × = rejected loss trial. Gradient sizes are coordinate-dependent; compare within a stage.', fontsize=10)
fig.savefig(OUT / 'loss_vs_iteration.png', dpi=180)
fig.savefig(OUT / 'loss_vs_iteration.svg')
plt.close(fig)

# A closer view of the long full-catalog phase; the objective is unchanged here.
selected = [s for s in DATA['slider'][1] if s['stage'] in ('release_M11', 'release_M15', 'release_M19')]
fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
fig.subplots_adjust(left=.07, right=.98, top=.75, bottom=.23, wspace=.3)
fig.suptitle('GPU slider | Where progress slows, and where it restarts', x=.07, y=.97,
             ha='left', fontsize=18, fontweight='bold')
fig.text(.07, .89, 'Full real catalog throughout · M11: steps 69–91 · M15: 91–109 · M19: 109–113', fontsize=11)
for i, stage in enumerate(selected):
    xs, history = stage['x'], stage['history']
    losses = np.array([r['loss'] for r in history])
    gradients = np.array([r['gradient_inf'] for r in history])
    color = ('#007f8b', '#8b5dad', '#bd7433')[i]
    name = stage['stage'].replace('release_', '')
    axes[0].plot(xs, losses, color=color, marker='o', ms=3, label=name)
    axes[1].plot(xs[1:], 100 * (losses[:-1]-losses[1:]) / losses[:-1], color=color, marker='o', ms=3)
    axes[2].plot(xs, gradients, color=color, marker='o', ms=3)
    for ax in axes:
        if i == 1:
            ax.axvspan(xs[0], xs[-1], color='#f3eef7', zorder=0)
        if i:
            ax.axvline(xs[0], color='#ccd4da', ls=':', lw=1)
for ax in axes:
    ax.set_yscale('log')
    ax.grid(axis='y', color='#dce3e7', lw=.7)
    ax.set_xlabel('Cumulative accepted iteration')
axes[0].set_ylabel('Data loss')
axes[1].set_ylabel('Loss decrease per accepted step (%)')
axes[2].set_ylabel('Max |gradient component|')
axes[0].legend(frameon=False, loc='lower left')
fig.text(.07, .105, 'M15 ends with loss 0.0240 and gradient 0.00579. At the same curve, adding M19 directions raises the gradient to 81.2.', fontsize=10)
fig.text(.07, .055, 'Four M19 steps then remove 99.7% of that loss. This supports stagnation within the smaller update space, not a globally vanished gradient.', fontsize=10)
fig.savefig(OUT / 'slider_release_detail.png', dpi=180)
fig.savefig(OUT / 'slider_release_detail.svg')
plt.close(fig)

rows, summary = [], {}
for arm, (fit, stages) in DATA.items():
    statuses = Counter(t['status'] for s in stages for t in s['trials'])
    summary[arm] = dict(accepted_steps=sum(s['accepted_steps'] for s in stages),
                        fit_seconds=fit['fit_and_localization_seconds'], trial_statuses=dict(statuses), stages=[])
    for s in stages:
        h = s['history']
        summary[arm]['stages'].append(dict(stage=s['stage'], start_iteration=s['offset'],
            end_iteration=int(s['x'][-1]), accepted_steps=s['accepted_steps'], stop=s['stop'],
            initial_loss=h[0]['loss'], final_loss=h[-1]['loss'], initial_gradient=h[0]['gradient_inf'],
            final_gradient=h[-1]['gradient_inf']))
        previous = None
        for x, r in zip(s['x'], h):
            rows.append(dict(arm=arm, stage=s['stage'], iteration=int(x), stage_iteration=r['iteration'],
                loss=r['loss'], gradient_inf=r['gradient_inf'], damping=r['damping'],
                step_norm_m=r['step_norm_m'],
                decrease_percent='' if previous is None else 100*(previous-r['loss'])/previous,
                source=str(SOURCE/arm/'runs/hook__c13.3'/(s['stage']+'.json'))))
            previous = r['loss']
with (OUT/'history.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
(OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({arm: {k: v for k, v in data.items() if k != 'stages'} for arm, data in summary.items()}, indent=2))
print('Wrote figures and source-derived data to', OUT)
