"""Independent Mie, rotation, coupled derivatives, and no-online-BIE checks."""
import numpy as np
import pytest
from scipy.special import jv,jvp,hankel1,h1vp
from ordered_boundary import PeriodicParameterization2D
from experiments.bie002_modal_diagnostic.fixtures import inputs
from .coefficient_operator import LaurentGeometry,CoefficientGeometry
from .scattering_library import compile_template,PoseChart
from .pose_inverse import PoseEvaluator


@pytest.mark.parametrize('backend',['native','nodal'])
def test_compiled_circle_matches_analytic_mie(backend):
    ko,ki,radius=64.,45.25,.03
    t=compile_template(LaurentGeometry.circle(radius=radius),ko,ki,order=10,backend=backend)
    m=t.modes
    exact=(ki*jvp(m,ki*radius)*jv(m,ko*radius)-jv(m,ki*radius)*ko*jvp(m,ko*radius))/(jv(m,ki*radius)*ko*h1vp(m,ko*radius)-ki*jvp(m,ki*radius)*hankel1(m,ko*radius))
    expected=np.diag(exact/t.normalization**2)
    assert np.linalg.norm(t.matrix-expected)/np.linalg.norm(expected)<5e-11


def test_rotating_compiled_laurent_object_matches_recompilation():
    g=LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0)
    alpha=.37
    rotated=LaurentGeometry({j:v*np.exp(1j*alpha) for j,v in g.coefficients.items()},0j,g.scale)
    original=compile_template(g,64.,45.25,order=10)
    reference=compile_template(rotated,64.,45.25,order=10)
    actual,derivative=original.rotated(alpha)
    assert np.linalg.norm(actual-reference.matrix)/np.linalg.norm(reference.matrix)<1e-10
    h=1e-5
    fd=(original.rotated(alpha+h)[0]-original.rotated(alpha-h)[0])/(2*h)
    assert np.linalg.norm(fd-derivative)/np.linalg.norm(derivative)<1e-8


@pytest.mark.parametrize('paired',[True,False])
def test_compiled_pose_matches_coupled_kress_with_complex_sources(paired):
    acq,_=inputs()
    acq=dict(acq,source_points=acq['source_points'][::4],receiver_points=acq['receiver_points'][::4],
             source_strength=1e-6*np.exp(1j*np.linspace(-.6,.4,6)))
    if not paired: acq['receiver_points']=acq['receiver_points'][:-1]
    chart=PoseChart([LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0),
                    LaurentGeometry.star(radius=.028,amplitude=.12,lobes=3,rotation=0)],
                   [.44+.49j,.56+.51j])
    x=np.array([.5,-.4,.3,-.4,.3,-.25])
    oracle=PoseEvaluator(chart,acq,[1.25e9],backend='nodal_rebuild',nodes=128,paired=paired)
    expected,expected_j=oracle.forward(x),oracle.jacobian(x)
    evaluator=PoseEvaluator(chart,acq,[1.25e9],paired=paired)
    actual,jac=evaluator.forward(x),evaluator.jacobian(x)
    assert np.linalg.norm(actual-expected)/np.linalg.norm(expected)<1e-9
    assert np.linalg.norm(jac-expected_j)/np.linalg.norm(expected_j)<1e-8
    direction=np.random.default_rng(17).normal(size=6)
    h=1e-5
    finite=(evaluator.forward(x+h*direction)-evaluator.forward(x-h*direction))/(2*h)
    assert np.linalg.norm(jac@direction-finite)/np.linalg.norm(finite)<1e-7


def test_native_library_and_online_pose_need_no_boundary_nodes_or_reassembly(monkeypatch):
    def forbidden(*args,**kwargs):
        raise AssertionError('Unexpected boundary sampling or online BIE assembly.')
    monkeypatch.setattr(PeriodicParameterization2D,'discretize',forbidden)
    acq,_=inputs()
    shape=LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0)
    chart=PoseChart([shape,shape],[.44+.49j,.56+.51j])
    evaluator=PoseEvaluator(chart,acq,[1.25e9])
    assert evaluator.work['compiled_templates']==1
    monkeypatch.setattr(CoefficientGeometry,'__init__',forbidden)
    for offset in [.1,.2]:
        x=np.array([offset,0,.2,-offset,0,-.2])
        assert np.all(np.isfinite(evaluator.forward(x)))
        assert np.all(np.isfinite(evaluator.jacobian(x)))
        assert all(s.boundary_unknowns==s.boundary_nodes==0 for s in evaluator.states)


def test_library_can_be_reused_across_component_type_assignments(monkeypatch):
    acq,_=inputs()
    shapes=[LaurentGeometry.ellipse(major=.033,minor=.025,rotation=0),
            LaurentGeometry.star(radius=.028,amplitude=.12,lobes=3,rotation=0)]
    cache={}
    first=PoseEvaluator(PoseChart(shapes,[.44+.49j,.56+.51j]),acq,[1.25e9],template_cache=cache)
    assert first.work['compiled_templates']==2
    def forbidden(*args,**kwargs):
        raise AssertionError('Previously compiled shapes should survive reassignment.')
    monkeypatch.setattr(CoefficientGeometry,'__init__',forbidden)
    second=PoseEvaluator(PoseChart(shapes[::-1],[.44+.49j,.56+.51j]),acq,[1.25e9],template_cache=cache)
    assert second.work['compiled_templates']==0
    assert np.all(np.isfinite(second.forward(np.zeros(6))))
