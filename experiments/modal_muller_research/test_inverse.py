"""Independent checks of native mode contractions and the inverse Jacobian."""
import numpy as np
import pytest
from .coefficient_operator import kernel_matrix,kernel_matrix_reference
from .inverse import ShapeChart,ShapeEvaluator,invert
from experiments.bie002_modal_diagnostic.fixtures import inputs


def test_inverse_does_not_silently_drop_material_properties():
    acq,_=inputs()
    for backend in ('native','nodal'):
        for key,value in [('mur',2.),('sigma',.01)]:
            unsupported=dict(acq,interior=dict(acq['interior'],**{key:value}))
            with pytest.raises(ValueError,match='lossless materials with mur=1'):
                ShapeEvaluator(ShapeChart(),unsupported,[.5e9],backend=backend)


def test_fast_singular_contraction_matches_literal_sum_without_wraparound():
    rng=np.random.default_rng(19)
    for bandwidth,cutoff in [(9,4),(16,12)]:
        p=rng.normal(size=(2*bandwidth+1,)*2)+1j*rng.normal(size=(2*bandwidth+1,)*2)
        q=rng.normal(size=p.shape)+1j*rng.normal(size=p.shape)
        np.testing.assert_allclose(kernel_matrix(p,q,cutoff),kernel_matrix_reference(p,q,cutoff),
                                   rtol=5e-14,atol=8e-14)


def test_native_shape_jacobian_matches_nodal_and_centered_differences():
    acq,_=inputs()
    chart=ShapeChart()
    x=np.array([1.2,-.8,.9,.4,-.2,.2,.1,1.1,1.3])
    frequency=[1.25e9]
    native=ShapeEvaluator(chart,acq,frequency,cutoff=24,bandwidth=48)
    nodal=ShapeEvaluator(chart,acq,frequency,backend='nodal',nodes=128)
    y,j=native.forward(x),native.jacobian(x)
    expected,expected_j=nodal.forward(x),nodal.jacobian(x)
    assert np.linalg.norm(y-expected)/np.linalg.norm(expected)<1e-8
    errors=np.linalg.norm(j-expected_j,axis=(0,1))/np.linalg.norm(expected_j,axis=(0,1))
    assert max(errors)<2e-7
    direction=np.random.default_rng(7).normal(size=chart.size)
    direction/=np.linalg.norm(direction)
    h=1e-4
    fd=(native.forward(x+h*direction)-native.forward(x-h*direction))/(2*h)
    tangent=j@direction
    assert np.linalg.norm(tangent-fd)/np.linalg.norm(fd)<2e-7


def test_complete_native_circle_inverse_uses_independent_observations():
    acq,_=inputs()
    chart=ShapeChart(modes=())
    truth=np.array([.4,-.3,.9])
    frequencies=[.5e9,1.25e9]
    observed=ShapeEvaluator(chart,acq,frequencies,backend='nodal',nodes=128).forward(truth)
    result=invert(chart,acq,frequencies,observed,[0.,0.,1.],cutoff=12,bandwidth=24,
                  terms=20,max_nfev=20,continuation=False)
    assert all(s['success'] for s in result['stages'])
    np.testing.assert_allclose(result['parameters'],truth,atol=2e-7,rtol=0)


def test_reciprocity_jacobians_match_refined_operator_with_complex_strengths():
    acq,_=inputs()
    acq=dict(acq)
    acq['source_strength']=1e-6*np.exp(1j*np.linspace(-.7,.9,len(acq['source_points'])))
    chart=ShapeChart()
    x=np.array([1.2,-.8,.9,.4,-.2,.2,.1,1.1,1.3])
    ref=ShapeEvaluator(chart,acq,[1.25e9],backend='nodal',nodes=128)
    exact=ref.jacobian(x)
    for backend,options in [('native',dict(cutoff=24,bandwidth=40)),('nodal',dict(nodes=64))]:
        candidate=ShapeEvaluator(chart,acq,[1.25e9],backend=backend,jacobian_kind='hadamard',**options)
        jac=candidate.jacobian(x)
        error=np.linalg.norm(jac-exact,axis=(0,1))/np.linalg.norm(exact,axis=(0,1))
        assert max(error)<5e-8
    direction=np.random.default_rng(19).normal(size=chart.size)
    direction/=np.linalg.norm(direction)
    native=ShapeEvaluator(chart,acq,[1.25e9],cutoff=32,bandwidth=64,jacobian_kind='hadamard')
    jac=native.jacobian(x)
    h=1e-4
    finite=(native.forward(x+h*direction)-native.forward(x-h*direction))/(2*h)
    assert np.linalg.norm(jac@direction-finite)/np.linalg.norm(finite)<1e-7


def test_hadamard_has_exact_tangential_null_direction():
    acq,_=inputs()
    chart=ShapeChart()
    x=np.array([1.2,-.8,.9,.4,-.2,.2,.1,1.1,1.3])
    evaluator=ShapeEvaluator(chart,acq,[1.25e9],cutoff=24,bandwidth=40)
    evaluator.forward(x)
    z=chart.geometry(x).coefficients
    # A cyclic reparameterization moves points tangentially without changing shape.
    tangent={j:1j*j*v for j,v in z.items()}
    value=evaluator.base.hadamard_jacobian([tangent])[0]
    assert np.linalg.norm(value)<1e-18
