"""Q1-Q5 of atlas_plan.md, from atlas_index.json and the local atlas arrays. No field solves.

    python atlas_analyse.py
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
LOCAL = HERE / 'atlas_local'

from experiments.shape_continuation import atlas_strategy_tests as ast, atlas_video as av, spd_cases as sc
from experiments.shape_continuation.geometry import FourierCurve, arclength_angles

spec = importlib.util.spec_from_file_location('sc041', HERE.parent/'SC-041-atlas-decisions/run.py')
sc041 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc041)
L_MM = 1e3*sc.LENGTH


def joint_orders(a, active, wavenumbers):
    """`atlas_video.joint` over all computed orders: capped score d and uncapped |q|, c per order."""
    A = np.vstack([a['A'][f] for f in active])/np.sqrt(len(active))
    r = np.concatenate([a['r'][f] for f in active])/np.sqrt(len(active))
    amplitude = av.horizon_mm(max(wavenumbers[f] for f in active), sc.LENGTH)
    d, _ = av.removable(A, r, amplitude)
    Q, R = np.linalg.qr(A)
    n = min(A.shape)                        # as `removable`: columns beyond the rank carry nothing
    q, c = np.zeros(A.shape[1]), np.zeros(A.shape[1])
    q[:n], c[:n] = Q.T@r, np.abs(np.diag(R))
    return dict(d=d, q=av.per_order(q**2, np.add), cap=av.per_order((c*amplitude)**2, np.add), misfit=np.linalg.norm(r))


def arclength_series(curve, values_fn, n=8192):
    """Sample a per-node quantity at uniform arclength."""
    nodes = curve.nodes(n)
    s, _ = arclength_angles(nodes)
    v = values_fn(nodes)
    return CubicSpline(np.r_[s, 2*np.pi], np.r_[v, v[0]], bc_type='periodic')(2*np.pi*np.arange(n)/n)


def order_energy(samples):
    """Energy per arclength ripple order (0, then cos^2+sin^2), from uniform samples."""
    F = np.fft.rfft(samples)/len(samples)
    e = np.abs(F)**2
    e[1:] *= 2
    return e


def normal_error(curve, truth_points):
    tree = cKDTree(truth_points)
    def f(nodes):
        p = nodes.points
        _, i = tree.query(p)
        return np.einsum('ij,ij->i', truth_points[i] - p, nodes.normals)*L_MM
    return arclength_series(curve, f)


def main():
    index = json.loads((HERE/'atlas_index.json').read_text())['rows']
    wavenumbers = np.array([o.wavenumber for o in ast.catalog_only('kite')])
    truths = {c: ast.curve_from(sc.read(ast.source_folder(c)/'truth.json')) for c in ('kite', 'circle_to_star')}
    truth_pts = {c: t.nodes(65536).points for c, t in truths.items()}
    rows, controls = [], dict(C1=[], C2=[], C3=[], failed=[], missing=[])
    for s in index:
        if 'traceback' in s:
            controls['failed'].append(s['id']); continue
        if 'misfit' not in s:
            controls['missing'].append(s['id']); continue
        a = dict(np.load(LOCAL/f"{s['id']:03d}.npz"))
        curve = FourierCurve(a['coefficients'])
        j = joint_orders(a, s['active'], wavenumbers)
        M = s['M']
        top = av.SHOW
        inside = j['d'][:min(M, av.BAND)+1].sum()
        outside = j['d'][M+1:top+1].sum() if M < top else np.nan
        score = sc041.geometry_score(s['case'], curve)
        err = order_energy(normal_error(curve, truth_pts[s['case']]))
        heat_profile = j['d'][:av.BAND+1]
        e30 = err[:av.BAND+1]
        cos = float(heat_profile@e30/np.linalg.norm(heat_profile)/np.linalg.norm(e30))
        rows.append(dict(id=s['id'], case=s['case'], track=s['track'], stage=s['stage'], iteration=s['iteration'], M=M,
                         loss=s['misfit']**2/2, inside=inside, outside=outside, total=j['d'].sum(),
                         q_by_order=j['q'].tolist(), cap_by_order=j['cap'].tolist(), d_by_order=j['d'].tolist(),
                         heat_f=a['heat'].tolist(), rms_mm=score['rms_mm'], hausdorff_mm=score['hausdorff_mm'],
                         min_radius_mm=score['tightest_radius_fine_mm'],
                         error_energy_le30=float(e30.sum()), error_energy_gt30=float(err[av.BAND+1:].sum()),
                         Q5_cosine=cos, Q5_heat_peak=int(np.argmax(heat_profile)), Q5_error_peak=int(np.argmax(e30))))
        for key in ('C1', 'C2', 'C3'):
            name = dict(C1='C1_key_matches', C2='C2_loss_relative', C3='C3_max_dex')[key]
            if s.get(name) is not None:
                controls[key].append((s['id'], s[name]))
    ok = dict(C1=all(v for _, v in controls['C1']), C2=max(v for _, v in controls['C2']) <= 1e-8,
              C3=max(v for _, v in controls['C3']) <= 1e-2)

    # Stage segments: consecutive states of one track and stage.
    segments = {}
    for r in rows:
        segments.setdefault((r['track'], r['stage']), []).append(r)
    for seg in segments.values():
        seg.sort(key=lambda r: r['iteration'])

    # Q1 drain order and spill.
    drain_m, drain_f, drain_step, spill = [], [], [], []
    for seg in segments.values():
        if len(seg) < 2:
            continue
        s0 = np.array(seg[0]['heat_f'])
        active = next(x for x in index if x['id'] == seg[0]['id'])['active']
        M = seg[0]['M']
        for f in active:
            for m in range(min(M, av.SHOW)+1):
                start = s0[m, f]
                if start <= 10.0**av.LOW:
                    continue
                for k, r in enumerate(seg[1:], 1):
                    if np.array(r['heat_f'])[m, f] <= start/10:
                        drain_m.append(m); drain_f.append(f); drain_step.append(k); break
        for a, b in zip(seg, seg[1:]):
            if np.isfinite(a['outside']) and b['inside'] < a['inside']:
                spill.append(bool(b['outside'] > a['outside']))
    q1 = dict(cells_drained=len(drain_step),
              rho_step_vs_order=spearmanr(drain_m, drain_step)[0] if len(set(drain_m)) > 1 else None,
              rho_step_vs_frequency=spearmanr(drain_f, drain_step)[0] if len(set(drain_f)) > 1 else None,
              first_step_share=float(np.mean(np.array(drain_step) == 1)) if drain_step else None,
              spill_fraction=float(np.mean(spill)) if spill else None, spill_pairs=len(spill))

    # Q2 sign agreement over consecutive pairs within a stage.
    def group(r):
        if r['case'] == 'circle_to_star':
            return 'star'
        return 'kite_before_feature' if r['min_radius_mm'] >= 1.0 else 'kite_after_feature'
    q2 = {}
    for seg in segments.values():
        for a, b in zip(seg, seg[1:]):
            g = q2.setdefault(group(b), dict(pairs=0, loss=0, rms=0, hausdorff=0))
            dim = np.sign(b['inside'] - a['inside'])
            g['pairs'] += 1
            g['loss'] += int(dim == np.sign(b['loss'] - a['loss']))
            g['rms'] += int(dim == np.sign(b['rms_mm'] - a['rms_mm']))
            g['hausdorff'] += int(dim == np.sign(b['hausdorff_mm'] - a['hausdorff_mm']))
    word = lambda x: 'tracks' if x >= .8 else ('does not track' if x < .6 else 'weak')
    for g in q2.values():
        for k in ('loss', 'rms', 'hausdorff'):
            g[k+'_agreement'] = g[k]/g['pairs'] if g['pairs'] else None
            g[k+'_verdict'] = word(g[k+'_agreement']) if g['pairs'] else None

    # Q3 removed or unseen: joint order cells that dim >= 1 dex over a stage.
    removed, unseen = 0, 0
    shares = []
    for seg in segments.values():
        if len(seg) < 2:
            continue
        a, b = seg[0], seg[-1]
        for m in range(min(a['M'], av.BAND)+1):
            h0, h1 = a['d_by_order'][m], b['d_by_order'][m]
            if h0 <= 0 or h1 <= 0 or np.log10(h0/h1)/2 < 1:
                continue
            drop = np.log10(h0/h1)/2
            qdrop = np.log10(a['q_by_order'][m]/b['q_by_order'][m])/2
            share = qdrop/drop
            shares.append(share)
            removed += share >= .8
            unseen += share < .8
    q3 = dict(cells=len(shares), removed=int(removed), not_removed=int(unseen),
              median_residual_share=float(np.median(shares)) if shares else None)

    # Q4 kite flank feature: energy by order and data signature of (state - K<=32 low-pass).
    q4 = {}
    for label, pick in (('SC-041 kite M22 endpoint', lambda r: r['track'] == 'SC041/kite/M22'),
                        ('remaining_m19 it4', lambda r: r['stage'] == 'remaining_m19' and r['iteration'] == 4)):
        cands = [r for r in rows if pick(r)]
        if not cands:
            continue
        r = max(cands, key=lambda r: r['iteration'])
        a = dict(np.load(LOCAL/f"{r['id']:03d}.npz"))
        curve = FourierCurve(a['coefficients'])
        c = np.array(curve.coefficients); c[np.abs(curve.modes) > 32] = 0
        low = FourierCurve(c)
        low_pts = low.nodes(65536).points
        delta = normal_error(curve, low_pts)          # state -> low-pass, along the state normal, mm
        e = order_energy(delta)
        # ripple coefficients (mm of unit-RMS ripple) for orders <= 30, in atlas column order
        n = len(delta); s = 2*np.pi*np.arange(n)/n
        cols = [np.ones(n)] + [g for m in range(1, av.BAND+1) for g in (np.sqrt(2)*np.cos(m*s), np.sqrt(2)*np.sin(m*s))]
        coef = np.array([np.mean(delta*g) for g in cols])
        signature = [float(np.linalg.norm(a['A'][f]@coef)/np.linalg.norm(a['r'][f])) for f in range(len(a['A']))]
        q4[label] = dict(id=r['id'], energy_le24=float(e[:av.SHOW+1].sum()/e.sum()),
                         energy_le30=float(e[:av.BAND+1].sum()/e.sum()), energy_gt30=float(e[av.BAND+1:].sum()/e.sum()),
                         feature_rms_mm=float(np.sqrt(np.mean(delta**2))), max_abs_mm=float(np.max(abs(delta))),
                         signature_over_residual=signature,
                         verdict='invisible to the atlas' if e[:av.BAND+1].sum()/e.sum() < .2 else 'visible to the atlas')

    # Q5 summary.
    q5 = {}
    for g in ('star', 'kite_before_feature', 'kite_after_feature'):
        sel = [r for r in rows if group(r) == g]
        if sel:
            q5[g] = dict(states=len(sel), median_cosine=float(np.median([r['Q5_cosine'] for r in sel])),
                         peak_agrees_within_2=float(np.mean([abs(r['Q5_heat_peak']-r['Q5_error_peak']) <= 2 for r in sel])),
                         median_error_energy_gt30_share=float(np.median([r['error_energy_gt30']/(r['error_energy_gt30']+r['error_energy_le30']) for r in sel])))

    report = dict(plan='atlas_plan.md', states=len(rows), controls_passed=ok, failed=controls['failed'], missing=controls['missing'],
                  C2_worst=max(v for _, v in controls['C2']), C3_worst=max(v for _, v in controls['C3']),
                  Q1=q1, Q2=q2, Q3=q3, Q4=q4, Q5=q5)
    (HERE/'atlas_analysis.json').write_text(json.dumps(dict(report, rows=[{k: v for k, v in r.items()
        if k not in ('heat_f',)} for r in rows]), indent=1, default=float) + '\n')
    print(json.dumps(report, indent=1, default=float))


if __name__ == '__main__':
    main()
