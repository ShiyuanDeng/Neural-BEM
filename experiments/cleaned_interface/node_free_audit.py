"""NF-001 bounded outsider diagnostics. Run with single-threaded BLAS from repo root.

python -m experiments.cleaned_interface.node_free_audit --output FRESH_DIRECTORY
See docs/iterations/cleaned_interfaces/iteration_16/03_plan.md for advance gates.
"""
import argparse
from dataclasses import replace
import hashlib
from pathlib import Path
import platform
import subprocess
import time

import numpy as np
import scipy
import torch

from experiments.shape_continuation.forward import PointSourceAcquisition
from experiments.shape_continuation.geometry import FourierCurve, grid_size
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage
from .analytic_projection import AnalyticSpectralUpdate, projection_derivatives
from .geometry import resize
from .io import read, write, curve_from
from .modal_geometry import ModalGeometry
from .modal_muller import ModalMuller, ModalSettings, token
from .n_update import curve_certificate
from .nu003 import SpectralProjectedUpdate, spectral_project
from .nu006 import BatchedCertifiedUpdate
from .nu007 import device_certificate
from .physics import Execution
from .problem import Observation
from .runner import deadline

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'results/validation/cleaned_interfaces'


def relative(a, b):
    return float(np.linalg.norm(a-b)/max(np.linalg.norm(b), 1e-300))


def fixtures():
    t = 2*np.pi*np.arange(2048)/2048
    saved = read(BASE/'NU-006/runs/core__hook/accepted.json')['states'][-1]
    return dict(circle=(resize(FourierCurve.circle(1.2, .2+.1j), 8), 3),
                kite=(FourierCurve.from_samples(np.cos(t)+.65*np.cos(2*t)-.65+1.5j*np.sin(t), 24), 7),
                ellipse10=(FourierCurve.from_samples(1.4*np.cos(t)+.14j*np.sin(t), 24), 7),
                saved_hook=(curve_from(saved['curve']), saved['M']))


def tangent_check(curve, M):
    unit, K, count = .05, curve.band, grid_size(max(curve.band, M))
    implementations = dict(fd_cpu=SpectralProjectedUpdate(unit), analytic=AnalyticSpectralUpdate(unit))
    if torch.cuda.is_available():
        implementations['fd_cuda'] = BatchedCertifiedUpdate(unit, device='cuda')
    spaces, seconds = {}, {}
    for name, update in implementations.items():
        update.prepare(curve, M, K)  # warmup; timings include complete subsequent preparations
        seconds[name] = []
        for _ in range(3):
            start = time.perf_counter()
            spaces[name] = update.prepare(curve, M, K)
            seconds[name].append(time.perf_counter()-start)
    exact, fd = spaces['analytic'].derivatives, spaces['fd_cpu'].derivatives
    cols = np.linalg.norm(exact-fd, axis=0)/np.maximum(np.linalg.norm(fd, axis=0), 1e-300)
    direction = np.random.default_rng(701).normal(size=2*M+1)
    direction /= np.linalg.norm(direction)
    derivatives = []
    for h in (1e-5, 1e-6, 1e-7, 1e-8, 1e-9):
        plus, minus = [spectral_project(curve, sign*h*direction, K, count, unit)[0] for sign in (1, -1)]
        derivatives.append(dict(step_m=h, relative=relative((plus-minus)/(2*h), exact@direction)))
    refined = projection_derivatives(curve, M, K, 2*count, unit)
    # Identical finite map for the same a, including independent validity checks.
    step = direction*1e-5
    trial = {}
    for name in ('fd_cpu', 'analytic'):
        try:
            candidate, info = implementations[name].trial(spaces[name], step)
            trial[name] = dict(status='returned', curve=candidate.coefficients, info=info)
        except ValueError as exc:
            trial[name] = dict(status='refused', reason=str(exc))
    identical = (all(t['status'] == 'returned' for t in trial.values()) and
                 np.array_equal(trial['fd_cpu']['curve'], trial['analytic']['curve']))
    return dict(K=K, M=M, count=count, columns_relative_max=float(cols.max()),
                tangent_refinement_relative=relative(exact, refined), finite_differences=derivatives,
                prepare_seconds=seconds, same_finite_trial=identical,
                trial={k: {a: b for a, b in v.items() if a != 'curve'} for k, v in trial.items()},
                passed=bool(cols.max() <= 1e-5 and np.isfinite(exact).all() and identical))


