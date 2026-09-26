"""Part 3 (signal_plan.md): truth-free geometry signals, screened on development states, tested on SC-044.

No field solves. Truth is used only for the targets (RMS, Hausdorff).

    python signals.py
"""
import glob
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
LOCAL = HERE / 'atlas_local'

from experiments.shape_continuation import atlas_strategy_tests as ast, atlas_video as av, spd_cases as sc
from experiments.shape_continuation.atlas_survey import symmetric_rms_distance
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.metrics import boundary_distance

import importlib.util
spec = importlib.util.spec_from_file_location('analyse', HERE/'atlas_analyse.py')
analyse = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyse)

L_MM = 1e3*sc.LENGTH
N = 16384
GEOMETRY = ('S1_highband_rms', 'S2_highband_peak', 'S3_inverse_min_radius', 'S4_curvature_roughness', 'S6_loss')
ALL = ('S0_atlas_inside',) + GEOMETRY[:4] + ('S5_highband_signature', 'S6_loss')


def cutoff(M):
    return max(48, 2*M)


def low_pass(curve, K):
    c = np.array(curve.coefficients)
    c[np.abs(curve.modes) > K] = 0
    return FourierCurve(c)


def geometry_signals(curve, M):
    K = cutoff(M)
    if curve.band > K:
        delta = analyse.normal_error(curve, low_pass(curve, K).nodes(65536).points)
    else:
        delta = np.zeros(8192)
    nodes = curve.nodes(N)
    k = np.asarray(nodes.curvatures)/L_MM                               # 1/mm
    ds = np.asarray(nodes.speeds)*(2*np.pi/N)*L_MM                      # mm per node
    dk = (np.roll(k, -1) - np.roll(k, 1))/(np.roll(ds, -1)/2 + ds + np.roll(ds, 1)/2)
    w = ds/ds.sum()
    return dict(S1_highband_rms=float(np.sqrt(np.mean(delta**2))), S2_highband_peak=float(np.max(np.abs(delta))),
                S3_inverse_min_radius=float(np.max(np.abs(k))), S4_curvature_roughness=float(np.sqrt(w@dk**2))), delta


def scores(curve, truth, truth_points):
    distance, _ = boundary_distance(truth, curve)
    return dict(rms_mm=1e3*symmetric_rms_distance(curve, truth_points, sc.LENGTH), hausdorff_mm=L_MM*distance)


def evaluate(rows, names, group_key):
    """Spearman across states and pairwise sign agreement, per group."""
    out = {}
    for g in sorted({r[group_key] for r in rows}):
        sel = [r for r in rows if r[group_key] == g]
        res = dict(states=len(sel))
        pairs = [(a, b) for a, b in zip(sel, sel[1:]) if a['segment'] == b['segment']]
        res['pairs'] = len(pairs)
        for n in names:
            x = [r[n] for r in sel]
            for target in ('hausdorff_mm', 'rms_mm'):
                rho = spearmanr(x, [r[target] for r in sel])[0] if len(set(x)) > 1 else None
                agree = [np.sign(b[n]-a[n]) == np.sign(b[target]-a[target]) for a, b in pairs]
                flat = sum(b[n] == a[n] for a, b in pairs)
                res[f'{n}|{target}'] = dict(rho=None if rho is None else float(rho),
                                            agreement=float(np.mean(agree)) if agree else None, unchanged_pairs=int(flat))
        out[g] = res
    return out


def verdict(result, names, groups, target):
    v = {}
    for n in names:
        ok = []
        for g in groups:
            r = result[g][f'{n}|{target}']
            ok.append(r['rho'] is not None and r['rho'] >= .6 and r['agreement'] is not None and r['agreement'] >= .7)
        v[n] = 'useful' if all(ok) else ('case-specific' if any(ok) else 'not useful')
    return v


def screen():
    index = {r['id']: r for r in json.loads((HERE/'atlas_index.json').read_text())['rows']}
    dev = json.loads((HERE/'atlas_analysis.json').read_text())['rows']
    rows = []
    for r in dev:
        a = dict(np.load(LOCAL/f"{r['id']:03d}.npz"))
        curve = FourierCurve(a['coefficients'])
        g, delta = geometry_signals(curve, r['M'])
        n = len(delta); s = 2*np.pi*np.arange(n)/n
        cols = [np.ones(n)] + [h for m in range(1, av.BAND+1) for h in (np.sqrt(2)*np.cos(m*s), np.sqrt(2)*np.sin(m*s))]
        coef = np.array([np.mean(delta*h) for h in cols])
        sig = max(np.linalg.norm(a['A'][f]@coef)/np.linalg.norm(a['r'][f]) for f in index[r['id']]['active'])
        rows.append(dict(id=r['id'], case=r['case'], segment=(r['track'], r['stage']), S0_atlas_inside=r['inside'],
                         S5_highband_signature=float(sig), S6_loss=r['loss'], rms_mm=r['rms_mm'],
                         hausdorff_mm=r['hausdorff_mm'], **g))
    result = evaluate(rows, ALL, 'case')
    return rows, result, dict(hausdorff=verdict(result, ALL, ('circle_to_star', 'kite'), 'hausdorff_mm'),
                              rms=verdict(result, ALL, ('circle_to_star', 'kite'), 'rms_mm'))


def test():
    base = RESULTS/'SC-044-noisy-fresh-cases'
    rows = []
    for case in ('asymmetric_lobes', 'deep_c'):
        truth = ast.curve_from(json.loads((base/'inputs'/case/'truth.json').read_text()))
        truth_points = truth.values(N)
        for path in sorted(glob.glob(str(base/'runs'/case/'*'/'*'/'accepted.json'))):
            profile, treatment = Path(path).parts[-3], Path(path).parts[-2]
            for s in json.loads(Path(path).read_text())['states']:
                curve = ast.curve_from(s['curve'])
                g, _ = geometry_signals(curve, s['M'])
                rows.append(dict(case=case, profile=profile, treatment=treatment, case_profile=f'{case}/{profile}',
                                 segment=(case, profile, treatment, s['stage']), stage=s['stage'], M=s['M'],
                                 S6_loss=s['loss'], **g, **scores(curve, truth, truth_points)))
    names = GEOMETRY
    return rows, evaluate(rows, names, 'case'), evaluate(rows, names, 'case_profile'), dict(
        hausdorff=verdict(evaluate(rows, names, 'case'), names, ('asymmetric_lobes', 'deep_c'), 'hausdorff_mm'),
        rms=verdict(evaluate(rows, names, 'case'), names, ('asymmetric_lobes', 'deep_c'), 'rms_mm'))


def main():
    dev_rows, dev, dev_verdict = screen()
    forward = [n for n in GEOMETRY if dev_verdict['hausdorff'][n] != 'not useful' or dev_verdict['rms'][n] != 'not useful']
    test_rows, test_case, test_profile, test_verdict = test()
    report = dict(plan='signal_plan.md', screen=dict(result=dev, verdict=dev_verdict, forwarded=forward),
                  test=dict(result=test_case, per_profile=test_profile, verdict=test_verdict,
                            states=len(test_rows)))
    clean = lambda rows: [{k: (list(v) if isinstance(v, tuple) else v) for k, v in r.items()} for r in rows]
    (HERE/'signals.json').write_text(json.dumps(dict(report, screen_rows=clean(dev_rows), test_rows=clean(test_rows)),
                                                indent=1, default=float) + '\n')
    print(json.dumps(dict(screen_verdict=dev_verdict, forwarded=forward, test_verdict=test_verdict), indent=1))


if __name__ == '__main__':
    main()
