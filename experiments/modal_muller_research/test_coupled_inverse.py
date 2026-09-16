"""Multiple-scattering derivatives and matrix-free adjoint checks."""
import numpy as np
import pytest
from ordered_boundary import PeriodicParameterization2D
from .coupled_inverse import SceneEvaluator
from .run_coupled_inverse import fixture


@pytest.mark.parametrize('paired',[True,False])
def test_coupled_reciprocity_and_actions_match_operator_derivative(paired):
    acq,chart,x,_=fixture()
    acq=dict(acq,source_points=acq['source_points'][::4],receiver_points=acq['receiver_points'][::4],
             source_strength=1e-6*np.exp(1j*np.linspace(-.5,.8,6)))
    if not paired:
        acq['receiver_points']=acq['receiver_points'][:-1]
    ref=SceneEvaluator(chart,acq,[1.25e9],backend='nodal',nodes=128,paired=paired)
    expected=ref.forward(x);exact=ref.base.operator_jacobian(paired)
    rng=np.random.default_rng(69);v=rng.normal(size=chart.size)
    for backend in ['nodal','native']:
        evaluator=SceneEvaluator(chart,acq,[1.25e9],backend=backend,paired=paired)
        actual=evaluator.forward(x)
        products=evaluator.sensitivity(x)
        traces=evaluator.sensitivity(x,'traces')
        jac=products.dense()
        assert np.linalg.norm(actual-expected)/np.linalg.norm(expected)<1e-10
        assert np.linalg.norm(jac-exact)/np.linalg.norm(exact)<1e-10
        np.testing.assert_allclose(traces.matvec(v),jac@v,rtol=1e-12,atol=1e-22)
        w=rng.normal(size=actual.shape)+1j*rng.normal(size=actual.shape)
        expected_adjoint=np.real(np.einsum('fdp,fd->p',jac.conj(),w))
        np.testing.assert_allclose(traces.rmatvec(w),expected_adjoint,rtol=1e-11,atol=1e-22)
        np.testing.assert_allclose(np.dot(v,traces.rmatvec(w)),np.real(np.vdot(w,traces.matvec(v))),rtol=1e-12,atol=1e-22)
        op=traces.real_operator(np.array([1e-7]),np.linspace(0,.01,chart.size))
        real_w=rng.normal(size=op.shape[0])
        np.testing.assert_allclose(real_w@op.matvec(v),v@op.rmatvec(real_w),rtol=1e-12,atol=1e-13)


def test_coupled_native_derivative_is_node_free_and_matches_finite_difference(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Native coupled path sampled the boundary.')
    monkeypatch.setattr(PeriodicParameterization2D,'discretize',forbidden)
    acq,chart,x,_=fixture()
    evaluator=SceneEvaluator(chart,acq,[1.25e9])
    factors=evaluator.sensitivity(x,'traces')
    v=np.random.default_rng(82).normal(size=chart.size);v/=np.linalg.norm(v)
    expected=factors.matvec(v);h=1e-4
    finite=(evaluator.forward(x+h*v)-evaluator.forward(x-h*v))/(2*h)
    assert np.linalg.norm(expected-finite)/np.linalg.norm(finite)<2e-7
