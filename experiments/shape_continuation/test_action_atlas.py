import numpy as np
import pytest

from .action_atlas import descent_lower_bound, predict


def test_correlated_columns_cannot_claim_an_infeasible_complete_correction():
    J = np.array([[1., 100.], [0., 1.]])
    r = np.array([0., 1.])
    result = predict(J, r, np.eye(2), 1.)
    assert result.constraint_active and result.physical_norm == pytest.approx(1.)
    assert 0 < result.predicted_decrease < .02
    assert np.linalg.norm(np.linalg.solve(J, -r)) > 100


@pytest.mark.parametrize('radius', [.03, 10.])
def test_physical_prediction_is_invariant_to_parameter_scaling_and_mixing(radius):
    rng = np.random.default_rng(41)
    J, r = rng.normal(size=(30, 5)), rng.normal(size=30)
    X = rng.normal(size=(5, 5))
    G = X.T @ X + np.eye(5)
    B = rng.normal(size=(5, 5)) + 3*np.eye(5)
    a = predict(J, r, G, radius)
    b = predict(J @ B, r, B.T @ G @ B, radius)
    assert np.allclose(a.step, B @ b.step, rtol=1e-9, atol=1e-12)
    assert a.predicted_decrease == pytest.approx(b.predicted_decrease)
    assert a.physical_norm <= radius*(1+1e-12)


def test_rank_deficiency_does_not_create_arbitrary_explained_residual():
    J = np.array([[1., 1., 0.], [0., 0., 0.]])
    result = predict(J, [1., 2.], np.eye(3), 10.)
    assert result.numerical_rank == 1
    assert result.predicted_decrease == pytest.approx(.5)
    assert result.linear_loss == pytest.approx(2.)
    assert np.allclose(result.step, [-.5, -.5, 0.])


def test_nested_spaces_never_reduce_optimal_gain_at_a_common_physical_radius():
    rng = np.random.default_rng(42)
    J, r = rng.normal(size=(20, 6)), rng.normal(size=20)
    gains = [predict(J[:, :n], r, np.eye(n), .2).predicted_decrease for n in range(1, 7)]
    assert np.all(np.diff(gains) >= -1e-14)


def test_remainder_bound_is_valid_and_sharp_for_aligned_error():
    r, v = np.array([2., 1.]), np.array([.3, -.4])
    pred = .5*(r@r-v@v)
    eps = .2
    error = eps*v/np.linalg.norm(v)
    actual = .5*(r@r-(v+error)@(v+error))
    assert descent_lower_bound(pred, np.linalg.norm(v), eps) == pytest.approx(actual)


def test_zero_residual_and_zero_jacobian_are_finite():
    for J, r in ((np.eye(2), np.zeros(2)), (np.zeros((3, 2)), np.ones(3))):
        result = predict(J, r, np.eye(2), 1.)
        assert result.physical_norm == 0 and result.predicted_decrease == 0
        assert result.record()['decrease_fraction'] == 0


def test_invalid_physical_metric_is_rejected():
    with pytest.raises(np.linalg.LinAlgError):
        predict(np.eye(2), np.ones(2), np.diag([1., 0.]), 1.)
