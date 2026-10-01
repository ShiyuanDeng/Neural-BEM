"""Bounded checks of the modal Müller service against nodal Kress and its own contract."""
from dataclasses import replace

import numpy as np
import pytest

from experiments.shape_continuation import forward as F
from experiments.shape_continuation.atlas_cases import c_shape_curve
from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, fit_stage
from . import benchmark as b
from . import physics
from .geometry import ProjectedUpdate, resize
from .modal_geometry import ModalGeometry
from .modal_muller import ModalMuller, ModalSettings, register, token
from .modal_operator import muller_matrix, radial_functions, scaled_hankel
from .physics import Execution, NodalKress
from .problem import Observation

K25 = 6.417188604442469  # exterior wavenumber at 2.5 GHz, package units


def relative(a, c):
    return float(np.linalg.norm(a-c)/np.linalg.norm(c))


def modal(**settings):
    return ModalMuller(Execution(device='cpu', frequency_threads=1), ModalSettings(**settings))


def c_curve(band=24):
    return resize(c_shape_curve(), band)


def test_scalar_radial_functions_match_high_precision():
    mp = pytest.importorskip('mpmath')
    mp.mp.dps = 40
    r2 = np.array([1e-10, 1e-4, .05, .9, 4., 12.])
    for ko in (K25, K25*(1+.25j)):
        ki = ko*np.sqrt(13.3)
        exact = []
        for x in r2:
            rr = mp.mpf(float(x))
            def split(k):
                k = mp.mpc(k)
                p = -mp.besselj(0, k*mp.sqrt(rr))/(4*mp.pi)
                q = .25j*mp.hankel1(0, k*mp.sqrt(rr))-p*mp.log(rr)
                dp = k*mp.besselj(1, k*mp.sqrt(rr))/(8*mp.pi*mp.sqrt(rr))
                dq = -1j*k*mp.hankel1(1, k*mp.sqrt(rr))/(8*mp.sqrt(rr))-dp*mp.log(rr)-p/rr
                return p, q, dp, dq
            po, qo, dpo, dqo = split(ko)
            pi, qi, dpi, dqi = split(ki)
            exact.append([complex(v) for v in (po-pi, qo-qi, dpo-dpi, dqo-dqi+(po-pi)/rr,
                                               mp.mpc(ko)**2*po-mp.mpc(ki)**2*pi, mp.mpc(ko)**2*qo-mp.mpc(ki)**2*qi)])
        values = radial_functions(r2, ko, ki)
        for got, want in zip(values, np.array(exact).T):
            assert relative(got, want) < 1e-13


def test_matrix_matches_projected_nodal_oracle_at_high_contrast():
    from experiments.modal_muller_research.modal import ModalSystem
    from gpr_bem_kress.execution import execution
    from gpr_bem_kress.system import build_muller_system
    curve, cutoff, count = c_shape_curve(), 64, 1024
    ki = K25*np.sqrt(13.3)
    nodes = curve.nodes(count)
    with execution(kernels='real_bessel'):
        dense = build_muller_system(nodes, K25, ki).system_matrix
    oracle = ModalSystem.from_nodal(dense, np.zeros((2*count, 1)), np.zeros((1, 2*count)), [nodes]).a
    index = np.r_[np.arange(-cutoff, cutoff+1) % count, count+np.arange(-cutoff, cutoff+1) % count]
    matrix, info = muller_matrix(ModalGeometry(curve, 128), K25, ki, cutoff)
    assert relative(matrix, oracle[np.ix_(index, index)]) < 1e-12
    assert info['amplification'] < 10


def test_scaled_hankel_matches_high_precision_beyond_float_range():
    mp = pytest.importorskip('mpmath')
    mp.mp.dps = 40
    for x, scale in ((.45, .17), (1.3, .1), (4.5, 2.2), (3+.5j, 1.7), (26.+.3j, 3.)):
        t = scaled_hankel(np.array([x]), scale, 260)[:, 0]
        for order in (0, 1, 40, 150, 260):  # H_260(0.45) is far beyond float64
            want = complex(mp.hankel1(order, mp.mpc(x))*mp.mpc(scale)**order/mp.factorial(order))
            assert abs(t[order]-want) <= 1e-13*abs(want)


def test_graf_reaches_offset_start_near_the_acquisition():
    """CI-001-modal refused this start (rho/d=0.87 needs ~248 orders); Kress 1024 is the oracle."""
    p = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == 'modal__c4__opposite_c'), b.DEFAULT_OUTPUT)
    curve = FourierCurve.circle(1.3, 3.6-2.8j)
    nodal = NodalKress(Execution(device='cpu', frequency_threads=1))
    for o in (p.real[0], p.real[-1]):
        prediction = modal().evaluate(curve, o, p.contrast, token(64))
        assert prediction.diagnostics['graf_order'] > 200
        assert relative(prediction.prediction, nodal.evaluate(curve, o, p.contrast, 1024).prediction) < 1e-11


