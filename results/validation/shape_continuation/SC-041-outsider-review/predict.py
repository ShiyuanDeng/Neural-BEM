"""Part 6 (predict_plan.md): entry-state maps committed before each suffix; then score.

    python predict.py run          # prefix -> maps -> commit prediction -> suffix, per shape
    python predict.py score
"""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


im = load('infometric', HERE/'infometric.py')
u = load('uncertainty', HERE/'uncertainty.py')
analyse = load('analyse_part5', HERE/'infometric_analyse.py')
m, c, INFO = im.m, im.c, im.INFO
u.data_norms = lambda case: im.data_norms(INFO, case)

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation.geometry import FourierCurve, arclength_angles

SHAPES = ('hooked_tip', 'fresh_a', 'fresh_b')
PRED = HERE/'predictions'


def fresh(seed):
    rng = np.random.default_rng(seed)
    for _ in range(20000):
        c_ = np.zeros(17, complex); c_[9] = 1.0
        for mm, s in ((-1, .45), (-2, .3), (2, .15), (-3, .15), (3, .08), (-4, .06)):
            c_[8+mm] = s*(rng.uniform(-1, 1) + 1j*rng.uniform(-1, 1))
        curve = FourierCurve(0.8*c_)
        try:
            curve.validate()
        except ValueError:
            continue
        k = np.asarray(curve.nodes(8192).curvatures)
        if k.min() < 0 and 2.0 <= 1e3*c.sc.LENGTH/k.max() <= 6.0:
            z = curve.values(8192)
            coefficients = np.array(curve.coefficients); coefficients[8] -= z.mean()
            return FourierCurve(coefficients)
    raise RuntimeError(seed)


def prepare_and_prefix(case):
    try:
        m.HERE = INFO
        folder = INFO/'inputs'/case
        if case != 'hooked_tip' and not (folder/'truth.json').exists():
            folder.mkdir(parents=True, exist_ok=True)
            c.write(folder/'truth.json', c.ast.curve_record(fresh({'fresh_a': 47001, 'fresh_b': 47002}[case])))
            assert m.generate(case), case
        prefix = INFO/'runs'/case/'clean'/'prefix'/'result.json'
        if not prefix.exists():
            m.fit_path(case, 'clean', 'none', prefix=True)
        pre = c.sc.read(prefix)
        if pre.get('outcome') != 'COMPLETED_SCHEDULE':
            return dict(case=case, failed='prefix', outcome=pre.get('outcome'))
        entry = c.ast.curve_from(pre['curve'])
        observations, _ = m.catalog(case, 'clean')
        with geometry_validation('cache'):
            s, w, F = im.sensitivity(entry, 512, observations, INFO, case)
            maps, _ = u.ratio_map(entry, 512, case)
        n = entry.nodes(512)
        arc = n.arc_length_weights/np.sum(n.arc_length_weights)
        su = 2*np.pi*np.arange(u.SAMPLES)/u.SAMPLES
        Fu = np.interp(su, np.sort(s), F[np.argsort(s)], period=2*np.pi)
        pct = lambda v: np.array([np.mean(v < x) for x in v])      # uniform arclength samples
        record = dict(case=case, entry_curve=c.ast.curve_record(entry), samples=u.SAMPLES,
                      F=Fu.tolist(), rho_white=maps['P1_white_1mm'].tolist(),
                      bottom10_F=(pct(Fu) < .10).tolist(), bottom10_rho=(pct(maps['P1_white_1mm']) < .10).tolist())
        PRED.mkdir(exist_ok=True)
        (PRED/f'{case}.json').write_text(json.dumps(record) + '\n')
        return dict(case=case, prediction=str(PRED/f'{case}.json'))
    except Exception:
        return dict(case=case, failed=traceback.format_exc())


def suffix(case):
    try:
        m.HERE = INFO
        return m.fit_path(case, 'clean', 'none')
    except Exception:
        return dict(case=case, failed=traceback.format_exc())


def commit(path, case):
    root = HERE.parents[3]
    subprocess.run(['git', 'add', str(path)], cwd=root, check=True)
    subprocess.run(['git', 'commit', '-q', '-m',
                    f'SC-041 outsider review part 6: {case} prediction committed before its suffix\n\n'
                    'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n'
                    'Claude-Session: https://claude.ai/code/session_018kMjPkDFjupLLhQqaAhTvB'], cwd=root, check=True)
    subprocess.run(['git', 'push', '-q', 'origin', 'HEAD:feature/shape-frequency-continuation'], cwd=root)
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, capture_output=True, text=True).stdout.strip()
    print('PREDICTION COMMITTED', case, head, flush=True)
    return head


def run():
    log = {}
    with ProcessPoolExecutor(3) as pool:
        pending = {pool.submit(prepare_and_prefix, k): ('prefix', k) for k in SHAPES}
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for f in done:
                kind, case = pending.pop(f)
                row = f.result()
                if kind == 'prefix':
                    if 'failed' in row:
                        print('PREFIX FAILED', case, row['failed'], flush=True)
                        log[case] = row
                        continue
                    log[case] = dict(prediction_commit=commit(row['prediction'], case))
                    pending[pool.submit(suffix, case)] = ('suffix', case)
                    print('SUFFIX STARTED', case, flush=True)
                else:
                    log[case]['suffix_outcome'] = row.get('outcome')
                    print('SUFFIX DONE', case, row.get('outcome'), row.get('score'), flush=True)
    (HERE/'predict_log.json').write_text(json.dumps(log, indent=1) + '\n')


def score():
    out = dict(plan='predict_plan.md', shapes={})
    for case in SHAPES:
        f = INFO/'runs'/case/'clean'/'none'/'result.json'
        p = PRED/f'{case}.json'
        if not (f.exists() and p.exists()):
            out['shapes'][case] = 'missing'; continue
        final = c.ast.curve_from(c.sc.read(f)['curve'])
        truth = c.ast.curve_from(c.sc.read(INFO/'inputs'/case/'truth.json'))
        feat = analyse.features(final, truth)
        pred = json.loads(p.read_text())
        entry = c.ast.curve_from(pred['entry_curve'])
        z = u.analyse.arclength_series(entry, lambda nd: nd.points[:, 0] + 1j*nd.points[:, 1])[::2]
        i = int(np.argmin(abs(z - complex(*feat['sharpest_point']))))
        F, rho = np.array(pred['F']), np.array(pred['rho_white'])
        out['shapes'][case] = dict(sharpest_spurious=feat['sharpest_spurious'], min_radius_mm=feat['min_radius_mm'],
                                   rms_mm=feat['rms_mm'], hausdorff_mm=feat['hausdorff_mm'],
                                   F_percentile=float(100*np.mean(F < F[i])),
                                   rho_percentile=float(100*np.mean(rho < rho[i])))
    counting = [v for v in out['shapes'].values() if isinstance(v, dict) and v['sharpest_spurious']]
    for key, name in (('F_percentile', 'F'), ('rho_percentile', 'rho')):
        inside = [v[key] < 10 for v in counting]
        outside25 = [v[key] >= 25 for v in counting]
        out[f'verdict_{name}'] = ('inconclusive' if len(counting) < 2 else 'supported' if all(inside) else
                                  'refuted' if sum(outside25) >= len(counting)/2 else 'inconclusive')
    out['counting_shapes'] = len(counting)
    (HERE/'predict_score.json').write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    run() if sys.argv[1] == 'run' else score()
