"""Outsider review of SC-041: where is kite's sharpest feature, and which runs have it?

Geometry only. Reads committed JSON shape records; no field solves. Truth is used
for scoring after the fact, as in the original experiments.
Run from the repository root with PYTHONPATH=solvers:.
"""
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy.spatial import cKDTree

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.geometry import FourierCurve

HERE = Path(__file__).resolve().parent
ROOT = sc.ROOT
RESULTS = HERE.parent
L = sc.LENGTH
N = 16384
TIP_WINDOW_MM = 2.0      # a feature this close to a true curvature peak counts as "at a tip"


def curves_in(obj):
    """Yield every Fourier coefficient record in a JSON tree, in document order."""
    if isinstance(obj, dict):
        for key in ('coefficients', 'curve'):
            v = obj.get(key)
            if isinstance(v, dict) and 'real' in v and 'imag' in v:
                yield v
        for v in obj.values():
            yield from curves_in(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from curves_in(v)


def curve(record):
    return FourierCurve(np.asarray(record['real']) + 1j*np.asarray(record['imag']))


def profile(c, n=N):
    nodes = c.nodes(n)
    return np.asarray(nodes.points), np.asarray(nodes.curvatures)


truth = ast.curve_from(sc.read(ast.source_folder('kite')/'truth.json'))
truth_points, truth_k = profile(truth)
truth_tree = cKDTree(truth_points)
# The two convex curvature peaks of the true kite (radius 2.14 mm).
peaks = [i for i in range(N) if truth_k[i] > 0 and truth_k[i] >= truth_k[i-1] and truth_k[i] >= truth_k[(i+1) % N]
         and 1e3*L/truth_k[i] < 3]
tips = truth_points[peaks]


def describe(c):
    points, k = profile(c)
    j = int(np.argmax(np.abs(k)))
    d_curve, _ = truth_tree.query(points)
    d_truth, _ = cKDTree(points).query(truth_points)
    _, m = truth_tree.query(points[j])
    worst = int(np.argmax(d_curve))
    return dict(
        min_radius_mm=float(1e3*L/abs(k[j])),
        feature_point=points[j].tolist(),
        feature_to_nearest_true_tip_mm=float(1e3*L*np.min(np.linalg.norm(tips - points[j], axis=1))),
        true_radius_at_feature_mm=float(1e3*L/abs(truth_k[m])),
        rms_mm=float(1e3*symmetric_rms_distance(c, truth.values(N), L)),
        # The reconstruction's own radius where it passes each true tip: is the tip itself present?
        radius_at_true_tips_mm=[float(1e3*L/abs(k[int(np.argmin(np.linalg.norm(points - t, axis=1)))])) for t in tips],
        hausdorff_mm=float(1e3*L*max(d_curve.max(), d_truth.max())),
        worst_error_to_feature_mm=float(1e3*L*np.linalg.norm(points[worst] - points[j])),
    )


def trajectory():
    index = json.loads((RESULTS/'SC-040-six-scene-pipeline/trajectories.json').read_text())
    steps = next(t for t in index['trajectories'] if t['case'] == 'kite')['steps']
    rows, cache = [], {}
    for s in steps:
        record = cache.setdefault(s['source'], json.loads((ROOT/s['source']).read_text()))
        if 'history' in record:
            row = next(r for r in record['history'] if isinstance(r, dict) and r.get('iteration') == s['iteration'])
            shape = row['coefficients']
        else:                               # a stage summary: its saved endpoint curve
            shape = record['curve']
        rows.append(dict(stage=s['stage'], iteration=s['iteration'], update_modes=s['update_modes'],
                         curve_band=s['curve_band'], loss=s['saved_loss'], **describe(curve(shape))))
    for M in (19, 22):
        result = json.loads((RESULTS/f'SC-041-atlas-decisions/runs/kite/M{M}/result.json').read_text())
        rows.append(dict(stage=f'SC-041 M{M}', iteration=result['accepted_steps'], update_modes=M, curve_band=192,
                         loss=result['final_loss'], **describe(curve(result['curve']))))
    return rows


def survey():
    """Last shape of every committed kite record, across all methods SC-025..SC-041."""
    files = subprocess.run(['git', 'ls-files', 'results/validation/shape_continuation'], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    rows = []
    for name in sorted(files):
        if 'kite' not in name or not name.endswith('.json') or 'truth' in name:
            continue
        try:
            records = list(curves_in(json.loads((ROOT/name).read_text())))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not records:
            continue
        try:
            row = describe(curve(records[-1]))
        except Exception as error:          # a record that is not a closed curve of this family
            row = dict(error=repr(error))
        rows.append(dict(file=name, **row))
    return rows


def main():
    report = dict(true_tips=tips.tolist(), true_tip_radius_mm=float(1e3*L/truth_k[peaks].max()),
                  tip_window_mm=TIP_WINDOW_MM, trajectory=trajectory(), survey=survey())
    ok = [r for r in report['survey'] if 'error' not in r]
    off_tip = [r for r in ok if r['feature_to_nearest_true_tip_mm'] > TIP_WINDOW_MM]
    report['counts'] = dict(records=len(report['survey']), scored=len(ok), off_tip=len(off_tip),
                            off_tip_and_sharper_than_truth=sum(r['min_radius_mm'] < report['true_tip_radius_mm'] for r in off_tip))
    (HERE/'kite_feature_survey.json').write_text(json.dumps(report, indent=1) + '\n')
    for r in report['trajectory']:
        print(f"{r['stage']:>13} it{r['iteration']:>2} M={r['update_modes']:>2} K={r['curve_band']:>3} "
              f"rmin={r['min_radius_mm']:8.4f} tip_dist={r['feature_to_nearest_true_tip_mm']:6.2f} "
              f"rms={r['rms_mm']:.4f} haus={r['hausdorff_mm']:.4f} worst-feature={r['worst_error_to_feature_mm']:.2f}")
    print(report['counts'])


if __name__ == '__main__':
    main()
