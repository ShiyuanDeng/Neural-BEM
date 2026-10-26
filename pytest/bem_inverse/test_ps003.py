"""PS-003's declared adapter and scalar-recording boundaries; no benchmark fits."""
from dataclasses import replace
import numpy as np

from bem_inverse import policies
from bem_inverse.physics import Execution
from bem_inverse.forward_solvers.modal_muller import ModalMuller
from bem_inverse.policy import CumulativePolicy
from experiments.benchmark import campaign
from test_continuation_policy import fixture
from test_entry_reuse import TwoFrequencyPhysics, ScalarUpdate, scalar_trial, stages
from bem_inverse.fit_stage import fit_stage
from bem_inverse.stage_types import BackendConfig
from bem_inverse.work import Ledger
from bem_inverse.continuation.geometry import FourierCurve


def test_slider_adaptation_preserves_policy_and_controls_only_full_catalog():
    problem, physics = fixture(), ModalMuller(Execution(device='cpu'))
    for name in ('feedback', 'four_phase', 'compact_release'):
        settings = campaign.settings_for(policy=name, policy_geometry_update='slider',
            localization='none', execution=Execution(device='cuda', frequency_threads=4))
        assert campaign.geometry_update_for(settings) == 'slider'
        assert settings['policy']['recipe'] == policies.recipe(name).settings()
        assert settings['execution']['stage_entry_reuse'] == (name == 'compact_release')
        assert campaign.geometry_update_for(campaign.settings_for(policy=name,
            localization='none', execution=Execution())) == 'spectral'
    base = policies.build('four_phase', **policies.BENCHMARK_CONTRACT)
    fixed = replace(base, full_catalog_trace_cutoff=128)
    a, b = base.operations(problem, physics), fixed.operations(problem, physics)
    for x, y in zip(a, b):
        if x.stage is None or len(x.stage.observations) != len(problem.real):
            assert x.record() == y.record()
        else:
            assert y.stage.nodes == 1024
            assert replace(y.stage, nodes=x.stage.nodes) == x.stage
            assert y.details['accuracy_profile']['coefficient_workspace']['production'] == 192
    fallback = CumulativePolicy(plain_progress_exit=True, progress_window=2,
        minimum_relative_progress=.05, progress_exit_minimum_modes=11)
    for op in fallback.operations(problem, physics) + fallback.tail(problem, physics, 50):
        if op.stage is not None:
            assert op.optimizer.plain_progress_exit == (op.stage.update_modes >= 11)


def test_scalar_recording_preserves_accepted_decisions_and_charges():
    results = []
    for recording in (False, True):
        physics = TwoFrequencyPhysics()
        stage = stages()[1]
        ledger = Ledger(cap=500, clock=lambda: 0., endpoint_reserve=0)
        ledger.begin_stage(stage.label, stage.quota)
        result = fit_stage(FourierCurve.circle(2), stage, .5, ScalarUpdate(),
            BackendConfig(step_bounds_m=(.15,)*3, max_damping_trials=2, record_diagnostics=recording), ledger,
            physics=physics, forward_solve=physics.forward_solve, geometry_update=scalar_trial)
        results.append(result)
    a, b = results
    assert (a.outcome, a.stop_reason, a.accepted_steps, a.work) == (b.outcome, b.stop_reason, b.accepted_steps, b.work)
    np.testing.assert_array_equal(a.curve.coefficients, b.curve.coefficients)
    assert [r['loss'] for r in a.history] == [r['loss'] for r in b.history]
    assert [r['status'] for r in a.trials] == [r['status'] for r in b.trials]
    assert b.diagnostics['damping_attempts'] >= b.accepted_steps
    assert 'raw_step_norm_m' in b.trials[0]
    assert 'recent_relative_decrease' in b.history[-1]
