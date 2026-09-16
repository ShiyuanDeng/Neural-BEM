"""No frequency systems/factorizations: geometry jet and input-contract tests."""
import numpy as np
import pytest
from ordered_boundary import circle, fourier_curve
from gpr_bem_kress.shape_derivative import KressDirection
from .operators import component_jets
from .support import deserialize, state_directions


def test_translation_and_native_period_shape_jets():
    curve=fourier_curve([[.5,.5],[.03,0]],[[0,0],[0,.02]],component_id='a',period=3.7).discretize(24)
    zero=np.zeros_like(curve.points)
    direction=KressDirection(np.tile([1.,-.5],(24,1)),zero,zero,zero)
    p,n,s,a=component_jets(curve,direction)
    np.testing.assert_allclose(n.v,curve.normals,atol=2e-15)
    np.testing.assert_allclose(a.v,curve.arc_length_weights,atol=2e-15)
    assert np.count_nonzero(n.d)==np.count_nonzero(s.d)==np.count_nonzero(a.d)==0


def test_shape_only_and_component_grid_validation():
    curve=circle((.5,.5),.03).discretize(24)
    with pytest.raises(ValueError,match='shape directions only'):
        component_jets(curve,KressDirection(exterior_epsr=1.))
    with pytest.raises(ValueError,match='node grid'):
        component_jets(curve,KressDirection(points=np.zeros((26,2)),
                                            first_derivatives=np.zeros((26,2))))


def test_coefficient_direction_jets_have_native_derivative_consistency():
    from ordered_boundary import OrderedBoundary2D
    state=deserialize([dict(chart='cartesian',maximum_mode=2,component_id='a',
        parameters=[.5,.5,.03,0,0,0,0,.03,0,0])])
    boundary=OrderedBoundary2D(tuple(c.parameterization().discretize(32) for c in state.components))
    d=np.zeros(10);d[4]=1.
    result=state_directions(state,boundary,d)[0]
    t=boundary.parameters
    np.testing.assert_allclose(result.points[:,0],np.cos(2*t),atol=1e-14)
    np.testing.assert_allclose(result.first_derivatives[:,0],-2*np.sin(2*t),atol=1e-14)
    np.testing.assert_allclose(result.second_derivatives[:,0],-4*np.cos(2*t),atol=1e-14)


def test_moving_normal_and_arc_jets_agree_with_geometry_differences():
    curve=circle((.5,.5),.03).discretize(32)
    direction=KressDirection(curve.points-[.5,.5],curve.first_derivatives,
                             curve.second_derivatives,curve.third_derivatives)
    _,n,s,a=component_jets(curve,direction)
    np.testing.assert_allclose(n.d,0,atol=2e-15)
    np.testing.assert_allclose(a.d,curve.arc_length_weights,atol=2e-15)
    np.testing.assert_allclose(s.d,curve.speeds,atol=2e-15)