def acquisition():
    t = 2*np.pi*np.arange(12)/12
    return PointSourceAcquisition(7*np.column_stack((np.cos(t), np.sin(t))),
                                 7.3*np.column_stack((np.cos(t+.07), np.sin(t+.07))), 1e-6)


def physics_check(curve, M):
    backend = ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(window_margin=48))
    update = AnalyticSpectralUpdate(.05)
    space = update.prepare(curve, M, curve.band)
    direction = np.random.default_rng(703).normal(size=2*M+1)
    direction /= np.linalg.norm(direction)
    scan = acquisition()
    rows = []
    for k in (2., 2.+.5j):
        obs = Observation(k, scan, np.ones(12, complex)*1e-6, .5e9)
        state = backend.evaluate(curve, obs, .5, token(64))
        jacobian = backend.derivative(state, update, space)
        refined = backend.evaluate(curve, obs, .5, token(96))
        jfine = backend.derivative(refined, update, space)
        errors = []
        for h in (1e-6, 5e-7, 1e-7):
            trials = [update.trial(space, sign*h*direction)[0] for sign in (1, -1)]
            p, m = [backend.evaluate(c, obs, .5, token(96)).prediction for c in trials]
            errors.append(dict(step_m=h, relative=relative((p-m)/(2*h), jfine@direction)))
        rows.append(dict(wavenumber=[k.real, k.imag], field_refinement=relative(state.prediction, refined.prediction),
                         jacobian_refinement=relative(jacobian, jfine), full_trial_fd=errors,
                         passed=bool(errors[-1]['relative'] <= 1e-3)))
    return rows


def lm_check():
    scan = acquisition()
    physics = ModalMuller(Execution(device='cpu', frequency_threads=1),
                         ModalSettings(trace_minimum=16, trace_step=8, window_margin=24))
    target = FourierCurve.circle(1., .01-.01j)
    observations = []
    for k in (1.2, 2.):
        obs = Observation(k, scan, np.ones(12, complex), .5e9)
        observations.append(replace(obs, scattered=physics.evaluate(target, obs, .5, token(32)).prediction))
    stage = FitStage('NF-001-mini-LM', tuple(observations), (.5, .5), (1e-5, 1e-5),
                     3, 8, token(24), token(32), 3, 300)
    start = resize(FourierCurve.circle(1.03, .03+.01j), 8)
    results = {}
    for name, update in [('fd', SpectralProjectedUpdate(.05)), ('analytic', AnalyticSpectralUpdate(.05))]:
        ledger = Ledger(cap=500, seconds=180)
        ledger.begin_stage(stage.label, stage.quota)
        r = fit_stage(start, stage, .5, update, BackendConfig(), ledger, physics=physics)
        results[name] = dict(outcome=r.outcome, accepted_steps=r.accepted_steps,
                             final_loss=r.final_loss, work=r.work, curve=r.curve.coefficients)
    a, b = results['fd'], results['analytic']
    return dict(arms=results, coefficient_relative=relative(a['curve'], b['curve']),
                same_steps=a['accepted_steps'] == b['accepted_steps'], same_outcome=a['outcome'] == b['outcome'],
                same_units=a['work']['work_units'] == b['work']['work_units'])


def adversarial_checks():
    rows = []
    for a in (0., .25, .45, .49, .499, .5, 1.):
        curve = FourierCurve(np.array([0, 0, 0, 1., a], complex))
        for window in (16, 32):
            known_min = max(0., 1-2*a)**2
            row = dict(a=a, window=window, true_min_modulus_squared=known_min,
                       simple_regular=a < .5, arms={})
            implementations = dict(cpu=lambda: curve_certificate(curve, window, max_degree=400))
            if torch.cuda.is_available():
                implementations['cuda'] = lambda: device_certificate(curve, window, 'cuda', max_degree=400)
            for name, evaluate in implementations.items():
                try:
                    cert = evaluate()
                    row['arms'][name] = dict(status='bounded', certificate=cert,
                        valid_against_exact_min=bool(0 < cert['beta'] <= known_min*(1+1e-12)))
                except ValueError as exc:
                    row['arms'][name] = dict(status='inconclusive', reason=str(exc))
            rows.append(row)
    # Orientation is a separate condition from nonzero W.
    try:
        ModalGeometry(FourierCurve(FourierCurve.circle().coefficients[::-1]), 16)
        reversed_status = 'unexpectedly accepted'
    except ValueError as exc:
        reversed_status = str(exc)
    return dict(rows=rows, clockwise_refusal=reversed_status)


