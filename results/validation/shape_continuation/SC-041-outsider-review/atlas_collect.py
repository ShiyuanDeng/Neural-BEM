"""Recompute historical atlas frames (atlas_video.py maths, unchanged) for chosen states. See atlas_plan.md.

Per state: regenerate the SC-039 shot on the recorded grid with the SC-039 solver calls, then keep, per
frequency, the relative Jacobian A_f (ripple orders 0..30), the relative residual r_f, the QR projection q
and new-information size c, and the heat exactly as `atlas_video.shot_atlas`. Arrays go to a local folder
(gitignored NPZ); a JSON index with controls is written here.

    python atlas_collect.py [workers]
"""
from concurrent.futures import ProcessPoolExecutor
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
LOCAL = HERE / 'atlas_local'          # NPZ, ignored by /results/**/*.npz

from experiments.shape_continuation import atlas_cases as ac, atlas_strategy_tests as ast, atlas_video as av
from experiments.shape_continuation import trajectory_atlas as ta
from experiments.shape_continuation.forward import PointSourceAcquisition, solve
from experiments.shape_continuation.geometry import FourierCurve

CHECK = {'circle_to_star': 3, 'kite': 3}   # C3: this many states per case get the 2x-grid atlas


def history_curve(source, iteration):
    record = json.loads((ta.sc.ROOT / source).read_text())
    if 'history' not in record:
        return ast.curve_from(record['curve'])
    row = next(r for r in record['history'] if isinstance(r, dict) and r.get('iteration') == iteration)
    c = row['coefficients']
    return FourierCurve(np.asarray(c['real']) + 1j*np.asarray(c['imag']))


def states():
    index = json.loads((RESULTS/'SC-040-six-scene-pipeline/trajectories.json').read_text())['trajectories']
    out = []
    for tid, case, keep in (('SC040/circle_to_star', 'circle_to_star', None),
                            ('F_released_m/kite', 'kite', ('release_1', 'dense_2', 'remaining_m19'))):
        steps = next(t for t in index if t['id'] == tid)['steps']
        last4 = max(i for i, s in enumerate(steps) if s['stage'] == 'stage_4')
        for i, s in enumerate(steps):
            if keep is not None and s['stage'] not in keep and i != last4:
                continue
            out.append(dict(case=case, track=tid, stage=s['stage'], iteration=s['iteration'], M=s['update_modes'],
                            K=s['curve_band'], nodes=s['nodes'], active_k=s['active_wavenumbers'],
                            saved_loss=s['saved_loss'], shot=s['shot'], source=s['source']))
    catalog = [o.wavenumber for o in ast.catalog_only('kite')]
    def accepted(case, folder, label, M, nodes):
        for s in json.loads((folder/'accepted.json').read_text())['states']:
            out.append(dict(case=case, track=label, stage=s.get('stage', label), iteration=s['iteration'], M=M,
                            K=None, nodes=nodes, active_k=catalog, saved_loss=s['loss'], shot=None,
                            curve=s['curve']))
    for M in (19, 22):
        accepted('kite', RESULTS/f'SC-041-atlas-decisions/runs/kite/M{M}', f'SC041/kite/M{M}', M, 768)
    for M in (22, 25):
        accepted('circle_to_star', RESULTS/f'SC-041-atlas-decisions/runs/circle_to_star/M{M}', f'SC041/star/M{M}', M, 512)
    S = HERE/'strategies'
    accepted('kite', S/'refit_K64', 'review/kite/refit_K64', 22, 768)
    accepted('kite', S/'raise_kite_M28_K64_from_refit_K64', 'review/kite/M28_K64', 28, 768)
    accepted('circle_to_star', S/'refit_circle_to_star_M31_K64_from_M25', 'review/star/M31_K64', 31, 512)
    accepted('circle_to_star', S/'raise_circle_to_star_M37_K64_from_refit_circle_to_star_M31_K64_from_M25',
             'review/star/M37_K64', 37, 512)
    for i, s in enumerate(out):
        s['id'] = i
    checked = {}
    for s in out:                                   # C3 on the first, middle and last state of each case
        pass
    for case, count in CHECK.items():
        ids = [s['id'] for s in out if s['case'] == case]
        for j in np.linspace(0, len(ids)-1, count).round().astype(int):
            out[ids[j]]['check'] = True
    return out


