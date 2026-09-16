"""Material/geometry rebuild, weighting, cache and derivative contracts."""

from dataclasses import replace
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sdf_inverse import MaterialSpec
from sdf_inverse.curve_updates import radial_fourier_parameterization
import sdf_inverse.material_inverse as core
from run_material_inverse_comparison import TRUTH, acquisition, frozen_observations, mie_response


def evaluator(nodes=32):
    problem = acquisition(pairs=4)
    clean, *_ = frozen_observations(problem)
    return core.MaterialCurveEvaluator(problem, clean, nodes=nodes)


def test_physical_box_certifies_positive_radius_and_radial_jets_are_exact():
    scaled = core.scaled_parameters([.052, .501, .499, .002, -.001, 4.])
    t = np.linspace(0, 2*np.pi, 32, endpoint=False)
    h = 1e-5
    for index in range(5):
        delta = np.zeros(6); delta[index] = h
        minus = radial_fourier_parameterization(core.candidate_state(scaled-delta)[1]).evaluate(t)
        plus = radial_fourier_parameterization(core.candidate_state(scaled+delta)[1]).evaluate(t)
        exact = core.scaled_direction(t, index)
        for attribute in ("points", "first_derivatives", "second_derivatives", "third_derivatives"):
            finite = (getattr(plus, attribute)-getattr(minus, attribute))/(2*h)
            np.testing.assert_allclose(finite, getattr(exact, attribute), atol=1e-11, rtol=1e-8)
    for bound in (core.PHYSICAL_LOWER, core.PHYSICAL_UPPER):
        _, state = core.candidate_state(core.scaled_parameters(bound))
        assert state.minimum_radius_lower_bound_m > .029


def test_candidate_material_rebuild_updates_k_operator_and_diagonal_and_cache_identity():
    model = evaluator()
    scaled = core.scaled_parameters(TRUTH)
    first = model.evaluate(scaled)
    assert model.evaluate(scaled) is first
    assert model.work["candidate_builds"] == 1
    changed = scaled.copy(); changed[5] += 1.
    second = model.evaluate(changed)
    assert second.problem.interior.epsr == 5.
    assert first.cache_key != second.cache_key
    assert second.problem is not first.problem
    for a, b in zip(first.forward_results, second.forward_results):
        assert a.system.k_interior != b.system.k_interior
        assert not np.allclose(a.system.system_matrix, b.system.system_matrix)
        # The full Mueller diagonal is identity; the material-dependent
        # analytic self diagonals are in its off-diagonal S/T blocks.
        count = model.nodes
        assert not np.allclose(np.diag(a.system.system_matrix[:count, count:]),
                               np.diag(b.system.system_matrix[:count, count:]))
        np.testing.assert_array_equal(a.right_hand_side, b.right_hand_side)
    assert not np.allclose(first.prediction, second.prediction, atol=0)
    assert model.evaluate(scaled).cache_key == first.cache_key
    assert model.work["candidate_builds"] == 3  # One-entry, no stale cross-epsr hit.


def test_material_and_shape_scaled_weighted_jacobian_matches_forward_finite_difference():
    model = evaluator()
    scaled = core.scaled_parameters([.052, .501, .499, .001, -.001, 4.])
    jacobian = model.jacobian(scaled)
    direction = np.array([.2, -.3, .1, .15, -.2, .4])
    h = 1e-5
    finite = (model.evaluate(scaled+h*direction).residual-model.evaluate(scaled-h*direction).residual)/(2*h)
    np.testing.assert_allclose(jacobian@direction, finite, atol=1e-7, rtol=2e-5)
    assert np.linalg.norm(jacobian[-len(jacobian)//2:]) > 0  # Imaginary residual is retained.


def test_frozen_observation_and_normalization_changes_are_detected():
    model = evaluator()
    scaled = core.scaled_parameters(TRUTH)
    model.evaluate(scaled)
    assert not model.observed.flags.writeable
    model.frequency_scales = 2*model.frequency_scales
    with pytest.raises(RuntimeError, match="normalization"):
        model.evaluate(scaled)
    model = evaluator()
    model.observed = np.array(model.observed, copy=True); model.observed[0, 0] += 1e-8j
    with pytest.raises(RuntimeError, match="observations"):
        model.evaluate(scaled)


def test_cache_cannot_bypass_index_validation_and_invalid_candidates_are_not_zero_residuals():
    model = evaluator()
    scaled = core.scaled_parameters(TRUTH)
    model.jacobian(scaled, active_indices=(0, 1))
    for invalid in ((0.,), (True,), (1, 1), ()):
        with pytest.raises(ValueError, match="active_indices"):
            model.jacobian(scaled, active_indices=invalid)
    invalid = scaled.copy(); invalid[-1] = -10
    with pytest.raises(ValueError, match="bounds"):
        model.evaluate(invalid)
    assert model.work["invalid_candidate_probes"] == 1


def test_failed_forward_attempt_is_counted(monkeypatch):
    model = evaluator()
    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("manufactured factorization failure")
    monkeypatch.setattr(core, "solve_kress_tmz_total_field_batch", fail)
    with pytest.raises(np.linalg.LinAlgError):
        model.evaluate(core.scaled_parameters(TRUTH))
    assert model.work["candidate_builds"] == 1
    assert model.work["forward_solves"] == model.work["failed_forward_solves"] == 1
    assert model.work["forward_seconds"] > 0


def test_small_fixed_material_recovery_and_maxeval_status_are_distinct():
    model = evaluator(64)
    initial = TRUTH.copy(); initial[5] = 5.
    final, report = core.fit_material_curve(model, initial, max_evaluations=20)
    assert abs(final.physical[5]-3.) < 1e-6
    assert report["verified_stationarity"]
    assert report["projected_gradient_inf"] <= report["stationarity_tolerance"]
    limited = evaluator()
    _, report = core.fit_material_curve(limited, initial, max_evaluations=1)
    assert not report["optimizer_success"]
    assert not report["verified_stationarity"]


def test_only_supported_lossless_nonmagnetic_materials_are_accepted():
    problem = replace(acquisition(pairs=4), interior=MaterialSpec(3., sigma=.01))
    with pytest.raises(ValueError, match="lossless"):
        core.MaterialCurveEvaluator(problem, np.ones((4, 2), complex))
