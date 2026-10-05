"""Independent checks for the approved external-case frequency extension."""
import numpy as np
from scipy.integrate import quad
from scipy.special import hankel1

from .ggb002 import noise, volume_kernel, qualify_adapter


def test_self_cell_matches_independent_radial_integration():
    area = (2/63)**2
    radius = np.sqrt(area/np.pi)
    for k in (2*np.pi/.75, 2*np.pi/0.24):
        def integrand(r):
            return .25j*hankel1(0,k*r)*2*np.pi*r
        integral = quad(lambda r: integrand(r).real,0,radius,epsabs=1e-13)[0] + 1j*quad(
            lambda r: integrand(r).imag,0,radius,epsabs=1e-13)[0]
        actual = volume_kernel(k,np.array([[0.,0.]]),area)[0,0]
        assert abs(actual-integral/area) < 1e-11


def test_noise_matches_receiver_first_released_convention():
    clean = (np.arange(20).reshape(4,5)+1)*(1+2j)
    actual,sigma = noise(clean)
    expected_sigma = .05*np.sqrt(np.mean(abs(clean)**2)/2)
    rng=np.random.RandomState(1000)
    receiver_first=clean.T
    expected=receiver_first+expected_sigma*(rng.randn(5,4)+1j*rng.randn(5,4))
    np.testing.assert_array_equal(actual,expected.T)
    assert sigma == expected_sigma


def test_full_panel_adapter_against_mie_and_rebuilt_geometry_cpu():
    receipt=qualify_adapter('cpu')
    assert receipt['passed']
    assert len(receipt['rows']) == 4
