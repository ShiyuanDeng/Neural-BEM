"""Regenerate the four-arm diagnostic table, plot and integrity audit."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from experiments.shape_continuation.legacy_cases import load_shape, physical, source_hashes, write


def main(output):
    manifest = json.loads((output/'manifest.json').read_text())
    data = json.loads((output/'input.json').read_text())
    names = ('control','halving','curvature10-halving0','curvature10-halving6')
    records = [json.loads((output/name/'result.json').read_text()) for name in names]
    assert source_hashes() == manifest['source_sha256']
    assert hashlib.sha256((output/'input.json').read_bytes()).hexdigest() == manifest['input_sha256']
    assert records[0]['exact_sc018_replay']
    for record in records:
        assert record['input_sha256'] == manifest['input_sha256']
        assert record['failure'] is None and 'evaluation_failure' not in record
        assert record['scores']['endpoint_field_refinement'] < 1e-6
    for first, second, key in ((0,1,'backtracks'),(2,3,'backtracks'),
                               (0,2,'curvature_tail_tolerance'),(1,3,'curvature_tail_tolerance')):
        differences = [k for k in records[first]['config']
                       if records[first]['config'][k] != records[second]['config'][k]]
        assert differences == [key]
    probe = json.loads((output/'same-state-probe.json').read_text())
    assert not probe['rows'][0]['accepted'] and probe['rows'][1]['accepted']
    assert probe['rows'][0]['before'] == probe['rows'][1]['before']
    write(output/'factorial-comparison.json',records)
    write(output/'verification.json',dict(
        all_four_arms_scored=True,source_hashes_match=True,input_hashes_match=True,
        exact_sc018_control_replay=True,one_setting_per_factorial_edge=True,
        same_state_probe_resumes_with_halving=True,
        numerical_core_changed=False,
        max_field_refinement=max(r['scores']['endpoint_field_refinement'] for r in records)))
    rows = []
    for r in records:
        s = r['scores']
        rows.append(f"| {100*r['config']['curvature_tail_tolerance']:g}% "
                    f"| {r['config']['backtracks']} | {r['forwards']} "
                    f"| {s['boundary_m']*1000:.4g} | {s['train_relative']:.4g} "
                    f"| {s['worst_holdout_relative']:.4g} | {r['stop']} "
                    f"| {'PASS' if r['passed'] else 'FAIL'} |")
    (output/'table.md').write_text('\n'.join([
        '| Curvature tail gate | Halvings | Frequency solves | Boundary mm | Train relative | Worst holdout relative | Stop | Gates |',
        '|---|---:|---:|---:|---:|---:|---|---|',*rows])+'\n')
    fig,axes = plt.subplots(1,2,figsize=(10,5.5),sharex=True,sharey=True)
    for j,ax in enumerate(axes):
        for key,label,color,style in [('initial','initial','0.65',':'),('truth','truth','black','--')]:
            z=physical(load_shape(data[key])).values(4096)
            ax.plot(z.real,z.imag,label=label,color=color,linestyle=style)
        for r,color,label in zip(records[j*2:j*2+2],('C0','C1'),('no halving','six halvings')):
            z=physical(load_shape(r['shape'])).values(4096)
            ax.plot(z.real,z.imag,color=color,label=label)
        ax.set(title=f"Curvature tail gate: {(1,10)[j]}%",xlabel='x (m)',ylabel='y (m)')
        ax.set_aspect('equal')
        ax.grid(alpha=.2)
    handles,labels=axes[0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=4)
    fig.suptitle('Ellipse-to-star: one setting changed along each comparison')
    fig.tight_layout(rect=(0,.07,1,.95))
    fig.savefig(output/'factorial-boundaries.png',dpi=160)
    plt.close(fig)
    print('\n'.join(rows))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    main(args.output)
