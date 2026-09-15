"""No physical kernels or solves: independent polynomial matrix controls."""
import numpy as np
from scipy.linalg import lu_factor
from .models import tangent, operator_prediction, break_even
from .fixtures import producer, coefficients


def family():
    rng = np.random.default_rng(20260915)
    arrays = [rng.normal(size=shape)+1j*rng.normal(size=shape)
              for shape in [(5,5),(5,2),(3,5)]*3]
    arrays[0] += 12*np.eye(5)
    return arrays[:3], arrays[3:6], arrays[6:]


def test_affine_operator_is_exact_and_tangent_has_quadratic_error():
    (a,b,c), d, _ = family()
    u = np.linalg.solve(a,b); dy = tangent(a,b,c,u,lu_factor(a),d)
    errors=[]
    for h in [.01,.005,.0025]:
        exact=(c+h*d[2])@np.linalg.solve(a+h*d[0],b+h*d[1])
        pred=operator_prediction(a,b,c,d,h)
        np.testing.assert_allclose(pred['Y'],exact,rtol=2e-14,atol=2e-14)
        assert pred['approximate_residual'] < 1e-13
        errors.append(np.linalg.norm(c@u+h*dy-exact))
    np.testing.assert_allclose(np.array(errors[:-1])/errors[1:],4,rtol=.015)


def test_nonlinear_operators_leave_both_models_with_quadratic_error():
    (a,b,c),d,q = family();u=np.linalg.solve(a,b)
    dy=tangent(a,b,c,u,lu_factor(a),d); errors=[]
    for h in [.001,.0005,.00025]:
        aa,bb,cc=[x+h*y+h*h*z for x,y,z in zip((a,b,c),d,q)]
        exact=cc@np.linalg.solve(aa,bb)
        op=operator_prediction(a,b,c,d,h)['Y']
        errors.append([np.linalg.norm(c@u+h*dy-exact),np.linalg.norm(op-exact),
                       np.linalg.norm(op-(c@u+h*dy))])
    e=np.array(errors)
    np.testing.assert_allclose(e[:-1]/e[1:],4,rtol=.015)


def test_coefficient_correspondence_has_exact_linear_point_jets():
    record=dict(maximum_mode=3,parameters=[.5,.5,.04,.002,0,0,.001,0,
                                         .002,.05,0,0,0,.001])
    c,s=coefficients(record); dc=np.zeros_like(c);ds=np.zeros_like(s)
    dc[2]=[.3,.1];ds[3]=[-.2,.4]
    t=np.linspace(0,2*np.pi,256,endpoint=False);h=.001
    base=producer(c,s).evaluate(t);changed=producer(c+h*dc,s+h*ds).evaluate(t)
    direction=producer(dc,ds).evaluate(t)
    for field in ('points','first_derivatives','second_derivatives','third_derivatives'):
        np.testing.assert_allclose(getattr(changed,field)-getattr(base,field),
                                   h*getattr(direction,field),atol=3e-16)


def test_break_even_requires_positive_saving():
    assert break_even(.3,.2,.1)==3
    assert break_even(.3,.1,.1) is None
    assert break_even(.3,.1,.2) is None
