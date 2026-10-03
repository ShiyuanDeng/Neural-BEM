"""Independent mathematical and existing-solver checks for TR diagnostics."""
from dataclasses import replace
import numpy as np
import pytest
from . import common as c
from .folds import hessian, track
from .handoffs import normal_graph


def test_structural_zero_and_weakest_null_direction():
    a = np.array([[1., 0., 0.], [0., 2., 0.]])
    s, u = c.spectrum(a)
    assert len(s) == 3 and s[-1] == 0
    assert np.linalg.norm(a@u) == 0


def test_full_and_paired_data_order_and_normalization():
    data = np.arange(1, 19).reshape(3, 2, 3)+1j
    assert np.array_equal(c.rows(data, True), np.stack([np.diag(data[:, i]) for i in range(2)], axis=1))
    assert np.array_equal(c.rows(data, False)[:, 0], data[:, 0].reshape(-1))
    jac = np.stack([data, 2*data], axis=-1)
    assert np.array_equal(c.rows(jac, True)[..., 1], 2*c.rows(data, True))


def test_circle_chart_metric_and_finite_velocity():
    chart = c.Chart(c.FourierCurve.circle(.6), 5, storage=32)
    assert chart.metric_error < 1e-12 and chart.projection_error < 1e-12
    q = np.arange(11)/100.
    actual = chart.curve(q).values(256)-chart.base.values(256)
    expected = c.values(chart.vectors, 256)@q
    assert np.max(abs(actual-expected)) < 1e-15
    nodes = chart.base.nodes(256)
    h = chart.velocities(None, nodes)@q*50
    assert np.sqrt(nodes.arc_length_weights@h**2/nodes.perimeter) == pytest.approx(np.linalg.norm(q))


def test_graph_circle_and_unrelated_disjoint_curve():
    graph = normal_graph(c.FourierCurve.circle(.6), c.FourierCurve.circle(.61), 64)
    assert graph['valid']
    assert np.max(abs(graph['h_package']-.01)) < 1e-12
    assert not normal_graph(c.FourierCurve.circle(.6), c.FourierCurve.circle(.2, 1.2), 64)['valid']


def test_full_hessian_contains_residual_curvature():
    # r(q)=q^2-2, Phi=.5*r^2: H=6q^2-4, while GN=4q^2.
    h, skew = hessian(lambda q: 2*q*(q*q-2), np.array([.5]), 1e-4)
    assert h[0, 0] == pytest.approx(-2.5, abs=1e-6)
    assert skew == 0


def test_pseudoarclength_passes_cubic_fold():
    def system(x):
        q, t = x
        return np.array([q**3-q-t]), np.array([[3*q*q-1, -1.]])
    result = track(system, [-1., 0.], max_steps=25, initial_step=.1, maximum_step=.1,
                   minimum_step=.001, time_scale=2.)
    assert any(r.get('tangent_time_reversal') for r in result['path'])
    assert max(r['gradient_inf'] for r in result['path']) < 1e-8
    assert max(r['x'][-1] for r in result['path']) > .37


@pytest.mark.parametrize('catalog', ['real', 'damped'])
def test_fixed_chart_derivative_against_rebuilt_forward(monkeypatch, catalog):
    monkeypatch.setattr(c, 'EXECUTION', c.Execution(device='cpu', frequency_threads=1))
    problem, truth = c.load_case(c.CASES[0])
    chart = c.Chart(truth, 3, problem.length_unit_m, storage=32)
    evaluator = c.Evaluator(problem, c.Budget(120, 100))
    obs = c.select(getattr(problem, catalog), 1)
    q = np.array([.1, -.03, .01, .005, .001, .002, -.001])
    u = np.arange(1., 8.); u /= np.linalg.norm(u)
    g, j = evaluator.evaluate(chart, q, obs, 128)
    step = .0003
    gp, _ = evaluator.evaluate(chart, q+step*u, obs, 128, False)
    gm, _ = evaluator.evaluate(chart, q-step*u, obs, 128, False)
    assert np.linalg.norm((gp-gm)/(2*step)-j@u)/np.linalg.norm(j@u) < 1e-6
    assert evaluator.budget.completed == 3 and evaluator.budget.derivatives == 1
