import numpy as np
from bem_inverse.continuation.geometry import FourierCurve
from bem_inverse import geometry as G
from .gc001 import moved_curve, UNIT
from .gc001_aliasing import resampled


def test_native_output_reproduces_maintained_spline():
    curve=G.resize(FourierCurve(np.array([.08j,10+10j,1.3])),8)
    a=np.array([.001,.0003,-.0002])
    moved=moved_curve(curve,a,1024)
    actual,_=resampled(moved,1024,1024,8)
    expected=G.project(curve,a,8,1024,UNIT)[0]
    np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-14)


def test_direct_fourier_position_and_output_refinement_on_circle():
    curve=FourierCurve.circle(1.3,10+10j)
    for n in (1024,2048,4096):
        actual,bound=resampled(curve,1024,n,8,direct=True)
        expected=G.resize(curve,8).coefficients
        np.testing.assert_allclose(actual,expected,rtol=0,atol=1e-14)
        assert bound==0
