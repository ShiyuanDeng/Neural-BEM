"""Independent checks for the sphere-only IBIM prototype."""
import numpy as np
from scipy.special import spherical_jn
from .sphere import narrow_band, assemble, delta_radial, eigenvalues, run_case, mie


def test_coarea_area_and_translation():
    for shift in ((.137,.271,.389),(.31,.07,.21)):
        points,weights,m=narrow_band(.17,shift=shift)
        assert m['area_relative_error'] < 3e-4
        # Centroid error is measured as a fraction of the unit radius.
        assert np.linalg.norm(np.sum(points*weights[:,None],axis=0))/weights.sum() < 5e-4
        np.testing.assert_allclose(np.linalg.norm(points,axis=1),1,atol=1e-14)


def test_radial_difference_matches_derivative():
    r=np.array([.005,.03,.2,1.])
    h=1e-6
    v,g1,g2=delta_radial(r,1.,2.)
    p=delta_radial(r+h,1.,2.);m=delta_radial(r-h,1.,2.)
    np.testing.assert_allclose((p[0]-m[0])/(2*h),g1,rtol=1e-7,atol=1e-8)
    np.testing.assert_allclose((p[1]-m[1])/(2*h),g2,rtol=1e-6,atol=1e-8)


def test_nonconstant_spherical_harmonic_operator():
    points,weights,_=narrow_band(.17)
    n=len(points);a=assemble(points,weights,1.,2.)
    y=points[:,2]
    v,k,t=np.subtract(eigenvalues(1.,1.,1),eigenvalues(2.,1.,1))
    predicted=a@np.r_[y,np.zeros(n)]
    reference=np.r_[(1-k)*y,-t*y]
    assert np.linalg.norm(predicted-reference)/np.linalg.norm(reference)<.003


def test_transmission_against_independent_3d_mie():
    coarse,_,_=run_case(.35,3.)
    fine,_,_=run_case(.17,3.)
    assert fine['field_relative_error'] < .003
    assert fine['field_relative_error'] < coarse['field_relative_error']/3
    r=np.array([[0.,0.,3.],[3.,0.,0.]])
    np.testing.assert_allclose(mie(2.,2.,r),0,atol=1e-14)
