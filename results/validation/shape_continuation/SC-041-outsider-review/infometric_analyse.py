"""Part 5 read-outs P1-P3 (infometric_plan.md). No field solves.

    python infometric_analyse.py
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
INFO = HERE / 'infometric'
SC044 = HERE.parent / 'SC-044-noisy-fresh-cases'

from experiments.shape_continuation import atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.metrics import boundary_distance

L_MM = 1e3*sc.LENGTH
N = 16384
CASES = ('kite', 'deep_c', 'deep_c@noise_seed_0', 'asymmetric_lobes', 'hooked_tip')
ARMS = ('A0_mass', 'A1_sensitivity', 'A2_curvature')


def truth_of(key):
    case = key.split('@')[0]
    folder = INFO if case in ('kite', 'hooked_tip') else SC044
    return ast.curve_from(json.loads((folder/'inputs'/case/'truth.json').read_text()))


def final_curve(folder):
    if (folder/'result.json').exists():
        return ast.curve_from(json.loads((folder/'result.json').read_text())['curve']), 'result'
    if (folder/'accepted.json').exists():
        return ast.curve_from(json.loads((folder/'accepted.json').read_text())['states'][-1]['curve']), 'last accepted'
    return None, 'missing'


def features(curve, truth):
    n, t = curve.nodes(N), truth.nodes(4*N)
    p, k = np.asarray(n.points), np.asarray(n.curvatures)/L_MM
    tp, tk = np.asarray(t.points), np.asarray(t.curvatures)/L_MM
    _, near = cKDTree(tp).query(p)
    S = float(np.max(np.abs(k)/np.maximum(np.abs(tk[near]), 1/50.)))
    j = int(np.argmax(np.abs(k)))
    spurious = bool(1/max(abs(tk[near[j]]), 1e-12) > 3/abs(k[j]))
    tips = []
    peaks = [i for i in range(len(tk)) if tk[i] > 0 and tk[i] >= tk[i-1] and tk[i] >= tk[(i+1) % len(tk)] and 1/tk[i] < 5]
    for i in peaks:
        close = np.linalg.norm(p - tp[i], axis=1)*L_MM <= 2
        r = 1/np.max(k[close]) if np.any(close) and np.max(k[close]) > 0 else np.inf
        tips.append(dict(truth_radius_mm=float(1/tk[i]), state_radius_mm=float(r), error=float(abs(r - 1/tk[i])*tk[i])))
    distance, _ = boundary_distance(truth, curve)
    return dict(rms_mm=1e3*symmetric_rms_distance(curve, truth.values(N), sc.LENGTH), hausdorff_mm=L_MM*distance,
                spurious_ratio=S, sharpest_point=p[j].tolist(), sharpest_spurious=spurious,
                min_radius_mm=float(1/np.max(np.abs(k))), tips=tips)


def predicted(key, point):
    """P1: is the point inside the top-10% (arclength-weighted) of w at the suffix entry state?"""
    f = INFO/'runs'/key.replace('@', '_')/'A0_mass'/'weight_release_M11.npz'
    if not f.exists():
        return None
    d = np.load(f)
    entry = FourierCurve(d['coefficients'])
    n = entry.nodes(len(d['w']))
    arc = n.arc_length_weights/np.sum(n.arc_length_weights)
    order = np.argsort(d['w'])[::-1]
    top = order[:np.searchsorted(np.cumsum(arc[order]), .10) + 1]
    i = int(np.argmin(np.linalg.norm(np.asarray(n.points) - point, axis=1)))
    return bool(i in set(top.tolist()))


def gm(x):
    x = np.asarray(x, float)
    return float(np.exp(np.mean(np.log(x)))) if len(x) else None


def main():
    rows = {}
    for key in CASES:
        truth = truth_of(key)
        for arm in ARMS:
            folder = INFO/'runs'/key.replace('@', '_')/arm
            curve, source = final_curve(folder)
            if curve is None:
                continue
            row = dict(case=key, arm=arm, source=source, **features(curve, truth))
            res = json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else {}
            row['stages'] = res.get('stages'); row['units'] = res.get('total_units')
            row['extra_sensitivity_cost'] = res.get('extra_sensitivity_cost')
            if arm == 'A0_mass' and row['sharpest_spurious']:
                row['P1_in_top10'] = predicted(key, np.array(row['sharpest_point']))
            rows[(key, arm)] = row
    complete = [k for k in CASES if all((k, a) in rows for a in ARMS)]
    p1 = [rows[(k, 'A0_mass')]['P1_in_top10'] for k in CASES if (k, 'A0_mass') in rows
          and rows[(k, 'A0_mass')].get('P1_in_top10') is not None]
    P1 = dict(spurious_states=len(p1), inside=int(sum(p1)),
              verdict=None if not p1 else ('pass' if np.mean(p1) >= .75 else 'fail'))
    ratio = lambda a, b, q: [rows[(k, a)][q]/rows[(k, b)][q] for k in complete]
    tip_worse = [max((ta['error'] - t0['error']) for ta, t0 in zip(rows[(k, 'A1_sensitivity')]['tips'], rows[(k, 'A0_mass')]['tips']))
                 for k in complete if rows[(k, 'A0_mass')]['tips']]
    S1 = np.median([rows[(k, 'A1_sensitivity')]['spurious_ratio'] for k in complete]) if complete else None
    S0 = np.median([rows[(k, 'A0_mass')]['spurious_ratio'] for k in complete]) if complete else None
    P2 = dict(cases=len(complete), hausdorff_gm_ratio=gm(ratio('A1_sensitivity', 'A0_mass', 'hausdorff_mm')),
              rms_gm_ratio=gm(ratio('A1_sensitivity', 'A0_mass', 'rms_mm')), median_S_A0=S0, median_S_A1=S1,
              worst_tip_error_increase=max(tip_worse) if tip_worse else None)
    P2['verdict'] = None if not complete else ('pass' if P2['hausdorff_gm_ratio'] <= .85 and S1 <= S0/2 and
        P2['rms_gm_ratio'] <= 1.10 and (not tip_worse or max(tip_worse) <= .25) else 'fail')
    tip = lambda a: [t['error'] for k in complete for t in rows[(k, a)]['tips']]
    P3 = dict(hausdorff_gm_ratio=gm(ratio('A1_sensitivity', 'A2_curvature', 'hausdorff_mm')),
              median_tip_error_A1=float(np.median(tip('A1_sensitivity'))) if tip('A1_sensitivity') else None,
              median_tip_error_A2=float(np.median(tip('A2_curvature'))) if tip('A2_curvature') else None)
    P3['verdict'] = None if not complete else ('pass' if P3['hausdorff_gm_ratio'] <= 1.0 and
        (P3['median_tip_error_A1'] is None or P3['median_tip_error_A1'] <= P3['median_tip_error_A2']) else 'fail')
    report = dict(plan='infometric_plan.md', complete_cases=complete, P1=P1, P2=P2, P3=P3,
                  rows=[dict(v) for v in rows.values()])
    (HERE/'infometric.json').write_text(json.dumps(report, indent=1, default=float) + '\n')
    print(json.dumps(dict(P1=P1, P2=P2, P3=P3, complete=complete), indent=1, default=float))
    for (k, a), r in rows.items():
        print(f"{k:22s} {a:15s} {r['source']:13s} RMS {r['rms_mm']:.4f} H {r['hausdorff_mm']:.4f} S {r['spurious_ratio']:7.2f} "
              f"rmin {r['min_radius_mm']:.2f} tips {[round(t['error'], 2) for t in r['tips']]} units {r['units']}")


if __name__ == '__main__':
    main()
