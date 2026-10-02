import numpy as np
import pytest

from ordered_boundary import circle
from gpr_bem_kress import build_muller_system, build_exterior_receiver_operator, kress_incident_trace_on_boundary
from experiments.support_certificates.core import green
from .sommerfeld import Sommerfeld, buried_scattering, fresnel, outgoing_beta


def test_lossless_and_lossy_equal_media_limit():
    targets=np.array([[.03,-.12],[-.04,-.2]])
    sources=np.array([[.1,.07],[-.1,.08]])
    for k in (15.,15.+.5j):
        layer=Sommerfeld(k,k,order=64)
        actual=layer.transmitted(targets,sources)
        expected=green(k,targets,sources)
        assert np.linalg.norm(actual-expected)/np.linalg.norm(expected)<1e-10
        assert np.max(abs(layer.reflected(targets,targets)))==0


def test_fresnel_jump_conditions_and_energy_flux():
    for theta in np.linspace(0,1.4,7):
        xi=15*np.sin(theta)
        r,t=fresnel(15.,35.,xi)
        ba,bg=outgoing_beta(15.,xi),outgoing_beta(35.,xi)
        # Independently solve the two interface continuity equations.
        expected=np.linalg.solve(np.array([[1.,-1.],[ba,bg]],complex),[-1.,ba])
        np.testing.assert_allclose([r,t],expected,atol=1e-14)
        assert abs(abs(r)**2+bg.real/ba.real*abs(t)**2-1)<1e-13


def test_reflected_operator_normal_derivatives_by_finite_difference():
    layer=Sommerfeld(15.,35.+.8j,order=96)
    curve=circle(center=(.01,-.15),radius=.025).discretize(32)
    points,normals=curve.points,curve.normals
    s,d,kp,h=layer.reflected_blocks(points,normals,np.ones(len(points)))
    eps=1e-6
    direct=layer.reflected(points,points)
    ds=(layer.reflected(points,points+eps*normals)-layer.reflected(points,points-eps*normals))/(2*eps)
    dt=(layer.reflected(points+eps*normals,points)-layer.reflected(points-eps*normals,points))/(2*eps)
    mixed=(layer.reflected(points+eps*normals,points+eps*normals)
           -layer.reflected(points+eps*normals,points-eps*normals)
           -layer.reflected(points-eps*normals,points+eps*normals)
           +layer.reflected(points-eps*normals,points-eps*normals))/(4*eps**2)
    for actual,expected,tol in ((s,direct,1e-13),(d,ds,1e-7),(kp,dt,1e-7),(h,mixed,2e-6)):
        assert np.linalg.norm(actual-expected)/np.linalg.norm(expected)<tol


def test_buried_bie_free_space_limit_and_zero_contrast():
    curve=circle(center=(.01,-.15),radius=.025).discretize(48)
    sources=np.array([[-.12,.08],[.13,.07]])
    receivers=np.array([[-.1,.06],[0,.06],[.1,.06]])
    k,ki=15.,11.
    actual=buried_scattering(curve,k,k,ki,sources,receivers)
    system=build_muller_system(curve,k,ki)
    field,normal=kress_incident_trace_on_boundary(curve,sources,k)
    traces=np.linalg.solve(system.system_matrix,np.vstack((field.T,normal.T)))
    expected=build_exterior_receiver_operator(curve,receivers,k).apply_state(traces).T
    assert np.linalg.norm(actual.scattered-expected)/np.linalg.norm(expected)<1e-9
    assert actual.residual<1e-13
    empty=buried_scattering(curve,15.,35.+.8j,35.+.8j,sources,receivers,order=96)
    assert np.max(abs(empty.scattered))<1e-12


def test_side_contract_rejects_interface_crossing():
    curve=circle(center=(0,-.01),radius=.025).discretize(32)
    with pytest.raises(ValueError,match='below'):
        buried_scattering(curve,15.,35.,25.,[[0,.05]],[[.1,.05]])


def test_independent_volume_disk_converges_to_bie():
    from .run import volume_disk
    center,radius=np.array([.015,-.15]),.025
    sources=np.array([[-.12,.06]])
    receivers=np.array([[-.1,.05],[.1,.05]])
    ka,kg,ki=15.,35.+.8j,(35.+.8j)/np.sqrt(2.)
    boundary=buried_scattering(circle(center=tuple(center),radius=radius).discretize(64),
        ka,kg,ki,sources,receivers,order=96).scattered
    errors=[]
    for n in (12,24):
        volume,_=volume_disk(Sommerfeld(ka,kg,96),ki,center,radius,sources,receivers,n)
        errors.append(np.linalg.norm(volume-boundary)/np.linalg.norm(boundary))
    assert errors[-1]<errors[0] and errors[-1]<1e-3
