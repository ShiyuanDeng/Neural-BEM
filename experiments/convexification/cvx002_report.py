"""Validate and plot saved CVX-002 receipts; performs no inverse/forward solve."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import tarfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text())


def report(folder):
    summary = read(folder/'summary.json')
    manifest = read(folder/'manifest.json')
    algebra = read(folder/'algebra_qualification.json')
    checks = dict(complete=summary['complete'], algebra=algebra['passed'],
                  launch_sources_unchanged=summary['source_hashes_unchanged'])
    with tarfile.open(folder/'sources.tar.gz') as archive:
        checks['archive_hashes'] = all(hashlib.sha256(archive.extractfile(p).read()).hexdigest() == h
                                      for p, h in manifest['source_hashes'].items())
    checks['current_source_hashes'] = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h
                                         for p, h in manifest['source_hashes'].items())
    checks['expected_cells'] = len(summary['results']) == len(manifest['settings']['cases'])*len(manifest['settings']['spans'])
    checks['unique_cells'] = len({(r['case'], r['weight_log_span']) for r in summary['results']}) == len(summary['results'])
    rows = []
    fitted = []
    for row in summary['results']:
        case, span = row['case'], row['weight_log_span']
        key = f'{case}/span{span:g}'
        if 'final' not in row:
            checks[key+'/failure_preserved'] = (folder/case/'failure.txt').exists() and bool(row.get('failure'))
            rows.append(dict(case=case, grid=row['grid'], span=span, status=row['status']))
            continue
        arm = folder/key
        checks[key+'/receipt_matches'] = read(arm/'result.json') == row
        history = row['history']
        checks[key+'/objective_monotone'] = all(b['objective'] <= a['objective'] for a, b in zip(history, history[1:]))
        checks[key+'/linear_stationarity'] = all(h['linear']['normalized_stationarity'] <= 1e-7 for h in history if 'linear' in h)
        checks[key+'/forward_qualified'] = row['paired']['qualified'] and all(c['passed'] for c in read(folder/case/'data_qualification.json')['checks'])
        checks[key+'/arrays_finite'] = all(np.isfinite(a).all() for name in ('latest.npz', 'initial_scoring.npz', 'final_scoring.npz')
                                         for a in np.load(arm/name).values())
        scored = np.load(arm/'final_scoring.npz')
        predicted = scored['occupancy'] > .5
        mask = scored['truth_mask']
        iou = np.count_nonzero(predicted & mask)/np.count_nonzero(predicted | mask)
        checks[key+'/iou_recomputed'] = abs(iou-row['final']['occupancy_iou']) < 1e-14
        eligible = (row['paired']['qualified'] and row['final']['sampled_symmetric_rms_mm'] <= .75*row['initial']['sampled_symmetric_rms_mm']
                    and row['final']['occupancy_iou'] >= row['initial']['occupancy_iou']+.10)
        checks[key+'/refinement_rule'] = eligible == row['refinement_eligible']
        rows.append(dict(case=case, grid=row['grid'], span=span, status=row['stop'],
                         coefficient_rmse=row['final']['coefficient_rmse'], iou=iou,
                         rms_mm=row['final']['sampled_symmetric_rms_mm'], hausdorff_mm=row['final']['sampled_hausdorff_mm'],
                         paired_rms=row['paired']['rms_relative_residual'], paired_max=row['paired']['maximum_relative_residual'],
                         objective=history[-1]['objective'], fit_seconds=row['fit_seconds'], refinement_eligible=eligible))
        fitted.append(row)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with (folder/'table.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    validation = dict(passed=all(checks.values()), checks=checks, optimized_arms=len(fitted),
                      prefit_or_fit_stops=len(rows)-len(fitted), seconds=summary['seconds'])
    (folder/'validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    if not validation['passed']:
        raise RuntimeError({k: v for k, v in checks.items() if not v})
    if fitted:
        fig, axes = plt.subplots(2, 3, figsize=(13, 8), constrained_layout=True)
        first = fitted[0]
        arm = folder/first['case']/f"span{first['weight_log_span']:g}"
        entries = [(arm/'initial_scoring.npz', 'Centered starting disk')]
        entries.extend((folder/r['case']/f"span{r['weight_log_span']:g}"/'final_scoring.npz',
                        f"{'Unweighted' if r['weight_log_span']==0 else 'Weighted'} endpoint, span {r['weight_log_span']:g}") for r in fitted[:2])
        for ax, (path, title) in zip(axes[0], entries):
            arrays = np.load(path)
            im = ax.imshow(arrays['coefficient'], origin='lower', extent=(-120, 120, -120, 120), cmap='viridis', vmin=.25, vmax=1.25)
            boundary = arrays['truth_boundary']*50
            ax.plot(boundary.real, boundary.imag, 'w--', lw=1.5, label='Truth')
            for k in arrays.files:
                if k.startswith('contour_'):
                    z = arrays[k]*50; ax.plot(z.real, z.imag, color='#ff7163', lw=1.1)
            ax.set(title=title, xlabel='x (mm)', ylabel='y (mm)', aspect='equal')
        fig.colorbar(im, ax=list(axes[0]), label='Raw coefficient c', shrink=.7)
        for r in fitted:
            label = f"span {r['weight_log_span']:g}"
            axes[1, 0].semilogy([h['iteration'] for h in r['history']], [h['objective'] for h in r['history']], 'o-', ms=3, label=label)
            axes[1, 1].semilogy([h['frequency_hz']/1e9 for h in r['paired']['rows']], [100*h['residual'] for h in r['paired']['rows']], 'o-', ms=3, label=label)
        axes[1, 0].set(title='Regularized objective', xlabel='Accepted iteration', ylabel='Objective (arm-specific weights)')
        axes[1, 0].legend(); axes[1, 0].grid(alpha=.2)
        axes[1, 1].axhline(.3, color='black', ls='--', label='TG-002 residual gate')
        axes[1, 1].set(title='Original paired data: shape readout', xlabel='Frequency (GHz)', ylabel='Relative residual (%)')
        axes[1, 1].legend(fontsize=8); axes[1, 1].grid(alpha=.2)
        lines = [f"Grid {first['grid']} x {first['grid']}; augmented full Cauchy data", 'White dashed: truth; red: every threshold contour', '',
                 f"Start IoU {first['initial']['occupancy_iou']:.3f}; RMS {first['initial']['sampled_symmetric_rms_mm']:.2f} mm"]
        for r in fitted:
            lines.extend([f"Span {r['weight_log_span']:g}: IoU {r['final']['occupancy_iou']:.3f}; RMS {r['final']['sampled_symmetric_rms_mm']:.2f} mm",
                          f"  Hausdorff {r['final']['sampled_hausdorff_mm']:.2f} mm; paired RMS {100*r['paired']['rms_relative_residual']:.1f}%"])
        lines.extend(['', f"{len(fitted)} arms optimized; {len(rows)-len(fitted)} prefit/fit stops", 'No certified TG-002 recovery'])
        axes[1, 2].axis('off'); axes[1, 2].text(0, 1, '\n'.join(lines), va='top', fontsize=10, linespacing=1.6)
        fig.suptitle('CVX-002 joint reference field reconstruction: circle contrast 0.5', fontsize=14)
        fig.savefig(folder/'overview.png', dpi=160); fig.savefig(folder/'overview.svg'); plt.close(fig)
        svg = folder/'overview.svg'
        svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    print(json.dumps(validation, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folders', nargs='+', type=Path)
    for path in parser.parse_args().folders:
        report(path)
