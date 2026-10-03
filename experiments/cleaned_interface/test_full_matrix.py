"""FM-001 gates: elimination, source/receiver ordering, exact trial acceptance."""
from dataclasses import replace
import numpy as np
import pytest
from scipy.linalg import lu_factor, lu_solve

from experiments.shape_continuation.geometry import FourierCurve
from experiments.shape_continuation.lm_backend import BackendConfig, FitStage, Ledger, Objective, fit_stage, normalize
from .full_matrix import receiver_weights, apply_receiver_weights, RelaxedStage, RelaxedObjective, RealRelaxedPrefix
from .physics import NodalKress, Execution
from .geometry import ProjectedUpdate, resize
from .problem import Observation
from .policy import CumulativePolicy
from . import benchmark as b


def test_noisy_fresh_catalog_reads_separate_frozen_clean_reference():
    from .fm001 import archived_clean
    from .io import read
    row = next(r for r in b.descriptors() if r['id']=='fresh__asymmetric_lobes__noise_seed_0')
    problem = b.fitting_problem(row,b.DEFAULT_OUTPUT)
    record = read(b.ROOT/row['clean'])
    expected = np.asarray(record['observed_real'])+1j*np.asarray(record['observed_imag'])
    np.testing.assert_array_equal(archived_clean(row,'real',problem.real),expected)
    assert not np.array_equal(expected,np.column_stack([o.scattered for o in problem.real]))


@pytest.mark.parametrize('paired', [False, True])
@pytest.mark.parametrize('tau', [.1, 3., 100.])
def test_closed_form_matches_direct_stacked_least_squares(paired, tau):
    rng = np.random.default_rng(55001)
    complex_random = lambda shape:rng.normal(size=shape)+1j*rng.normal(size=shape)
    a = complex_random((13, 13))+8*np.eye(13)
    c, rhs, data = complex_random((4, 13)), complex_random((13, 4)), complex_random((4, 4))
    h = lu_solve(lu_factor(a), c.conj().T, trans=2)
    weight = receiver_weights(h, c, tau, paired=paired)
    lam = tau*np.median(np.sum(abs(c)**2, axis=1))
    prediction = (c@np.linalg.solve(a, rhs)).T
    residual = np.diag(prediction-data) if paired else prediction-data
    closed = np.linalg.norm(apply_receiver_weights(residual.reshape(-1), weight, residual.shape))**2
    direct = 0.
    for source in range(4):
        rows = c[source:source+1] if paired else c
        d = data[source, source:source+1] if paired else data[source]
        stacked = np.vstack((rows, np.sqrt(lam)*a))
        target = np.r_[d, np.sqrt(lam)*rhs[:, source]]
        q = np.linalg.lstsq(stacked, target, rcond=None)[0]
        direct += np.linalg.norm(stacked@q-target)**2
    error = abs(closed-direct)/direct
    print('stacked_ls_relative', paired, tau, error)
    assert error <= 1e-12


def test_large_tau_reproduces_ordinary_loss_and_receiver_order():
    rng = np.random.default_rng(55)
    h = rng.normal(size=(15, 5))+1j*rng.normal(size=(15, 5))
    c = rng.normal(size=(5, 15))+1j*rng.normal(size=(5, 15))
    residual = rng.normal(size=(3, 5))+1j*rng.normal(size=(3, 5))
    w = receiver_weights(h, c, 1e12)
    transformed = apply_receiver_weights(residual.reshape(-1), w, residual.shape).reshape(residual.shape)
    np.testing.assert_allclose(transformed, np.stack([w@r for r in residual]), atol=1e-14)
    relative = abs(np.linalg.norm(transformed)**2/np.linalg.norm(residual)**2-1)
    print('tau_large_relative', relative)
    assert relative <= 1e-9


