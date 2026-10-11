"""Independent controls for the NG-001 finite coefficient map and verifier."""
from unittest.mock import patch

import numpy as np

from bem_inverse.coefficient_geometry import CoefficientGeometry, crop
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse.interval_geometry import IntervalGeometry
from bem_inverse.spectral import spectral_project
from bem_inverse.analytic_projection import projection_derivatives


def test_circle_radius_identity_and_no_boundary_evaluation():
    curve=FourierCurve(crop(FourierCurve.circle(1.3,2+3j).coefficients,8))
    with (patch.object(FourierCurve,'values',side_effect=AssertionError('boundary samples')),
          patch.object(FourierCurve,'nodes',side_effect=AssertionError('boundary nodes'))):
        model=CoefficientGeometry(curve,2,band=64)
        zero,_,_=model.trial(np.zeros(5))
        moved,_,_=model.trial(np.array([.001,0,0,0,0]))
    np.testing.assert_array_equal(zero,curve.coefficients)
    expected=curve.coefficients.copy()
    expected[9] += .001/.05
    np.testing.assert_allclose(moved,expected,atol=2e-12,rtol=0)


def test_complete_tangent_matches_finite_map_and_independent_quadrature():
    curve=FourierCurve(crop(np.array([.06,2+3j,1.3]),8))
    model=CoefficientGeometry(curve,2,band=96)
    directions=np.array([[.1,.3,-.2,.05,.2],[-.2,.1,.2,.3,.1]])
    dot,_=model.tangent(directions)
    eps=1e-7
    finite=np.stack([(model.trial(eps*a)[0]-model.trial(-eps*a)[0])/(2*eps)
                     for a in directions],axis=1)
    np.testing.assert_allclose(dot,finite,atol=2e-7,rtol=2e-7)
    reference=projection_derivatives(curve,2,8,4096,.05)@directions.T
    np.testing.assert_allclose(dot,reference,atol=2e-7,rtol=2e-7)
    a=directions[0]*.001
    control=spectral_project(curve,a,8,8192,.05)[0]-spectral_project(curve,np.zeros(5),8,8192,.05)[0]
    np.testing.assert_allclose(model.trial(a)[0]-curve.coefficients,control,atol=1e-10,rtol=0)


def test_interval_cover_and_unresolved_crossing_without_nodes():
    verifier=IntervalGeometry(max_seconds=10.,max_depth=10)
    with (patch.object(FourierCurve,'values',side_effect=AssertionError('samples')),
          patch.object(FourierCurve,'nodes',side_effect=AssertionError('nodes'))):
        circle=FourierCurve.circle(1.3).coefficients
        result=verifier.certify(circle)
        assert result['outcome']=='valid' and result['arithmetic_verified']
        candidate=circle.copy()
        candidate[2] += .01
        assert verifier.increment(result,circle,candidate)['outcome']=='valid'
        crossing=np.zeros(5,complex)
        crossing[3:]=1
        bad=verifier.certify(crossing)
        assert bad['outcome']=='unresolved'


def test_interval_regularity_tail_is_not_discarded():
    verifier=IntervalGeometry(max_seconds=10.)
    curve=crop(FourierCurve.circle().coefficients,100)
    curve[-1]=1e-14
    result=verifier.certify(curve)
    assert result['outcome']=='valid'
    assert result['omitted_derivative_bound'] >= 100e-14
