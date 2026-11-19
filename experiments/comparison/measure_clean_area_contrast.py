"""Measure area and recovered material on each saved clean TG-002 curve."""
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import curve_from, read
from experiments.benchmark import campaign
from experiments.comparison.check_stage_stops import BASE, curve_region
from experiments.comparison.compare_clean_schedules import OUT, write_rows
from experiments.comparison.trace_slider_refusals import ACTIVITY, GREEN, ORANGE


def main():
    with (OUT/'original_stages.csv').open() as stream:
        inventory = {(r['case'], r['stage']): r for r in csv.DictReader(stream)}
    with (OUT/'original_cases.csv').open() as stream:
        cases = list(csv.DictReader(stream))
    rows = []
    fig, axes = plt.subplots(1, 3, figsize=(10.4, 3.6), constrained_layout=True)
    for info in cases:
        case = info['case']
        fit = read(BASE.folder()/case/'fit.json')
        row = campaign.row(case)
        truth = curve_region(curve_from(read(campaign.ROOT/row['truth'])))
        states = [('start', read(campaign.ROOT/row['initial']), float(info['start_contrast']))]
        states += [(s['stage'], s['curve'], s['contrast']) for s in fit['stages']]
        measurements = []
        for number, (name, record, contrast) in enumerate(states):
            if number:
                stage = inventory[case, name]
                assert int(stage['number']) == number and float(stage['contrast']) == contrast
            area = curve_region(curve_from(record)).area
            true_eta = float(info['true_contrast'])
            area_ratio, eta_ratio = area/truth.area, contrast/true_eta
            measurements.append(dict(case=case, passed=info['passed'], number=number, stage=name,
                                     area_mm2=area*1e6, truth_area_mm2=truth.area*1e6, contrast=contrast,
                                     true_contrast=true_eta, area_ratio=area_ratio, contrast_ratio=eta_ratio,
                                     product=area_ratio*eta_ratio,
                                     excess_contrast_area_ratio=area_ratio*(contrast-1)/(true_eta-1)))
        rows.extend(measurements)
        for ax, field in zip(axes, ['area_ratio', 'contrast_ratio', 'product']):
            vals = [m[field] for m in measurements]
            color = GREEN if info['passed'] == 'True' else ORANGE
            ax.plot(range(len(vals)), vals, color=color, alpha=.48, lw=.9)
            ax.scatter([len(vals)-1], [vals[-1]], s=9, color=color)
    for ax, title in zip(axes, ['Enclosed area / true area', 'Contrast / true contrast', 'Product of ratios']):
        ax.set(yscale='log', title=title, xlabel='Stage exit (0 = start)')
        ax.axhline(1, ls=':', lw=.8, color='black')
        ax.set_xticks(np.arange(0, max(r['number'] for r in rows)+1, 2))
    for name, color in [('16 passes', GREEN), ('14 misses', ORANGE)]:
        axes[0].plot([], [], color=color, label=name)
    axes[0].legend(frameon=False, loc='upper right', fontsize=8)
    write_rows(OUT/'original_area_contrast.csv', rows)
    (ACTIVITY/'figures').mkdir(exist_ok=True)
    fig.savefig(ACTIVITY/'figures/area_contrast_by_stage.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    main()