def fixture(damping=0., device='cpu', contrast=13.3, nodes=512):
    scan = replace(b.acquisition(), paired=False)
    template = Observation(1.2*(1+1j*damping), scan, np.ones(scan.data_shape)*1e-6, .5e9)
    backend = NodalKress(Execution(device=device, frequency_threads=1))
    truth = FourierCurve.circle(1.02, .01+.03j)
    observation = replace(template, scattered=backend.evaluate(truth, template, contrast, nodes).prediction)
    return backend, observation, resize(FourierCurve.circle(1.08, .02+.05j), 8)


@pytest.mark.parametrize('damping', [0., .25])
def test_full_matrix_jacobian_and_paired_diagonal(damping):
    backend, observation, curve = fixture(damping)
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, 3, 8)
    state = backend.evaluate(curve, observation, 13.3, 512)
    jacobian = backend.derivative(state, update, space)
    paired = replace(observation, acquisition=replace(observation.acquisition, paired=True),
                     scattered=np.diag(observation.scattered))
    diagonal = backend.evaluate(curve, paired, 13.3, 512)
    np.testing.assert_array_equal(diagonal.prediction, np.diag(state.prediction))
    np.testing.assert_array_equal(backend.derivative(diagonal, update, space), jacobian[np.arange(24), np.arange(24)])
    direction = np.random.default_rng(55).normal(size=7)
    direction /= np.linalg.norm(direction)
    plus, minus = [backend.evaluate(update.trial(space, sign*1e-7*direction)[0], observation, 13.3, 512).prediction
                   for sign in (1, -1)]
    fd = (plus-minus)/2e-7
    error = np.linalg.norm(fd-jacobian@direction)/np.linalg.norm(fd)
    print('full_matrix_fd_relative', damping, error)
    assert error <= 1e-3


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_existing_lu_adjoint_and_large_tau_physics(device):
    if device == 'cuda':
        torch = pytest.importorskip('torch')
        if not torch.cuda.is_available():
            pytest.skip('CUDA unavailable')
    backend, observation, curve = fixture(.25, device, nodes=64)
    state = backend.evaluate(curve, observation, 13.3, 64)
    weights = backend.relaxation_weights(state, 3.)
    from experiments.shape_continuation import forward as f
    handle = state._handle
    c = f._operators(handle.curve)[1](handle.curve, handle.acquisition.receivers, handle.wavenumber).state_rows
    h = np.linalg.solve(handle.matrix.conj().T, c.conj().T)
    np.testing.assert_allclose(weights, receiver_weights(h, c, 3.), rtol=1e-11, atol=1e-13)
    residual = (state.prediction-observation.scattered).reshape(-1)
    weighted = apply_receiver_weights(residual, backend.relaxation_weights(state, 1e12), observation.scattered.shape)
    assert abs(np.linalg.norm(weighted)**2/np.linalg.norm(residual)**2-1) <= 1e-9


def test_trials_recompute_weights_and_refined_losses():
    backend, obs, curve = fixture(nodes=128, contrast=.5)
    stage = RelaxedStage('relaxed', (obs,), (1.,), (1e-5,), 3, 8, 64, 128, 1, 300, relaxed_tau=3.)
    ledger = Ledger(cap=500, seconds=120)
    objective = RelaxedObjective(stage, .5, BackendConfig(), ledger, physics=backend)
    update = ProjectedUpdate(.05)
    base = objective.production(curve, 'base')
    candidate_curve = update.trial(update.prepare(curve, 3, 8), np.ones(7)*1e-5)[0]
    trial = objective.production(candidate_curve, 'candidate')
    assert not np.array_equal(base.receiver_weights[0], trial.receiver_weights[0])
    for evaluated, nodes in [(base, 64), (trial, 64), (objective.refined(candidate_curve), 128)]:
        state = backend.evaluate(evaluated.curve, obs, .5, nodes)
        weight = backend.relaxation_weights(state, 3.)
        residual = apply_receiver_weights((state.prediction-obs.scattered).reshape(-1), weight, obs.scattered.shape)
        normalized = normalize(residual[:, None], obs.scattered.reshape(-1, 1), (1.,))
        assert evaluated.loss == pytest.approx(.5*float(normalized@normalized), rel=1e-13)
    assert not objective.refined(candidate_curve).forwards
    ledger = Ledger(cap=500, seconds=120)
    ledger.begin_stage(stage.label, stage.quota)
    result = fit_stage(curve, stage, .5, update, BackendConfig(), ledger,
                       physics=backend, objective_factory=RelaxedObjective)
    assert result.accepted_steps == 1
    assert result.acceptance_checks[0]['accepted']
    assert any('relaxation_adjoint' in name for name in result.work['reciprocal_batches'])


