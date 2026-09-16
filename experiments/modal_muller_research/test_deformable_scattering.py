"""Shape-T derivatives: independent operator, finite-difference, and nodal checks."""
import numpy as np
import pytest
from ordered_boundary import PeriodicParameterization2D
from .coefficient_operator import LaurentGeometry,CoefficientGeometry
from .scattering_library import compile_template
from .deformable_scattering import compile_shape_jet,operator_shape_jet,DeformableEvaluator,LinearizedEvaluator
from .deformation_inverse import shape_fixture,NodalDeformableEvaluator,invert_relinearized


def test_laurent_scattering_derivative_matches_operator_and_recompilation():
    g=LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0)
    directions=[{1:.002/g.scale},{-1:.0015/g.scale},{-2:(.001+.0003j)/g.scale}]
    t,j,_=compile_shape_jet(g,directions,64.,45.25,.042,order=12)
    operator=operator_shape_jet(g,directions,64.,45.25,.042)
    assert np.linalg.norm(j-operator)/np.linalg.norm(operator)<1e-10
    tn,jn,_=compile_shape_jet(g,directions,64.,45.25,.042,order=12,backend='nodal',nodes=128)
    assert np.linalg.norm(j-jn)/np.linalg.norm(j)<1e-10
    assert np.linalg.norm(t.matrix-tn.matrix)/np.linalg.norm(t.matrix)<1e-10
    for i,d in enumerate(directions):
        def shifted(h):
            z=g.coefficients.copy()
            for k,v in d.items(): z[k]=z.get(k,0)+h*v
            return compile_template(LaurentGeometry(z,0j,g.scale),64.,45.25,
                                    normalization_radius=.042,order=12).matrix
        h=1e-4;fd=(shifted(h)-shifted(-h))/(2*h)
        assert np.linalg.norm(j[i]-fd)/np.linalg.norm(fd)<1e-7


@pytest.mark.parametrize('paired',[True,False])
def test_coupled_shape_pose_derivative_matches_kress_and_directional_fd(paired):
    acq,chart,x,_=shape_fixture(2)
    acq=dict(acq,source_points=acq['source_points'][::4],receiver_points=acq['receiver_points'][::4],
             source_strength=1e-6*np.exp(1j*np.linspace(-.6,.4,6)))
    if not paired: acq['receiver_points']=acq['receiver_points'][:-1]
    e=DeformableEvaluator(chart,acq,[1.25e9],paired=paired,order=14)
    reference=NodalDeformableEvaluator(chart,acq,[1.25e9],nodes=128,paired=paired)
    y,j=e.forward(x),e.jacobian(x)
    yr,jr=reference.forward(x),reference.jacobian(x)
    assert np.linalg.norm(y-yr)/np.linalg.norm(yr)<1e-9
    assert np.linalg.norm(j-jr)/np.linalg.norm(jr)<1e-8
    direction=np.random.default_rng(311).normal(size=chart.size)
    h=1e-4;fd=(e.forward(x+h*direction)-e.forward(x-h*direction))/(2*h)
    assert np.linalg.norm(j@direction-fd)/np.linalg.norm(fd)<1e-7


def test_shape_linear_model_has_quadratic_error_and_no_boundary_work(monkeypatch):
    acq,chart,truth,initial=shape_fixture(2)
    def forbidden(*args,**kwargs): raise AssertionError('Unexpected boundary work.')
    monkeypatch.setattr(PeriodicParameterization2D,'discretize',forbidden)
    exact=DeformableEvaluator(chart,acq,[1.25e9])
    model=LinearizedEvaluator(exact,initial)
    errors=[np.linalg.norm(exact.forward(h*truth)-model.forward(h*truth)) for h in [.05,.1]]
    assert 3.7<errors[1]/errors[0]<4.3
    monkeypatch.setattr(CoefficientGeometry,'__init__',forbidden)
    assert np.all(np.isfinite(model.forward(.2*truth)))
    assert np.all(np.isfinite(model.jacobian(.2*truth)))
    assert model.work['local_compilations']==0


def test_pose_changes_reuse_shape_jets_and_one_shape_change_is_local():
    acq,chart,truth,initial=shape_fixture(2)
    exact=DeformableEvaluator(chart,acq,[.5e9,1.25e9])
    exact.forward(initial)
    assert exact.work['local_compilations']==4
    x=initial.copy();x[:3]=truth[:3]
    exact.forward(x)
    assert exact.work['local_compilations']==4
    x[3]=.2
    exact.forward(x)
    assert exact.work['local_compilations']==6


def test_circle_shape_harmonics_have_specific_scattering_mode_bands():
    g=LaurentGeometry.circle(radius=.03)
    harmonics=[2,3,5]
    directions=[{1+k:.0005/g.scale,1-k:.0005/g.scale} for k in harmonics]
    t,j,_=compile_shape_jet(g,directions,64.,45.25,.04,order=12)
    difference=t.modes[None,:]-t.modes[:,None]
    for k,derivative in zip(harmonics,j):
        forbidden=np.abs(difference)!=k
        assert np.linalg.norm(derivative[forbidden])/np.linalg.norm(derivative)<1e-12


def test_relinearized_inverse_finishes_with_exact_shape_validation():
    acq,chart,truth,initial=shape_fixture(2)
    observations=NodalDeformableEvaluator(chart,acq,[.5e9,1.25e9],nodes=128).forward(truth)
    fitted=invert_relinearized(chart,acq,[.5e9,1.25e9],observations,initial,cutoff=16,bandwidth=32)
    assert fitted['success']
    assert fitted['residual_norm']<1e-8
    assert np.linalg.norm(np.array(fitted['parameters'])-truth)<1e-5
    assert fitted['work']['forward_evaluations']>=2
    assert fitted['history'][-1]['model_data_discrepancy']<1e-8
