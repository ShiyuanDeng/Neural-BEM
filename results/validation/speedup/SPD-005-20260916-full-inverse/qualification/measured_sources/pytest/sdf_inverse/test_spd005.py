"""Reciprocal production bridge: numerical, runtime and budget regressions."""
from dataclasses import replace
import json
import os
import subprocess
import sys
import numpy as np
import pytest
import run_top017 as continuation
from gpr_bem_kress.execution import execution
from sdf_bem_multicomponent import PairedForwardProblem
from sdf_inverse import radial_topology as rt
from sdf_inverse import analytic_jacobian as aj
from sdf_inverse.optimization import ComplexScatteredData
from sdf_inverse.runtime import inverse_runtime, runtime_metadata
from sdf_inverse.work_accounting import collect_work, observe_analytic_work, analytic_work
from test_spd001 import setup_case


@pytest.mark.parametrize('count', [1, 3])
def test_coupled_reciprocal_weighted_complex_sources_against_operator_and_fd(count):
    state, data, geometry, solve = setup_case(count)
    problem = replace(PairedForwardProblem.from_compatible(data.forward_problem),
                      source_strengths=np.array([.7+.4j, -.3+.8j]))
    data = ComplexScatteredData(problem, data.observed_scattered_response, data.frequency_weights)
    directions = state.gauge_tangent_basis()[[0, 2, -1]]
    with execution(kernels='real_bessel'):
        operator, reference = aj.cartesian_residual_jacobian(
            state, data, geometry, solve_config=solve, directions=directions, method='operator')
        with collect_work() as ledger:
            reciprocal, prediction = aj.cartesian_residual_jacobian(
                state, data, geometry, solve_config=solve, directions=directions, method='reciprocal')
        fd = np.column_stack([(rt.evaluate_multiradial_objective(state.incremented(1e-6*d), data,
            geometry, solve_config=solve).residual-rt.evaluate_multiradial_objective(
            state.incremented(-1e-6*d), data, geometry, solve_config=solve).residual)/2e-6 for d in directions])
    np.testing.assert_array_equal(prediction, reference)
    np.testing.assert_allclose(reciprocal, operator, rtol=2e-8, atol=2e-8)
    np.testing.assert_allclose(reciprocal, fd, rtol=2e-4, atol=2e-7)
    counts = ledger.snapshot()['totals']
    assert counts['factorization_count'] == counts['reciprocal_frequency_solve_count'] == 2
    assert counts['analytic_primal_rhs_count'] == counts['reciprocal_rhs_count'] == 48
    assert counts['reciprocal_contraction_count'] == 6
    assert counts['derivative_assembly_count'] == counts['tangent_solve_count'] == 0


def test_reciprocal_runtime_reaches_real_continuation_and_subprocess(tmp_path, monkeypatch):
    monkeypatch.setenv('SDF_INVERSE_RUNTIME', 'reciprocal')
    metadata = json.loads(subprocess.check_output([sys.executable, '-c',
        'import json; from sdf_inverse.runtime import runtime_metadata; print(json.dumps(runtime_metadata()))'],
        env=os.environ, text=True))
    assert metadata['shape_derivative'] == 'reciprocal'
    with inverse_runtime('fast'):
        assert runtime_metadata()['shape_derivative'] == 'operator'
    state, data, geometry, solve = setup_case(1)
    config = rt.ParameterFDConfig(max_iterations=1, max_parameters=64, finite_difference_steps=1e-4,
        gradient_tolerance=1e50, loss_tolerance=1e-30, infeasible_trial_policy='reject')
    ledger = continuation.Ledger(cap=1000, seconds=30)
    ledger.begin_stage(1, 1000)
    with ledger.instrument(), collect_work() as passive:
        _, terminal = continuation.fit_stage(state, data, (128, 256), solve, config, .008, ledger, tmp_path/'stage')
    assert terminal['stage_outcome'] == 'NORMAL_OPTIMIZER_RETURN', terminal['reason']
    assert terminal['effective_training_exposure']
    counts = passive.snapshot()['totals']
    assert sum(ledger.reciprocal_completed.values()) == counts['reciprocal_frequency_solve_count'] == 2
    assert sum(ledger.completed.values()) == counts['bie_frequency_solve_count']
    assert ledger.budget_total == ledger.total+2
    assert sum(ledger.derivative_attempted.values()) == 0


def test_runtime_coarse_grid_fallback_is_exact_operator_derivative():
    state, data, geometry, solve = setup_case(1)
    directions = state.gauge_tangent_basis()[[0, -1]]
    with inverse_runtime('reciprocal'), execution(kernels='real_bessel'), collect_work() as work:
        matrix, prediction = aj.cartesian_residual_jacobian(state, data, geometry,
            solve_config=solve, directions=directions)
        counts = work.snapshot()['totals']
        reference, expected = aj.cartesian_residual_jacobian(state, data, geometry,
            solve_config=solve, directions=directions, method='operator')
    np.testing.assert_array_equal(matrix, reference)
    np.testing.assert_array_equal(prediction, expected)
    assert counts['reciprocal_frequency_solve_count'] == 0
    assert counts['derivative_assembly_count'] == 4


def test_reciprocal_failure_and_stage_reserve_are_charged_separately():
    ledger = continuation.Ledger(cap=100, seconds=30)
    ledger.begin_stage(1, 14)
    with observe_analytic_work(ledger.analytic_event):
        with analytic_work('base', 1.):
            pass
        with pytest.raises(ValueError):
            with analytic_work('reciprocal', 1.):
                raise ValueError('synthetic failure')
        with pytest.raises(continuation.StageQuota):
            with analytic_work('reciprocal', 1.):
                pytest.fail('endpoint reserve lost')
    assert ledger.total == 1 and ledger.budget_total == 2
    assert sum(ledger.reciprocal_failed.values()) == 1
    assert sum(ledger.derivative_attempted.values()) == 0
    assert ledger.snapshot()['stage_work_units'] == 2


def test_unsupported_materials_keep_the_forward_restriction():
    state, data, geometry, solve = setup_case(1)
    problem = PairedForwardProblem.from_compatible(data.forward_problem)
    problem = replace(problem, interior=replace(problem.interior, sigma=.01))
    data = ComplexScatteredData(problem, data.observed_scattered_response)
    with inverse_runtime('reciprocal'), pytest.raises(ValueError, match='lossless'):
        aj.cartesian_residual_jacobian(state, data, geometry, solve_config=solve,
                                      directions=state.gauge_tangent_basis()[:1])
