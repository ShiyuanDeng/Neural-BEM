"""Analyze saved FI-001 output; never evaluate physics."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from bem_inverse.io import read, write
from .study import COUNTS, OUT, ROOT, SPECS


def complex_array(values):
    if isinstance(values, dict):
        return values['real']+1j*values['imag']
    return np.array([complex_array(v) for v in values])


def analyze():
    all_rows, response = [], {}
    for name in SPECS:
        folder = OUT/name
        rows = read(folder/'summary.json')
        all_rows.extend(rows)
        manifest = read(folder/'manifest.json')
        f = np.array(manifest['frequencies_hz'])/1e9
        exact = read(folder/'exact_outputs.json')
        field = complex_array(exact['fields'])
        jac = complex_array(exact['jacobians'])
        norms = np.linalg.norm(field, axis=1)
        jnorms = np.linalg.norm(jac, axis=(1, 2))
        change = np.linalg.norm(np.diff(field, axis=0), axis=1)/np.sqrt(norms[:-1]*norms[1:])
        correlation = np.abs(np.sum(field[:-1].conj()*field[1:], axis=1))/(norms[:-1]*norms[1:])
        response[name] = dict(frequency_ghz=f, field_norm=norms, jacobian_frobenius_norm=jnorms,
            neighboring_field_change=change, neighboring_absolute_correlation=correlation,
            largest_change_interval_ghz=f[np.argmax(change):np.argmax(change)+2],
            field_peak_to_minimum=float(norms.max()/norms.min()),
            jacobian_peak_to_minimum=float(jnorms.max()/jnorms.min()),
            largest_neighbor_change=float(change.max()),
            maximum_rss_mb=max(r['machine_after']['max_rss_mb'] for r in rows))
    write(OUT/'response_analysis.json', response)
    flat = []
    for r in all_rows:
        flat.append(dict(curve=r['curve'], arm=r['arm'], nodes=r['nodes'],
            worst_field=r['errors']['worst_field'],
            worst_jacobian=r['errors']['worst_jacobian'],
            worst_local_jacobian=r['errors']['worst_local_jacobian'],
            field_tolerance_ratio=r['errors']['field_tolerance_ratio'],
            passed=r['errors']['passed'], exact_seconds=r['exact_seconds'],
            interpolated_seconds=r['interpolated_seconds'], saving=r['saving'],
            load_average=r['machine_before']['load_average'][0],
            gpu=r['machine_before']['gpu']))
    with (OUT/'table.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    for metric, key, ylabel in [('fields', 'field_relative', 'relative field error'),
                                ('jacobians', 'jacobian_per_frequency_column_relative',
                                 'worst local Jacobian-column error')]:
        fig, axes = plt.subplots(2, 2, figsize=(11, 7), sharex=True)
        for row_index, name in enumerate(('hook_release', 'hook_final')):
            manifest = read(OUT/name/'manifest.json')
            f = np.array(manifest['frequencies_hz'])/1e9
            for col, arm in enumerate(('A', 'B')):
                ax = axes[row_index, col]
                for r in read(OUT/name/'summary.json'):
                    if r['arm'] != arm:
                        continue
                    value = np.array(r['errors'][key])
                    if value.ndim == 2:
                        value = value.max(axis=1)
                    held = np.array([i for i in range(19) if i not in r['node_indices']])
                    ax.semilogy(f[held], value[held], '.-', label=f"{r['nodes']} nodes")
                if metric == 'fields':
                    ax.step(f, np.where(f <= .5, 1e-5, 1e-7), where='post',
                            color='black', linestyle='--', label='field tolerance')
                else:
                    ax.axhline(1e-3, color='black', linestyle='--', label='1e-3 reference line')
                ax.set_title(f"{name}: Ku {manifest['trace_cutoff']}; arm {arm}")
                ax.set_ylabel(ylabel)
                ax.grid(alpha=.2)
                ax.set_xlabel('frequency (GHz)')
        axes[0, 0].legend(fontsize=7, ncol=2)
        if metric == 'jacobians':
            fig.suptitle('Local errors are diagnostic; passing uses normalized frequency-stacked columns', fontsize=10)
        fig.tight_layout()
        fig.savefig(OUT/f'{metric}_by_frequency.svg')
        plt.close(fig)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for name, r in response.items():
        axes[0].semilogy(r['frequency_ghz'], r['field_norm'], '.-', label=name)
        axes[1].semilogy(r['frequency_ghz'], r['jacobian_frobenius_norm'], '.-')
        axes[2].plot(np.array(r['frequency_ghz'])[:-1]+.0625, r['neighboring_field_change'], '.-')
    for ax, label in zip(axes, ('field norm', 'Jacobian Frobenius norm', 'neighboring field change')):
        ax.set_xlabel('frequency (GHz)')
        ax.set_ylabel(label)
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(OUT/'exact_response.svg')
    plt.close(fig)
    report = ['| Curve | Arm | Nodes | Worst field | Worst stacked J | Exact s | Interpolated s | Saving |',
              '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in flat:
        report.append(f"| {r['curve']} | {r['arm']} | {r['nodes']} | {r['worst_field']:.3g} | "
                      f"{r['worst_jacobian']:.3g} | {r['exact_seconds']:.3f} | "
                      f"{r['interpolated_seconds']:.3f} | {100*r['saving']:.1f}% |")
    (OUT/'table.md').write_text('\n'.join(report)+'\n')
    print('\n'.join(report))
    for name, r in response.items():
        print(name, {k:v for k,v in r.items() if k in ('field_peak_to_minimum',
              'jacobian_peak_to_minimum', 'largest_neighbor_change', 'largest_change_interval_ghz', 'maximum_rss_mb')})


if __name__ == '__main__':
    analyze()
