import numpy as np
import pytest

from .indicators import threshold_circles, tikhonov_sampling
from .paths import scif_path


def test_scif_reflection_first_hit_reproducibility_and_cap():
    assert scif_path([1., 2., 3.], seed=7, upward_probability=1.)['indices'] == [0, 1, 2]
    row = scif_path(range(8), seed=12)
    assert row == scif_path(range(8), seed=12)
    assert row['completed'] and 7 not in row['indices'][:-1]
    assert all(b == max(0, a-1) or b == a+1 for a, b in zip(row['indices'], row['indices'][1:]))
    assert any(b < a for a, b in zip(row['indices'], row['indices'][1:]))
    assert not scif_path(range(8), seed=12, max_visits=2)['completed']
    assert scif_path([.5], seed=12)['indices'] == [0]


def test_tikhonov_residual_and_unattainable_discrepancy():
    a = np.diag([1., .1, .01])
    b = np.array([[1., 0], [.1, 0], [.01, 1]], complex)
    out = tikhonov_sampling(a, b, .05)
    assert out['discrepancy_attained'].all()
    np.testing.assert_allclose(out['relative_residual'], .05, rtol=1e-9)
    for j, alpha in enumerate(out['alpha']):
        x = np.linalg.solve(a.conj().T @ a + alpha*np.eye(3), a.conj().T @ b[:, j])
        assert 1/np.linalg.norm(x) == pytest.approx(out['indicator'][j])
    rank_deficient = np.array([[1., 0], [0., 1.], [0., 0.]])
    failed=tikhonov_sampling(rank_deficient, np.array([[0.], [0.], [1.]]))
    assert not failed['discrepancy_attained'][0]
    assert np.isnan(failed['indicator'][0])
    with pytest.raises(ValueError, match='full'):
        tikhonov_sampling(np.ones(5), np.ones((5, 3)))


def test_circle_seeds_do_not_require_truth_count_and_keep_empty_failure():
    x, y = np.meshgrid(np.linspace(.3, .7, 81), np.linspace(.3, .7, 81))
    points = np.stack((x, y), axis=-1)
    values = -np.exp(-((x-.44)**2+(y-.5)**2)/.0003)-np.exp(-((x-.56)**2+(y-.5)**2)/.0003)
    seeds, _ = threshold_circles(points, values)
    assert len(seeds) == 2
    np.testing.assert_allclose(sorted(s.center[0] for s in seeds), [.44, .56], atol=.002)
    assert threshold_circles(points, np.ones_like(x))[0] == ()


def test_empty_topological_derivative_matches_small_disk_objective_change():
    # Verify the existing exact TD's sign, source amplitude and area factor.
    from experiments.shape_continuation.forward import PointSourceAcquisition, solve
    from experiments.shape_continuation.geometry import FourierCurve
    from scipy.special import hankel1
    t = np.arange(12) * 2*np.pi/12
    acquisition = PointSourceAcquisition(np.column_stack((4*np.cos(t),4*np.sin(t))),
        np.column_stack((4*np.cos(t+.2),4*np.sin(t+.2))), strength=2+.5j)
    k, contrast, center = 1.2, .5, .2+.1j
    observed = solve(FourierCurve.circle(.3, center), k, contrast, acquisition, 96).prediction
    point = np.array([center.real,center.imag])
    source = acquisition.strength*.25j*hankel1(0,k*np.linalg.norm(acquisition.sources-point,axis=1))
    reciprocal = .25j*hankel1(0,k*np.linalg.norm(acquisition.receivers-point,axis=1))
    derivative = np.real(np.vdot(-observed, k*k*(contrast-1)*source*reciprocal))
    errors = []
    for radius in (.008,.004,.002):
        response = solve(FourierCurve.circle(radius,center),k,contrast,acquisition,64).prediction
        change = (.5*np.linalg.norm(response-observed)**2-.5*np.linalg.norm(observed)**2)/(np.pi*radius**2)
        errors.append(abs(change-derivative)/abs(derivative))
    assert errors[-1] < errors[0] and errors[-1] < 1e-3
