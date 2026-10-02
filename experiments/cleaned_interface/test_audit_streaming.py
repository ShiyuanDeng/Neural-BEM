"""Single-curve regressions for the maintained runner's audit memory lifetime."""
from dataclasses import replace
import numpy as np
import pytest

from experiments.shape_continuation.forward import PointSourceAcquisition
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, Objective
from .geometry import ProjectedUpdate, resize
from .io import read
from .physics import Execution, NodalKress
from .policy import CumulativePolicy
from .problem import Observation, Problem
from . import runner


def fixture():
    angles = np.linspace(0, 2*np.pi, 12, endpoint=False)
    scan = PointSourceAcquisition(5*np.column_stack((np.cos(angles), np.sin(angles))),
        5.5*np.column_stack((np.cos(angles+.03), np.sin(angles+.03))), 1e-6)
    real = tuple(Observation(k, scan, np.ones(12, complex)*1e-6, f) for k, f in
                 zip((.6, .9, 1.2, 1.8, 2.4), (.25e9, .375e9, .5e9, .75e9, 1e9)))
    damped = tuple(replace(o, wavenumber=o.wavenumber*(1+.25j)) for o in real)
    return Problem(resize(FourierCurve.circle(1.02, .03+.02j), 8), real, damped, .5)


def reference_dense_audit(curve, stage, config, problem, physics, update, seconds):
    """Pre-streaming formulas retained as an independent numerical reference."""
    count = len(problem.real)
    stage = replace(stage, observations=problem.real, weights=tuple(np.ones(count)/count), curve_modes=curve.band,
                    discrepancy_tolerances=tuple(1e-5 if o.frequency_hz <= .5e9 else 1e-7 for o in problem.real))
    ledger = Ledger(cap=6*count+16, seconds=seconds, endpoint_reserve=0)
    coarse = Objective(stage, problem.contrast, config, ledger, physics=physics)
    fine = Objective(replace(stage, nodes=stage.refined_nodes, refined_nodes=physics.refine_resolution(stage.refined_nodes)),
                     problem.contrast, config, ledger, physics=physics)
    low, high = coarse.production(curve, 'audit_base'), fine.production(curve, 'audit_fine')
    space = update.prepare(curve, stage.update_modes, curve.band)
    ja, jb = coarse.jacobian(low, update, space), fine.jacobian(high, update, space)
    fields = np.linalg.norm(low.prediction-high.prediction, axis=0)/np.linalg.norm(high.prediction, axis=0)
    colnorm = np.linalg.norm(jb, axis=0)
    derivative = np.linalg.norm(ja-jb, axis=0)/np.maximum(colnorm, 1e-30)
    direction = np.random.default_rng(42001).normal(size=ja.shape[1]); direction /= np.linalg.norm(direction)
    plus, minus = [fine.production(update.trial(space, sign*1e-7*direction)[0], 'audit_fd') for sign in (1, -1)]
    fd = (plus.residual-minus.residual)/2e-7
    error = float(np.linalg.norm(fd-jb@direction)/max(np.linalg.norm(fd), 1e-30))
    return dict(passed=bool(np.all(fields <= stage.discrepancy_tolerances) and max(derivative) <= 1e-3 and error <= 1e-3),
        field_relative=fields, jacobian_relative=derivative, jacobian_column_norm=colnorm,
        full_trial_fd_relative=error, fine_loss=high.loss,
        relative_residual=np.linalg.norm(high.prediction-fine.observed, axis=0)/np.linalg.norm(fine.observed, axis=0),
        work=ledger.snapshot())


@pytest.mark.parametrize('solver', ['nodal', 'modal'])
def test_streamed_audit_is_bitwise_equivalent_for_maintained_services(solver):
    p = fixture()
    execution = Execution(device='cpu', frequency_threads=1)
    if solver == 'nodal':
        physics = NodalKress(execution)
        nodes, refined = 64, 128
    else:
        from .modal_muller import ModalMuller, ModalSettings, token
        physics = ModalMuller(execution, ModalSettings(trace_minimum=16, trace_step=8, window_margin=16))
        nodes, refined = token(16), token(24)
    stage = FitStage('audit', p.real, (.2,)*5, (1e-5,)*3+(1e-7,)*2, 3, 8, nodes, refined, 1)
    args = (p.initial, stage, BackendConfig(), p, physics, ProjectedUpdate(.05), 300.)
    previous = reference_dense_audit(*args)
    current = runner.audit(*args)
    for name in previous.keys()-{'work'}:
        np.testing.assert_array_equal(current[name], previous[name], err_msg=name)
    for name in ('work_units', 'solves', 'reciprocal_batches', 'failed'):
        assert current['work'][name] == previous['work'][name]
    assert current['work']['work_units'] == 30


def test_failed_initial_audit_is_not_repeated_for_identical_endpoint(monkeypatch, tmp_path):
    calls = []
    def refuse(*args):
        calls.append(args[0].coefficients.copy())
        return dict(passed=False, traceback='deliberate initial numerical refusal',
                    work=dict(work_units=7, solves={'audit': 7}, reciprocal_batches={}, failed={}), seconds=1.)
    monkeypatch.setattr(runner, 'audit', refuse)
    policy = CumulativePolicy(prefix_frequencies_hz=(.375e9, .5e9, .75e9, 1e9))
    row = runner.fit(fixture(), physics=NodalKress(Execution(device='cpu', frequency_threads=1)),
                     policy=policy, output=tmp_path)
    assert len(calls) == 1
    assert row['outcome'] == 'EXCEPTION' and not row['initial_audit_passed'] and not row['final_audit_passed']
    assert row['audit_units'] == row['total_units'] == 7 and row['fit_work'] is None
    final = read(tmp_path/'final_audit.json')
    assert final['reused_identical_initial_audit'] is True
    assert final['work']['work_units'] == 0
    assert final['original_audit_work']['work_units'] == 7
