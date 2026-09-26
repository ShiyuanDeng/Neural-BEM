"""Part 4 (uncertainty_plan.md): does noise-scaled posterior uncertainty localize spurious features?

    python uncertainty.py [workers]
"""
from concurrent.futures import ProcessPoolExecutor
import importlib.util
import json
from pathlib import Path
import sys
import traceback

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect = load('atlas_collect', HERE/'atlas_collect.py')
analyse = load('atlas_analyse', HERE/'atlas_analyse.py')

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, spd_cases as sc
from experiments.shape_continuation import trajectory_atlas as ta
from experiments.shape_continuation.geometry import FourierCurve, arclength_angles

ORDERS = 128
SAMPLES = 4096
L_MM = 1e3*sc.LENGTH
PRIORS = {'P1_white_1mm': lambda m: np.ones_like(m, float), 'P2_decay': lambda m: (1 + m/8.0)**-1.5}
SC044 = RESULTS/'SC-044-noisy-fresh-cases'


def basis(s):
    """Unit-RMS arclength normal ripples, orders 0..ORDERS, at angles s; also each column's order."""
    cols, orders = [np.ones_like(s)], [0]
    for m in range(1, ORDERS+1):
        cols += [np.sqrt(2)*np.cos(m*s), np.sqrt(2)*np.sin(m*s)]
        orders += [m, m]
    return np.column_stack(cols), np.array(orders)


def states():
    out = []
    index = json.loads((RESULTS/'SC-040-six-scene-pipeline/trajectories.json').read_text())['trajectories']
    kite = next(t for t in index if t['id'] == 'F_released_m/kite')['steps']
    last4 = max(i for i, s in enumerate(kite) if s['stage'] == 'stage_4')
    rem = next(s for s in kite if s['stage'] == 'remaining_m19' and s['iteration'] == 4)
    for label, s in (('kite stage_4 end (K=20)', kite[last4]), ('kite remaining_m19 it4', rem)):
        out.append(dict(set='screen', label=label, case='kite', nodes=s['nodes'], shot=s['shot'],
                        curve=collect.history_curve(s['source'], s['iteration'])))
    last = lambda p: json.loads(Path(p).read_text())['states'][-1]['curve']
    out.append(dict(set='screen', label='kite SC-041 M22 end', case='kite', nodes=768, shot=None,
                    curve=ast.curve_from(json.loads((RESULTS/'SC-041-atlas-decisions/runs/kite/M22/result.json').read_text())['curve'])))
    out.append(dict(set='screen', label='kite review refit_K64 end', case='kite', nodes=768, shot=None,
                    curve=ast.curve_from(last(HERE/'strategies/refit_K64/accepted.json'))))
    out.append(dict(set='screen', label='star SC-041 M25 end', case='circle_to_star', nodes=512, shot=None,
                    curve=ast.curve_from(json.loads((RESULTS/'SC-041-atlas-decisions/runs/circle_to_star/M25/result.json').read_text())['curve'])))
    for case in ('asymmetric_lobes', 'deep_c'):
        for profile in ('clean', 'noise_seed_0', 'noise_seed_1'):
            for arm in ('none', 'boundary', 'cap'):
                out.append(dict(set='test', label=f'{case}/{profile}/{arm}', case=case, nodes=512, shot=None,
                                curve=ast.curve_from(last(SC044/'runs'/case/profile/arm/'accepted.json'))))
    for i, s in enumerate(out):
        s['id'] = i
    for i in [j for j, s in enumerate(out) if s['set'] == 'test'][:2]:
        out[i]['check'] = True
    return out


def data_norms(case):
    if case in ('asymmetric_lobes', 'deep_c'):
        d = json.loads((SC044/'inputs'/case/'clean.json').read_text())
        values = np.array(d['observed_real']) + 1j*np.array(d['observed_imag'])          # (pairs, F)
        return np.linalg.norm(values, axis=0), values.shape[0]
    values = np.array([o.scattered for o in ast.catalog_only(case)])                   # (F, pairs)
    return np.linalg.norm(values, axis=1), values.shape[1]


def ratio_map(curve, n, case):
    observations = ast.catalog_only('kite')        # SC-044 and the development runs share this acquisition
    sh = collect.shot(curve, n, observations, ac.contrast())
    nodes = curve.nodes(n)
    s_nodes, _ = arclength_angles(nodes)
    H, orders = basis(s_nodes)
    H = H*(1e-3/sc.LENGTH)                          # per mm, as atlas_video.ripple_basis
    norms, pairs = data_norms(case)
    sigma = 0.01*norms/np.sqrt(2*pairs)
    info = np.zeros((H.shape[1],)*2)
    for f in range(len(observations)):
        J = ta.jacobian(sh, f, n, H)
        Jw = np.concatenate([J.real, J.imag])/sigma[f]
        info += Jw.T@Jw
    s = 2*np.pi*np.arange(SAMPLES)/SAMPLES
    Phi, _ = basis(s)
    out = {}
    for name, rule in PRIORS.items():
        p = rule(orders)**2
        C = np.linalg.inv(info + np.diag(1/p))
        post = np.einsum('ij,jk,ik->i', Phi, C, Phi)
        prior = (Phi**2)@p
        out[name] = np.sqrt(np.clip(post/prior, 0, None))
    return out, sh


