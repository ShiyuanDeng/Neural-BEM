"""Compiled Kress: full gauge derivatives, fallback, caching and real fitting."""
from dataclasses import replace
import json
import numpy as np
import pytest
import run_top017 as continuation
from gpr_bem_kress.execution import execution
from sdf_bem_multicomponent import PairedForwardProblem
from sdf_inverse import radial_topology as rt
from sdf_inverse import analytic_jacobian as aj
from sdf_inverse.compiled_jacobian import CompiledEvaluator, relative_columns
from sdf_inverse.optimization import ComplexScatteredData
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work, observe_analytic_work, analytic_work
from test_spd001 import setup_case


@pytest.mark.parametrize('count', [1, 3])
def test_full_gauge_complex_sources_match_full_kress_and_fd(count):
    state, data, geometry, solve = setup_case(count)
    geometry = replace(geometry, num_nodes=128)
    problem = replace(PairedForwardProblem.from_compatible(data.forward_problem),
                      source_strengths=np.array([.7+.4j, -.3+.8j])*1e-6)
    data = ComplexScatteredData(problem, data.observed_scattered_response, data.frequency_weights)
    directions = state.gauge_tangent_basis()
    evaluator = CompiledEvaluator(data, geometry, solve, directions, allow_single=True)
    with execution(kernels='real_bessel'), collect_work() as work:
        actual = evaluator.evaluate(state)
        assert actual is not None, evaluator.snapshot()
        jac, pred = aj.cartesian_residual_jacobian(state, data, geometry,
            solve_config=solve, directions=directions, method='reciprocal')
        np.testing.assert_allclose(actual['prediction'], pred, rtol=1e-9, atol=1e-19)
        assert max(relative_columns(actual['jacobian'], jac)) < 1e-7
        direction = np.sum(directions, axis=0)/np.sqrt(len(directions))
        finite = []
        for sign in (1, -1):
            value = rt.evaluate_multiradial_objective(state.incremented(sign*1e-6*direction), data,
                geometry, solve_config=solve, compiled_evaluator=evaluator)
            finite.append(value.residual)
        fd = (finite[0]-finite[1])/2e-6
        np.testing.assert_allclose(actual['jacobian'] @ np.ones(len(directions))/np.sqrt(len(directions)),
                                   fd, rtol=2e-4, atol=2e-9)
    assert work.snapshot()['totals']['compiled_frequency_batch_count'] == 6


def test_cache_tracks_local_shape_and_reuses_pose_changes():
    state, data, geometry, solve = setup_case(2)
    geometry = replace(geometry, num_nodes=128)
    evaluator = CompiledEvaluator(data, geometry, solve, state.gauge_tangent_basis())
    with execution(kernels='real_bessel'):
        assert evaluator.evaluate(state) is not None
        baseline = evaluator.counts['local_compilations']
        step = np.zeros(state.parameter_count); step[0] = .001
        shifted = state.incremented(step)
        assert evaluator.evaluate(shifted) is not None
        assert evaluator.counts['local_compilations'] == baseline
        step[2] = .0001
        assert evaluator.evaluate(state.incremented(step)) is not None
        assert evaluator.counts['local_compilations'] == baseline+2


def test_unconverged_angles_use_identical_full_kress_objective_and_jacobian():
    state, data, geometry, solve = setup_case(2)
    geometry = replace(geometry, num_nodes=128)
    directions = state.gauge_tangent_basis()
    evaluator = CompiledEvaluator(data, geometry, solve, directions, order_pairs=((2, 4),))
    with execution(kernels='real_bessel'), inverse_runtime('compiled'):
        actual = rt.evaluate_multiradial_objective(state, data, geometry,
            solve_config=solve, compiled_evaluator=evaluator)
        reference = rt.evaluate_multiradial_objective(state, data, geometry, solve_config=solve)
        np.testing.assert_array_equal(actual.prediction, reference.prediction)
        assert evaluator.counts['fallback:angular_convergence'] == 1
        jac, pred = aj.cartesian_residual_jacobian(state, data, geometry, solve_config=solve,
            directions=directions, compiled_evaluator=evaluator)
        expected, prediction = aj.cartesian_residual_jacobian(state, data, geometry,
            solve_config=solve, directions=directions, method='reciprocal')
        np.testing.assert_array_equal(jac, expected)
        np.testing.assert_array_equal(pred, prediction)


def test_valid_close_ellipses_fall_back_when_bounding_circles_overlap():
    state, data, geometry, solve = setup_case(2)
    components = []
    for index, component in enumerate(state.components):
        c = component.cosine_coefficients.copy(); s = component.sine_coefficients.copy()
        c[0] = [.45+.07*index, .5]; c[1] = [.012, 0]; s[1] = [0, .09]
        components.append(replace(component, cosine_coefficients=c, sine_coefficients=s))
    state = rt.MultiRadialFourierState(tuple(components)); geometry = replace(geometry, num_nodes=256)
    evaluator = CompiledEvaluator(data, geometry, solve, state.gauge_tangent_basis())
    assert rt.multiradial_geometry_admissible(state, geometry, solve_config=solve)
    assert evaluator.evaluate(state) is None
    assert evaluator.counts['fallback:bounding_circles_overlap'] == 1
    assert not evaluator.cache


def test_compiled_batches_obey_stage_budget_and_preserve_failures():
    ledger = continuation.Ledger(cap=100, seconds=30)
    ledger.begin_stage(1, 14)
    with observe_analytic_work(ledger.analytic_event):
        with analytic_work('compiled', 1.):
            pass
        with pytest.raises(FloatingPointError):
            with analytic_work('compiled', 1.):
                raise FloatingPointError('synthetic')
        with pytest.raises(continuation.StageQuota):
            with analytic_work('compiled', 1.):
                pytest.fail('endpoint reserve lost')
    assert ledger.total == 0 and ledger.budget_total == 2
    assert sum(ledger.compiled_failed.values()) == 1
    assert ledger.snapshot()['stage_work_units'] == 2


def test_compiled_runtime_reaches_real_continuation_only(tmp_path):
    state, data, geometry, solve = setup_case(2)
    config = rt.ParameterFDConfig(max_iterations=1, max_parameters=64, finite_difference_steps=1e-4,
        gradient_tolerance=1e50, loss_tolerance=1e-30, infeasible_trial_policy='reject')
    ledger = continuation.Ledger(cap=2000, seconds=60)
    ledger.begin_stage(1, 2000)
    with inverse_runtime('compiled'), ledger.instrument(), collect_work() as passive:
        assert runtime_metadata()['continuation_backend'] == 'compiled'
        _, terminal = continuation.fit_stage(state, data, (256, 512), solve, config, .008, ledger, tmp_path/'stage')
    assert terminal['stage_outcome'] == 'NORMAL_OPTIMIZER_RETURN', terminal['reason']
    assert terminal['effective_training_exposure']
    assert sum(ledger.compiled_completed.values()) == passive.snapshot()['totals']['compiled_frequency_batch_count'] == 2
    assert sum(ledger.reciprocal_completed.values()) == 0
    record = json.loads((tmp_path/'stage/compiled_backend.json').read_text())
    assert record['events'][-1]['backend'] == 'compiled'
    with inverse_runtime('compiled'), execution(kernels='real_bessel'), collect_work() as low:
        rt.run_multiradial_fd_inverse(state, data, geometry, solve_config=solve, config=config)
    assert low.snapshot()['totals']['compiled_frequency_batch_count'] == 0
    with inverse_runtime('fast'):
        assert runtime_metadata()['continuation_backend'] == 'full_kress'