def test_certificate_refuses_crossing_and_clockwise_curves_and_accepts_the_c():
    with pytest.raises(ValueError):
        ModalGeometry(FourierCurve(np.array([0, 0, 0, 1, 1], complex)), 32)  # z=w+w^2 crosses itself
    with pytest.raises(ValueError, match='counterclockwise'):
        ModalGeometry(FourierCurve(np.array([1, 0, 0], complex)), 32)
    interval = ModalGeometry(c_curve(), 64).log_interval
    certificate = interval['certificate']
    assert 0 < interval['lower'] <= certificate['lower'] < interval['sampled_minimum'] <= interval['upper']
    assert certificate['residual']+certificate['allowance'] < 1e-5


@pytest.mark.parametrize('damping', [0., .25])
def test_predictions_and_complete_trial_derivative(damping):
    backend = modal()
    scan = b.acquisition()
    k = 1.2*(1+1j*damping)
    observation = Observation(k, scan, np.ones(24, complex), .5e9)
    curve = resize(FourierCurve.circle(1.02, .03+.02j), 8)
    state = backend.evaluate(curve, observation, .5, token(64))
    if damping:
        from experiments.modal_atlas.damped import solve
        reference = solve(curve, k, .5, scan, 512).prediction
    else:
        reference = F.solve(curve, k.real, .5, scan, 512, execution_backend='cpu').prediction
    assert relative(state.prediction, reference) < 1e-11
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, 3, 8)
    jacobian = backend.derivative(state, update, space)
    direction = np.random.default_rng(42).normal(size=7)
    direction /= np.linalg.norm(direction)
    plus, minus = [backend.evaluate(update.trial(space, s*1e-7*direction)[0], observation, .5, token(64)).prediction
                   for s in (1, -1)]
    fd = (plus-minus)/2e-7
    assert relative(jacobian@direction, fd) < 1e-5
    assert not hasattr(state, 'curve') and not hasattr(state, 'traces')
    with pytest.raises(ValueError, match='different curves'):
        backend.derivative(state, update, update.prepare(resize(FourierCurve.circle(1.1), 8), 3, 8))


def test_hadamard_jacobian_matches_nodal_at_high_contrast():
    curve = c_curve()
    scan = b.acquisition()
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, 12, 24)
    k = K25*.4
    reference = F.solve(curve, k, 13.3, scan, 1024, execution_backend='cpu')
    expected = F.shape_jacobian(reference, update.velocities(space, reference.curve))
    backend = modal()
    state = backend.evaluate(curve, Observation(k, scan, reference.prediction, 1e9), 13.3, token(64))
    assert relative(state.prediction, reference.prediction) < 1e-11
    assert relative(backend.derivative(state, update, space), expected) < 1e-10


def test_frontier_profile_matches_nodal():
    curve = resize(FourierCurve.circle(1.02, .03+.02j), 8)
    scan = b.acquisition()
    observation = Observation(K25*.4, scan, np.ones(24, complex), 1e9)
    got = modal().observable_frontier(curve, observation, 4., 9, .01)
    want = NodalKress(Execution(device='cpu', frequency_threads=1)).observable_frontier(curve, observation, 4., 9, .01)
    assert got['frontier'] == want['frontier']
    assert relative(got['column_profile'], want['column_profile']) < 1e-8


def test_threads_do_not_change_values():
    scan = b.acquisition()
    curve = c_curve(12)
    observations = [Observation(K25*f, scan, np.ones(24, complex), f*2.5e9) for f in (.2, .3, .4)]
    values = []
    for threads in (1, 3):
        backend = ModalMuller(Execution(device='cpu', frequency_threads=threads))
        with backend.ordered_calls(lambda o: backend.evaluate(curve, o, 13.3, token(64)).prediction, observations) as calls:
            values.append(np.stack([call() for call in calls]))
        assert backend.receipt()['counts']['geometry'] == 1
    np.testing.assert_array_equal(*values)