def truth_curve(case):
    if case in ('asymmetric_lobes', 'deep_c'):
        return ast.curve_from(json.loads((SC044/'inputs'/case/'truth.json').read_text()))
    return ast.curve_from(sc.read(ast.source_folder(case)/'truth.json'))


def work(s):
    try:
        curve = s['curve']
        row = dict(id=s['id'], set=s['set'], label=s['label'], case=s['case'],
                   C1_key=None if s['shot'] is None else ta.shot_key(curve) == s['shot'])
        maps, _ = ratio_map(curve, s['nodes'], s['case'])
        if s.get('check'):
            fine, _ = ratio_map(curve, 2*s['nodes'], s['case'])
            row['C2_max_abs'] = max(float(np.max(abs(maps[k]-fine[k]))) for k in maps)
        truth = truth_curve(s['case'])
        tpts = truth.nodes(65536).points
        e = np.abs(analyse.normal_error(curve, tpts))[::2]                  # 8192 -> 4096 uniform arclength
        kappa = analyse.arclength_series(curve, lambda nd: np.asarray(nd.curvatures))[::2]
        j = int(np.argmax(np.abs(kappa)))
        # spurious? truth radius at the nearest truth point vs the state's radius there
        tn = truth.nodes(65536)
        z = analyse.arclength_series(curve, lambda nd: nd.points[:, 0] + 1j*nd.points[:, 1])[::2][j]
        k_truth = abs(np.asarray(tn.curvatures)[np.argmin(abs(tn.points[:, 0] + 1j*tn.points[:, 1] - z))])
        row.update(state_radius_mm=float(L_MM/abs(kappa[j])), truth_radius_there_mm=float(L_MM/max(k_truth, 1e-12)))
        row['spurious_sharpest'] = row['truth_radius_there_mm'] > 3*row['state_radius_mm']
        for name, r in maps.items():
            row[f'{name}|R1'] = float(spearmanr(r, e)[0])
            row[f'{name}|R2_percentile'] = float(100*np.mean(r < r[j]))
            row[f'{name}|median_ratio'] = float(np.median(r))
            row[f'{name}|ratio_range'] = [float(r.min()), float(r.max())]
        np.savez(HERE/'atlas_local'/f"uncertainty_{s['id']:02d}.npz", error=e, kappa=kappa,
                 **{k: v for k, v in maps.items()})
        print('DONE', s['id'], s['label'], {k: round(v, 3) for k, v in row.items() if '|R1' in k}, flush=True)
        return row
    except Exception:
        print('FAILED', s['id'], traceback.format_exc(), flush=True)
        return dict(id=s['id'], traceback=traceback.format_exc())


def summarize(rows):
    test = [r for r in rows if r.get('set') == 'test' and 'traceback' not in r]
    out = dict(test_states=len(test))
    verdicts = []
    for name in PRIORS:
        r1 = [r[f'{name}|R1'] for r in test]
        spur = [r[f'{name}|R2_percentile'] for r in test if r['spurious_sharpest']]
        res = dict(median_R1=float(np.median(r1)), positive_R1=int(sum(x > 0 for x in r1)),
                   spurious_states=len(spur), median_R2=float(np.median(spur)) if spur else None)
        passed = res['median_R1'] >= .4 and res['positive_R1'] >= 14 and spur and res['median_R2'] >= 75
        res['verdict'] = 'pass' if passed else ('fail' if res['median_R1'] < .2 else 'inconclusive')
        out[name] = res
        verdicts.append(res['verdict'])
    out['overall'] = 'pass' if all(v == 'pass' for v in verdicts) else (
        'fail' if any(v == 'fail' for v in verdicts) else 'inconclusive')
    return out


def main(workers=2):
    listed = states()
    with ProcessPoolExecutor(workers) as pool:
        rows = list(pool.map(work, listed))
    report = dict(plan='uncertainty_plan.md', summary=summarize(rows), rows=rows)
    (HERE/'uncertainty.json').write_text(json.dumps(report, indent=1, default=float) + '\n')
    print(json.dumps(report['summary'], indent=1))


if __name__ == '__main__':
    main(*map(int, sys.argv[1:2]))
