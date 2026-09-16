"""Physical and algebraic checks independent of the native assembly path."""
import numpy as np
import pytest
from scipy.special import hankel1, h1vp, jv, jvp
from ordered_boundary import star, circle, PeriodicParameterization2D
from gpr_bem_kress.system import build_muller_system
from gpr_bem_kress.execution import execution
from .coefficient_operator import (LaurentGeometry, CoefficientGeometry, ModalMomentFamily,
                                   embed, kernel_matrix)
from .coefficient_fields import solve, RegularWaves, cross_matrix
from .modal import ModalSystem


def ring():
    theta = np.arange(5)*2*np.pi/5
    return np.column_stack((.25*np.cos(theta), .25*np.sin(theta)))


def test_exact_log_symbol_and_mode_selection():
    # exp(2it-3is) L(t-s): only m-n=-1, with entry -2pi/|n-3|.
    matrix = kernel_matrix(embed({(2, -3): 1}, 12), embed({},12), 5)
    expected = np.zeros_like(matrix)
    for i,m in enumerate(range(-5,6)):
        for j,n in enumerate(range(-5,6)):
            if m-n == -1 and n != 3:
                expected[i,j] = -2*np.pi/abs(n-3)
    np.testing.assert_allclose(matrix,expected,atol=2e-15)


def test_circle_matches_independent_mie_and_uses_no_boundary_nodes(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Native solve tried to discretize the boundary.')
    monkeypatch.setattr(PeriodicParameterization2D,'discretize',forbidden)
    ko,ki,radius=64.,45.25,.05
    sources=ring()
    receivers=ring()+np.array([.015,-.01])
    result=solve([LaurentGeometry.circle(radius=radius)],ko,ki,sources,receivers,
                 strengths=1.,cutoff=24,bandwidth=64,angular_order=32)
    modes=np.arange(-32,33)
    jo,ji=jv(modes,ko*radius),jv(modes,ki*radius)
    djo,dji=ko*jvp(modes,ko*radius),ki*jvp(modes,ki*radius)
    ho,dho=hankel1(modes,ko*radius),ko*h1vp(modes,ko*radius)
    ratio=(dji*jo-ji*djo)/(ji*dho-dji*ho)
    s=sources[:,0]+1j*sources[:,1]
    r=receivers[:,0]+1j*receivers[:,1]
    incident=.25j*hankel1(modes[:,None],ko*np.abs(s)[None,:])*np.exp(-1j*modes[:,None]*np.angle(s)[None,:])
    outgoing=hankel1(modes[None,:],ko*np.abs(r)[:,None])*np.exp(1j*modes[None,:]*np.angle(r)[:,None])
    exact=(outgoing*ratio)@incident
    assert np.linalg.norm(result['y']-exact)/np.linalg.norm(exact)<2e-11
    assert result['boundary_nodes']==result['point_pair_kernel_calls']==0


def test_flux_muller_all_blocks_against_dense_oracle():
    curve=star((0,0),.036,.24,5,rotation=.2).discretize(256,require_even=True)
    with execution(kernels='real_bessel'):
        physical=build_muller_system(curve,64.,45.25).system_matrix
    modal=ModalSystem.from_nodal(physical,np.zeros((512,1)),np.zeros((1,512)),[curve])
    cutoff=24
    index=np.r_[np.arange(-cutoff,cutoff+1)%256,256+np.arange(-cutoff,cutoff+1)%256]
    exact=modal.a[np.ix_(index,index)]
    direct,_=CoefficientGeometry(LaurentGeometry.star(),64).assemble(64.,45.25,cutoff)
    np.testing.assert_allclose(direct,exact,rtol=1e-10,atol=3e-13)


def test_compiled_family_matches_fresh_assembly_at_unseen_waves():
    prepared=CoefficientGeometry(LaurentGeometry.star(),64)
    family=ModalMomentFamily(prepared,24,24)
    for ko,ki in [(25.,18.),(62.,40.5)]:
        fast,_=family.assemble(ko,ki)
        direct,_=prepared.assemble(ko,ki,24,24)
        np.testing.assert_allclose(fast,direct,rtol=1e-10,atol=3e-13)


def test_zero_contrast_identity_and_zero_scattering():
    g=LaurentGeometry.star()
    prepared=CoefficientGeometry(g,64)
    matrix,_=prepared.assemble(32.,32.,32)
    np.testing.assert_array_equal(matrix,np.eye(130))
    result=solve([g],32.,32.,ring(),ring()+.01,prepared=[prepared],
                 cutoff=32,bandwidth=64,angular_order=32)
    assert np.linalg.norm(result['y'])<1e-17


def test_cross_translation_matches_direct_exterior_kernel_oracle():
    from gpr_bem_kress.multicomponent import build_exterior_cross_blocks
    cutoff=16
    gt,gs=LaurentGeometry.circle(0j,.03),LaurentGeometry.circle(.2+.04j,.035)
    target=circle((0,0),.03,component_id='t').discretize(128,require_even=True)
    source=circle((.2,.04),.035,component_id='s').discretize(128,require_even=True)
    cross=build_exterior_cross_blocks(target,source,48.)
    # Different component radii require different row and column flux scalings.
    p=np.exp(1j*np.arange(128)[:,None]*(2*np.pi/128)*np.arange(-cutoff,cutoff+1))/np.sqrt(128)
    exact=np.block([[-p.conj().T@cross.k@p, p.conj().T@cross.v@p/.035],
                    [-.03*p.conj().T@cross.t@p, (.03/.035)*p.conj().T@cross.kp@p]])
    native=cross_matrix(RegularWaves(gt,48.,64,28),RegularWaves(gs,48.,64,28),cutoff)
    np.testing.assert_allclose(native,exact,rtol=1e-9,atol=3e-13)


def test_expansion_domains_fail_explicitly():
    # A clearly uncertified quotient must not silently apply the log series.
    with pytest.raises(ValueError,match='certificate'):
        CoefficientGeometry(LaurentGeometry.from_coefficients({1:1,-1:2}),32)
    waves=RegularWaves(LaurentGeometry.circle(radius=.05),32.,32,16)
    with pytest.raises(ValueError,match='bounding circle'):
        waves.point_kernels([[.01,0]])
    with pytest.raises(ValueError,match='bounding circles'):
        cross_matrix(waves,waves,12)
