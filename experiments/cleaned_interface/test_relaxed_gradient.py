"""Complete relaxed-loss differentiation, including shape-dependent penalty."""
from dataclasses import replace
import numpy as np
import pytest

from .test_full_matrix import fixture
from .full_matrix import RelaxedStage, RelaxedObjective, RealRelaxedPrefix
from .geometry import ProjectedUpdate
from experiments.shape_continuation.lm_backend import BackendConfig, Ledger, fit_stage


@pytest.mark.parametrize('paired', [False, True])
@pytest.mark.parametrize('damping', [0., .25])
@pytest.mark.parametrize('tau', [.1, 3., 100.])
def test_complete_reduced_gradient_matches_recomputed_loss(paired, damping, tau):
    backend, obs, curve = fixture(damping, nodes=128)
    if paired:
        obs = replace(obs, acquisition=replace(obs.acquisition, paired=True), scattered=np.diag(obs.scattered))
    # Noncircular geometry also exercises normal, speed and row-norm derivatives.
    coefficients = curve.coefficients.copy()
    coefficients[curve.band-1] = .06+.02j
    curve = type(curve)(coefficients)
    stage = RelaxedStage('gradient', (obs,), (.7,), (1e-5,), 3, 8, 128, 256, 1, 300, relaxed_tau=tau)
    objective = RelaxedObjective(stage, 13.3, BackendConfig(), Ledger(), physics=backend)
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, 3, 8)
    evaluated = objective.production(curve, 'base')
    gradient = objective.gradient(evaluated, update, space)
    rng = np.random.default_rng(56002)
    for direction in (np.eye(7)[0], rng.normal(size=7)):
        direction = direction/np.linalg.norm(direction)
        losses = [objective.production(update.trial(space, s*1e-7*direction)[0], 'fd').loss for s in (1, -1)]
        fd = (losses[0]-losses[1])/2e-7
        assert gradient@direction == pytest.approx(fd, rel=2e-5, abs=1e-7)
    info = evaluated.forwards[0].diagnostics['relaxed_gradient']
    assert info['primal_A_relative'] < 2e-10
    assert info['variable_projection_loss']*.7/np.linalg.norm(obs.scattered)**2 == pytest.approx(evaluated.loss, rel=1e-10)
    assert backend.receipt()['counts']['relaxed_gradients'] == 1


def test_archived_c_warmup_uses_correct_descent_direction():
    from . import benchmark as b
    from .fm001 import OUTPUT, full_problem
    from .io import read, curve_from
    from .physics import NodalKress, Execution
    case = 'modal__c13.3__development_c'
    row = next(r for r in b.descriptors() if r['id'] == case)
    problem, _ = full_problem(row, OUTPUT)
    saved = read(OUTPUT/'FRr'/'runs'/case/'warmup_025_real_relaxed.json')
    assert saved['accepted_steps'] == 0
    curve = curve_from(saved['curve'])
    backend = NodalKress(Execution(device='cpu', frequency_threads=1))
    op = next(o for o in RealRelaxedPrefix().operations(problem, backend) if o.kind == 'fit')
    objective = RelaxedObjective(op.stage, problem.contrast, op.optimizer, Ledger(), physics=backend)
    update = ProjectedUpdate(problem.length_unit_m)
    space = update.prepare(curve, op.stage.update_modes, curve.band)
    base = objective.production(curve, 'base')
    old = objective.jacobian(base, update, space).T@base.residual
    complete = objective.gradient(base, update, space)
    np.testing.assert_allclose(complete, [1.307436455, -.179008520, -.052979509], rtol=2e-6)
    assert complete@old < 0
    stage = replace(op.stage, iterations=1)
    ledger = Ledger(cap=500, seconds=120)
    ledger.begin_stage(stage.label, stage.quota)
    result = fit_stage(curve, stage, problem.contrast, update, op.optimizer, ledger,
                       physics=backend, objective_factory=RelaxedObjective)
    assert result.accepted_steps == 1
    assert result.final_loss < result.initial_loss
    assert sum(value for key, value in result.work['solves'].items()
               if key.endswith('relaxed_gradient_correction')) > 0


@pytest.mark.parametrize('device', ['cpu', 'cuda'])
def test_multifrequency_gradient_normalization_and_factor_path(device):
    if device == 'cuda':
        torch = pytest.importorskip('torch')
        if not torch.cuda.is_available():
            pytest.skip('CUDA unavailable')
    backend, real, curve = fixture(0., device=device, nodes=128)
    damped_backend, damped, _ = fixture(.25, device=device, nodes=128)
    stage = RelaxedStage('multi', (real, damped), (.2, .8), (1e-5, 1e-5), 3, 8, 128, 256, 1, 500, relaxed_tau=3.)
    objective = RelaxedObjective(stage, 13.3, BackendConfig(), Ledger(), physics=backend)
    update = ProjectedUpdate(.05)
    space = update.prepare(curve, 3, 8)
    base = objective.production(curve, 'base')
    gradient = objective.gradient(base, update, space)
    direction = np.random.default_rng(56003).normal(size=7)
    direction /= np.linalg.norm(direction)
    losses = [objective.production(update.trial(space, s*1e-7*direction)[0], 'fd').loss for s in (1,-1)]
    assert gradient@direction == pytest.approx((losses[0]-losses[1])/2e-7, rel=2e-5, abs=1e-7)
    if device == 'cuda':
        from .physics import NodalKress, Execution
        cpu = NodalKress(Execution(device='cpu', frequency_threads=1))
        other = RelaxedObjective(stage, 13.3, BackendConfig(), Ledger(), physics=cpu)
        reference = other.gradient(other.production(curve, 'base'), update, space)
        np.testing.assert_allclose(gradient, reference, rtol=2e-7, atol=1e-7)


def test_factorial_arms_change_only_early_damping_and_relaxation():
    from .fm002 import FactorialPrefix, ARMS, CASES
    from .fm001 import full_problem, OUTPUT
    from . import benchmark as b
    from .physics import NodalKress, Execution
    from .policy import CumulativePolicy
    row = next(r for r in b.descriptors() if r['id']==CASES[0])
    problem, _ = full_problem(row, OUTPUT)
    backend = NodalKress(Execution(device='cpu'))
    baseline = CumulativePolicy().operations(problem, backend)
    for arm, (damped, relaxed) in ARMS.items():
        policy = FactorialPrefix(damped_prefix=damped, relaxation=relaxed)
        operations = policy.operations(problem, backend)
        assert len(operations)==len(baseline)
        assert policy.fit_units == CumulativePolicy().fit_units
        assert policy.fit_seconds == CumulativePolicy().fit_seconds
        prefix_count = 0
        for actual, old in zip(operations, baseline):
            if old.kind=='fit' and old.label.endswith('_damped'):
                prefix_count += 1
                assert actual.stage.update_modes==old.stage.update_modes
                assert actual.stage.quota==old.stage.quota
                assert actual.optimizer==old.optimizer
                assert all((complex(o.wavenumber).imag>0)==damped for o in actual.stage.observations)
                assert (getattr(actual.stage,'relaxed_tau',None) is not None)==relaxed
            else:
                assert actual.record()==old.record()
        assert prefix_count==5
