import numpy as np
import pytest
import torch

from experiments.cleaned_interface.n_update import curve_certificate
from experiments.cleaned_interface.nu006 import BatchedCertifiedUpdate
from experiments.cleaned_interface.nu007 import DeviceCertifiedUpdate, device_certificate
from experiments.shape_continuation.geometry import FourierCurve

DEVICES = ['cpu', pytest.param('cuda', marks=pytest.mark.skipif(not torch.cuda.is_available(), reason='no CUDA'))]


def kite(K=24):
    t = 2*np.pi*np.arange(1024)/1024
    z = (np.cos(t)+.65*np.cos(2*t)-.65)+1.5j*np.sin(t)
    return FourierCurve.from_samples(z, K)


@pytest.mark.parametrize('device', DEVICES)
@pytest.mark.parametrize('window', [16, 64])
def test_device_certificate_matches_host(device, window):
    curve = kite()
    host, port = curve_certificate(curve, window), device_certificate(curve, window, device)
    for key in ('rho', 'reciprocal_l1', 'beta', 'Lambda', 'nu'):
        assert port[key] == pytest.approx(host[key], rel=1e-10, abs=1e-12)   # rho sits at FFT round-off
    assert port['log_degree'] == host['log_degree']


@pytest.mark.parametrize('device', DEVICES)
def test_device_certificate_refuses_figure_eight(device):
    t = 2*np.pi*np.arange(1024)/1024
    eight = FourierCurve.from_samples(np.sin(2*t)/2+1j*np.sin(t)+.01*np.cos(t), 8)
    with pytest.raises(ValueError):
        curve_certificate(eight, 32)
    with pytest.raises(ValueError):
        device_certificate(eight, 32, device)


@pytest.mark.parametrize('device', DEVICES)
def test_update_tiers_match(device):
    curve, unit = kite(), .05
    host, port = BatchedCertifiedUpdate(unit, device=device), DeviceCertifiedUpdate(unit, device=device)
    a, b = host.prepare(curve, 5, curve.band), port.prepare(curve, 5, curve.band)
    step = np.random.default_rng(3).normal(size=11)*2e-3
    x, ix = host.trial(a, step)
    y, iy = port.trial(b, step)
    assert np.array_equal(x.coefficients, y.coefficients) and ix['validity_tiers'] == iy['validity_tiers']
