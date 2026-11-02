"""MR-001 comparison table: known-contrast control against material recovery.

    PYTHONPATH=solvers:. python -m experiments.gaugal_comparison.mr001_report \
        results/validation/cleaned_interfaces/MR-001/R1_known_contrast \
        results/validation/cleaned_interfaces/MR-001/R2_material_weak_start > table.md
"""
import json
from pathlib import Path
import statistics
import sys


def rows(run_dir):
    out = {}
    for path in sorted((Path(run_dir)/'runs').glob('*/result.json')):
        r = json.loads(path.read_text())
        out[r['case']['id']] = r
    return out


def stage_contrasts(r):
    return [s.get('contrast') for s in r.get('stages', []) if s.get('contrast') is not None]


def main(control_dir, material_dir):
    control, material = rows(control_dir), rows(material_dir)
    print('| Case | Control recovered | Material recovered | Start contrast | Final contrast | Contrast error | '
          'RMS mm (control / material) | Time s (control / material) | Material outcome |')
    print('|---|---|---|---:|---:|---:|---:|---:|---|')
    times = []
    for case_id, c in control.items():
        m = material.get(case_id)
        if m is None:
            continue
        cm, mm = c.get('metrics') or {}, m.get('metrics') or {}
        err = m.get('contrast_relative_error')
        print(f"| `{case_id}` | {'yes' if c['recovered'] else 'no'} | {'yes' if m['recovered'] else 'no'} | "
              f"{m.get('contrast_start', float('nan')):.3g} | {m.get('contrast_final', float('nan')):.6g} | "
              f"{'' if err is None else f'{err:.1e}'} | "
              f"{cm.get('rms_mm', float('nan')):.3g} / {mm.get('rms_mm', float('nan')):.3g} | "
              f"{c.get('total_seconds', float('nan')):.1f} / {m.get('total_seconds', float('nan')):.1f} | "
              f"{m.get('outcome')} |")
        if c.get('total_seconds') and m.get('total_seconds'):
            times.append(m['total_seconds']/c['total_seconds'])
    both = [k for k in control if k in material]
    print()
    print(f"Recovered: control {sum(control[k]['recovered'] for k in both)}/{len(both)}, "
          f"material {sum(material[k]['recovered'] for k in both)}/{len(both)}.")
    if times:
        print(f"Time ratio material/control: median {statistics.median(times):.2f}, "
              f"range {min(times):.2f}-{max(times):.2f}.")
    paths = {k: stage_contrasts(material[k]) for k in both}
    print()
    print('Contrast at the end of each stage:')
    for k, v in paths.items():
        print(f"- `{k}`: " + ', '.join(f'{x:.4g}' for x in v))


if __name__ == '__main__':
    main(*sys.argv[1:3])
