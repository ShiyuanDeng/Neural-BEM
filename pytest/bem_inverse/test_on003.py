"""Meaningful analytic/control guards for ON-003, never a default backend."""
import numpy as np
from scipy.integrate import quad
from bem_inverse.on003_ewald import flat_near, near_kernel, far_kernel, cutoff, circle_near, circle_exact


def test_flat_heat_transform_and_grazing():
    k=13.+3.25j; tau=2e-5
    for omega in (0.,13.,26.):
        a=omega**2-k*k
        f=lambda u: np.sqrt(tau/np.pi)*np.exp(-a*tau*u*u)
        reference=quad(lambda u:f(u).real,0,1,epsabs=1e-14)[0]+1j*quad(lambda u:f(u).imag,0,1,epsabs=1e-14)[0]
        np.testing.assert_allclose(flat_near(omega,k,tau),reference,rtol=1e-12,atol=1e-14)
    np.testing.assert_allclose(flat_near(13.,13.,tau),np.sqrt(tau/np.pi),rtol=1e-15)


def test_heat_kernel_against_independent_integral_and_outgoing_split():
    from scipy.special import hankel1
    k=52.+13j; tau=1e-5
    for r in (1e-4,.002,.02):
        f=lambda u:np.exp(k*k*tau*u-r*r/(4*tau*u))/(4*np.pi*u) if u else 0j
        ref=quad(lambda u:f(u).real,0,1,epsabs=1e-12)[0]+1j*quad(lambda u:f(u).imag,0,1,epsabs=1e-12)[0]
        np.testing.assert_allclose(near_kernel(r,k,tau),ref,rtol=1e-10,atol=1e-12)
        np.testing.assert_allclose(near_kernel(r,k,tau)+far_kernel(r,k,tau),.25j*hankel1(0,k*r),rtol=1e-13)
    np.testing.assert_allclose(far_kernel(1e-9,k,tau),far_kernel(0.,k,tau),rtol=1e-11,atol=1e-12)


def test_exact_circle_matches_maue_and_near_quadrature_refinement():
    k=18.+4.5j; a=.065; tau=1e-4; n=np.arange(-10,11)
    exact=circle_exact(a,k,n)
    Vm=circle_exact(a,k,n-1)[0]; Vp=circle_exact(a,k,n+1)[0]
    np.testing.assert_allclose(exact[2],-n*n*exact[0]+a*a*k*k/2*(Vm+Vp),rtol=2e-12,atol=2e-13)
    np.testing.assert_allclose(circle_near(a,k,tau,n,1024),circle_near(a,k,tau,n,2048),rtol=1e-10,atol=1e-12)


def test_cutoff_exact_support_and_smooth_transition():
    r=np.array([0.,.1,.11,.12,.13,.14])
    w=cutoff(r,.1,.14)
    np.testing.assert_array_equal(w[:2],[1,1]); assert w[-1]==0
    assert np.all(np.diff(w)<=0); np.testing.assert_allclose(w[3],.5)


def test_radial_transform_zero_mode_normalization_and_grid_layout():
    from bem_inverse.on003_ewald import FarGrid, far_kernel
    k=13.+3.25j; tau=1e-5
    grid=FarGrid.build(128,tau,.16)
    diagonal,info=grid.multiplier(k,256)
    assert grid.inverse.shape==(128**2,) and diagonal.shape==(128**2,)
    f=lambda r:2*np.pi*r*complex(far_kernel(r,k,tau))*float(cutoff(r,grid.R0,grid.R1))/grid.period**2
    expected=quad(lambda r:f(r).real,0,grid.R1,points=[grid.R0],epsabs=1e-12)[0]+1j*quad(lambda r:f(r).imag,0,grid.R1,points=[grid.R0],epsabs=1e-12)[0]
    np.testing.assert_allclose(diagonal[0],expected,rtol=1e-10,atol=1e-12)
    cap=np.pi*grid.size/grid.period
    nyquist=np.any(np.isclose(abs(grid.q),cap,rtol=1e-13,atol=0),axis=1)
    assert np.all(diagonal[nyquist]==0)


def test_circle_heat_time_reference_is_independent_of_angular_quadrature():
    from bem_inverse.on003_circle_reference import heat_circle
    n=np.arange(-10,11); a=.065; k=18.+4.5j; tau=1e-4
    reference=heat_circle(a,k,tau,n,512)
    np.testing.assert_allclose(heat_circle(a,k,tau,n,256),reference,rtol=1e-10,atol=1e-12)
    np.testing.assert_allclose(circle_near(a,k,tau,n,2048),reference,rtol=1e-9,atol=1e-11)
