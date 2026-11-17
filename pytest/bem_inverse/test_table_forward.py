"""Explicit CPU tables: analytic plane waves, disk scattering, masks and refusals."""
import numpy as np
import pytest
from scipy.special import jv, jvp, hankel1, h1vp

from bem_inverse import Execution, FourierCurve, Observation, PlaneWaveAcquisition, PointSourceAcquisition
from bem_inverse.a1_geometry import ModalGeometry
from bem_inverse.a3_waves import plane_wave_kernels
from bem_inverse.forward_solvers.modal_muller import ModalMuller, ModalSettings, forward_solve


def acquisition(mask=None):
    theta=np.array([.2,1.3,2.7])
    phi=np.arange(7)*2*np.pi/7
    return PlaneWaveAcquisition(np.c_[np.cos(theta),np.sin(theta)],
                                10*np.c_[np.cos(phi),np.sin(phi)],mask)


def disk_series(k, eta, radius, center, acq):
    orders=np.arange(-30,31)
    ki=k*np.sqrt(eta)
    jo,ji=jv(orders,k*radius),jv(orders,ki*radius)
    djo,dji=k*jvp(orders,k*radius),ki*jvp(orders,ki*radius)
    coefficient=(dji*jo-djo*ji)/(k*h1vp(orders,k*radius)*ji-hankel1(orders,k*radius)*dji)
    direction=np.arctan2(acq.directions[:,1],acq.directions[:,0])
    receiver=acq.receivers[:,0]+1j*acq.receivers[:,1]-center
    incoming=(1j)**orders[:,None]*np.exp(-1j*orders[:,None]*direction)
    incoming*=np.exp(1j*k*(acq.directions[:,0]*center.real+acq.directions[:,1]*center.imag))
    outgoing=hankel1(orders[:,None],k*abs(receiver))*np.exp(1j*orders[:,None]*np.angle(receiver))
    table=(coefficient[:,None]*incoming).T@outgoing
    return table if acq.mask is None else table[acq.mask]


def test_plane_wave_modal_coefficients_and_flux_match_translated_disk_series():
    k,radius,center=1.7,.8,.15-.2j
    geometry=ModalGeometry(FourierCurve.circle(radius,center),64)
    acq=acquisition()
    value,flux,info=plane_wave_kernels(geometry,k,acq.directions)
    m=np.arange(-64,65)
    theta=np.arctan2(acq.directions[:,1],acq.directions[:,0])
    phase=np.exp(1j*k*(acq.directions[:,0]*center.real+acq.directions[:,1]*center.imag))
    angular=(1j)**m[:,None]*np.exp(-1j*m[:,None]*theta)*phase
    np.testing.assert_allclose(value,jv(m,k*radius)[:,None]*angular,atol=1e-13,rtol=1e-12)
    np.testing.assert_allclose(flux,(k*radius*jvp(m,k*radius))[:,None]*angular,atol=1e-13,rtol=1e-12)
    assert info['plane_tail_bound']<=1e-16


@pytest.mark.parametrize('eta',[.33,2.])
@pytest.mark.parametrize('masked',[False,True])
def test_full_or_masked_disk_table_matches_independent_mie_series(eta,masked):
    mask=np.arange(21).reshape(3,7)%3!=0 if masked else None
    acq=acquisition(mask);k=1.;center=.15-.2j;radius=.8
    observation=Observation(k,acq,np.ones(acq.data_shape,complex),1.)
    context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
    prediction=forward_solve(FourierCurve.circle(radius,center),observation,eta,512,context=context)
    expected=disk_series(k,eta,radius,center,acq)
    assert prediction.prediction.shape==acq.data_shape
    assert np.linalg.norm(prediction.prediction-expected)/np.linalg.norm(expected)<1e-10


def test_new_mode_is_explicit_cpu_only_and_mask_validation_is_strict():
    acq=acquisition();obs=Observation(1.,acq,np.ones(acq.data_shape),1.)
    for context,match in [(ModalMuller(Execution(device='cpu')),'table_mode=True'),
                          (ModalMuller(Execution(device='auto'),ModalSettings(table_mode=True)),"device='cpu'")]:
        with pytest.raises(ValueError,match=match):
            forward_solve(FourierCurve.circle(),obs,.33,512,context=context)
    with pytest.raises(ValueError,match='mask'):
        acquisition(np.ones((3,7),int))
    with pytest.raises(ValueError,match='mask'):
        acquisition(np.zeros((3,7),bool))
    with pytest.raises(ValueError,match='paired=False'):
        PointSourceAcquisition(np.array([[4.,0.]]),np.array([[5.,0.]]),mask=np.ones((1,1),bool))


def test_masked_unpaired_point_sources_select_the_full_table():
    src=np.array([[4.,0.],[0.,4.]])
    rx=np.array([[5.,0.],[0.,5.],[-5.,0.]])
    mask=np.array([[True,False,True],[False,True,True]])
    context=ModalMuller(Execution(device='cpu',frequency_threads=1),ModalSettings(table_mode=True))
    values=[]
    for use_mask in [None,mask]:
        acq=PointSourceAcquisition(src,rx,paired=False,mask=use_mask)
        obs=Observation(1.,acq,np.ones(acq.data_shape),1.)
        values.append(forward_solve(FourierCurve.circle(),obs,2.,512,context=context).prediction)
    np.testing.assert_array_equal(values[1],values[0][mask])
