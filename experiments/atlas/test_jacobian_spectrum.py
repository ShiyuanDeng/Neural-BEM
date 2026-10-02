"""Independent numerical gates for atlas coordinates and physical derivatives."""
import numpy as np
from experiments.atlas.run_jacobian_spectrum import (
    NormalBasis, acquisition, circle, ellipse, validate_columns, solve, circle_mie, relative, spectral,
)


def test_normal_basis_metric_and_jets():
    p = ellipse((.5,.5),.04,.025)
    basis = NormalBasis(p,5)
    t = np.linspace(0,2*np.pi,4096,endpoint=False)
    curve = p.discretize(len(t))
    a = basis.values(t)
    assert np.max(abs(a.T @ (a*curve.arc_length_weights[:,None])/basis.length-np.eye(11))) < 1e-8
    t = np.array([.23,1.34,4.5])
    step = 1e-5
    v, v1, v2 = basis.jets(t,7)
    plus, minus = basis.jets(t+step,7), basis.jets(t-step,7)
    np.testing.assert_allclose((plus[0]-minus[0])/(2*step),v1,rtol=1e-7,atol=1e-8)
    np.testing.assert_allclose((plus[1]-minus[1])/(2*step),v2,rtol=1e-7,atol=1e-8)


def test_kress_analytic_and_reciprocal_against_fd():
    p = ellipse((.5,.5),.04,.025)
    basis = NormalBasis(p,5)
    sources, receivers = acquisition(4)
    rows = validate_columns(p,basis,2.,4.,128,sources,receivers,[0,3,8])
    assert max(r['fd_relative'] for r in rows) < 2e-6
    assert max(r['reciprocal_relative'] for r in rows) < 2e-6


def test_circle_independent_mie():
    sources,receivers = acquisition(4)
    base = solve((circle((.5,.5),.03),),8.,9.,128,sources,receivers)
    assert relative(base.Y.T,circle_mie(8.,9.,sources,receivers)) < 1e-9


def test_real_stacking_keeps_structural_nullspace():
    j = np.array([[1.,1j,0.,0.,0.],[0.,0.,1.,1j,0.]])
    s,vh,m = spectral(j,j)
    assert vh.shape == (5,5)
    assert m['rank'] == 4 and m['structural_nullity'] == 1
    np.testing.assert_allclose(s,[1,1,1,1,0])
    np.testing.assert_allclose(j @ vh[-1],0.)