def test_none_tau_preserves_objective_and_frr_policy():
    backend, obs, curve = fixture(nodes=64)
    stage = FitStage('ordinary', (obs,), (1.,), (1e-5,), 3, 8, 64, 128, 1)
    ordinary = Objective(stage, 13.3, BackendConfig(), Ledger(), physics=backend).production(curve, 'base')
    none = Objective(RelaxedStage.from_stage(stage, None), 13.3, BackendConfig(), Ledger(), physics=backend).production(curve, 'base')
    np.testing.assert_array_equal(ordinary.residual, none.residual)
    row = next(r for r in b.descriptors() if r['id']=='modal__c13.3__development_c')
    p = b.fitting_problem(row, b.DEFAULT_OUTPUT)
    ops = RealRelaxedPrefix().operations(p, backend)
    fits = [op for op in ops if op.kind=='fit']
    assert [op.stage.relaxed_tau for op in fits[:5]] == [3, 3, 10, 30, 100]
    assert all(complex(o.wavenumber).imag == 0 for op in fits for o in op.stage.observations)
    assert all(getattr(op.stage, 'relaxed_tau', None) is None for op in fits[5:])
    assert ops[1].label == 'damped_localization'


@pytest.mark.parametrize('relaxed', [False, True])
def test_full_matrix_runner_keeps_paired_localization_and_exact_audits(tmp_path, relaxed):
    from .policy import LocalizationRule
    from .runner import fit
    from .problem import Problem
    class Backend(NodalKress):
        def resolution_profile(self, storage_band):
            return dict(production=64, refined=128, nodal_resolution=64)
        def disk_landscape(self, observations, *args):
            assert all(o.acquisition.paired and o.scattered.shape==(24,) for o in observations)
            return super().disk_landscape(observations, *args)
    class Policy(RealRelaxedPrefix if relaxed else CumulativePolicy):
        def operations(self, problem, physics):
            ops = super().operations(problem, physics)
            fits = [replace(o, stage=replace(o.stage, iterations=1)) for o in ops if o.kind=='fit']
            return (ops[0], ops[1], *fits[:2], ops[-2], ops[-1])
        def tail(self, *args):
            return ()
    backend = Backend(Execution(device='cpu', frequency_threads=1))
    scan = replace(b.acquisition(), paired=False)
    templates = tuple(Observation(k, scan, np.ones((24,24))*1e-6, f*1e9) for k,f in
                      zip((.6,1.2,1.8,2.4,3.), (.25,.5,.75,1.,1.25)))
    truth = FourierCurve.circle(1.01)
    real = tuple(replace(o, scattered=backend.evaluate(truth,o,.5,128).prediction) for o in templates)
    damped = tuple(replace(o,wavenumber=o.wavenumber*(1+.25j)) for o in templates)
    damped = tuple(replace(o,scattered=backend.evaluate(truth,o,.5,128).prediction) for o in damped)
    problem = Problem(FourierCurve.circle(1.02),real,damped,.5)
    policy = Policy(storage_band=24, frontier_top=7, localization=LocalizationRule(
        center_min_m=.5,center_max_m=.5,radius_min_m=.05,radius_max_m=.05,
        max_starts=1,refinement_iterations=1))
    result = fit(problem,physics=backend,policy=policy,output=tmp_path)
    assert result['outcome']=='COMPLETED_SCHEDULE',result['detail']
    assert result['initial_audit_passed'] and result['final_audit_passed']
    assert len(result['relative_residual'])==len(result['paired_relative_residual'])==5
    assert len(result['stages'])==2