def test_lm_stage_reproduces_nodal_decisions():
    scan = b.acquisition()
    target = FourierCurve.circle(1.0)
    values = F.solve(target, 1.2, .5, scan, 512, execution_backend='cpu').prediction
    stage = FitStage('equivalence', (Observation(1.2, scan, values, .5e9),), (1.,), (1e-5,), 3, 8, token(64), token(96), 3, 300)
    nodal_stage = replace(stage, nodes=128, refined_nodes=256)
    curve = resize(FourierCurve.circle(1.03, .01j), 8)
    rows = []
    for physics_service, fit in ((NodalKress(Execution(device='cpu', frequency_threads=1)), nodal_stage),
                                 (modal(), stage)):
        ledger = Ledger(cap=400, seconds=300)
        ledger.begin_stage(fit.label, fit.quota)
        rows.append(fit_stage(curve, fit, .5, ProjectedUpdate(.05), BackendConfig(), ledger, physics=physics_service))
    a, c = rows
    assert a.accepted_steps == c.accepted_steps and a.outcome == c.outcome
    assert [t['status'] for t in a.trials] == [t['status'] for t in c.trials]
    assert np.max(np.abs(a.curve.coefficients-c.curve.coefficients)) < 1e-9
    assert abs(a.final_loss/c.final_loss-1) < 1e-6


def test_registration_profile_and_capabilities(monkeypatch):
    monkeypatch.setattr(physics, '_BACKENDS', dict(physics._BACKENDS))
    with pytest.raises(NotImplementedError):
        physics.make_backend('modal_muller')
    register()
    register()
    backend = physics.make_backend('modal_muller', Execution(device='cpu'))
    assert isinstance(backend, ModalMuller)
    assert [backend.resolution_profile(k)['K_trace'] for k in (1, 20, 64, 128, 192)] == [64, 64, 64, 96, 128]
    profile = backend.resolution_profile(192)
    assert profile['refined'] == backend.refine_resolution(profile['production']) == token(160)
    p = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == 'modal__c4__development_c'), b.DEFAULT_OUTPUT)
    FitStage('token_guard', p.real, (1/19,)*19, (1e-7,)*19, 67, 192, profile['production'], profile['refined'], 1)
    with pytest.raises(ValueError, match='multiples'):
        backend.evaluate(FourierCurve.circle(), p.real[0], p.contrast, 100)
    backend.validate(p)
    monkeypatch.setattr(physics.CA, 'available', lambda: False)
    with pytest.raises(RuntimeError, match='Explicit CUDA'):
        ModalMuller(Execution(device='cuda')).validate(p)
    with pytest.raises(RuntimeError, match='Explicit CUDA'):
        ModalMuller(Execution(device='cuda')).evaluate(FourierCurve.circle(), p.real[0], p.contrast, token(64))
    assert ModalMuller(Execution(device='auto')).evaluate(
        FourierCurve.circle(), p.real[0], p.contrast, token(64)).diagnostics['fallback'] == 'CUDA unavailable'
    with pytest.raises(ValueError, match='material'):
        backend.validate(replace(p, material='variable_density'))
    with pytest.raises(ValueError, match='Graf'):
        far = FourierCurve.circle(1., 5.5+0j)
        backend.evaluate(far, p.real[0], p.contrast, token(64))


def test_runner_end_to_end_with_modal_service_on_nodal_data(tmp_path):
    """Localization, cleanup, frontier and both audits through the modal service."""
    from .policy import CumulativePolicy, LocalizationRule, Operation
    from .problem import Problem
    from .runner import fit

    class ShortPolicy(CumulativePolicy):
        def operations(self, p, service):
            ops = super().operations(p, service)
            fits = [o for o in ops if o.kind == 'fit']
            warm = replace(fits[0], stage=replace(fits[0].stage, iterations=1))
            following = replace(fits[1], stage=replace(fits[1].stage, iterations=1))
            clean = Operation('cleanup', 'test_cleanup', 'exercise exact cleanup', 'after warm-up', 'next fit',
                              details=dict(retained_band=4, storage_band=8))
            return (ops[0], ops[1], warm, clean, following, ops[-2], ops[-1])

        def tail(self, p, service, frontier):
            return ()
    nodal = NodalKress(Execution(device='cpu', frequency_threads=1))
    template = b.fitting_problem(next(r for r in b.descriptors() if r['id'] == 'modal__c4__development_c'),
                                 b.DEFAULT_OUTPUT)
    truth = FourierCurve.circle()
    real = tuple(replace(o, scattered=nodal.evaluate(truth, o, .5, 512).prediction) for o in template.real)
    damped = tuple(replace(o, scattered=nodal.evaluate(truth, o, .5, 512).prediction) for o in template.damped)
    p = Problem(FourierCurve.circle(1.02), real, damped, .5)
    policy = ShortPolicy(storage_band=24, frontier_top=7,
        localization=LocalizationRule(center_min_m=.5, center_max_m=.5, center_step_m=.004,
            radius_min_m=.05, radius_max_m=.05, radius_step_m=.001, max_starts=1, refinement_iterations=1))
    service = ModalMuller(Execution(device='cpu', frequency_threads=4))
    result = fit(p, physics=service, policy=policy, output=tmp_path)
    assert result['outcome'] == 'COMPLETED_SCHEDULE', result['detail']
    assert result['initial_audit_passed'] and result['final_audit_passed']
    assert result['localization']['units'] == 6 and result['localization']['selected_backend'] == 'modal_muller'
    assert {e['operation']['operation'] for e in result['decisions']} == {'audit', 'localize', 'fit', 'cleanup', 'frontier'}
    receipt = result['physics']
    assert receipt['solver'] == 'modal_muller' and receipt['counts']['failed_evaluations'] == 0
    assert set(receipt['devices']) == {'cpu-modal', 'cpu-mie'}