def quadrature_checks():
    rows = []
    for aspect in (1., 10., 100.):
        c = FourierCurve(np.array([(1-1/aspect)/2, 0, (1+1/aspect)/2], complex))
        band = 24
        reference = spectral_project(c, np.zeros(7), band, 16384, .05)[0]
        values = []
        for count in (64, 128, 256, 512, 1024, 2048):
            value = spectral_project(c, np.zeros(7), band, count, .05)[0]
            values.append(dict(count=count, relative_to_16384=relative(value, reference)))
        rows.append(dict(aspect_ratio=aspect, band=band, values=values))
    return rows


def gpu_gate_analysis():
    path = BASE/'NU-007-precheck/gap.json'
    old = read(path)
    rows = old['rows']
    host, device = np.array([[r['host'], r['device']] for r in rows]).T
    absolute = np.abs(host-device)
    scaled = absolute/np.maximum(1, np.maximum(np.abs(host), np.abs(device)))
    finite = bool(np.isfinite(host).all() and np.isfinite(device).all())
    return dict(source=str(path.relative_to(ROOT)), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                bounds=len(rows), unique_states=len({(r['case'], r['stage']) for r in rows}),
                finite=finite, worst_relative=float(np.max(absolute/np.maximum(np.abs(host), 1e-300))),
                worst_threshold_scaled=float(scaled.max()), same_side=bool(np.all((host < 1) == (device < 1))),
                minimum_threshold_margin=float(np.minimum(abs(host-1), abs(device-1)).min()),
                diagnostic_pass=bool(finite and len(rows) == 3824 and scaled.max() <= 1e-9
                                     and np.all((host < 1) == (device < 1))),
                adopted=False, fresh_campaign=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    output = parser.parse_args().output
    if output.exists():
        raise FileExistsError('Use a fresh output directory; preserve all prior diagnostics.')
    output.mkdir(parents=True)
    torch.set_num_threads(1)
    source_paths = {*Path(__file__).parent.glob('*.py'), *ROOT.glob('solvers/**/*.py')}
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(source_paths)}
    write(output/'provenance.json', dict(sources=sources, parent_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), python=platform.python_version(),
        numpy=np.__version__, scipy=scipy.__version__, torch=torch.__version__,
        cuda=torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        baseline_tests='76 passed in 86.67 s before edits', sequential=True, controlled_host_load=False))
    results = {}
    started = time.perf_counter()
    with deadline(1200):
        cases = fixtures()
        for name, (curve, M) in cases.items():
            result = tangent_check(curve, M)
            results.setdefault('tangents', {})[name] = result
            write(output/f'tangent_{name}.json', result)
            print(name, 'tangent', result['columns_relative_max'], 'gate', result['passed'], flush=True)
        for name in ('kite', 'saved_hook'):
            curve, M = cases[name]
            result = physics_check(curve, M)
            results.setdefault('physics', {})[name] = result
            write(output/f'physics_{name}.json', result)
            print(name, 'physics', [r['full_trial_fd'][-1]['relative'] for r in result], flush=True)
        for name, fn in [('lm', lm_check), ('adversarial', adversarial_checks),
                         ('quadrature', quadrature_checks), ('gpu_gate', gpu_gate_analysis)]:
            results[name] = fn()
            write(output/f'{name}.json', results[name])
            print(name, 'done', flush=True)
    results['seconds'] = time.perf_counter()-started
    results['analytic_retained_opt_in'] = bool(all(r['passed'] for r in results['tangents'].values()) and
        all(r['passed'] for rows in results['physics'].values() for r in rows) and
        all(results['lm'][key] for key in ('same_steps', 'same_outcome', 'same_units')))
    write(output/'summary.json', results)
    print('complete', results['seconds'], 'analytic retained', results['analytic_retained_opt_in'], flush=True)


if __name__ == '__main__':
    main()
