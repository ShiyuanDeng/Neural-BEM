"""RD-2: does the update band limit the boundary's harmonics? Saved states only, zero field solves.

For every accepted state of hybrid R0 (SC-029 baseline prefixes) and SPD-L (SC-034 arm L) it records, in
the same arclength measure for both methods:
  * tail(M): fraction of bending (curvature) energy int kappa^2 ds above arclength harmonic M, where M is the
    stage's update band (Borges eq. 13, `geometry.curvature_tail`);
  * bending energy int kappa^2 ds relative to a circle of the same perimeter (2 pi / L);
  * the tightest curvature radius.
Truth enters only the reference rows (the target's own tail at each M).
Run from the repository root: PYTHONPATH=solvers:. python <this file>
"""
import json
from pathlib import Path

import numpy as np

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.geometry import curvature_tail

HERE = Path(__file__).resolve().parent
R0 = sc.ROOT / 'results/validation/shape_continuation/SC-029-atlas-strategies/runs/baseline'
SPDL = sc.ROOT / 'results/validation/shape_continuation/SC-034-spd-legacy-controls/runs/L'
BANDS = (3, 5, 7, 9)
L = sc.LENGTH


def measure(curve, band):
    nodes = curve.nodes(8192)
    kappa, speed = nodes.curvatures, np.abs(nodes.derivatives) if hasattr(nodes, 'derivatives') else None
    perimeter = curve.length() if hasattr(curve, 'length') else None
    z = curve.values(8192)
    ds = np.abs(np.roll(z, -1) - z)
    energy = float(np.sum(kappa ** 2 * ds))          # normalized units; circle of perimeter P gives 4 pi^2 / P
    circle = 4 * np.pi ** 2 / float(np.sum(ds))
    return dict(tail=float(curvature_tail(curve, band)), energy_ratio=energy / circle,
                radius_mm=float(1e3 * L / np.max(np.abs(kappa))))


def hybrid(case):
    rows = []
    for stage, band in zip(range(1, 5), BANDS):
        path = R0 / case / 'none' / f'stage_{stage}_history.json'
        if not path.exists():
            break
        for item in json.loads(path.read_text())['history']:
            rows.append(dict(stage=stage, band=band, **measure(ast.curve_from(item['coefficients']), band)))
    return rows


def spd_l(case):
    p = sc.spd_modules()[0].p
    rows = []
    for stage, band in zip(range(1, 5), BANDS):
        path = SPDL / case / f'stage_{stage}' / 'trajectory.jsonl'
        if not path.exists():
            break
        for line in path.read_text().splitlines():
            state = p.driver.deserialize_state(json.loads(line)['state'])
            rows.append(dict(stage=stage, band=band, **measure(sc.from_cartesian(state.components[0]), band)))
    return rows


def summary(rows):
    out = {}
    for stage in sorted({r['stage'] for r in rows}):
        part = [r for r in rows if r['stage'] == stage]
        out[stage] = dict(band=part[0]['band'], states=len(part), max_tail=max(r['tail'] for r in part),
                          end_tail=part[-1]['tail'], max_energy_ratio=max(r['energy_ratio'] for r in part),
                          min_radius_mm=min(r['radius_mm'] for r in part))
    return out


def main():
    result, lines = {}, []
    for case in ast.CASES:
        truth = ast.curve_from(json.loads((ast.source_folder(case) / 'truth.json').read_text()))
        reference = {band: measure(truth, band) for band in BANDS}
        result[case] = dict(truth=reference, hybrid_r0=summary(hybrid(case)), spd_l=summary(spd_l(case)))
        lines.append(f"{case}: truth tail above M=3/5/7/9 = "
                     + ' / '.join(f"{reference[b]['tail']:.3f}" for b in BANDS)
                     + f"; truth energy ratio {reference[3]['energy_ratio']:.2f}, radius {reference[3]['radius_mm']:.1f} mm")
        for arm in ('hybrid_r0', 'spd_l'):
            for stage, s in result[case][arm].items():
                lines.append(f"  {arm:9s} stage {stage} (M={s['band']}, {s['states']:2d} states): tail max {s['max_tail']:.3f}"
                             f" end {s['end_tail']:.3f}; energy ratio max {s['max_energy_ratio']:.2f}; min radius {s['min_radius_mm']:.2f} mm")
    (HERE / 'audit.json').write_text(json.dumps(result, indent=2) + '\n')
    (HERE / 'audit.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