def cuda_or_skip():
    torch = pytest.importorskip('torch')
    if not torch.cuda.is_available():
        pytest.skip('CUDA unavailable')
    return torch


@pytest.mark.parametrize('frequency,damping', [(1e9, 0.), (1e9, .25), (2.5e9, 0.)])
def test_cuda_matches_cpu_and_keeps_handles_on_host(frequency, damping):
    cuda_or_skip()
    curve, scan, update = c_curve(), b.acquisition(), ProjectedUpdate(.05)
    space = update.prepare(curve, 12, 24)
    k = K25*frequency/2.5e9*(1+1j*damping)
    observation = Observation(k if damping else k.real, scan, np.ones(24, complex), frequency)
    cpu, gpu = modal(), ModalMuller(Execution(device='cuda', frequency_threads=1))
    a, c = [service.evaluate(curve, observation, 13.3, token(96)) for service in (cpu, gpu)]
    assert c.diagnostics['device'] == 'cuda-modal' and gpu.receipt()['devices'] == {'cuda-modal': 1}
    assert relative(c.prediction, a.prediction) < 1e-11
    assert relative(gpu.derivative(c, update, space), cpu.derivative(a, update, space)) < 1e-10
    assert all(isinstance(v, np.ndarray) for v in (*c._handle.factors, c._handle.traces, c._handle.reciprocal_rhs))
    if frequency == 1e9 and not damping:
        reference = F.solve(curve, k.real, 13.3, scan, 1024, execution_backend='cpu')
        assert relative(c.prediction, reference.prediction) < 1e-11


def test_cuda_oom_falls_back_under_auto_and_fails_explicitly(monkeypatch):
    torch = cuda_or_skip()
    from . import modal_cuda

    def exhausted(*args, **kwargs):
        raise torch.OutOfMemoryError('simulated modal assembly OOM')
    monkeypatch.setattr(modal_cuda, 'muller_matrix', exhausted)
    curve, scan = c_curve(12), b.acquisition()
    observation = Observation(K25*.4, scan, np.ones(24, complex), 1e9)
    expected = modal().evaluate(curve, observation, 13.3, token(64)).prediction
    auto = ModalMuller(Execution(device='auto', frequency_threads=1))
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        got = auto.evaluate(curve, observation, 13.3, token(64))
    np.testing.assert_array_equal(got.prediction, expected)
    assert got.diagnostics['fallback'] == 'modal CUDA OOM' and auto.receipt()['fallback_reasons']
    with pytest.raises(torch.OutOfMemoryError):
        ModalMuller(Execution(device='cuda', frequency_threads=1)).evaluate(curve, observation, 13.3, token(64))


def test_cuda_lm_stage_reproduces_cpu_decisions():
    cuda_or_skip()
    scan = b.acquisition()
    values = F.solve(FourierCurve.circle(1.0), 1.2, 4., scan, 512, execution_backend='cpu').prediction
    stage = FitStage('equivalence', (Observation(1.2, scan, values, .5e9),), (1.,), (1e-5,), 3, 8, token(64), token(96), 3, 300)
    rows = []
    for device in ('cpu', 'cuda'):
        ledger = Ledger(cap=400, seconds=300)
        ledger.begin_stage(stage.label, stage.quota)
        rows.append(fit_stage(resize(FourierCurve.circle(1.03, .01j), 8), stage, 4., ProjectedUpdate(.05),
                              BackendConfig(), ledger, physics=ModalMuller(Execution(device=device, frequency_threads=3))))
    a, c = rows
    assert [t['status'] for t in a.trials] == [t['status'] for t in c.trials] and a.accepted_steps == c.accepted_steps
    assert np.max(np.abs(a.curve.coefficients-c.curve.coefficients)) < 1e-11
