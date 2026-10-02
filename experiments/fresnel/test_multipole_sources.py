from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'solvers')]
import numpy as np
import pytest
from scipy.constants import c
from scipy.special import hankel1,jv,jvp,h1vp
from ordered_boundary import circle
from solvers.io.fresnel2001 import load_fresnel2001
from experiments.fresnel.multipole_sources import multipole_basis,fit_multipoles,evaluate_fit
from experiments.fresnel.multipole_forward import solve_multipole_forward,linearize_multipole_forward
from experiments.fresnel.run_fresnel2001 import coefficient_slots,curve_from_parameters,coefficient_directions
from experiments.fresnel.qualify_sources import synthetic_aperture_control


def test_analytic_gradient_hessian_and_helmholtz():
    points=np.array([[-.02,.01],[.04,-.03],[.03,.06]])
    source=np.array([.69,.10]); k=61.;order=4
    value,gradient,hessian=multipole_basis(points,source,k,order)
    np.testing.assert_allclose(np.trace(hessian,axis1=-2,axis2=-1),-k*k*value,rtol=4e-14,atol=2e-12)
    h=2e-6
    for d in range(2):
        plus,minus=points.copy(),points.copy();plus[:,d]+=h;minus[:,d]-=h
        vp,gp,_=multipole_basis(plus,source,k,order)
        vm,gm,_=multipole_basis(minus,source,k,order)
        np.testing.assert_allclose((vp-vm)/(2*h),gradient[...,d],rtol=2e-7,atol=2e-9)
        np.testing.assert_allclose((gp-gm)/(2*h),hessian[...,d],rtol=2e-7,atol=2e-8)