def shot(curve, n, observations, contrast):
    arrays = {}
    traces, reciprocal, prediction = [], [], []
    for o in observations:
        a = o.acquisition
        state = solve(curve, o.wavenumber, contrast, PointSourceAcquisition(a.sources, a.receivers, a.strength, paired=False), n)
        inverse, _ = ta.reciprocal_traces(state)
        traces.append(state.traces); reciprocal.append(inverse); prediction.append(state.prediction)
    arrays[f'weights_{n}'] = state.curve.arc_length_weights
    arrays[f'traces_{n}'] = np.stack(traces)
    arrays[f'reciprocal_{n}'] = np.stack(reciprocal)
    arrays[f'prediction_{n}'] = np.stack(prediction)
    arrays['wavenumbers'] = np.array([o.wavenumber for o in observations])
    arrays['interior_wavenumbers'] = arrays['wavenumbers']*np.sqrt(contrast)
    arrays['coefficients'] = curve.coefficients
    arrays['length_unit_m'] = np.array(ta.sc.LENGTH)
    return arrays


def atlas(sh, observed, n):
    """`atlas_video.shot_atlas`, keeping q, c and the blocks."""
    unit = float(sh['length_unit_m'])
    h = av.ripple_basis(sh['coefficients'], n, unit)
    F = len(observed)
    heat = np.zeros((av.BAND+1, F)); q_all, c_all, blocks, residuals = [], [], [], []
    for f in range(F):
        scale = np.linalg.norm(observed[f])
        A = av.stacked(ta.jacobian(sh, f, n, h))/scale
        r = av.stacked(np.diag(sh[f'prediction_{n}'][f]) - observed[f])/scale
        d, _ = av.removable(A, r, av.horizon_mm(sh['wavenumbers'][f], unit))
        Q, R = np.linalg.qr(A)
        heat[:, f] = np.sqrt(d)
        q_all.append(Q.T@r); c_all.append(np.abs(np.diag(R))); blocks.append(A); residuals.append(r)
    return dict(heat=heat, q=np.array(q_all), c=np.array(c_all), A=np.array(blocks), r=np.array(residuals))


def work(s):
    started = time.time()
    try:
        observations = ast.catalog_only(s['case'])
        observed = np.array([o.scattered for o in observations])
        curve = history_curve(s['source'], s['iteration']) if s['shot'] else ast.curve_from(s['curve'])
        row = dict(id=s['id'], key=ta.shot_key(curve))
        row['C1_key_matches'] = None if s['shot'] is None else row['key'] == s['shot']
        n = s['nodes']
        sh = shot(curve, n, observations, ac.contrast())
        at = atlas(sh, observed, n)
        active = [int(np.argmin(abs(sh['wavenumbers']-k))) for k in s['active_k']]
        joint = av.joint(dict(blocks=list(at['A']), residuals=list(at['r']), wavenumbers=sh['wavenumbers'],
                              unit=float(sh['length_unit_m'])), active, s['M'])
        row['misfit'] = joint['misfit']
        row['C2_loss_relative'] = None if s['saved_loss'] is None else abs(joint['misfit']**2/2 - s['saved_loss'])/s['saved_loss']
        row.update(inside=joint['inside'], near=joint['near'], active=active)
        extra = {}
        if s.get('check'):
            fine = atlas(shot(curve, 2*n, observations, ac.contrast()), observed, 2*n)
            clip = lambda x: np.log10(np.maximum(x[:av.SHOW+1], 10.0**av.LOW))
            row['C3_max_dex'] = float(np.max(abs(clip(at['heat']) - clip(fine['heat']))))
        np.savez(LOCAL/f"{s['id']:03d}.npz", coefficients=curve.coefficients, joint_column=joint['column'], **at)
        row['seconds'] = time.time() - started
        print('DONE', s['id'], s['track'], s['stage'], s['iteration'], row['C1_key_matches'], row['C2_loss_relative'],
              row.get('C3_max_dex'), round(row['seconds']), flush=True)
        return row
    except Exception:
        print('FAILED', s['id'], traceback.format_exc(), flush=True)
        return dict(id=s['id'], traceback=traceback.format_exc())


def main(workers=2):
    LOCAL.mkdir(exist_ok=True)
    listed = states()
    index = HERE/'atlas_index.json'
    done = {r['id']: r for r in json.loads(index.read_text())['rows']} if index.exists() else {}
    todo = [s for s in listed if s['id'] not in done or 'traceback' in done[s['id']]]
    print('states', len(listed), 'todo', len(todo), flush=True)
    with ProcessPoolExecutor(workers) as pool:
        for row in pool.map(work, todo):
            done[row['id']] = row
            meta = [dict({k: v for k, v in s.items() if k not in ('curve',)}, **done.get(s['id'], {})) for s in listed]
            index.write_text(json.dumps(dict(plan='atlas_plan.md', rows=meta), indent=1, default=float) + '\n')


if __name__ == '__main__':
    main(*map(int, sys.argv[1:2]))
