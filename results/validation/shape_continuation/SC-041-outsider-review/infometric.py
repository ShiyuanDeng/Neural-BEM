"""Part 5 (infometric_plan.md): sensitivity-weighted step metric vs mass and curvature metrics.

    python infometric.py generate          # hooked_tip data (and kite inputs file)
    python infometric.py run [workers]     # hooked_tip prefix, then 5 cases x 3 arms
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace, asdict
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent
INFO = HERE / 'infometric'
SC044 = RESULTS / 'SC-044-noisy-fresh-cases'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load('sc044_run', SC044/'run.py')         # SC-044 machinery, unchanged; its folder is re-pointed per call
m.verify = lambda: None                        # SC-044's source-hash guard refers to its own bundle
c = m.c
collect = load('atlas_collect', HERE/'atlas_collect.py')
sc038 = load('sc038_run', RESULTS/'SC-038-update-band-release/run.py')

from ordered_boundary.validation_cache import geometry_validation
from experiments.shape_continuation.geometry import FourierCurve, arclength_angles
from experiments.shape_continuation.lm_backend import Ledger, fit_stage, NORMAL_RETURN, STAGE_QUOTA, stage_record

CASES = {  # case: (profile, folder holding inputs/ and prefix, nodes)
    'kite': ('clean', INFO, 768),
    'deep_c': ('clean', SC044, 512),
    'deep_c@noise_seed_0': ('noise_seed_0', SC044, 512),
    'asymmetric_lobes': ('clean', SC044, 512),
    'hooked_tip': ('clean', INFO, 512),
}
ARMS = ('A0_mass', 'A1_sensitivity', 'A2_curvature')
STAGE_SECONDS = 1200


def hooked_tip_truth():
    rng = np.random.default_rng(47000)
    for trial in range(42):
        c_ = np.zeros(17, complex); c_[9] = 1.0
        for mm, s in ((-1, .45), (-2, .3), (2, .15), (-3, .15), (3, .08), (-4, .06)):
            c_[8+mm] = s*(rng.uniform(-1, 1) + 1j*rng.uniform(-1, 1))
    c_ = 0.8*c_
    z = FourierCurve(c_).values(8192)
    c_[8] -= z.mean()
    return FourierCurve(c_)


def generate():
    (INFO/'inputs'/'hooked_tip').mkdir(parents=True, exist_ok=True)
    (INFO/'inputs'/'kite').mkdir(parents=True, exist_ok=True)
    truth = hooked_tip_truth()
    c.write(INFO/'inputs'/'hooked_tip'/'truth.json', c.ast.curve_record(truth))
    m.HERE = INFO
    ok = m.generate('hooked_tip')
    values = np.array([o.scattered for o in c.ast.catalog_only('kite')]).T          # (pairs, F)
    c.write(INFO/'inputs'/'kite'/'clean.json', dict(observed_real=values.real, observed_imag=values.imag,
            sigma_real_imag=np.zeros(values.shape[1]), profile='clean', relative_complex_rms=0.))
    c.write(INFO/'inputs'/'kite'/'truth.json', c.sc.read(c.ast.source_folder('kite')/'truth.json'))
    print('generated; hooked_tip data qualified:', ok, flush=True)


def data_norms(folder, case):
    d = c.sc.read(folder/'inputs'/case/'clean.json')
    values = np.array(d['observed_real']) + 1j*np.array(d['observed_imag'])
    return np.linalg.norm(values, axis=0), values.shape[0]


class MetricUpdate(c.reference.ProjectedUpdate):
    """SC-035 projected update with a selectable step metric (mass, sensitivity-weighted mass, curvature)."""

    def __init__(self, length_unit_m, mode):
        super().__init__(length_unit_m)
        self.mode = mode
        self.weight_s = self.weight_w = None

    def set_weight(self, s, w):
        order = np.argsort(s)
        self.weight_s, self.weight_w = np.asarray(s)[order], np.asarray(w)[order]

    def weight(self, s):
        return np.interp(np.mod(s, 2*np.pi), self.weight_s, self.weight_w, period=2*np.pi)

    def metric(self, space, kind, smoothing_m=None):
        n = space.curve.nodes(space.count)
        basis = self.velocities(space, n)*self.length_unit_m
        w = n.arc_length_weights/n.perimeter
        if kind == 'mass':
            if self.mode == 'A1_sensitivity':
                s, _ = arclength_angles(n)
                w = w*self.weight(s)
            return basis.T@(w[:, None]*basis)
        if kind != 'curvature':
            raise ValueError(kind)
        count = n.num_nodes
        freq = np.fft.fftfreq(count, 1/count)
        d = lambda f: np.fft.ifft(1j*freq[:, None]*np.fft.fft(f, axis=0), axis=0).real
        speed = (np.asarray(n.speeds)*self.length_unit_m)[:, None]       # metres per radian of parameter
        h_s = d(basis)/speed
        h_ss = d(h_s)/speed
        kappa = (np.asarray(n.curvatures)/self.length_unit_m)[:, None]
        change = -(h_ss + kappa**2*basis)
        return basis.T@(w[:, None]*basis) + smoothing_m**4*(change.T@(w[:, None]*change))


def sensitivity(curve, nodes, observations, folder, case):
    sh = collect.shot(curve, nodes, observations, c.ac.contrast())
    norms, pairs = data_norms(folder, case)
    sigma = 0.01*norms/np.sqrt(2*pairs)
    k, ki = sh['wavenumbers'], sh['interior_wavenumbers']
    F = np.zeros(nodes)
    for f in range(len(observations)):
        u, v = sh[f'traces_{nodes}'][f, :nodes], sh[f'reciprocal_{nodes}'][f, :nodes]
        F += np.sum(np.abs((ki[f]**2 - k[f]**2)*u*v)**2, axis=1)/sigma[f]**2
    n = curve.nodes(nodes)
    s, _ = arclength_angles(n)
    arc = n.arc_length_weights/np.sum(n.arc_length_weights)
    w = np.clip(np.sqrt(F/(arc@F)), 0.1, 10.0)
    return s, w, F


def stages_for(key):
    profile, folder, nodes = CASES[key]
    case = key.split('@')[0]
    m.HERE = folder
    stages, configs = m.make_stages(case, profile, 'none')
    if nodes != 512:
        stages = [replace(s, nodes=nodes, refined_nodes=2*nodes) for s in stages]
    return case, profile, folder, stages, configs


def entry_curve(key):
    case, profile, folder, _, _ = stages_for(key)
    if key == 'kite':
        return sc038.prefix('kite')[0]
    return c.ast.curve_from(c.sc.read(folder/'runs'/case/profile/'prefix'/'result.json')['curve'])


def run_prefix(key):
    case, profile, folder, _, _ = stages_for(key)
    m.HERE = folder
    return m.fit_path(case, profile, 'none', prefix=True)


def run_arm(job):
    key, arm = job
    out = INFO/'runs'/key.replace('@', '_')/arm
    out.mkdir(parents=True, exist_ok=False)
    try:
        case, profile, folder, stages, configs = stages_for(key)
        stages, configs = stages[4:6], configs[4:6]                         # release_M11, release_M19
        curve = entry_curve(key)
        update = MetricUpdate(c.sc.LENGTH, arm)
        accepted, records, extra, total = [], [], [], 0
        c.write(out/'configuration.json', dict(case=key, arm=arm, stages=[stage_record(s) for s in stages],
                initial=c.ast.curve_record(curve), stage_seconds=STAGE_SECONDS, damping_rule='hanke'))
        for stage, config in zip(stages, configs):
            config = replace(config, damping_rule='hanke', metric='curvature' if arm == 'A2_curvature' else 'mass')
            curve = c.resize(curve, stage.curve_modes)
            if arm == 'A1_sensitivity' or not records:                     # entry map also serves P1 for A0
                started = time.time()
                with geometry_validation('cache'):
                    s, w, F = sensitivity(curve, stage.nodes, stage.observations, folder, case)
                update.set_weight(s, w)
                extra.append(dict(stage=stage.label, field_solves=len(stage.observations),
                                  reciprocal_solves=len(stage.observations), seconds=time.time()-started))
                np.savez(out/f'weight_{stage.label}.npz', s=s, w=w, F=F, coefficients=curve.coefficients)
            ledger = Ledger(cap=stage.quota+1, seconds=STAGE_SECONDS)
            ledger.begin_stage(stage.label, stage.quota)
            base = total

            def checkpoint(i, e, stage=stage, ledger=ledger, base=base):
                accepted.append(dict(stage=stage.label, M=stage.update_modes, iteration=i, loss=e.loss,
                                     total_units=base+ledger.units, curve=c.ast.curve_record(e.curve)))
                c.write(out/'accepted.json', dict(states=accepted))

            with geometry_validation('cache'):
                result = fit_stage(curve, stage, c.ac.contrast(), update, config, ledger, on_accept=checkpoint)
            curve = result.curve
            total += ledger.units
            records.append(dict(stage=stage.label, M=stage.update_modes, outcome=result.outcome, stop=result.stop_reason,
                                detail=result.detail, initial_loss=result.initial_loss, final_loss=result.final_loss,
                                units=ledger.units, total_units=total))
            print('STAGE', key, arm, stage.label, result.outcome, f'{result.final_loss:.4g}', ledger.units, flush=True)
            if result.outcome not in (NORMAL_RETURN, STAGE_QUOTA):
                break
        row = dict(case=key, arm=arm, stages=records, total_units=total, extra_sensitivity_cost=extra,
                   curve=c.ast.curve_record(curve))
        c.write(out/'result.json', row)
        print('DONE', key, arm, flush=True)
        return row
    except Exception:
        row = dict(case=key, arm=arm, traceback=traceback.format_exc())
        c.write(out/'failure.json', row)
        print('FAILED', key, arm, row['traceback'], flush=True)
        return row


def run(workers=2):
    jobs = [(k, a) for k in CASES if k != 'hooked_tip' for a in ARMS]
    with ProcessPoolExecutor(workers) as pool:
        prefix = pool.submit(run_prefix, 'hooked_tip')
        futures = [pool.submit(run_arm, j) for j in jobs]
        pre = prefix.result()
        print('PREFIX hooked_tip', pre.get('outcome'), pre.get('score'), flush=True)
        if pre.get('outcome') == 'COMPLETED_SCHEDULE':
            futures += [pool.submit(run_arm, ('hooked_tip', a)) for a in ARMS]
        for f in as_completed(futures):
            f.result()


if __name__ == '__main__':
    if sys.argv[1] == 'generate':
        generate()
    else:
        run(*map(int, sys.argv[2:3]))