def test_svd_recovery_rotation_and_singularity_contract():
    angles=np.deg2rad(np.arange(60,301,5));points=.76*np.column_stack((np.cos(angles),np.sin(angles)))
    source=np.array([.72,0.]);k=30.;order=3
    coefficients=np.array([.1j,.2-.1j,.3,.8,.1j,-.2,.05])
    a=multipole_basis(points,source,k,order)[0]
    fit=fit_multipoles(a,a@coefficients)
    np.testing.assert_allclose(fit.coefficients,coefficients,rtol=2e-10,atol=2e-10)
    theta=.84;rot=np.array([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    values,gradient,hessian=evaluate_fit(points,source,k,fit)
    v2,g2,h2=evaluate_fit(points@rot.T,source@rot.T,k,fit)
    np.testing.assert_allclose(v2,values,rtol=2e-13,atol=1e-13)
    np.testing.assert_allclose(g2,gradient@rot.T,rtol=2e-12,atol=1e-12)
    np.testing.assert_allclose(h2,np.einsum('ij,pjk,lk->pil',rot,hessian,rot),rtol=3e-12,atol=1e-11)
    with pytest.raises(ValueError,match='singular'):multipole_basis(source[None],source,k,order)


def test_independent_finite_aperture_continuation_and_noise():
    x,y=np.meshgrid(np.linspace(-.08,.08,7),np.linspace(-.08,.08,7))
    rows=synthetic_aperture_control(np.column_stack((x.ravel(),y.ravel())))
    assert len(rows)==6
    assert max(r['target_field_and_scaled_gradient_error'] for r in rows)<.002


def exact_circle_scatter(center,radius,receiver,source,k,coefficients):
    # Independent Fourier-Bessel boundary matching, all mode coupling diagonal.
    theta=np.arange(512)*2*np.pi/512
    normal=np.column_stack((np.cos(theta),np.sin(theta)))
    points=center+radius*normal
    value,gradient,_=multipole_basis(points,source,k,(len(coefficients)-1)//2)
    u=value@coefficients;v=np.einsum('pmd,m,pd->p',gradient,coefficients,normal)
    uf,vf=np.fft.fft(u)/len(u),np.fft.fft(v)/len(v)
    orders=np.arange(-30,31);ki=k*np.sqrt(3)
    ji,jdi=jv(orders,ki*radius),ki*jvp(orders,ki*radius)
    h,hd=hankel1(orders,k*radius),k*h1vp(orders,k*radius)
    b=(jdi*uf[orders%len(u)]-ji*vf[orders%len(u)])/(ji*hd-jdi*h)
    delta=receiver-center;r=np.linalg.norm(delta,axis=1);angle=np.arctan2(delta[:,1],delta[:,0])
    return (hankel1(orders[None],k*r[:,None])*np.exp(1j*angle[:,None]*orders))@b


@pytest.mark.parametrize('ghz',[1,4])
def test_multipole_kress_matches_independent_circle_series(ghz):
    k=2*np.pi*ghz*1e9/c
    source=np.array([[.72,0.],[0.,.72]])
    angles=np.linspace(.7,5.5,9);receiver=.76*np.column_stack((np.cos(angles),np.sin(angles)))
    center=np.array([.005,.025]);radius=.015
    coeff=np.array([.1+.02j,.2j,1.,-.2+.1j,.06j])
    result=solve_multipole_forward(circle(tuple(center),radius).discretize(64),source,receiver,k,coeff)
    exact=np.array([exact_circle_scatter(center,radius,receiver,s,k,coeff) for s in source])
    assert np.linalg.norm(result.scattered_receiver-exact)/np.linalg.norm(exact)<1e-8
    assert result.incident_representation_relative_leak<1e-11
    assert result.linear_system_relative_residual<1e-11


def test_multipole_shape_jvp_matches_central_difference():
    k=2*np.pi*1e9/c;data=load_fresnel2001(ROOT/'data/fresnel/dielTM_dec8f.exp')
    slots=coefficient_slots(2);p=np.zeros(len(slots))
    p[slots.index(('cos',0,1))]=25;p[slots.index(('cos',1,0))]=15;p[slots.index(('sin',1,1))]=15
    coefficients=np.array([.1j,.2,1.,.1-.1j,-.05])
    source=data.source_points[:3];receiver=data.receiver_points[::7]
    curve=curve_from_parameters(p,2,64)
    base=solve_multipole_forward(curve,source,receiver,k,coefficients)
    for index in (0,2,7):
        analytic=linearize_multipole_forward(base,coefficient_directions(curve,2)[index])
        h=1e-3;up=p.copy();down=p.copy();up[index]+=h;down[index]-=h
        plus=solve_multipole_forward(curve_from_parameters(up,2,64),source,receiver,k,coefficients)
        minus=solve_multipole_forward(curve_from_parameters(down,2,64),source,receiver,k,coefficients)
        fd=(plus.scattered_receiver-minus.scattered_receiver)/(2*h)
        assert np.linalg.norm(analytic-fd)/np.linalg.norm(fd)<2e-6


def test_selected_measured_fourth_frequency_model_circle_and_jvp():
    data=load_fresnel2001(ROOT/'data/fresnel/dielTM_dec8f.exp');k=2*np.pi*4e9/c
    window=(np.arange(49)>=12)&(np.arange(49)<=36)
    points=data.receiver_points[data.receiver_labels[0]-1]
    a=multipole_basis(points,data.source_points[0],k,4)[0]
    fit=fit_multipoles(a[window],data.incident[3].mean(axis=0)[window])
    assert fit.rank==9
    center=np.array([.005,.025]);radius=.015
    curve=circle(tuple(center),radius).discretize(64)
    source=data.source_points[:2];receiver=data.receiver_points[::9]
    base=solve_multipole_forward(curve,source,receiver,k,fit.coefficients)
    exact=np.array([exact_circle_scatter(center,radius,receiver,s,k,fit.coefficients) for s in source])
    assert np.linalg.norm(base.scattered_receiver-exact)/np.linalg.norm(exact)<1e-7
    from gpr_bem_kress.shape_derivative import KressDirection
    velocity=np.broadcast_to([.001,0.],curve.points.shape)
    analytic=linearize_multipole_forward(base,KressDirection(points=velocity,first_derivatives=np.zeros_like(velocity)))
    errors=[]
    for h in (.03,.01):
        plus=solve_multipole_forward(circle(tuple(center+[h*.001,0.]),radius).discretize(64),source,receiver,k,fit.coefficients)
        minus=solve_multipole_forward(circle(tuple(center-[h*.001,0.]),radius).discretize(64),source,receiver,k,fit.coefficients)
        fd=(plus.scattered_receiver-minus.scattered_receiver)/(2*h)
        errors.append(np.linalg.norm(fd-analytic)/np.linalg.norm(analytic))
    assert errors[-1]<3e-6 and errors[-1]<errors[0]
